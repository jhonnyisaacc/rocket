import type { FastifyInstance } from "fastify";
import type { Alert, ExecutionReport, Holding, SwapIntent, TokenRecord, TxRecord } from "./domain.js";
import { chainByKey } from "./chains.js";
import { configSecrets, loadConfig, publicConfig, type AppConfig } from "./config.js";
import { holdingFitsChain, type BalanceReader } from "./balances.js";
import { resolveTokenDecimals } from "./token-decimals.js";
import { decideWithdraw, execute, restoreSpent, type ExecutorDeps } from "./executor.js";
import { latencyLog } from "./latency.js";
import { buildApp, mutatingLimit } from "./http.js";
import { fetchHyperliquidMid, quoteHop } from "./clients.js";
import { redactError, zeroLoadedSecrets } from "./redact.js";
import { broadcastRoute, lookupAgedTx, recoverToken, withdrawNative } from "./broadcast.js";
import { assertApprovedAgent, fetchSzDecimals } from "./hyperliquid.js";
import { createLogger } from "./log.js";
import { assertBoot, loadManagedSigner, tokenMatches, type TransactionSigner } from "./managed-signer.js";
import { seedApprovals } from "./approvals.js";
import { commitSpend, readKillSwitch, reconcileReserved, recordSpend, recordTx, releaseSpend, spendDay, spentOnDay } from "./spend.js";
import { planRebalance } from "./rebalance.js";
import { screenToken } from "./screening.js";
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
    idempotencyKey: alert.id,
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

function deps(config: AppConfig, signer: TransactionSigner | null, secrets: readonly string[], journal: ReturnType<typeof txJournal>, priceOf: PriceOf): ExecutorDeps {
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
      return quoteHop(config, { ...hop, sellAmount: hop.sellAmount }, reference);
    },
    markPrice: (coin) => fetchHyperliquidMid(config.hyperliquidUrl, coin),
    send: (request, onTx) => broadcastRoute(config, signer, request, config.maxSlippageBps / 100, fetch, secrets, { onTx }),
    recordTx: journal,
    szDecimals: (market) => fetchSzDecimals(config.hyperliquidUrl, market),
    recordSpend:
      config.live && config.databaseUrl
        ? (key, usd) => recordSpend(config.databaseUrl as string, key, usd, spendDay(new Date(), config.spendTimezone), config.dailyUsdCap)
        : undefined,
    killSwitchEnabled: async () => {
      if (config.killSwitch) return true;
      if (!config.databaseUrl) return false;
      return readKillSwitch(config.databaseUrl);
    },
    commitSpend: config.live && config.databaseUrl ? (key) => commitSpend(config.databaseUrl as string, key) : undefined,
    releaseSpend: config.live && config.databaseUrl ? (key) => releaseSpend(config.databaseUrl as string, key) : undefined,
    screenToken: config.screening ? (token) => screenToken(config, token) : undefined,
    readTokenDecimals: (token) => resolveTokenDecimals(token.chainKey, token.address, token.chain, config.rpcByChainKey[token.chainKey]),
  };
}

export async function createExecutorApp(
  config: AppConfig,
  runtime: ExecutorDeps,
  signer: TransactionSigner | null,
  secrets: readonly string[],
  holdings: SwapIntent["holdings"],
  logger = false,
  readBalance: BalanceReader | null = null,
  fetchImpl: typeof fetch = fetch,
): Promise<FastifyInstance> {
  const app = await buildApp({ authToken: config.authToken ?? "", secrets, logger });
  const guard = { preHandler: app.auth([app.verifyBearer]), config: mutatingLimit };
  app.get("/health", async () => ({ ok: true, service: "executor", ...publicConfig(config) }));
  app.post("/execute", guard, async (request, reply) => {
    const parsed = intentSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: "invalid request" });
    const report = await execute(parsed.data, { ...runtime, mode: "dry_run" });
    console.log(JSON.stringify({ report: { ...report, latency: latencyLog(report.latency) } }));
    await notify(config, report, secrets);
    return report;
  });
  app.post("/listing", guard, async (request, reply) => {
    const parsed = alertSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: "invalid request" });
    if (!config.resolverUrl || !config.authToken) return reply.code(503).send({ error: "RESOLVER_URL is not set" });
    const response = await fetchImpl(`${config.resolverUrl.replace(/\/$/, "")}/alert`, {
      method: "POST",
      headers: { "content-type": "application/json", authorization: `Bearer ${config.authToken}` },
      body: JSON.stringify(parsed.data),
    });
    const resolution = resolutionSchema.safeParse(await response.json());
    if (!resolution.success) return reply.code(200).send({ decision: "skipped", reason: "resolver response did not match the schema" });
    if (resolution.data.kind !== "hit" || !resolution.data.token) {
      return reply.code(200).send({ decision: "skipped", reason: resolution.data.kind, latency: { alertReceivedMs: 0 } });
    }
    const intent = intentFromResolution(parsed.data, resolution.data, holdings, config.maxUsdPerTrade, config.maxSlippageBps);
    if (!intent) return reply.code(200).send({ decision: "skipped", reason: resolution.data.kind, latency: { alertReceivedMs: 0 } });
    const report = await execute(intent, { ...runtime, readBalance });
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
    const decision = decideWithdraw({
      adminOk: Boolean(config.adminToken) && tokenMatches(presented, config.adminToken ?? ""),
      enabled: config.withdrawEnabled,
      amount: parsed.data.amount,
      cap: config.maxWithdrawAmount,
      destinationAllowed: config.withdrawAllowlist.some((item) => item.toLowerCase() === parsed.data.to.toLowerCase()),
      mint: parsed.data.mint,
      recoveryAllowlist: config.tokenRecoveryAllowlist,
      live: config.live,
      killSwitch: config.killSwitch,
      signerReady: signer !== null,
      chainKey: parsed.data.chainKey,
      decimals: parsed.data.decimals,
    });
    if (decision.error) return reply.code(decision.http).send({ error: decision.error });
    if (decision.decision === "would_send") return { decision: "would_send", to: parsed.data.to, mode: config.live ? "live" : "dry_run" };
    if (!signer || !parsed.data.chainKey || parsed.data.amount === undefined) return reply.code(409).send({ error: "live withdraw needs a signer, chainKey, and amount" });
    const onTx = async (tx: TxRecord) => runtime.recordTx?.(null, tx);
    let tx: TxRecord;
    if (!parsed.data.mint) {
      tx = await withdrawNative({ config, signer, chainKey: parsed.data.chainKey, to: parsed.data.to, amount: parsed.data.amount, secrets, onTx });
    } else {
      if (parsed.data.decimals === undefined) return reply.code(409).send({ error: "token withdraw needs decimals" });
      tx = await recoverToken({
        config,
        signer,
        chainKey: parsed.data.chainKey,
        to: parsed.data.to,
        amount: parsed.data.amount,
        mint: parsed.data.mint,
        decimals: parsed.data.decimals,
        secrets,
        onTx,
      });
    }
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
  assertBoot(config);
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
  if (config.databaseUrl) {
    await reconcileReserved(config.databaseUrl, config.reconcileAfterMinutes, (chainKey, hash) => lookupAgedTx(config, chainKey, hash), (entry) =>
      logger.info({ reconcile: entry }, "reconciled reserved spend"),
    );
    const day = spendDay(new Date(), config.spendTimezone);
    restoreSpent(await spentOnDay(config.databaseUrl, day), day);
  }
  const prices = createPriceCache(coingeckoLoader(config, pricedHoldings(holdingsParsed.data, config.enabledChainKeys)), config.priceMaxAgeMs);
  const refreshPrices = () => prices.refresh().catch((error: unknown) => logger.warn({ err: error }, "price refresh failed"));
  await refreshPrices();
  setInterval(refreshPrices, config.priceRefreshMs).unref();
  const runtime = deps(config, signer, secrets, txJournal(config, (entry) => logger.info(entry, "signed tx")), (holding) => prices.priceOf(holding));
  const app = await createExecutorApp(config, runtime, signer, secrets, holdingsParsed.data, true, config.live ? chainReader(config, signer) : null);
  const stop = () => {
    zeroLoadedSecrets();
    process.exit(0);
  };
  process.once("SIGINT", stop);
  process.once("SIGTERM", stop);
  await app.listen({ port: config.port, host: "0.0.0.0" });
  console.log(JSON.stringify({ service: "executor", port: config.port, ...publicConfig(config) }));
}

function chainReader(config: AppConfig, signer: TransactionSigner | null): BalanceReader {
  return async (holding: Holding) => {
    if (!signer || !holding.chainKey) return null;
    const spec = chainByKey(holding.chainKey);
    const rpc = config.rpcByChainKey[holding.chainKey];
    if (!spec || !rpc) return null;
    const decimals = holding.decimals ?? (holding.native ? (spec.chain.kind === "solana" ? 9 : 18) : null);
    if (decimals === null) return null;
    if (holding.chainKey && !holdingFitsChain(holding, holding.chainKey)) return null;
    if (spec.chain.kind === "solana") {
      const owner = signer.solanaAddress();
      if (!owner) return null;
      const { Connection, PublicKey } = await import("@solana/web3.js");
      const connection = new Connection(rpc, "confirmed");
      if (holding.native) return (await connection.getBalance(new PublicKey(owner))) / 10 ** decimals;
      let mint;
      try {
        mint = new PublicKey(holding.address);
      } catch {
        return null;
      }
      const accounts = await connection.getParsedTokenAccountsByOwner(new PublicKey(owner), { mint });
      const ui = accounts.value[0]?.account.data.parsed?.info?.tokenAmount?.uiAmountString;
      return typeof ui === "string" ? Number(ui) : null;
    }
    if (spec.chain.kind !== "evm") return null;
    const owner = signer.evmAddress();
    if (!owner) return null;
    const { createPublicClient, erc20Abi, formatUnits, http } = await import("viem");
    const client = createPublicClient({ transport: http(rpc, { retryCount: 0, timeout: 1500 }) });
    if (holding.native) {
      const raw = await client.getBalance({ address: owner as `0x${string}` });
      return Number(formatUnits(raw, decimals));
    }
    if (!/^0x[0-9a-fA-F]{40}$/.test(holding.address)) return null;
    const raw = await client.readContract({ address: holding.address as `0x${string}`, abi: erc20Abi, functionName: "balanceOf", args: [owner as `0x${string}`] });
    return Number(formatUnits(raw, decimals));
  };
}

const entry = process.argv[1] ?? "";
if (entry.endsWith("executor-server.js")) {
  main().catch((error: unknown) => {
    console.error(JSON.stringify({ error: redactError(error) }));
    process.exit(1);
  });
}
