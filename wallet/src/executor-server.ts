import type { FastifyInstance } from "fastify";
import { guardFor } from "./aggregators.js";
import { withTimeout } from "./timeout.js";
import type { Alert, ExecutionReport, Holding, SwapIntent, TokenRecord, TxRecord } from "./domain.js";
import { chainByKey } from "./chains.js";
import { configSecrets, drainTimeoutMs, loadConfig, publicConfig, type AppConfig } from "./config.js";
import { createBalanceCache, holdingFitsChain, type BalanceCache, type BalanceReader } from "./balances.js";
import { resolveTokenDecimals } from "./token-decimals.js";
import { createExecutorState, decideWithdraw, execute, restoreSpent, type ExecutorDeps, type ExecutorState } from "./executor.js";
import { chainReader } from "./executor-server/chain-reader.js";
import { latencyLog } from "./latency.js";
import { anyTokenMatches, bearerOf, buildApp, mutatingLimit, perMinute, shutdown } from "./http.js";
import { fetchHyperliquidMid, quoteHop } from "./clients.js";
import { redactError, zeroLoadedSecrets } from "./redact.js";
import { broadcastRoute, lookupAgedTx, recoverToken, withdrawNative } from "./broadcast.js";
import { assertApprovedAgent, fetchSzDecimals } from "./hyperliquid.js";
import { createLogger } from "./log.js";
import { assertBoot, loadManagedSigner, tokenMatches, type TransactionSigner } from "./managed-signer.js";
import { seedApprovals } from "./approvals.js";
import {
  acquireExecutorLock,
  backfillStrategyIds,
  closeSpendPools,
  commitSpend,
  commitWithdraw,
  createMemoryWithdrawJournal,
  listingKey,
  readKillSwitch,
  reconcileReserved,
  recordSpend,
  recordTx,
  releaseSpend,
  releaseWithdraw,
  reserveWithdraw,
  spendDay,
  spentOnDay,
  type SpendScope,
  strategyKey,
} from "./spend.js";
import { planRebalance } from "./rebalance.js";
import { screenToken } from "./screening.js";
import { supportTierFor } from "./support.js";
import { evmReadClient, firstOk, solanaConnection } from "./rpc.js";
import { coingeckoLoader, createPriceCache, pricedHoldings, type PriceOf } from "./prices.js";
import { alertSchema, holdingsSchema, intentSchema, rebalanceSchema, resolutionSchema, withdrawSchema } from "./schemas.js";

function intentToken(token: TokenRecord): SwapIntent["token"] {
  return {
    symbol: token.ticker,
    address: token.contract,
    decimals: token.decimals,
    chain: token.chain,
    chainKey: token.chainKey,
    pairMap: token.pairMap,
  };
}

export function intentFromResolution(
  alert: Alert,
  resolution: { kind: string; token?: TokenRecord; alternates?: TokenRecord[] },
  holdings: SwapIntent["holdings"],
  notionalUsd: number,
  slippageBps: number,
): SwapIntent | null {
  if (resolution.kind !== "hit" || !resolution.token) return null;
  return {
    idempotencyKey: listingKey(alert.id),
    side: "buy",
    notionalUsd,
    slippageBps,
    token: intentToken(resolution.token),
    holdings,
    hyperliquid: resolution.token.hyperliquid ?? null,
    receivedAtMs: Date.parse(alert.receivedAt),
    alternates: (resolution.alternates ?? []).map(intentToken),
  };
}

async function notify(config: AppConfig, report: ExecutionReport, secrets: readonly string[]): Promise<void> {
  if (!config.notifierUrl) return;
  await fetch(config.notifierUrl, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      idempotencyKey: report.idempotencyKey,
      mode: report.mode,
      decision: report.decision,
      reason: report.reason,
      venue: report.venue,
      route: report.route,
      latency: latencyLog(report.latency),
    }),
  }).catch((error: unknown) => {
    console.log(JSON.stringify({ notifier: redactError(error, secrets) }));
  });
}

export function txJournal(config: AppConfig, log: (entry: { idempotencyKey: string | null; tx: TxRecord }) => void) {
  return async (idempotencyKey: string | null, tx: TxRecord): Promise<void> => {
    log({ idempotencyKey, tx });
    if (config.databaseUrl) await recordTx(config.databaseUrl, idempotencyKey, tx);
  };
}

function deps(
  config: AppConfig,
  signer: TransactionSigner | null,
  secrets: readonly string[],
  journal: ReturnType<typeof txJournal>,
  priceOf: PriceOf,
  balances: BalanceCache | null,
  opts: { state?: ExecutorState; spendScope?: SpendScope; databaseUrl?: string | null } = {},
): ExecutorDeps {
  const databaseUrl = opts.databaseUrl !== undefined ? opts.databaseUrl : config.databaseUrl;
  const spent = (tx: TxRecord) => balances?.invalidate(tx.chainKey);
  return {
    config,
    priceOf,
    mode: config.live ? "live" : "dry_run",
    spentTodayUsd: 0,
    quoteHop: (hop, context) => {
      const reference =
        context.priceUsd !== null && context.decimals !== null
          ? { spentUsd: context.spentUsd, priceUsd: context.priceUsd, decimals: context.decimals }
          : null;
      const taker = hop.chain.kind === "evm" ? signer?.evmAddress() : hop.chain.kind === "solana" ? signer?.solanaAddress() : null;
      return quoteHop(config, { ...hop, taker: taker ?? null }, reference);
    },
    markPrice: (coin) => fetchHyperliquidMid(config.hyperliquidUrl, coin),
    send: (request, onTx) => broadcastRoute(config, signer, request, config.maxSlippageBps / 100, fetch, secrets, { onTx }),
    recordTx: async (key, tx) => {
      spent(tx);
      await journal(key, tx);
    },
    szDecimals: (market) => fetchSzDecimals(config.hyperliquidUrl, market),
    state: opts.state ?? createExecutorState(),
    spendScope: opts.spendScope,
    recordSpend:
      config.live && databaseUrl
        ? (key, usd, scope) => recordSpend(databaseUrl, key, usd, spendDay(new Date(), config.spendTimezone), config.dailyUsdCap, scope)
        : undefined,
    killSwitchEnabled: async () => {
      if (config.killSwitch) return true;
      if (!databaseUrl) return false;
      return readKillSwitch(databaseUrl);
    },
    commitSpend: config.live && databaseUrl ? (key) => commitSpend(databaseUrl, key) : undefined,
    releaseSpend: config.live && databaseUrl ? (key) => releaseSpend(databaseUrl, key) : undefined,
    screenToken: config.screening ? (token) => screenToken(config, token) : undefined,
    supportTierFor: (chainKey) => supportTierFor(config.supportByChain, chainKey),
    readTokenDecimals: (token) => resolveTokenDecimals(token.chainKey, token.address, token.chain, config.rpcByChainKey[token.chainKey]),
    readBalance: balances?.read ?? null,
  };
}

export type ExecutorInstance = {
  config: AppConfig;
  state: ExecutorState;
  deps: ExecutorDeps;
  execute: (intent: SwapIntent, overrides?: Partial<ExecutorDeps>) => Promise<ExecutionReport>;
};

export function createExecutor(
  config: AppConfig,
  signer: TransactionSigner | null,
  db: string | null,
  opts: { priceOf?: PriceOf; balances?: BalanceCache | null; secrets?: readonly string[] } = {},
): ExecutorInstance {
  const state = createExecutorState();
  const secrets = opts.secrets ?? configSecrets(config).filter((item) => item.length >= 8);
  const runtime = deps(config, signer, secrets, txJournal({ ...config, databaseUrl: db }, () => undefined), opts.priceOf ?? (() => null), opts.balances ?? null, { state, databaseUrl: db });
  return {
    config,
    state,
    deps: runtime,
    execute: (intent, overrides = {}) => execute(intent, { ...runtime, ...overrides, state }),
  };
}

export async function createExecutorApp(
  config: AppConfig,
  runtime: ExecutorDeps,
  signer: TransactionSigner | null,
  secrets: readonly string[],
  holdings: SwapIntent["holdings"],
  logger = false,
  fetchImpl: typeof fetch = fetch,
): Promise<FastifyInstance> {
  const app = await buildApp({ authTokens: config.executorAuthTokens, secrets, logger });
  const memoryWithdraw = createMemoryWithdrawJournal();
  const guard = { preHandler: app.auth([app.verifyBearer]), config: mutatingLimit };
  const listingGuard = { preHandler: app.auth([app.verifyBearer]), config: perMinute(config.listingRateLimitPerMin) };
  app.get("/health", async () => ({ ok: true }));
  app.get("/status", { preHandler: app.auth([app.verifyBearer]) }, async () => ({ ok: true, service: "executor", ...publicConfig(config) }));
  app.get("/provider-health", { preHandler: app.auth([app.verifyBearer]) }, async () => ({ providers: guardFor(config).snapshot() }));
  app.post("/execute", { config: mutatingLimit }, async (request, reply) => {
    const presented = bearerOf(request);
    const strategyPeek = Object.values(config.strategies).some((strategy) => anyTokenMatches(presented, strategy.tokens));
    if (!anyTokenMatches(presented, config.executorAuthTokens) && !strategyPeek) return reply.code(401).send({ error: "unauthorized" });
    const parsed = intentSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: "invalid request" });
    if (anyTokenMatches(presented, config.executorAuthTokens)) {
      const report = await app.drain.track(() => execute(parsed.data, { ...runtime, mode: "dry_run" }));
      console.log(JSON.stringify({ report: { ...report, latency: latencyLog(report.latency) } }));
      await notify(config, report, secrets);
      return report;
    }
    const strategyEntry = Object.entries(config.strategies).find(([, strategy]) => anyTokenMatches(presented, strategy.tokens));
    if (!strategyEntry) return reply.code(401).send({ error: "unauthorized" });
    const [strategyId, strategy] = strategyEntry;
    const intent: SwapIntent = { ...parsed.data, idempotencyKey: strategyKey(strategyId, parsed.data.idempotencyKey) };
    if (parsed.data.notionalUsd > strategy.maxUsdPerTrade) {
      return {
        idempotencyKey: intent.idempotencyKey,
        mode: runtime.mode,
        decision: "skipped",
        reason: `strategy ${strategyId} maxUsdPerTrade cap ${strategy.maxUsdPerTrade} USD`,
        venue: parsed.data.token.chainKey,
        route: null,
        latency: { alertReceivedMs: parsed.data.receivedAtMs },
      };
    }
    const report = await app.drain.track(() =>
      execute(intent, { ...runtime, spendScope: { strategyId, capUsd: strategy.dailyUsdCap } }),
    );
    console.log(JSON.stringify({ report: { ...report, latency: latencyLog(report.latency) } }));
    await notify(config, report, secrets);
    return report;
  });
  app.post("/listing", listingGuard, async (request, reply) => {
    const parsed = alertSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: "invalid request" });
    if (config.killSwitch || (runtime.killSwitchEnabled ? await runtime.killSwitchEnabled().catch(() => true) : false)) {
      return reply.code(200).send({ decision: "skipped", reason: "kill switch is on", latency: { alertReceivedMs: 0 } });
    }
    if (!config.resolverUrl || config.resolverAuthTokens.length === 0) return reply.code(503).send({ error: "RESOLVER_URL is not set" });
    let resolution;
    const resolverUrl = config.resolverUrl;
    const resolverToken = config.resolverAuthTokens[0];
    try {
      const body = await withTimeout(config.resolverTimeoutMs, async (signal) => {
        const response = await fetchImpl(`${resolverUrl.replace(/\/$/, "")}/alert`, {
          method: "POST",
          headers: { "content-type": "application/json", authorization: `Bearer ${resolverToken}` },
          body: JSON.stringify(parsed.data),
          signal,
        });
        return response.ok ? ((await response.json()) as unknown) : undefined;
      });
      if (body === undefined) return reply.code(200).send({ decision: "skipped", reason: "resolver_error" });
      resolution = resolutionSchema.safeParse(body);
    } catch {
      return reply.code(200).send({ decision: "skipped", reason: "resolver_error" });
    }
    if (!resolution.success) return reply.code(200).send({ decision: "skipped", reason: "resolver response did not match the schema" });
    if (resolution.data.kind !== "hit" || !resolution.data.token) {
      return reply.code(200).send({ decision: "skipped", reason: resolution.data.kind, latency: { alertReceivedMs: 0 } });
    }
    const intent = intentFromResolution(parsed.data, resolution.data, holdings, config.maxUsdPerTrade, config.maxSlippageBps);
    if (!intent) return reply.code(200).send({ decision: "skipped", reason: resolution.data.kind, latency: { alertReceivedMs: 0 } });
    const report = await app.drain.track(() => execute(intent, runtime));
    console.log(JSON.stringify({ report: { ...report, latency: latencyLog(report.latency) } }));
    await notify(config, report, secrets);
    return report;
  });
  app.post("/withdraw", guard, async (request, reply) => {
    const header = request.headers["x-admin-token"];
    const presented = typeof header === "string" ? header : "";
    const parsed = withdrawSchema.safeParse(request.body);
    if (!parsed.success) {
      const adminOk = Boolean(config.adminToken) && tokenMatches(presented, config.adminToken ?? "");
      if (!adminOk) return reply.code(401).send({ error: "unauthorized" });
      return reply.code(400).send({ error: "invalid request" });
    }
    const dbStopped = runtime.killSwitchEnabled ? await runtime.killSwitchEnabled().catch(() => true) : false;
    const decision = decideWithdraw({
      adminOk: Boolean(config.adminToken) && tokenMatches(presented, config.adminToken ?? ""),
      enabled: config.withdrawEnabled,
      amount: parsed.data.amount,
      cap: config.maxWithdrawAmount,
      destinationAllowed: config.withdrawAllowlist.some((item) => item.toLowerCase() === parsed.data.to.toLowerCase()),
      mint: parsed.data.mint,
      recoveryAllowlist: config.tokenRecoveryAllowlist,
      live: config.live,
      killSwitch: config.killSwitch || dbStopped,
      signerReady: signer !== null,
      chainKey: parsed.data.chainKey,
      decimals: parsed.data.decimals,
    });
    if (decision.error) return reply.code(decision.http).send({ error: decision.error });
    if (decision.decision === "would_send") return { decision: "would_send", to: parsed.data.to, mode: config.live ? "live" : "dry_run" };
    if (!parsed.data.idempotencyKey) return reply.code(409).send({ error: "live withdraw needs an idempotencyKey" });
    if (!signer || !parsed.data.chainKey || parsed.data.amount === undefined) return reply.code(409).send({ error: "live withdraw needs a signer, chainKey, and amount" });
    const withdrawKey = `withdraw:${parsed.data.idempotencyKey}`;
    const withdrawScope = `${parsed.data.chainKey}:${parsed.data.mint ?? "native"}`;
    const withdrawDay = spendDay(new Date(), config.spendTimezone);
    const reserved = config.databaseUrl
      ? await reserveWithdraw(config.databaseUrl, withdrawKey, withdrawScope, parsed.data.amount, withdrawDay, config.maxWithdrawDailyAmount)
      : await memoryWithdraw.reserve(withdrawKey, withdrawScope, parsed.data.amount, withdrawDay, config.maxWithdrawDailyAmount);
    if (reserved === "exists") return reply.code(409).send({ error: "duplicate withdraw" });
    if (reserved === "cap") return reply.code(403).send({ error: "withdraw exceeds the daily cap" });
    const commitKey = async () => {
      if (config.databaseUrl) await commitWithdraw(config.databaseUrl, withdrawKey);
      else await memoryWithdraw.commit(withdrawKey);
    };
    const releaseKey = async () => {
      if (config.databaseUrl) await releaseWithdraw(config.databaseUrl, withdrawKey).catch(() => undefined);
      else await memoryWithdraw.release(withdrawKey);
    };
    const onTx = async (tx: TxRecord) => runtime.recordTx?.(null, tx);
    let tx: TxRecord;
    try {
      if (!parsed.data.mint) {
        tx = await app.drain.track(() => withdrawNative({ config, signer, chainKey: parsed.data.chainKey as string, to: parsed.data.to, amount: parsed.data.amount as number, secrets, onTx }));
      } else {
        if (parsed.data.decimals === undefined) {
          await releaseKey();
          return reply.code(409).send({ error: "token withdraw needs decimals" });
        }
        const recovery = { chainKey: parsed.data.chainKey, amount: parsed.data.amount, mint: parsed.data.mint, decimals: parsed.data.decimals };
        tx = await app.drain.track(() =>
          recoverToken({
            config,
            signer,
            chainKey: recovery.chainKey,
            to: parsed.data.to,
            amount: recovery.amount,
            mint: recovery.mint,
            decimals: recovery.decimals,
            secrets,
            onTx,
          }),
        );
      }
    } catch (error) {
      await releaseKey();
      throw error;
    }
    await commitKey();
    return { decision: "sent", to: parsed.data.to, chainKey: parsed.data.chainKey, mint: parsed.data.mint, tx };
  });
  app.post("/rebalance", guard, async (request, reply) => {
    const parsed = rebalanceSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: "invalid request" });
    return planRebalance({
      quotes: parsed.data.quotes,
      maxBridgeUsd: config.maxBridgeUsd,
      maxFeeBps: config.maxBridgeFeeBps,
      spentBridgeUsd: parsed.data.spentBridgeUsd,
      dailyBridgeCap: config.dailyBridgeUsdCap,
      ownAddresses: parsed.data.ownAddresses,
      allowlist: config.withdrawAllowlist,
    });
  });
  return app;
}

async function main(): Promise<void> {
  const config = loadConfig();
  assertBoot(config, "executor");
  seedApprovals(config.approvalSeed);
  const { signer, secrets: signerSecrets } = loadManagedSigner(process.env, config);
  if (config.live && !signer) throw new Error("live mode requires Turnkey");
  if (config.live && !config.databaseUrl) throw new Error("live mode requires DATABASE_URL so the daily cap survives restart");
  if (config.live) {
    const agent = process.env.TURNKEY_HYPERLIQUID_ADDRESS;
    if (agent) {
      if (!config.hyperliquidAccount) throw new Error("live mode requires HYPERLIQUID_ACCOUNT_ADDRESS to verify the agent");
      await assertApprovedAgent(config.hyperliquidUrl, config.hyperliquidAccount, agent, fetch);
    }
  }
  const holdingsParsed = holdingsSchema.safeParse(JSON.parse(process.env.WALLET_HOLDINGS_JSON ?? "[]"));
  if (!holdingsParsed.success) throw new Error("WALLET_HOLDINGS_JSON is invalid");
  const secrets = [...signerSecrets, ...configSecrets(config)].filter((item) => item.length >= 8);
  const logger = createLogger(secrets);
  const releaseLock = config.databaseUrl ? await acquireExecutorLock(config.databaseUrl, () => process.exit(1)) : null;
  const state = createExecutorState();
  const reconcile = async () => {
    if (!config.databaseUrl) return;
    await reconcileReserved(config.databaseUrl, config.reconcileAfterMinutes, (tx) => lookupAgedTx(config, tx), (entry) =>
      logger.info({ reconcile: entry }, "reconciled reserved spend"),
    );
  };
  if (config.databaseUrl) {
    await backfillStrategyIds(config.databaseUrl, Object.keys(config.strategies));
    await reconcile();
    const day = spendDay(new Date(), config.spendTimezone);
    restoreSpent(state, await spentOnDay(config.databaseUrl, day), day);
  }
  const prices = createPriceCache(coingeckoLoader(config, pricedHoldings(holdingsParsed.data, config.enabledChainKeys)), config.priceMaxAgeMs);
  const refreshPrices = () => prices.refresh().catch((error: unknown) => logger.warn({ err: error }, "price refresh failed"));
  await refreshPrices();
  const priceTimer = setInterval(refreshPrices, config.priceRefreshMs);
  priceTimer.unref();
  const reconcileTimer = config.databaseUrl ? setInterval(() => void reconcile().catch((error: unknown) => logger.warn({ err: error }, "reconcile failed")), config.reconcileIntervalMs) : null;
  reconcileTimer?.unref();
  const balances = config.live ? createBalanceCache(chainReader(config, signer), config.balanceCacheMs) : null;
  const runtime = deps(config, signer, secrets, txJournal(config, (entry) => logger.info(entry, "signed tx")), (holding) => prices.priceOf(holding), balances, { state });
  const app = await createExecutorApp(config, runtime, signer, secrets, holdingsParsed.data, true);
  let stopping = false;
  const stop = () => {
    if (stopping) return;
    stopping = true;
    void shutdown(app, Math.min(drainTimeoutMs(config), 20_000), async () => {
      clearInterval(priceTimer);
      if (reconcileTimer) clearInterval(reconcileTimer);
      zeroLoadedSecrets();
      await closeSpendPools();
      await releaseLock?.();
    }).then((idle) => process.exit(idle ? 0 : 1));
  };
  process.once("SIGINT", stop);
  process.once("SIGTERM", stop);
  await app.listen({ port: config.port, host: "0.0.0.0" });
  console.log(JSON.stringify({ service: "executor", port: config.port, ...publicConfig(config) }));
}

const entry = process.argv[1] ?? "";
if (entry.endsWith("executor-server.js")) {
  main().catch((error: unknown) => {
    console.error(JSON.stringify({ error: redactError(error) }));
    process.exit(1);
  });
}
