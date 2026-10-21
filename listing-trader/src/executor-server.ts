import type { Alert, ExecutionReport, SwapIntent } from "./domain.js";
import { loadConfig, publicConfig, type AppConfig } from "./config.js";
import { authorizeWithdraw, execute, restoreSpent, type ExecutorDeps } from "./executor.js";
import { latencyLog } from "./latency.js";
import { readJson, sendJson, startServer } from "./http.js";
import { fetchHyperliquidMid, quoteHop } from "./clients.js";
import { redactError } from "./redact.js";
import { broadcastRoute, withdrawNative } from "./broadcast.js";
import { loadSigner, signerSecrets } from "./signer.js";
import { recordSpend, releaseSpend, spentOnDay, utcDay } from "./spend.js";

export function intentFromResolution(alert: Alert, resolution: { kind: string; token?: SwapIntent["token"] & { hyperliquid?: SwapIntent["hyperliquid"] } }, holdings: SwapIntent["holdings"], notionalUsd: number, slippageBps: number): SwapIntent | null {
  if (resolution.kind !== "hit" || !resolution.token) return null;
  return {
    idempotencyKey: alert.id,
    side: "buy",
    notionalUsd,
    slippageBps,
    token: resolution.token,
    holdings,
    hyperliquid: resolution.token.hyperliquid ?? null,
    receivedAtMs: Date.parse(alert.receivedAt),
  };
}

async function notify(config: AppConfig, report: ExecutionReport): Promise<void> {
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
  });
}

function deps(config: AppConfig, signer: ReturnType<typeof loadSigner>): ExecutorDeps {
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
    send: (request) => broadcastRoute(config, signer, request, config.maxSlippageBps / 100),
    recordSpend: config.live && config.databaseUrl ? (key, usd) => recordSpend(config.databaseUrl as string, key, usd) : undefined,
    releaseSpend: config.live && config.databaseUrl ? (key) => releaseSpend(config.databaseUrl as string, key) : undefined,
  };
}

async function main(): Promise<void> {
  const config = loadConfig();
  const signer = loadSigner(process.env);
  if (config.live && !signer) throw new Error("live mode requires a keystore or wallet secrets");
  if (config.live && !config.databaseUrl) throw new Error("live mode requires DATABASE_URL so the daily cap survives restart");
  if (config.databaseUrl) restoreSpent(await spentOnDay(config.databaseUrl, utcDay()));
  const secrets = signerSecrets(signer);
  const runtime = deps(config, signer);
  const server = startServer(
    config.port,
    async (req, res) => {
    const url = new URL(req.url ?? "/", "http://localhost");
    if (req.method === "GET" && url.pathname === "/health") {
      sendJson(res, 200, { ok: true, service: "executor", ...publicConfig(config) });
      return;
    }
    if (req.method === "POST" && url.pathname === "/execute") {
      const intent = (await readJson(req)) as SwapIntent;
      const report = await execute(intent, runtime);
      console.log(JSON.stringify({ report: { ...report, latency: latencyLog(report.latency) } }));
      await notify(config, report).catch((error: unknown) => {
        console.log(JSON.stringify({ notifier: redactError(error, secrets) }));
      });
      sendJson(res, 200, report);
      return;
    }
    if (req.method === "POST" && url.pathname === "/listing") {
      const alert = (await readJson(req)) as Alert;
      if (!config.resolverUrl) {
        sendJson(res, 503, { error: "RESOLVER_URL is not set" });
        return;
      }
      const response = await fetch(`${config.resolverUrl.replace(/\/$/, "")}/alert`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(alert),
      });
      const resolution = (await response.json()) as { kind: string; token?: SwapIntent["token"] & { hyperliquid?: SwapIntent["hyperliquid"] } };
      const holdings = JSON.parse(process.env.WALLET_HOLDINGS_JSON ?? "[]") as SwapIntent["holdings"];
      const intent = intentFromResolution(alert, resolution, holdings, config.maxUsdPerTrade, config.maxSlippageBps);
      if (!intent) {
        sendJson(res, 200, { decision: "skipped", reason: resolution.kind, latency: { alertReceivedMs: 0 } });
        return;
      }
      const report = await execute(intent, runtime);
      console.log(JSON.stringify({ report: { ...report, latency: latencyLog(report.latency) } }));
      await notify(config, report).catch((error: unknown) => {
        console.log(JSON.stringify({ notifier: redactError(error, secrets) }));
      });
      sendJson(res, 200, report);
      return;
    }
    if (req.method === "POST" && url.pathname === "/withdraw") {
      const body = (await readJson(req)) as { to?: string; chainKey?: string; amount?: number };
      if (!body.to) {
        sendJson(res, 400, { error: "to is required" });
        return;
      }
      const allowed = authorizeWithdraw(body.to, config.withdrawAllowlist);
      if (!allowed.ok) {
        sendJson(res, 403, { error: allowed.reason });
        return;
      }
      if (config.killSwitch || !config.live) {
        sendJson(res, 200, { decision: "would_send", to: body.to, mode: config.live ? "live" : "dry_run" });
        return;
      }
      if (!signer || !body.chainKey || !(body.amount && body.amount > 0)) {
        sendJson(res, 409, { error: "live withdraw needs a signer, chainKey, and amount" });
        return;
      }
      await withdrawNative({ config, material: signer, chainKey: body.chainKey, to: body.to, amount: body.amount });
      sendJson(res, 200, { decision: "sent", to: body.to, chainKey: body.chainKey });
      return;
    }
    sendJson(res, 404, { error: "not found" });
    },
    secrets,
  );
  console.log(JSON.stringify({ service: "executor", port: config.port, ...publicConfig(config) }));
  server.on("error", (error) => {
    console.error(JSON.stringify({ error: redactError(error, secrets) }));
  });
}

const entry = process.argv[1] ?? "";
if (entry.endsWith("executor-server.js")) {
  main().catch((error: unknown) => {
    console.error(JSON.stringify({ error: redactError(error) }));
    process.exit(1);
  });
}
