import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import test from "node:test";
import { Keypair } from "@solana/web3.js";
import { encodeFunctionData, erc20Abi } from "viem";
import { resetProviderGuards } from "../src/aggregators.js";
import { applyBalance, holdingsForTrade } from "../src/balances.js";
import { broadcastRoute } from "../src/broadcast.js";
import { readHiddenLine } from "../src/create-wallet.js";
import { assertLiveEdges, loadConfig } from "../src/config.js";
import { buildPairMap } from "../src/pairs.js";
import { execute, resetExecutorState, type ExecutorDeps } from "../src/executor.js";
import { createExecutorApp } from "../src/executor-server.js";
import { decryptWallet, encryptWallet, createWalletMaterial } from "../src/keystore.js";
import { BODY_LIMIT, REQUEST_TIMEOUT_MS } from "../src/http.js";
import { assertBoot, loadManagedSigner, type TransactionSigner } from "../src/managed-signer.js";
import { listedContract, poolMeetsFloor } from "../src/parsers.js";
import { redactError, Secret, trackSecret, zeroLoadedSecrets } from "../src/redact.js";
import { createResolverApp, refreshLiquidity } from "../src/resolver-server.js";
import { MemoryWatchlist } from "../src/watchlist.js";
import { assertEvmSigning, DEFAULT_MAX_VALUE_WEI, JUPITER_PROGRAM_ID, SOLANA_BASE_PROGRAMS } from "../src/signing-policy.js";
import { createMemoryJournal, spendDay } from "../src/spend.js";
import type { SwapIntent } from "../src/domain.js";

const tokenAuth = "0123456789abcdef";
const adminAuth = "admin-token-0123456";
const owner = "0x1111111111111111111111111111111111111111";
const router = "0x2222222222222222222222222222222222222222";

function alertBody() {
  return {
    id: `alert-${Math.random()}`,
    ticker: "MPLX",
    projectName: "Metaplex",
    source: "test",
    publishedAt: "2026-10-21T00:00:00.000Z",
    receivedAt: "2026-10-21T00:00:00.000Z",
  };
}

function pair(createdAtMs: number, volume24hUsd: number) {
  return {
    chainId: "solana",
    pairAddress: "pool",
    baseToken: { address: "mint", symbol: "MPLX", name: "Metaplex" },
    quoteToken: { address: "usdc", symbol: "USDC" },
    liquidity: { usd: 200_000 },
    priceUsd: "1",
    pairCreatedAt: createdAtMs,
    volume: { h24: volume24hUsd },
  };
}

function lookupFetch(createdAtMs: number, volume24hUsd: number, honeypot = "0"): typeof fetch {
  return (async (input: RequestInfo | URL) => {
    const url = new URL(String(input), "https://api.dexscreener.com");
    if (url.pathname.endsWith("/dex/search")) {
      return new Response(JSON.stringify({ pairs: [pair(createdAtMs, volume24hUsd)] }), { status: 200 });
    }
    if (url.hostname === "api.gopluslabs.io") {
      return new Response(JSON.stringify({ code: 1, result: { mint: { is_honeypot: honeypot, cannot_sell_all: "0", buy_tax: "0", sell_tax: "0" } } }), { status: 200 });
    }
    return new Response(JSON.stringify([{ id: "metaplex", symbol: "mplx", name: "Metaplex", platforms: { solana: "mint" } }]), { status: 200 });
  }) as typeof fetch;
}

function intent(): SwapIntent {
  return {
    idempotencyKey: `id-${Math.random()}`,
    side: "buy",
    notionalUsd: 5,
    slippageBps: 50,
    token: {
      symbol: "MPLX",
      address: "mplx",
      decimals: 6,
      chain: { kind: "solana" },
      chainKey: "solana",
      pairMap: buildPairMap([
        {
          poolAddress: "p",
          dex: "raydium",
          chainKey: "solana",
          baseSymbol: "MPLX",
          baseAddress: "mplx",
          quoteSymbol: "SOL",
          quoteAddress: "sol",
          liquidityUsd: 2_000_000,
          priceUsd: 0.2,
          baseDecimals: 6,
        },
      ]),
    },
    holdings: [
      { symbol: "USDC", address: "usdc", amount: 20, usd: 20, native: false, decimals: 6 },
      { symbol: "SOL", address: "sol", amount: 1, usd: 150, native: true },
    ],
    hyperliquid: null,
    receivedAtMs: 1_000,
  };
}

function runtime(config: ReturnType<typeof loadConfig>, sends: string[], quote: ExecutorDeps["quoteHop"]): ExecutorDeps {
  return {
    config,
    mode: "live",
    spentTodayUsd: 0,
    quoteHop: quote,
    markPrice: async () => 1,
    send: async (action) => {
      sends.push(action.kind);
    },
    now: () => 1_050,
  };
}

test("mutating routes reject a missing bearer token and /replace is gone", async () => {
  const config = loadConfig({ AUTH_TOKEN: tokenAuth });
  const list = new MemoryWatchlist();
  const resolver = await createResolverApp(config, list, false, lookupFetch(Date.now(), 100_000));
  const missing = await resolver.inject({ method: "POST", url: "/alert", payload: alertBody() });
  assert.equal(missing.statusCode, 401);
  const replaced = await resolver.inject({
    method: "POST",
    url: "/replace",
    headers: { authorization: `Bearer ${tokenAuth}`, "content-type": "application/json" },
    payload: { tokens: [] },
  });
  assert.equal(replaced.statusCode, 404);
  assert.equal(list.records().length, 0);
  await resolver.close();
});

test("a live lookup does not upsert and a dry-run hit stays out of the watchlist", async () => {
  const live = loadConfig({ AUTH_TOKEN: tokenAuth, LISTING_TRADER_LIVE: "true" });
  const liveList = new MemoryWatchlist();
  const liveApp = await createResolverApp(live, liveList, false, lookupFetch(Date.now() - 48 * 3_600_000, 100_000));
  const liveResponse = await liveApp.inject({
    method: "POST",
    url: "/alert",
    headers: { authorization: `Bearer ${tokenAuth}`, "content-type": "application/json" },
    payload: alertBody(),
  });
  assert.equal(liveResponse.statusCode, 200);
  assert.equal(liveResponse.json().kind, "unlisted");
  assert.equal(liveResponse.json().detail, "live lookup is report-only");
  assert.equal(liveList.records().length, 0);
  await liveApp.close();

  const dry = loadConfig({ AUTH_TOKEN: tokenAuth });
  const dryList = new MemoryWatchlist();
  const dryApp = await createResolverApp(dry, dryList, false, lookupFetch(Date.now() - 48 * 3_600_000, 100_000));
  const dryResponse = await dryApp.inject({
    method: "POST",
    url: "/alert",
    headers: { authorization: `Bearer ${tokenAuth}`, "content-type": "application/json" },
    payload: alertBody(),
  });
  assert.equal(dryResponse.json().kind, "hit");
  assert.equal(dryList.records().length, 0);
  const young = await createResolverApp(dry, dryList, false, lookupFetch(Date.now(), 100_000));
  const youngResponse = await young.inject({
    method: "POST",
    url: "/alert",
    headers: { authorization: `Bearer ${tokenAuth}`, "content-type": "application/json" },
    payload: alertBody(),
  });
  assert.equal(youngResponse.json().kind, "unlisted");
  assert.equal(dryList.records().length, 0);
  await dryApp.close();
  await young.close();
});

test("a live honeypot stays unlisted and a refresh drops it", async () => {
  const live = loadConfig({ AUTH_TOKEN: tokenAuth, LISTING_TRADER_LIVE: "true" });
  const list = new MemoryWatchlist();
  const app = await createResolverApp(live, list, false, lookupFetch(Date.now() - 48 * 3_600_000, 100_000, "1"));
  const response = await app.inject({
    method: "POST",
    url: "/alert",
    headers: { authorization: `Bearer ${tokenAuth}`, "content-type": "application/json" },
    payload: alertBody(),
  });
  assert.equal(response.json().kind, "unlisted");
  assert.equal(response.json().detail, "token screening rejected the contract");
  assert.equal(list.records().length, 0);
  await app.close();

  const refreshList = new MemoryWatchlist();
  refreshList.replace([
    {
      id: "solana:mint",
      ticker: "MPLX",
      names: ["Metaplex"],
      chainKey: "solana",
      chain: { kind: "solana" },
      contract: "mint",
      decimals: 6,
      pairMap: buildPairMap([
        {
          poolAddress: "pool",
          dex: "raydium",
          chainKey: "solana",
          baseSymbol: "MPLX",
          baseAddress: "mint",
          quoteSymbol: "USDC",
          quoteAddress: "usdc",
          liquidityUsd: 200_000,
          priceUsd: 1,
          baseDecimals: 6,
        },
      ]),
      hyperliquid: null,
      refreshedAt: "2026-10-21T00:00:00.000Z",
    },
  ]);
  await refreshLiquidity(loadConfig({ TOKEN_SCREENING: "true", AUTH_TOKEN: tokenAuth }), refreshList, async (input) => {
    const url = new URL(String(input), "https://api.dexscreener.com");
    if (url.hostname === "api.gopluslabs.io") {
      return new Response(JSON.stringify({ code: 1, result: { mint: { is_honeypot: "1", buy_tax: "0", sell_tax: "0" } } }), { status: 200 });
    }
    return new Response(JSON.stringify({ pairs: [pair(Date.now() - 48 * 3_600_000, 100_000)] }), { status: 200 });
  });
  assert.equal(refreshList.records().length, 0);
});

test("live mode does not send a token the screener denies", async () => {
  resetExecutorState();
  const config = loadConfig({ AUTH_TOKEN: tokenAuth, LISTING_TRADER_LIVE: "true" });
  const sends: string[] = [];
  const report = await execute(intent(), {
    ...runtime(config, sends, async () => ({ priceImpactPct: 0.2, feeUsd: 0.01, buyAmount: "10" })),
    screenToken: async () => "deny",
  });
  assert.equal(report.decision, "skipped");
  assert.equal(report.reason, "token screening rejected the contract");
  assert.equal(sends.length, 0);
});

test("pool floor and coin list membership are required before a dry-run hit", () => {
  const now = Date.now();
  const oldEnough = { liquidityUsd: 1, createdAtMs: now - 48 * 3_600_000, volume24hUsd: 10_000 };
  assert.equal(poolMeetsFloor([oldEnough as never], now, 24, 10_000), true);
  assert.equal(poolMeetsFloor([{ ...oldEnough, volume24hUsd: 9 } as never], now, 24, 10_000), false);
  assert.equal(
    listedContract([{ id: "metaplex", symbol: "mplx", name: "Metaplex", platforms: { solana: "mint" } }], { ticker: "MPLX", projectName: "Metaplex" }, "solana", "mint"),
    true,
  );
  assert.equal(
    listedContract([{ id: "other", symbol: "mplx", name: "Metaplex", platforms: { solana: "else" } }], { ticker: "MPLX", projectName: "Metaplex" }, "solana", "mint"),
    false,
  );
});

test("/execute stays dry-run, a thrown quote is a generic 500, and plain text is rejected", async () => {
  resetExecutorState();
  const databaseUrl = "postgres://listing:s3cret-db@db.internal:5432/listing";
  const rpc = "https://rpc.example/v2/secret-rpc-key";
  const config = loadConfig({ AUTH_TOKEN: tokenAuth });
  const sends: string[] = [];
  const app = await createExecutorApp(config, runtime(config, sends, async () => ({ priceImpactPct: 0.2, feeUsd: 0.01, buyAmount: "10" })), null, [databaseUrl, rpc], []);
  const denied = await app.inject({ method: "POST", url: "/listing", payload: alertBody() });
  assert.equal(denied.statusCode, 401);
  const dry = await app.inject({
    method: "POST",
    url: "/execute",
    headers: { authorization: `Bearer ${tokenAuth}`, "content-type": "application/json" },
    payload: intent(),
  });
  assert.equal(dry.statusCode, 200);
  assert.equal(dry.json().mode, "dry_run");
  assert.equal(sends.length, 0);
  const plain = await app.inject({
    method: "POST",
    url: "/execute",
    headers: { authorization: `Bearer ${tokenAuth}`, "content-type": "text/plain" },
    payload: "hello",
  });
  assert.equal(plain.statusCode, 415);
  assert.equal(plain.json().error, "unsupported media type");
  await app.close();

  const failing = await createExecutorApp(
    config,
    runtime(config, sends, async () => {
      throw new Error(`connect ${databaseUrl} via ${rpc}`);
    }),
    null,
    [databaseUrl, rpc],
    [],
  );
  const crashed = await failing.inject({
    method: "POST",
    url: "/execute",
    headers: { authorization: `Bearer ${tokenAuth}`, "content-type": "application/json" },
    payload: intent(),
  });
  assert.equal(crashed.statusCode, 500);
  assert.deepEqual(crashed.json(), { error: "internal error" });
  assert.equal(BODY_LIMIT <= 64 * 1024, true);
  assert.equal(failing.server.requestTimeout, REQUEST_TIMEOUT_MS);
  await failing.close();
  const redacted = redactError(new Error(`connect ${databaseUrl} via ${rpc}`), [databaseUrl, rpc]);
  assert.equal(redacted, "connect [redacted] via [redacted]");
});

test("withdraw requires the admin token, the enable flag, the cap, and the allowlist", async () => {
  const config = loadConfig({
    AUTH_TOKEN: tokenAuth,
    ADMIN_TOKEN: adminAuth,
    WITHDRAW_ENABLED: "true",
    OWNER_WITHDRAW_ADDRESSES: owner,
    MAX_WITHDRAW_AMOUNT: "1",
  });
  const app = await createExecutorApp(config, runtime(config, [], async () => ({ priceImpactPct: null, feeUsd: 0, buyAmount: "0" })), null, [], []);
  const headers = { "content-type": "application/json", authorization: `Bearer ${tokenAuth}`, "x-admin-token": adminAuth };
  const trading = await app.inject({
    method: "POST",
    url: "/withdraw",
    headers: { "content-type": "application/json", authorization: `Bearer ${tokenAuth}` },
    payload: { to: owner, amount: 1, chainKey: "base" },
  });
  assert.equal(trading.statusCode, 401);
  const noBearer = await app.inject({
    method: "POST",
    url: "/withdraw",
    headers: { "content-type": "application/json", "x-admin-token": adminAuth },
    payload: { to: owner, amount: 1, chainKey: "base" },
  });
  assert.equal(noBearer.statusCode, 401);
  const disabled = await createExecutorApp(loadConfig({ AUTH_TOKEN: tokenAuth, ADMIN_TOKEN: adminAuth }), runtime(config, [], async () => ({ priceImpactPct: null, feeUsd: 0, buyAmount: "0" })), null, [], []);
  const off = await disabled.inject({
    method: "POST",
    url: "/withdraw",
    headers,
    payload: { to: owner, amount: 1, chainKey: "base" },
  });
  assert.equal(off.statusCode, 403);
  assert.equal(off.json().error, "withdraw is disabled");
  const over = await app.inject({
    method: "POST",
    url: "/withdraw",
    headers,
    payload: { to: owner, amount: 5, chainKey: "base" },
  });
  assert.equal(over.statusCode, 403);
  const foreign = await app.inject({
    method: "POST",
    url: "/withdraw",
    headers,
    payload: { to: "0x3333333333333333333333333333333333333333", amount: 1, chainKey: "base" },
  });
  assert.equal(foreign.statusCode, 403);
  const tokenDenied = await app.inject({
    method: "POST",
    url: "/withdraw",
    headers,
    payload: { to: owner, amount: 1, chainKey: "base", mint: "0x4444444444444444444444444444444444444444", decimals: 6 },
  });
  assert.equal(tokenDenied.statusCode, 403);
  const planned = await app.inject({
    method: "POST",
    url: "/withdraw",
    headers,
    payload: { to: owner, amount: 1, chainKey: "base" },
  });
  assert.equal(planned.statusCode, 200);
  assert.equal(planned.json().decision, "would_send");
  await app.close();
  await disabled.close();
  assert.throws(() => assertBoot(loadConfig({ AUTH_TOKEN: tokenAuth, WITHDRAW_ENABLED: "true" })), /OWNER_WITHDRAW_ADDRESSES/);
  assert.throws(() => assertBoot(loadConfig({ AUTH_TOKEN: tokenAuth, WITHDRAW_ENABLED: "true", OWNER_WITHDRAW_ADDRESSES: "not-an-address" })), /invalid address/);
});

test("two reservations that share a lock cannot both pass the daily cap", async () => {
  const journal = createMemoryJournal();
  const [first, second] = await Promise.all([journal.reserve("a", 20, "2026-10-21", 25), journal.reserve("b", 20, "2026-10-21", 25)]);
  assert.deepEqual([first, second].sort(), ["cap", "reserved"]);
  const instant = new Date("2026-10-21T02:00:00.000Z");
  assert.equal(spendDay(instant, "UTC"), "2026-10-21");
  assert.equal(spendDay(instant, "America/Argentina/Buenos_Aires"), "2026-10-20");
});

test("a router allowed on one chain is denied on another, and a token sell cannot attach value", () => {
  const config = loadConfig({ ROUTER_ALLOWLIST_JSON: JSON.stringify({ "8453": [router] }) });
  const base = {
    data: "0x" as const,
    withdrawAllowlist: [],
    maxValueWei: DEFAULT_MAX_VALUE_WEI,
    allowHotApproval: false,
  };
  assert.throws(() => assertEvmSigning({ ...base, chainId: 1, to: router, value: 0n, purpose: "swap", routers: config.routerAllowlist[1] ?? [] }), /router allowlist is empty/);
  assert.doesNotThrow(() => assertEvmSigning({ ...base, chainId: 8453, to: router, value: 0n, purpose: "swap", routers: config.routerAllowlist[8453] ?? [] }));
  assert.throws(
    () => assertEvmSigning({ ...base, chainId: 8453, to: router, value: 1n, purpose: "swap", nativeSell: false, routers: config.routerAllowlist[8453] ?? [] }),
    /token sell must not attach native value/,
  );
  assert.doesNotThrow(() => assertEvmSigning({ ...base, chainId: 8453, to: router, value: 1n, purpose: "swap", nativeSell: true, routers: config.routerAllowlist[8453] ?? [] }));
  const data = encodeFunctionData({ abi: erc20Abi, functionName: "transfer", args: [owner, 1n] });
  assert.throws(
    () =>
      assertEvmSigning({
        ...base,
        chainId: 8453,
        to: "0x4444444444444444444444444444444444444444",
        data,
        value: 0n,
        purpose: "withdraw",
        routers: [],
        withdrawAllowlist: [owner],
        recoveryTokens: [],
      }),
    /recovery allowlist/,
  );
  assert.doesNotThrow(() =>
    assertEvmSigning({
      ...base,
      chainId: 8453,
      to: "0x4444444444444444444444444444444444444444",
      data,
      value: 0n,
      purpose: "withdraw",
      routers: [],
      withdrawAllowlist: [owner],
      recoveryTokens: ["0x4444444444444444444444444444444444444444"],
    }),
  );
  assert.equal(SOLANA_BASE_PROGRAMS.includes(JUPITER_PROGRAM_ID), true);
});

test("live mode pins aggregator hosts and private service URLs", () => {
  const live = { LISTING_TRADER_LIVE: "true", AUTH_TOKEN: tokenAuth };
  assert.throws(() => assertBoot(loadConfig({ ...live, JUPITER_API_BASE: "https://evil.example/swap/v1" })), /pins jupiterBase/);
  assert.throws(() => assertBoot(loadConfig({ ...live, RESOLVER_URL: "http://evil.example/alert" })), /https or a railway.internal host/);
  assert.doesNotThrow(() => assertBoot(loadConfig({ ...live, RESOLVER_URL: "http://resolver.railway.internal:8080" })));
  assert.doesNotThrow(() => assertLiveEdges(loadConfig({ AUTH_TOKEN: tokenAuth, RESOLVER_URL: "http://127.0.0.1:8080" }), {}));
});

test("the kill switch skips a live buy and a missing balance read does not trade", async () => {
  resetExecutorState();
  const config = loadConfig({ AUTH_TOKEN: tokenAuth, LISTING_TRADER_LIVE: "true", RESOLVER_URL: "http://resolver.railway.internal:8080" });
  const sends: string[] = [];
  const stopped = await execute(intent(), { ...runtime(config, sends, async () => ({ priceImpactPct: 0.2, feeUsd: 0.01, buyAmount: "10" })), killSwitchEnabled: async () => true });
  assert.equal(stopped.decision, "skipped");
  assert.equal(stopped.reason, "kill switch is on");
  assert.equal(sends.length, 0);

  const holding = { symbol: "USDC", address: "usdc", amount: 20, usd: 20, native: false, decimals: 6 };
  assert.equal(applyBalance(holding, 1).amount, 1);
  assert.equal(applyBalance(holding, 1).usd, 1);
  const unread = await holdingsForTrade(true, [holding], null);
  assert.equal(unread.ok, false);
  const app = await createExecutorApp(
    config,
    runtime(config, sends, async () => ({ priceImpactPct: 0.2, feeUsd: 0.01, buyAmount: "10" })),
    null,
    [],
    [holding],
    false,
    null,
    async () => new Response(JSON.stringify({ kind: "unlisted" }), { status: 200 }),
  );
  const response = await app.inject({
    method: "POST",
    url: "/listing",
    headers: { authorization: `Bearer ${tokenAuth}`, "content-type": "application/json" },
    payload: alertBody(),
  });
  assert.equal(response.json().reason, "unlisted");
  const hitApp = await createExecutorApp(
    config,
    runtime(config, sends, async () => ({ priceImpactPct: 0.2, feeUsd: 0.01, buyAmount: "10" })),
    null,
    [],
    [holding],
    false,
    null,
    async () =>
      new Response(
        JSON.stringify({
          kind: "hit",
          token: {
            id: "solana:mint",
            ticker: "MPLX",
            names: ["Metaplex"],
            chainKey: "solana",
            chain: { kind: "solana" },
            contract: "mint",
            decimals: 6,
            pairMap: buildPairMap([]),
            hyperliquid: null,
            refreshedAt: "2026-10-21T00:00:00.000Z",
          },
        }),
        { status: 200 },
      ),
  );
  const blocked = await hitApp.inject({
    method: "POST",
    url: "/listing",
    headers: { authorization: `Bearer ${tokenAuth}`, "content-type": "application/json" },
    payload: alertBody(),
  });
  assert.equal(blocked.json().reason, "balance was not read");
  assert.equal(sends.length, 0);
  await app.close();
  await hitApp.close();
});

test("keystore headers are authenticated, buffers zero, and the passphrase prompt does not echo", async () => {
  const material = createWalletMaterial();
  const file = encryptWallet(material, "correct horse battery");
  const opened = decryptWallet(file, "correct horse battery");
  assert.equal(opened.evmAddress, file.addresses.evm);
  assert.equal(opened.solanaAddress, file.addresses.solana);
  assert.equal(file.n, 131072);
  assert.throws(() => decryptWallet({ ...file, addresses: { ...file.addresses, evm: owner } }, "correct horse battery"), /keystore/);
  const secret = trackSecret(new Secret("supersecretvalue"));
  zeroLoadedSecrets();
  assert.equal(secret.reveal(), "");
  const env = { KEYSTORE_PASSPHRASE: "correct horse battery", ALLOW_LOCAL_SIGNER: "true" };
  assert.throws(() => loadManagedSigner(env, loadConfig({ LISTING_TRADER_LIVE: "true", ALLOW_LOCAL_SIGNER: "true", AUTH_TOKEN: tokenAuth })), /live mode requires Turnkey/);
  assert.equal(env.KEYSTORE_PASSPHRASE, undefined);
  let written = "";
  const listeners = new Set<(chunk: Buffer) => void>();
  const stdin = {
    isRaw: false,
    setRawMode() {},
    resume() {},
    pause() {},
    on(_event: "data", listener: (chunk: Buffer) => void) {
      listeners.add(listener);
    },
    off(_event: "data", listener: (chunk: Buffer) => void) {
      listeners.delete(listener);
    },
  };
  const pending = readHiddenLine(stdin, {
    write(chunk: string) {
      written += chunk;
    },
  });
  for (const listener of listeners) listener(Buffer.from("hunter2\n"));
  assert.equal(await pending, "hunter2");
  assert.equal(written.includes("hunter2"), false);
});

test("the image digest is pinned and jayson can load its json parser", () => {
  const docker = readFileSync(new URL("../../Dockerfile", import.meta.url), "utf8");
  assert.match(docker, /node:22-bookworm-slim@sha256:3ed98443660ff48413b5af19ecefce3b9d50845a901a43420d47cc63a9fddbe9/);
  assert.match(docker, /npm ci --ignore-scripts/);
  assert.match(docker, /npm ci --omit=dev --ignore-scripts/);
  const pkg = JSON.parse(readFileSync(new URL("../../package.json", import.meta.url), "utf8")) as { overrides?: { uuid?: string; "stream-json"?: string } };
  assert.equal(pkg.overrides?.uuid, "11.1.1");
  execFileSync(process.execPath, ["-e", "require('jayson/lib/utils')"], { cwd: new URL("../..", import.meta.url) });
});

test("jupiter swap build sends the slippage cap", async () => {
  resetProviderGuards();
  const config = loadConfig({ AUTH_TOKEN: tokenAuth, SOLANA_RPC_URL: "http://127.0.0.1:9", MAX_SLIPPAGE_BPS: "100" });
  const bodies: Array<{ slippageBps?: number }> = [];
  const signer: TransactionSigner = {
    backend: "keystore",
    evmAddress: () => null,
    solanaAddress: () => Keypair.generate().publicKey.toBase58(),
    async signEvm() {
      return "0x";
    },
    async signSolana() {
      return new Uint8Array();
    },
    async signHyperliquid() {
      return { r: "0x01", s: "0x02", v: 27 };
    },
  };
  await assert.rejects(() =>
    broadcastRoute(
      config,
      signer,
      {
        kind: "solana",
        description: "swap",
        chain: { kind: "solana" },
        hyperliquidActions: [],
        legs: [{ sellAddress: "usdc", buyAddress: "mint", sellAmount: "1000", spentUsd: 5, priceUsd: 1, decimals: 6 }],
      },
      1,
      async (input, init) => {
        const url = String(input);
        if (url.endsWith("/swap")) {
          bodies.push(JSON.parse(String(init?.body)) as { slippageBps?: number });
          return new Response(JSON.stringify({ swapTransaction: "aaaa" }), { status: 200 });
        }
        return new Response(JSON.stringify({ outAmount: "10", priceImpactPct: "0.001" }), { status: 200 });
      },
    ),
  );
  assert.equal(bodies[0]?.slippageBps, 100);
});
