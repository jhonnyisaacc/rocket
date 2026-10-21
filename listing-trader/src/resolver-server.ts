import type { Alert, TokenRecord } from "./domain.js";
import { loadConfig, publicConfig, type AppConfig } from "./config.js";
import { matchAlert } from "./match.js";
import { hyperliquidFromMeta, poolsFromDexScreener, readKoreanName, tokenFromDexSearch, type CoinListRow } from "./parsers.js";
import { addressChunks, applyLiquidity, rebuildIdentities, shortlistTokens, withKoreanName } from "./refresh.js";
import { redactError } from "./redact.js";
import { MemoryWatchlist, hydrateFromPostgres, saveToPostgres } from "./watchlist.js";
import { readJson, sendJson, startServer } from "./http.js";

export const watchlist = new MemoryWatchlist();

export function resolveAlert(alert: Alert, minLiquidityUsd: number) {
  return matchAlert(watchlist.index, alert, minLiquidityUsd);
}

async function getJson(url: string, init: RequestInit, fetchImpl: typeof fetch): Promise<unknown> {
  const response = await fetchImpl(url, init);
  if (!response.ok) throw new Error(`lookup failed ${response.status}`);
  return response.json();
}

export async function refreshWatchlist(config: AppConfig, list: MemoryWatchlist, fetchImpl: typeof fetch = fetch): Promise<void> {
  const headers: Record<string, string> = {};
  if (process.env.COINGECKO_API_KEY) headers["x-cg-demo-api-key"] = process.env.COINGECKO_API_KEY;
  const coinList = await getJson(`${config.coingeckoBase}/coins/list?include_platform=true`, { headers }, fetchImpl);
  if (!Array.isArray(coinList)) throw new Error("coin list was not an array");
  const metaBody = await getJson(
    `${config.hyperliquidUrl.replace(/\/$/, "")}/info`,
    { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ type: "meta" }) },
    fetchImpl,
  );
  const markets = hyperliquidFromMeta(metaBody);
  list.setMarkets(markets);
  list.replace(rebuildIdentities(list.records(), coinList as CoinListRow[], markets));
  await refreshLiquidity(config, list, fetchImpl);
}

export async function refreshLiquidity(config: AppConfig, list: MemoryWatchlist, fetchImpl: typeof fetch = fetch): Promise<void> {
  const pools = [];
  for (const chunk of addressChunks(list.records(), config.shortlistLimit)) {
    const body = await getJson(`${config.dexscreenerBase}/latest/dex/tokens/${chunk.join(",")}`, {}, fetchImpl);
    pools.push(...poolsFromDexScreener(body, config.dexscreenerSlugOverrides));
  }
  let tokens = applyLiquidity(list.records(), pools, new Date().toISOString(), config.quoteDecimals, config.shortlistLimit);
  const headers: Record<string, string> = {};
  if (process.env.COINGECKO_API_KEY) headers["x-cg-demo-api-key"] = process.env.COINGECKO_API_KEY;
  for (const token of shortlistTokens(tokens, config.shortlistLimit)) {
    if (!token.sourceId) continue;
    try {
      const detail = await getJson(
        `${config.coingeckoBase}/coins/${encodeURIComponent(token.sourceId)}?localization=true&tickers=false&market_data=false&community_data=false&developer_data=false&sparkline=false`,
        { headers },
        fetchImpl,
      );
      tokens = tokens.map((item) => (item.id === token.id ? withKoreanName(item, readKoreanName(detail)) : item));
    } catch {
      continue;
    }
  }
  list.replace(tokens);
  if (config.databaseUrl) await saveToPostgres(config.databaseUrl, list.records());
}

async function liveLookup(config: AppConfig, alert: Alert, fetchImpl: typeof fetch): Promise<TokenRecord | "ambiguous" | "none" | "timed_out"> {
  const url = `${config.dexscreenerBase}/latest/dex/search?q=${encodeURIComponent(alert.ticker)}`;
  try {
    const response = await fetchImpl(url, { signal: AbortSignal.timeout(config.liveLookupTimeoutMs) });
    if (!response.ok) return "none";
    const found = tokenFromDexSearch(await response.json(), alert, new Date().toISOString(), config.dexscreenerSlugOverrides);
    if (found.kind === "ambiguous") return "ambiguous";
    if (found.kind === "token") return found.token;
    return "none";
  } catch {
    return "timed_out";
  }
}

async function main(): Promise<void> {
  const config = loadConfig();
  if (config.databaseUrl) {
    watchlist.replace(await hydrateFromPostgres(config.databaseUrl));
  }
  let refreshing = false;
  const refresh = (kind: "full" | "liquidity") => {
    if (!config.refreshEnabled || refreshing) return;
    refreshing = true;
    const run = kind === "full" ? refreshWatchlist(config, watchlist) : refreshLiquidity(config, watchlist);
    void run
      .catch((error: unknown) => {
        console.error(JSON.stringify({ refresh: kind, error: redactError(error) }));
      })
      .finally(() => {
        refreshing = false;
      });
  };
  const server = startServer(config.port, async (req, res) => {
    const url = new URL(req.url ?? "/", "http://localhost");
    if (req.method === "GET" && url.pathname === "/health") {
      sendJson(res, 200, { ok: true, service: "resolver", tokens: watchlist.records().length, ...publicConfig(config) });
      return;
    }
    if (req.method === "POST" && url.pathname === "/alert") {
      const body = (await readJson(req)) as Alert;
      let outcome = resolveAlert(body, config.minLiquidityUsd);
      if (outcome.kind === "unlisted") {
        const found = await liveLookup(config, body, fetch);
        if (found === "ambiguous") {
          sendJson(res, 200, { kind: "ambiguous", ticker: body.ticker, detail: "live lookup matched more than one contract" });
          return;
        }
        if (found === "timed_out") {
          sendJson(res, 200, { kind: "unlisted", ticker: body.ticker, detail: "live lookup timed out or failed" });
          return;
        }
        if (found !== "none") {
          watchlist.upsert(found);
          outcome = resolveAlert(body, config.minLiquidityUsd);
        }
      }
      sendJson(res, 200, outcome);
      return;
    }
    if (req.method === "POST" && url.pathname === "/replace") {
      const body = (await readJson(req)) as { tokens?: TokenRecord[] };
      watchlist.replace(body.tokens ?? []);
      if (config.databaseUrl) await saveToPostgres(config.databaseUrl, watchlist.records());
      sendJson(res, 200, { count: watchlist.records().length });
      return;
    }
    sendJson(res, 404, { error: "not found" });
  });
  console.log(JSON.stringify({ service: "resolver", port: config.port, ...publicConfig(config) }));
  refresh("full");
  setInterval(() => refresh("liquidity"), config.liquidityRefreshMs);
  setInterval(() => refresh("full"), config.fullRefreshMs);
  server.on("error", (error) => {
    console.error(JSON.stringify({ error: redactError(error) }));
  });
}

const entry = process.argv[1] ?? "";
if (entry.endsWith("resolver-server.js")) {
  main().catch((error: unknown) => {
    console.error(JSON.stringify({ error: redactError(error) }));
    process.exit(1);
  });
}
