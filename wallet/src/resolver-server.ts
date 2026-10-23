import type { FastifyInstance } from "fastify";
import { withTimeout } from "./timeout.js";
import type { Alert, TokenRecord } from "./domain.js";
import { loadConfig, publicConfig, type AppConfig } from "./config.js";
import { matchAlert } from "./match.js";
import { attachPools, hyperliquidFromMeta, listedContract, poolMeetsFloor, poolsFromDexScreener, readKoreanName, tokenFromDexSearch, type CoinListRow } from "./parsers.js";
import { addressChunks, applyLiquidity, rebuildIdentities, shortlistTokens, withKoreanName } from "./refresh.js";
import { redactError, zeroLoadedSecrets } from "./redact.js";
import { isSolanaAddress } from "./signer.js";
import { MemoryWatchlist, hydrateFromPostgres, saveToPostgres } from "./watchlist.js";
import { buildApp, mutatingLimit, shutdown } from "./http.js";
import { assertBoot } from "./managed-signer.js";
import { alertSchema } from "./schemas.js";
import { screenToken } from "./screening.js";
import { fillTokenDecimals } from "./token-decimals.js";
import { z } from "zod";
import { vendorResponse } from "./vendor-fetch.js";

export const watchlist = new MemoryWatchlist();

export function resolveAlert(alert: Alert, minLiquidityUsd: number, allowedChains?: ReadonlySet<string>) {
  return matchAlert(watchlist.index, alert, minLiquidityUsd, allowedChains);
}

const coinListSchema = z.array(z.object({ id: z.string(), symbol: z.string(), name: z.string() }).passthrough());

async function readCapped(response: Response, maxBodyBytes: number): Promise<string> {
  const reader = response.body?.getReader();
  if (!reader) {
    const text = await response.text();
    if (new TextEncoder().encode(text).byteLength > maxBodyBytes) throw new Error("response body too large");
    return text;
  }
  const chunks: Uint8Array[] = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > maxBodyBytes) {
      await reader.cancel();
      throw new Error("response body too large");
    }
    chunks.push(value);
  }
  const merged = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) { merged.set(chunk, offset); offset += chunk.byteLength; }
  return new TextDecoder().decode(merged);
}

export function isValidDexAddress(address: string): boolean {
  return /^0x[0-9a-fA-F]{40}$/.test(address) || isSolanaAddress(address) || /^[A-Za-z0-9_-]{1,128}$/.test(address);
}

export async function getJson(url: string, init: RequestInit, fetchImpl: typeof fetch, timeoutMs = 5_000, maxBodyBytes = 16 * 1024 * 1024): Promise<unknown> {
  const text = await withTimeout(
    timeoutMs,
    async (signal) => {
      const aborted = new Promise<never>((_resolve, reject) => {
        signal.addEventListener("abort", () => reject(signal.reason ?? new Error("request timed out")), { once: true });
      });
      const response = await Promise.race([vendorResponse(fetchImpl, url, { ...init, signal }), aborted]);
      if (!response.ok) throw new Error(`lookup failed ${response.status}`);
      return readCapped(response, maxBodyBytes);
    },
    init.signal ?? undefined,
  );
  return JSON.parse(text) as unknown;
}

export async function refreshWatchlist(config: AppConfig, list: MemoryWatchlist, fetchImpl: typeof fetch = fetch): Promise<void> {
  const headers: Record<string, string> = {};
  if (process.env.COINGECKO_API_KEY) headers["x-cg-demo-api-key"] = process.env.COINGECKO_API_KEY;
  const coinList = coinListSchema.parse(await getJson(`${config.coingeckoBase}/coins/list?include_platform=true`, { headers }, fetchImpl, config.resolverFetchTimeoutMs, config.resolverMaxBodyBytes));
  const metaBody = await getJson(
    `${config.hyperliquidUrl.replace(/\/$/, "")}/info`,
    { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ type: "meta" }) },
    fetchImpl,
    config.resolverFetchTimeoutMs,
    config.resolverMaxBodyBytes,
  );
  const markets = hyperliquidFromMeta(metaBody);
  list.setMarkets(markets);
  list.replace(rebuildIdentities(list.records(), coinList as CoinListRow[], markets));
  await refreshLiquidity(config, list, fetchImpl);
}

export async function refreshLiquidity(config: AppConfig, list: MemoryWatchlist, fetchImpl: typeof fetch = fetch): Promise<void> {
  const pools = [];
  for (const chunk of addressChunks(list.records(), config.shortlistLimit)) {
    const safe = chunk.filter(isValidDexAddress);
    if (safe.length === 0) continue;
    const body = await getJson(`${config.dexscreenerBase}/latest/dex/tokens/${safe.join(",")}`, {}, fetchImpl, config.resolverFetchTimeoutMs, config.resolverMaxBodyBytes);
    pools.push(...poolsFromDexScreener(body, config.dexscreenerSlugOverrides));
  }
  let tokens = applyLiquidity(list.records(), pools, new Date().toISOString(), config.quoteAssets, config.shortlistLimit);
  const headers: Record<string, string> = {};
  if (process.env.COINGECKO_API_KEY) headers["x-cg-demo-api-key"] = process.env.COINGECKO_API_KEY;
  for (const token of shortlistTokens(tokens, config.shortlistLimit)) {
    if (!token.sourceId) continue;
    try {
      const detail = await getJson(
        `${config.coingeckoBase}/coins/${encodeURIComponent(token.sourceId)}?localization=true&tickers=false&market_data=false&community_data=false&developer_data=false&sparkline=false`,
        { headers },
        fetchImpl,
        config.resolverFetchTimeoutMs,
        config.resolverMaxBodyBytes,
      );
      tokens = tokens.map((item) => (item.id === token.id ? withKoreanName(item, readKoreanName(detail)) : item));
    } catch {
      continue;
    }
  }
  if (config.screening) {
    const kept = [];
    for (const token of tokens) {
      if (token.pairMap.pools.length === 0) {
        kept.push(token);
        continue;
      }
      const verdict = await screenToken(config, { chainKey: token.chainKey, chain: token.chain, contract: token.contract }, fetchImpl);
      if (verdict === "allow") kept.push(token);
    }
    tokens = kept;
  }
  tokens = await fillTokenDecimals(tokens, config.rpcByChainKey);
  list.replace(tokens);
  if (config.databaseUrl) await saveToPostgres(config.databaseUrl, list.records());
}

async function liveLookup(
  config: AppConfig,
  alert: Alert,
  fetchImpl: typeof fetch,
): Promise<{ kind: "ambiguous" | "none" | "timed_out" | "screened" | "young" | "unlisted_contract" | "report" } | { kind: "qualified"; token: TokenRecord }> {
  const url = `${config.dexscreenerBase}/latest/dex/search?q=${encodeURIComponent(alert.ticker)}`;
  try {
    const body = await getJson(url, {}, fetchImpl, config.liveLookupTimeoutMs, config.resolverMaxBodyBytes);
    const found = tokenFromDexSearch(body, alert, new Date().toISOString(), config.quoteAssets, config.dexscreenerSlugOverrides);
    if (found.kind === "ambiguous") return { kind: "ambiguous" };
    if (found.kind !== "token") return { kind: "none" };
    const token = (await fillTokenDecimals([found.token], config.rpcByChainKey))[0] ?? found.token;
    if (config.screening) {
      const verdict = await screenToken(config, { chainKey: token.chainKey, chain: token.chain, contract: token.contract }, fetchImpl);
      if (verdict !== "allow") return { kind: "screened" };
    }
    if (config.live) return { kind: "report" };
    const pools = token.pairMap.pools;
    if (!poolMeetsFloor(pools, Date.now(), config.minPoolAgeHours, config.minVolume24hUsd)) return { kind: "young" };
    const headers: Record<string, string> = {};
    if (process.env.COINGECKO_API_KEY) headers["x-cg-demo-api-key"] = process.env.COINGECKO_API_KEY;
    const listed = coinListSchema.safeParse(await getJson(`${config.coingeckoBase}/coins/list?include_platform=true`, { headers }, fetchImpl, config.resolverFetchTimeoutMs, config.resolverMaxBodyBytes));
    if (!listed.success || !listedContract(listed.data, alert, token.chainKey, token.contract)) return { kind: "unlisted_contract" };
    return { kind: "qualified", token };
  } catch {
    return { kind: "timed_out" };
  }
}

export async function createResolverApp(config: AppConfig, list: MemoryWatchlist = watchlist, logger = false, fetchImpl: typeof fetch = fetch): Promise<FastifyInstance> {
  const app = await buildApp({ authTokens: config.resolverAuthTokens, logger });
  const guard = { preHandler: app.auth([app.verifyBearer]), config: mutatingLimit };
  app.get("/health", async () => ({ ok: true }));
  app.get("/status", { preHandler: app.auth([app.verifyBearer]) }, async () => ({ ok: true, service: "resolver", tokens: list.records().length, ...publicConfig(config) }));
  app.post("/alert", guard, async (request, reply) => {
    const parsed = alertSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: "invalid request" });
    let outcome = await app.drain.track(async () => resolveAlert(parsed.data, config.minLiquidityUsd, config.enabledChainKeys));
    if (outcome.kind === "unlisted") {
      const found = await liveLookup(config, parsed.data, fetchImpl);
      if (found.kind === "qualified") return { kind: "hit", token: found.token, alternates: [] };
      if (found.kind === "none") return outcome;
      const detail =
        found.kind === "ambiguous"
          ? "live lookup matched more than one contract"
          : found.kind === "timed_out"
            ? "live lookup timed out or failed"
            : found.kind === "screened"
              ? "token screening rejected the contract"
              : found.kind === "young"
                ? "pool is younger than the age floor or below the volume floor"
                : found.kind === "unlisted_contract"
                  ? "contract is not on the coin list for that name"
                  : "live lookup is report-only";
      return { kind: "unlisted", ticker: parsed.data.ticker, detail };
    }
    return outcome;
  });
  return app;
}

async function main(): Promise<void> {
  const config = loadConfig();
  assertBoot(config, "resolver");
  if (config.databaseUrl) {
    const stored = await hydrateFromPostgres(config.databaseUrl);
    watchlist.replace(stored.map((token) => attachPools(token, token.pairMap.pools, token.refreshedAt, config.quoteAssets)));
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
  const app = await createResolverApp(config, watchlist, true);
  await app.listen({ port: config.port, host: "0.0.0.0" });
  console.log(JSON.stringify({ service: "resolver", port: config.port, ...publicConfig(config) }));
  refresh("full");
  const timers = [setInterval(() => refresh("liquidity"), config.liquidityRefreshMs), setInterval(() => refresh("full"), config.fullRefreshMs)];
  let stopping = false;
  const stop = () => {
    if (stopping) return;
    stopping = true;
    void shutdown(app, 20_000, async () => { for (const timer of timers) clearInterval(timer); zeroLoadedSecrets(); }).then(() => process.exit(0));
  };
  process.once("SIGINT", stop);
  process.once("SIGTERM", stop);
}

const entry = process.argv[1] ?? "";
if (entry.endsWith("resolver-server.js")) {
  main().catch((error: unknown) => {
    console.error(JSON.stringify({ error: redactError(error) }));
    process.exit(1);
  });
}
