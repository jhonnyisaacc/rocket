import type { FastifyInstance } from "fastify";
import type { Alert, ExecutionReport, SwapIntent, TokenRecord } from "./domain.js";
import { loadConfig, publicConfig, type AppConfig } from "./config.js";
import { authorizeWithdraw, execute, restoreSpent, type ExecutorDeps } from "./executor.js";
import { latencyLog } from "./latency.js";
import { buildApp, mutatingLimit } from "./http.js";
import { fetchHyperliquidMid, quoteHop } from "./clients.js";
import { redactError } from "./redact.js";
import { broadcastRoute, withdrawNative } from "./broadcast.js";
import { assertBoot, loadManagedSigner, signingSecrets, type TransactionSigner } from "./managed-signer.js";
import { seedApprovals } from "./approvals.js";
import { loadSigner } from "./signer.js";
import { commitSpend, recordSpend, releaseSpend, spentOnDay, utcDay } from "./spend.js";
import { planRebalance } from "./rebalance.js";
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

function deps(config: AppConfig, signer: TransactionSigner | null, secrets: readonly string[]): ExecutorDeps {
  return {
    config,
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
    send: (request) => broadcastRoute(config, signer, request, config.maxSlippageBps / 100, fetch, secrets),
    recordSpend:
      config.live && config.databaseUrl
        ? (key, usd) => recordSpend(config.databaseUrl as string, key, usd, utcDay(), config.dailyUsdCap)
        : undefined,
    commitSpend: config.live && config.databaseUrl ? (key) => commitSpend(config.databaseUrl as string, key) : undefined,
    releaseSpend: config.live && config.databaseUrl ? (key) => releaseSpend(config.databaseUrl as string, key) : undefined,
  };
}

export async function createExecutorApp(
  config: AppConfig,
  runtime: ExecutorDeps,
  signer: TransactionSigner | null,
  secrets: readonly string[],
  holdings: SwapIntent["holdings"],
  logger = false,
): Promise<FastifyInstance> {
  const app = await buildApp({ authToken: config.authToken ?? "", secrets, logger });
  const guard = { preHandler: app.auth([app.verifyBearer]), config: mutatingLimit };
  app.get("/health", async () => ({ ok: true, service: "executor", ...publicConfig(config) }));
  app.post("/execute", guard, async (request, reply) => {
    const parsed = intentSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: "invalid request" });
    const report = await execute(parsed.data, runtime);
    console.log(JSON.stringify({ report: { ...report, latency: latencyLog(report.latency) } }));
    await notify(config, report, secrets);
    return report;
  });
  app.post("/listing", guard, async (request, reply) => {
    const parsed = alertSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: "invalid request" });
    if (!config.resolverUrl || !config.authToken) return reply.code(503).send({ error: "RESOLVER_URL is not set" });
    const response = await fetch(`${config.resolverUrl.replace(/\/$/, "")}/alert`, {
      method: "POST",
      headers: { "content-type": "application/json", authorization: `Bearer ${config.authToken}` },
      body: JSON.stringify(parsed.data),
    });
    const resolution = resolutionSchema.safeParse(await response.json());
    if (!resolution.success) return reply.code(200).send({ decision: "skipped", reason: "resolver response did not match the schema" });
    const intent = intentFromResolution(parsed.data, resolution.data, holdings, config.maxUsdPerTrade, config.maxSlippageBps);
    if (!intent) return reply.code(200).send({ decision: "skipped", reason: resolution.data.kind, latency: { alertReceivedMs: 0 } });
    const report = await execute(intent, runtime);
    console.log(JSON.stringify({ report: { ...report, latency: latencyLog(report.latency) } }));
    await notify(config, report, secrets);
    return report;
  });
  app.post("/withdraw", guard, async (request, reply) => {
    const parsed = withdrawSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: "invalid request" });
    const allowed = authorizeWithdraw(parsed.data.to, config.withdrawAllowlist);
    if (!allowed.ok) return reply.code(403).send({ error: allowed.reason });
    if (config.killSwitch || !config.live) return { decision: "would_send", to: parsed.data.to, mode: config.live ? "live" : "dry_run" };
    if (!signer || !parsed.data.chainKey || !(parsed.data.amount && parsed.data.amount > 0)) {
      return reply.code(409).send({ error: "live withdraw needs a signer, chainKey, and amount" });
    }
    await withdrawNative({ config, signer, chainKey: parsed.data.chainKey, to: parsed.data.to, amount: parsed.data.amount, secrets });
    return { decision: "sent", to: parsed.data.to, chainKey: parsed.data.chainKey };
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
  const signer = loadManagedSigner(process.env, config);
  if (config.live && !signer) throw new Error("live mode requires Turnkey or an allowed local signer");
  if (config.live && !config.databaseUrl) throw new Error("live mode requires DATABASE_URL so the daily cap survives restart");
  if (config.databaseUrl) restoreSpent(await spentOnDay(config.databaseUrl, utcDay()));
  const holdingsParsed = holdingsSchema.safeParse(JSON.parse(process.env.WALLET_HOLDINGS_JSON ?? "[]"));
  if (!holdingsParsed.success) throw new Error("WALLET_HOLDINGS_JSON is invalid");
  const secrets = signingSecrets(process.env, loadSigner(process.env));
  const runtime = deps(config, signer, secrets);
  const app = await createExecutorApp(config, runtime, signer, secrets, holdingsParsed.data, true);
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
