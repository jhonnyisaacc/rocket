import type { FastifyInstance } from "fastify";
import type { Alert, TokenRecord } from "./domain.js";
import { loadConfig, publicConfig, type AppConfig } from "./config.js";
import { matchAlert } from "./match.js";
import { hyperliquidFromMeta, poolsFromDexScreener, readKoreanName, tokenFromDexSearch, type CoinListRow } from "./parsers.js";
import { addressChunks, applyLiquidity, rebuildIdentities, shortlistTokens, withKoreanName } from "./refresh.js";
import { redactError } from "./redact.js";
import { MemoryWatchlist, hydrateFromPostgres, saveToPostgres } from "./watchlist.js";
import { buildApp, mutatingLimit } from "./http.js";
import { assertBoot } from "./managed-signer.js";
import { alertSchema, replaceSchema } from "./schemas.js";
import { screenToken } from "./screening.js";
import { z } from "zod";

export const watchlist = new MemoryWatchlist();

export function resolveAlert(alert: Alert, minLiquidityUsd: number, allowedChains?: ReadonlySet<string>) {
  return matchAlert(watchlist.index, alert, minLiquidityUsd, allowedChains);
}

const coinListSchema = z.array(z.object({ id: z.string(), symbol: z.string(), name: z.string() }).passthrough());

async function getJson(url: string, init: RequestInit, fetchImpl: typeof fetch): Promise<unknown> {
  const response = await fetchImpl(url, init);
  if (!response.ok) throw new Error(`lookup failed ${response.status}`);
  return response.json();
}

export async function refreshWatchlist(config: AppConfig, list: MemoryWatchlist, fetchImpl: typeof fetch = fetch): Promise<void> {
  const headers: Record<string, string> = {};
  if (process.env.COINGECKO_API_KEY) headers["x-cg-demo-api-key"] = process.env.COINGECKO_API_KEY;
  const coinList = coinListSchema.parse(await getJson(`${config.coingeckoBase}/coins/list?include_platform=true`, { headers }, fetchImpl));
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

async function liveLookup(config: AppConfig, alert: Alert, fetchImpl: typeof fetch): Promise<TokenRecord | "ambiguous" | "none" | "timed_out" | "screened"> {
  const url = `${config.dexscreenerBase}/latest/dex/search?q=${encodeURIComponent(alert.ticker)}`;
  try {
    const response = await fetchImpl(url, { signal: AbortSignal.timeout(config.liveLookupTimeoutMs) });
    if (!response.ok) return "none";
    const found = tokenFromDexSearch(await response.json(), alert, new Date().toISOString(), config.dexscreenerSlugOverrides);
    if (found.kind === "ambiguous") return "ambiguous";
    if (found.kind !== "token") return "none";
    if (config.screening) {
      const verdict = await screenToken(config, { chainKey: found.token.chainKey, chain: found.token.chain, contract: found.token.contract }, fetchImpl);
      if (verdict !== "allow") return "screened";
    }
    return found.token;
  } catch {
    return "timed_out";
  }
}

export async function createResolverApp(config: AppConfig, list: MemoryWatchlist = watchlist, logger = false): Promise<FastifyInstance> {
  const app = await buildApp({ authToken: config.authToken ?? "", logger });
  const guard = { preHandler: app.auth([app.verifyBearer]), config: mutatingLimit };
  app.get("/health", async () => ({ ok: true, service: "resolver", tokens: list.records().length, ...publicConfig(config) }));
  app.post("/alert", guard, async (request, reply) => {
    const parsed = alertSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: "invalid request" });
    let outcome = resolveAlert(parsed.data, config.minLiquidityUsd, config.enabledChainKeys);
    if (outcome.kind === "unlisted") {
      const found = await liveLookup(config, parsed.data, fetch);
      if (found === "ambiguous") return { kind: "ambiguous", ticker: parsed.data.ticker, detail: "live lookup matched more than one contract" };
      if (found === "timed_out") return { kind: "unlisted", ticker: parsed.data.ticker, detail: "live lookup timed out or failed" };
      if (found === "screened") return { kind: "unlisted", ticker: parsed.data.ticker, detail: "token screening rejected the contract" };
      if (found !== "none") {
        list.upsert(found);
        outcome = resolveAlert(parsed.data, config.minLiquidityUsd, config.enabledChainKeys);
      }
    }
    return outcome;
  });
  app.post("/replace", guard, async (request, reply) => {
    const parsed = replaceSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: "invalid request" });
    list.replace(parsed.data.tokens as TokenRecord[]);
    if (config.databaseUrl) await saveToPostgres(config.databaseUrl, list.records());
    return { count: list.records().length };
  });
  return app;
}

async function main(): Promise<void> {
  const config = loadConfig();
  assertBoot(config);
  if (config.databaseUrl) watchlist.replace(await hydrateFromPostgres(config.databaseUrl));
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
  const app = await createResolverApp(config, watchlist, true);
  await app.listen({ port: config.port, host: "0.0.0.0" });
  console.log(JSON.stringify({ service: "resolver", port: config.port, ...publicConfig(config) }));
  refresh("full");
  setInterval(() => refresh("liquidity"), config.liquidityRefreshMs);
  setInterval(() => refresh("full"), config.fullRefreshMs);
}

const entry = process.argv[1] ?? "";
if (entry.endsWith("resolver-server.js")) {
  main().catch((error: unknown) => {
    console.error(JSON.stringify({ error: redactError(error) }));
    process.exit(1);
  });
}
