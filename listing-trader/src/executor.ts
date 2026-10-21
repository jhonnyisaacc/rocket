import type { ChainRef, ExecutionReport, Latency, RouteLeg, RouteQuote, SwapIntent } from "./domain.js";
import { chainByKey } from "./chains.js";
import { checkLimits, type LimitConfig } from "./limits.js";
import { stamp } from "./latency.js";
import { combineHopImpact, pickRoute, planRoutes } from "./routing.js";
import { buildLeverage, buildOrder, orderSize, type HyperliquidAction } from "./hyperliquid.js";

export type HopQuote = {
  priceImpactPct: number | null;
  feeUsd: number;
  buyAmount: string;
  raw?: unknown;
  prepared?: { to: string | null; data: string | null; value: string };
};

export type SendRequest = {
  kind: "evm" | "solana" | "hypercore";
  description: string;
  chain: ChainRef;
  legs: RouteLeg[];
  hyperliquidActions: HyperliquidAction[];
};

export class BroadcastError extends Error {
  constructor(
    message: string,
    readonly broadcast: boolean,
  ) {
    super(message);
  }
}

export type ExecutorDeps = {
  config: LimitConfig;
  mode: "dry_run" | "live";
  spentTodayUsd: number;
  quoteHop: (
    hop: { sellAddress: string; buyAddress: string; sellAmount: string; chain: ChainRef },
    context: { spentUsd: number; priceUsd: number | null; decimals: number | null },
  ) => Promise<HopQuote>;
  markPrice: (coin: string) => Promise<number | null>;
  send: (action: SendRequest) => Promise<void>;
  recordSpend?: (idempotencyKey: string, usd: number) => Promise<"inserted" | "exists">;
  releaseSpend?: (idempotencyKey: string) => Promise<void>;
  now?: () => number;
};

const reports = new Map<string, ExecutionReport>();
let spentUsd = 0;

export function resetExecutorState(): void {
  reports.clear();
  spentUsd = 0;
}

export function spentToday(): number {
  return spentUsd;
}

export function restoreSpent(usd: number): void {
  spentUsd = usd;
}

function skipped(intent: SwapIntent, latency: Latency, reason: string, venue: string, mode: "dry_run" | "live"): ExecutionReport {
  return {
    idempotencyKey: intent.idempotencyKey,
    mode,
    decision: "skipped",
    reason,
    venue,
    route: null,
    latency,
  };
}

function legOf(
  hop: { sellAddress: string; buyAddress: string; sellAmount: string },
  context: { spentUsd: number; priceUsd: number | null; decimals: number | null },
): RouteLeg {
  return {
    sellAddress: hop.sellAddress,
    buyAddress: hop.buyAddress,
    sellAmount: hop.sellAmount,
    spentUsd: context.spentUsd,
    priceUsd: context.priceUsd,
    decimals: context.decimals,
  };
}

async function quotePlan(intent: SwapIntent, deps: ExecutorDeps): Promise<{ quotes: RouteQuote[]; unsized: boolean }> {
  const spec = chainByKey(intent.token.chainKey);
  const reserve = spec?.minNativeReserve ?? 0;
  const plans = planRoutes({
    tokenSymbol: intent.token.symbol,
    tokenAddress: intent.token.address,
    pairMap: intent.token.pairMap,
    holdings: intent.holdings,
    minNativeReserve: reserve,
    notionalUsd: intent.notionalUsd,
  });
  const context = {
    spentUsd: intent.notionalUsd,
    priceUsd: intent.token.pairMap.top?.priceUsd ?? null,
    decimals: intent.token.decimals,
  };
  const quotes: RouteQuote[] = [];
  for (const plan of plans) {
    if (plan.kind === "aggregator") {
      const hop = await deps.quoteHop({ ...plan.hop, chain: intent.token.chain }, context);
      if (hop.priceImpactPct === null) continue;
      quotes.push({
        planId: plan.id,
        kind: "aggregator",
        hops: [`${plan.hop.sellSymbol}->${plan.hop.buySymbol}`],
        priceImpactPct: hop.priceImpactPct,
        feeUsd: hop.feeUsd,
        buyAmount: hop.buyAmount,
        legs: [legOf(plan.hop, context)],
      });
      continue;
    }
    const firstContext =
      plan.quotePriceUsd !== null && plan.quoteDecimals !== null
        ? { spentUsd: intent.notionalUsd, priceUsd: plan.quotePriceUsd, decimals: plan.quoteDecimals }
        : { spentUsd: intent.notionalUsd, priceUsd: null, decimals: null };
    const first = await deps.quoteHop({ ...plan.first, chain: intent.token.chain }, firstContext);
    if (first.priceImpactPct === null || !/^[1-9][0-9]*$/.test(first.buyAmount)) continue;
    let secondSpent = intent.notionalUsd;
    if (plan.quotePriceUsd !== null && plan.quoteDecimals !== null) {
      const received = Number(first.buyAmount) / 10 ** plan.quoteDecimals;
      if (Number.isFinite(received) && received > 0) secondSpent = received * plan.quotePriceUsd;
    }
    const second = await deps.quoteHop(
      { ...plan.second, sellAmount: first.buyAmount, chain: intent.token.chain },
      { spentUsd: secondSpent, priceUsd: context.priceUsd, decimals: context.decimals },
    );
    if (second.priceImpactPct === null) continue;
    quotes.push({
      planId: plan.id,
      kind: "two_hop",
      hops: [`${plan.first.sellSymbol}->${plan.first.buySymbol}`, `${plan.second.sellSymbol}->${plan.second.buySymbol}`],
      priceImpactPct: combineHopImpact(first.priceImpactPct, second.priceImpactPct),
      feeUsd: first.feeUsd + second.feeUsd,
      buyAmount: second.buyAmount,
      legs: [
        legOf(plan.first, firstContext),
        legOf({ ...plan.second, sellAmount: first.buyAmount }, { spentUsd: secondSpent, priceUsd: context.priceUsd, decimals: context.decimals }),
      ],
    });
  }
  const unsized =
    plans.length > 0 &&
    plans.every((plan) => (plan.kind === "aggregator" ? plan.hop.sellAmount === "0" : plan.first.sellAmount === "0"));
  return { quotes, unsized };
}

async function commitLive(
  intent: SwapIntent,
  deps: ExecutorDeps,
  latency: Latency,
  venueKey: string,
  route: RouteQuote | null,
  request: SendRequest,
  reason: string,
  now: () => number,
): Promise<ExecutionReport> {
  reports.set(intent.idempotencyKey, skipped(intent, latency, "send in progress", venueKey, deps.mode));
  if (deps.recordSpend) {
    try {
      const status = await deps.recordSpend(intent.idempotencyKey, intent.notionalUsd);
      if (status === "exists") {
        const report = skipped(intent, latency, "duplicate spend", venueKey, deps.mode);
        reports.set(intent.idempotencyKey, report);
        return report;
      }
    } catch (error) {
      reports.delete(intent.idempotencyKey);
      const message = error instanceof Error ? error.message : "spend journal failed";
      return skipped(intent, latency, message, venueKey, deps.mode);
    }
  }
  try {
    latency = stamp(latency, "signedMs", now());
    await deps.send(request);
  } catch (error) {
    const broadcast = error instanceof BroadcastError && error.broadcast;
    const message = error instanceof Error ? error.message : "send failed";
    if (!broadcast) {
      await deps.releaseSpend?.(intent.idempotencyKey)?.catch(() => undefined);
      reports.delete(intent.idempotencyKey);
      return skipped(intent, latency, message, venueKey, deps.mode);
    }
    spentUsd += intent.notionalUsd;
    latency = stamp(latency, "sentMs", now());
    const report = skipped(intent, latency, message, venueKey, deps.mode);
    reports.set(intent.idempotencyKey, report);
    return report;
  }
  spentUsd += intent.notionalUsd;
  latency = stamp(latency, "sentMs", now());
  latency = stamp(latency, "confirmedMs", now());
  const report: ExecutionReport = {
    idempotencyKey: intent.idempotencyKey,
    mode: "live",
    decision: "sent",
    reason,
    venue: venueKey,
    route,
    latency,
  };
  reports.set(intent.idempotencyKey, report);
  return report;
}

export async function execute(intent: SwapIntent, deps: ExecutorDeps): Promise<ExecutionReport> {
  const existing = reports.get(intent.idempotencyKey);
  if (existing) return existing;
  const now = deps.now ?? Date.now;
  let latency: Latency = { alertReceivedMs: intent.receivedAtMs };
  latency = stamp(latency, "resolvedMs", now());
  const spec = chainByKey(intent.token.chainKey);
  const liquidity = intent.token.pairMap.top?.liquidityUsd ?? null;
  const useHyper = intent.hyperliquid !== null && (liquidity === null || liquidity < deps.config.minLiquidityUsd);
  const venueChain = useHyper ? { kind: "hypercore" as const, market: intent.hyperliquid?.market ?? "perp" } : intent.token.chain;
  const venueKey = useHyper ? "hypercore" : intent.token.chainKey;
  const limits = checkLimits(deps.config, {
    notionalUsd: intent.notionalUsd,
    slippageBps: intent.slippageBps,
    leverage: 1,
    spentTodayUsd: deps.spentTodayUsd + spentUsd,
    chain: venueChain,
    chainKey: venueKey,
    liquidityUsd: useHyper ? null : liquidity,
  });
  if (!limits.ok) {
    const report = skipped(intent, latency, limits.reason, venueKey, deps.mode);
    reports.set(intent.idempotencyKey, report);
    return report;
  }
  if (spec?.liveSend === "disabled" && deps.mode === "live" && !useHyper) {
    const report = skipped(intent, latency, spec.gap ?? "live send disabled for this chain", venueKey, deps.mode);
    reports.set(intent.idempotencyKey, report);
    return report;
  }

  if (useHyper && intent.hyperliquid) {
    const mark = await deps.markPrice(intent.hyperliquid.coin);
    latency = stamp(latency, "quotedMs", now());
    if (mark === null) {
      const report = skipped(intent, latency, "hyperliquid mark price unverifiable", "hypercore", deps.mode);
      reports.set(intent.idempotencyKey, report);
      return report;
    }
    const leverage = buildLeverage(intent.hyperliquid.assetIndex, 1);
    const order = buildOrder({
      asset: intent.hyperliquid.assetIndex,
      isBuy: intent.side === "buy",
      limitPx: mark,
      size: orderSize(intent.notionalUsd, mark),
    });
    const actions: HyperliquidAction[] = [leverage, order];
    if (deps.mode === "dry_run") {
      const report: ExecutionReport = {
        idempotencyKey: intent.idempotencyKey,
        mode: "dry_run",
        decision: "would_send",
        reason: `hypercore ${intent.hyperliquid.coin} leverage 1 actions ${actions.map((item) => item.type).join(",")}`,
        venue: "hypercore",
        route: null,
        latency,
      };
      reports.set(intent.idempotencyKey, report);
      return report;
    }
    return commitLive(
      intent,
      deps,
      latency,
      "hypercore",
      null,
      {
        kind: "hypercore",
        description: intent.hyperliquid.coin,
        chain: venueChain,
        legs: [],
        hyperliquidActions: actions,
      },
      `hypercore ${intent.hyperliquid.coin}`,
      now,
    );
  }

  const planned = await quotePlan(intent, deps);
  latency = stamp(latency, "quotedMs", now());
  if (planned.quotes.length === 0) {
    const reason = planned.unsized ? "holding decimals missing" : "no route inside the slippage cap";
    const report = skipped(intent, latency, reason, venueKey, deps.mode);
    reports.set(intent.idempotencyKey, report);
    return report;
  }
  const picked = pickRoute(planned.quotes, intent.slippageBps);
  if ("kind" in picked && picked.kind === "none") {
    const report = skipped(intent, latency, picked.reason, venueKey, deps.mode);
    reports.set(intent.idempotencyKey, report);
    return report;
  }
  const route = picked as RouteQuote;
  if (deps.mode === "dry_run") {
    const report: ExecutionReport = {
      idempotencyKey: intent.idempotencyKey,
      mode: "dry_run",
      decision: "would_send",
      reason: `${route.kind} ${route.hops.join(" then ")} impact ${route.priceImpactPct}`,
      venue: venueKey,
      route,
      latency,
    };
    reports.set(intent.idempotencyKey, report);
    return report;
  }
  return commitLive(
    intent,
    deps,
    latency,
    venueKey,
    route,
    {
      kind: intent.token.chain.kind === "solana" ? "solana" : "evm",
      description: route.planId,
      chain: intent.token.chain,
      legs: route.legs ?? [],
      hyperliquidActions: [],
    },
    route.planId,
    now,
  );
}

export function authorizeWithdraw(to: string, allowlist: readonly string[]): { ok: true } | { ok: false; reason: string } {
  const target = to.toLowerCase();
  const allowed = allowlist.some((item) => item.toLowerCase() === target);
  if (!allowed) return { ok: false, reason: "destination is not allowlisted" };
  return { ok: true };
}
