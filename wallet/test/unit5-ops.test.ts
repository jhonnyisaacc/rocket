import assert from "node:assert/strict";
import test from "node:test";
import { loadConfig } from "../src/config.js";
import { createExecutorState, execute, type ExecutorDeps } from "../src/executor.js";
import { createExecutorApp, intentFromResolution } from "../src/executor-server.js";
import { createResolverApp, getJson, isValidDexAddress } from "../src/resolver-server.js";
import { buildApp, shutdown } from "../src/http.js";
import { createBalanceCache } from "../src/balances.js";
import { EXECUTOR_LOCK_SQL, RESERVE_SUM_SCOPED_SQL, createMemoryJournal, listingKey, lockAcquired, reserveDecision, strategyKey } from "../src/spend.js";
import { parseTokenRecords } from "../src/watchlist.js";
import { createExecutor } from "../src/index.js";
import { landedSend } from "./fixtures.js";

const EXEC = "executor-token-123456";
const RES = "resolver-token-123456";
const STRAT = "strategy-token-12345";
const ADMIN = "admin-token-1234567";

function intent(key = "k1") {
  return {
    idempotencyKey: key,
    side: "buy" as const,
    notionalUsd: 5,
    slippageBps: 100,
    token: {
      symbol: "MPLX",
      address: "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      decimals: 6,
      chain: { kind: "evm" as const, chainId: 8453 },
      chainKey: "base",
      pairMap: { pools: [], top: null },
    },
    holdings: [{ symbol: "USDC", address: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", amount: 20, usd: 20, native: false, decimals: 6, chainKey: "base" }],
    hyperliquid: null,
    receivedAtMs: 1000,
  };
}

function runtime(config: ReturnType<typeof loadConfig>, overrides: Partial<ExecutorDeps> = {}): ExecutorDeps {
  return {
    config,
    mode: "dry_run",
    spentTodayUsd: 0,
    state: createExecutorState(),
    quoteHop: async () => ({ priceImpactPct: 0.1, feeUsd: 0, buyAmount: "10", signable: true }),
    markPrice: async () => null,
    send: async () => landedSend(),
    ...overrides,
  };
}

test("health exposes only ok and status needs auth", async () => {
  const config = loadConfig({ EXECUTOR_AUTH_TOKEN: EXEC, RESOLVER_AUTH_TOKEN: RES });
  const app = await createExecutorApp(config, runtime(config), null, [], []);
  const health = await app.inject({ method: "GET", url: "/health" });
  assert.deepEqual(health.json(), { ok: true });
  const anon = await app.inject({ method: "GET", url: "/status" });
  assert.equal(anon.statusCode, 401);
  const authed = await app.inject({ method: "GET", url: "/status", headers: { authorization: `Bearer ${EXEC}` } });
  assert.equal(authed.statusCode, 200);
  assert.equal(authed.json().service, "executor");
  await app.close();
  const resolver = await createResolverApp(loadConfig({ RESOLVER_AUTH_TOKEN: RES, EXECUTOR_AUTH_TOKEN: EXEC }));
  assert.deepEqual((await resolver.inject({ method: "GET", url: "/health" })).json(), { ok: true });
  await resolver.close();
});

test("shutdown drains: mutating routes 503 and it waits for in-flight work", async () => {
  const app = await buildApp({ authTokens: [EXEC], logger: false });
  let release!: () => void;
  const gate = new Promise<void>((r) => (release = r));
  app.post("/work", { preHandler: app.auth([app.verifyBearer]) }, async () => app.drain.track(async () => { await gate; return { done: true }; }));
  const pending = app.inject({ method: "POST", url: "/work", headers: { authorization: `Bearer ${EXEC}`, "content-type": "application/json" }, payload: {} });
  await new Promise((r) => setTimeout(r, 20));
  let cleaned = false;
  const stopped = shutdown(app, 2000, async () => { cleaned = true; });
  const during = await app.inject({ method: "POST", url: "/work", headers: { authorization: `Bearer ${EXEC}`, "content-type": "application/json" }, payload: {} });
  assert.equal(during.statusCode, 503);
  release();
  assert.equal(await stopped, true);
  assert.equal(cleaned, true);
  assert.equal((await pending).statusCode, 200);
});

test("resolver getJson times out and caps the body", async () => {
  await assert.rejects(() => getJson("https://x.invalid/", {}, async () => new Promise<Response>(() => undefined), 20, 1024), /abort|timeout/i);
  await assert.rejects(() => getJson("https://x.invalid/", {}, async () => new Response("x".repeat(2048)), 1000, 1024), /too large/);
  assert.equal(isValidDexAddress("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"), true);
  assert.equal(isValidDexAddress("So11111111111111111111111111111111111111112"), true);
  assert.equal(isValidDexAddress("../../etc/passwd"), false);
  assert.equal(isValidDexAddress("not an address!"), false);
});

test("listing returns resolver_error and the kill switch blocks it before the resolver", async () => {
  const config = loadConfig({ EXECUTOR_AUTH_TOKEN: EXEC, RESOLVER_AUTH_TOKEN: RES, RESOLVER_URL: "http://resolver.railway.internal:8080" });
  let calls = 0;
  const fetchImpl = (async () => { calls += 1; return new Response("nope", { status: 502 }); }) as typeof fetch;
  const app = await createExecutorApp(config, runtime(config), null, [], [], false, fetchImpl);
  const alert = { id: "a1", ticker: "MPLX", projectName: "Metaplex", source: "x", publishedAt: "2026-01-01", receivedAt: "2026-01-01" };
  const res = await app.inject({ method: "POST", url: "/listing", headers: { authorization: `Bearer ${EXEC}`, "content-type": "application/json" }, payload: alert });
  assert.equal(res.json().reason, "resolver_error");
  await app.close();
  const killed = loadConfig({ EXECUTOR_AUTH_TOKEN: EXEC, RESOLVER_AUTH_TOKEN: RES, RESOLVER_URL: "http://resolver.railway.internal:8080", KILL_SWITCH: "1" });
  const app2 = await createExecutorApp(killed, runtime(killed), null, [], [], false, fetchImpl);
  const before = calls;
  const res2 = await app2.inject({ method: "POST", url: "/listing", headers: { authorization: `Bearer ${EXEC}`, "content-type": "application/json" }, payload: alert });
  assert.match(res2.json().reason, /kill switch/);
  assert.equal(calls, before);
  await app2.close();
});

test("strategy token executes live-namespaced and enforces its own cap", async () => {
  const config = loadConfig({
    EXECUTOR_AUTH_TOKEN: EXEC, RESOLVER_AUTH_TOKEN: RES, ADMIN_TOKEN: ADMIN,
    STRATEGY_CAPS_JSON: JSON.stringify({ copy1: { dailyUsdCap: 50, maxUsdPerTrade: 10, token: STRAT } }),
  });
  const scopes: unknown[] = [];
  const reads: string[] = [];
  const balances = createBalanceCache(async (holding) => {
    reads.push(holding.symbol);
    return 20;
  }, 60_000);
  const wired = createExecutor(config, null, null, { balances, priceOf: () => 1 }).deps;
  const rt: ExecutorDeps = {
    ...wired,
    mode: "live",
    quoteHop: async () => ({ priceImpactPct: 0.1, feeUsd: 0, buyAmount: "10", signable: true }),
    send: async () => landedSend(),
    recordSpend: async (_k, _u, scope) => {
      scopes.push(scope);
      return "reserved";
    },
    commitSpend: async () => undefined,
    releaseSpend: async () => undefined,
  };
  const app = await createExecutorApp(config, rt, null, [], []);
  const ok = await app.inject({ method: "POST", url: "/execute", headers: { authorization: `Bearer ${STRAT}`, "content-type": "application/json" }, payload: intent("s1") });
  assert.equal(ok.json().idempotencyKey, "copy1:s1");
  assert.equal(ok.json().decision, "sent", "the strategy route reads live balances through the runtime the server builds");
  assert.deepEqual(reads, ["USDC"]);
  assert.deepEqual(scopes, [{ strategyId: "copy1", capUsd: 50 }]);
  const tooBig = await app.inject({ method: "POST", url: "/execute", headers: { authorization: `Bearer ${STRAT}`, "content-type": "application/json" }, payload: { ...intent("s2"), notionalUsd: 11 } });
  assert.match(tooBig.json().reason, /strategy.*cap|maxUsdPerTrade/i);
  await app.close();
});

test("watchlist hydration parses rows and skips invalid ones; executor lock is advisory", () => {
  const good = { id: "1", ticker: "MPLX", names: ["Metaplex"], chainKey: "base", chain: { kind: "evm", chainId: 8453 }, contract: "0xaaa", decimals: 6, pairMap: { pools: [], top: null }, hyperliquid: null, refreshedAt: "2026-01-01", sourceId: null };
  const parsed = parseTokenRecords([good, { bogus: true }, null]);
  assert.equal(parsed.length, 1);
  assert.equal(parsed[0]?.ticker, "MPLX");
  assert.match(EXECUTOR_LOCK_SQL, /pg_try_advisory_lock/);
  assert.match(RESERVE_SUM_SCOPED_SQL, /strategy_id = \$2/);
  assert.equal(lockAcquired([{ locked: true }]), true);
  assert.equal(lockAcquired([{ locked: false }]), false);
  assert.equal(lockAcquired([]), false);
});

test("createExecutor instances keep separate reports", async () => {
  const config = loadConfig({ EXECUTOR_AUTH_TOKEN: EXEC, RESOLVER_AUTH_TOKEN: RES });
  const a = createExecutor(config, null, null);
  const b = createExecutor(config, null, null);
  assert.notEqual(a.state, b.state);
  const overrides = { quoteHop: async () => ({ priceImpactPct: 0.1, feeUsd: 0, buyAmount: "10", signable: true }) };
  const r1 = await a.execute(intent("same") as never, overrides);
  const r2 = await b.execute(intent("same") as never, overrides);
  assert.equal(r1.decision, "would_send");
  assert.equal(r2.decision, "would_send");
  assert.notEqual(r1, r2);
});

test("a dry-run preview does not answer for a live trade with the same key", async () => {
  const config = loadConfig({ EXECUTOR_AUTH_TOKEN: EXEC, RESOLVER_AUTH_TOKEN: RES });
  const state = createExecutorState();
  let sends = 0;
  const live = runtime(config, {
    state,
    mode: "live",
    readBalance: async () => 20,
    priceOf: () => 1,
    send: async () => {
      sends += 1;
      return landedSend();
    },
  });
  const preview = await execute(intent("same") as never, { ...live, mode: "dry_run" });
  assert.equal(preview.decision, "would_send");
  const traded = await execute(intent("same") as never, live);
  assert.equal(traded.decision, "sent");
  assert.equal(sends, 1);
});

test("listing and strategy idempotency keys never alias", () => {
  assert.equal(listingKey("a1"), "a1", "a bare alert id keeps its historical key");
  assert.equal(listingKey("copy1:s1"), "listing:copy1:s1");
  assert.notEqual(listingKey("copy1:s1"), strategyKey("copy1", "s1"));
  const alert = { id: "copy1:s1", ticker: "MPLX", projectName: "Metaplex", source: "x", publishedAt: "2026-01-01", receivedAt: "2026-01-01" };
  const token = parseTokenRecords([{ id: "1", ticker: "MPLX", names: ["Metaplex"], chainKey: "base", chain: { kind: "evm", chainId: 8453 }, contract: "0xaaa", decimals: 6, pairMap: { pools: [], top: null }, hyperliquid: null, refreshedAt: "2026-01-01", sourceId: null }])[0];
  const fromAlert = intentFromResolution(alert, { kind: "hit", token }, [], 5, 100);
  assert.equal(fromAlert?.idempotencyKey, "listing:copy1:s1");
  assert.throws(
    () => loadConfig({ STRATEGY_CAPS_JSON: JSON.stringify({ listing: { dailyUsdCap: 5, maxUsdPerTrade: 5, token: STRAT } }) }),
    /invalid entry for listing/,
  );
});

test("a strategy reservation is held to the global cap as well as its own", async () => {
  assert.equal(reserveDecision({ existing: null, spent: 24, usd: 5, cap: 25, scoped: { spent: 0, cap: 50 } }), "cap", "global cap binds a strategy");
  assert.equal(reserveDecision({ existing: null, spent: 0, usd: 5, cap: 25, scoped: { spent: 48, cap: 50 } }), "cap", "strategy cap binds");
  assert.equal(reserveDecision({ existing: null, spent: 10, usd: 5, cap: 25, scoped: { spent: 10, cap: 50 } }), "reserved");
  const journal = createMemoryJournal();
  const day = "2026-10-21";
  assert.equal(await journal.reserve("a1", 20, day, 25), "reserved");
  assert.equal(await journal.reserve("copy1:s1", 10, day, 25, { strategyId: "copy1", capUsd: 50 }), "cap", "listing spend counts against the global cap");
  assert.equal(await journal.reserve("copy1:s2", 5, day, 25, { strategyId: "copy1", capUsd: 50 }), "reserved");
  assert.equal(await journal.reserve("copy2:s1", 1, day, 25, { strategyId: "copy2", capUsd: 50 }), "cap", "global cap is shared across strategies");
  assert.equal(await journal.reserve("a2", 1, day, 25), "cap");
});
