import type { ChainRef, ExecutionReport, Latency, RouteLeg, RouteQuote, SwapIntent } from "./domain.js";
import { chainByKey, feeRankOf } from "./chains.js";
import { checkLimits, type LimitConfig } from "./limits.js";
import { stamp } from "./latency.js";
import { combineHopImpact, pickRoute, planRoutes } from "./routing.js";
import { buildLeverage, buildOrder, cappedLimitPx, orderSize, type HyperliquidAction } from "./hyperliquid.js";

export type HopQuote = {
  priceImpactPct: number | null;
  feeUsd: number;
  buyAmount: string;
  raw?: unknown;
  prepared?: { to: string | null; data: string | null; value: string };
  provider?: string;
  gasUsd?: number;
  netOutputUsd?: number;
  signable?: boolean;
  note?: string;
};

export type SendRequest = {
  kind: "evm" | "solana" | "hypercore";
  description: string;
  chain: ChainRef;
  legs: RouteLeg[];
  hyperliquidActions: HyperliquidAction[];
  provider?: string;
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
  recordSpend?: (idempotencyKey: string, usd: number) => Promise<"inserted" | "exists" | "reserved" | "cap">;
  commitSpend?: (idempotencyKey: string) => Promise<void>;
  releaseSpend?: (idempotencyKey: string) => Promise<void>;
  now?: () => number;
  killSwitchEnabled?: () => Promise<boolean>;
  screenToken?: (token: { chainKey: string; chain: ChainRef; contract: string }) => Promise<"allow" | "deny">;
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

function decorate(quote: RouteQuote, token: SwapIntent["token"]): RouteQuote {
  return { ...quote, chainKey: token.chainKey, feeRank: feeRankOf(token.chainKey), chain: token.chain };
}

async function quotePlan(intent: SwapIntent, token: SwapIntent["token"], deps: ExecutorDeps): Promise<{ quotes: RouteQuote[]; unsized: boolean }> {
  const spec = chainByKey(token.chainKey);
  const reserve = spec?.minNativeReserve ?? 0;
  const plans = planRoutes({
    tokenSymbol: token.symbol,
    tokenAddress: token.address,
    pairMap: token.pairMap,
    holdings: intent.holdings,
    minNativeReserve: reserve,
    notionalUsd: intent.notionalUsd,
    chainKey: token.chainKey,
  });
  const context = {
    spentUsd: intent.notionalUsd,
    priceUsd: intent.token.pairMap.top?.priceUsd ?? null,
    decimals: token.decimals,
  };
  const quotes: RouteQuote[] = [];
  for (const plan of plans) {
    if (plan.kind === "aggregator") {
      const hop = await deps.quoteHop({ ...plan.hop, chain: token.chain }, context);
      if (hop.priceImpactPct === null) continue;
      quotes.push(decorate({
        planId: plan.id,
        kind: "aggregator",
        hops: [`${plan.hop.sellSymbol}->${plan.hop.buySymbol}`],
        priceImpactPct: hop.priceImpactPct,
        feeUsd: hop.feeUsd,
        buyAmount: hop.buyAmount,
        legs: [legOf(plan.hop, context)],
        provider: hop.provider,
        netOutputUsd: hop.netOutputUsd,
        gasUsd: hop.gasUsd,
        signable: hop.signable,
        note: hop.note,
      }, token));
      continue;
    }
    const firstContext =
      plan.quotePriceUsd !== null && plan.quoteDecimals !== null
        ? { spentUsd: intent.notionalUsd, priceUsd: plan.quotePriceUsd, decimals: plan.quoteDecimals }
        : { spentUsd: intent.notionalUsd, priceUsd: null, decimals: null };
    const first = await deps.quoteHop({ ...plan.first, chain: token.chain }, firstContext);
    if (first.priceImpactPct === null || !/^[1-9][0-9]*$/.test(first.buyAmount)) continue;
    let secondSpent = intent.notionalUsd;
    if (plan.quotePriceUsd !== null && plan.quoteDecimals !== null) {
      const received = Number(first.buyAmount) / 10 ** plan.quoteDecimals;
      if (Number.isFinite(received) && received > 0) secondSpent = received * plan.quotePriceUsd;
    }
    const second = await deps.quoteHop(
      { ...plan.second, sellAmount: first.buyAmount, chain: token.chain },
      { spentUsd: secondSpent, priceUsd: context.priceUsd, decimals: context.decimals },
    );
    if (second.priceImpactPct === null) continue;
    const gasUsd = (first.gasUsd ?? 0) + (second.gasUsd ?? 0);
    const netOutputUsd = second.netOutputUsd === undefined ? undefined : second.netOutputUsd - first.feeUsd - (first.gasUsd ?? 0);
    quotes.push(decorate({
      planId: plan.id,
      kind: "two_hop",
      hops: [`${plan.first.sellSymbol}->${plan.first.buySymbol}`, `${plan.second.sellSymbol}->${plan.second.buySymbol}`],
      priceImpactPct: combineHopImpact(first.priceImpactPct, second.priceImpactPct),
      feeUsd: first.feeUsd + second.feeUsd,
      buyAmount: second.buyAmount,
      gasUsd,
      netOutputUsd,
      provider: second.provider ?? first.provider,
      signable: first.signable !== false && second.signable !== false,
      note: second.note ?? first.note,
      legs: [
        legOf(plan.first, firstContext),
        legOf({ ...plan.second, sellAmount: first.buyAmount }, { spentUsd: secondSpent, priceUsd: context.priceUsd, decimals: context.decimals }),
      ],
    }, token));
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
      if (status === "cap") {
        reports.delete(intent.idempotencyKey);
        return skipped(intent, latency, `daily cap ${deps.config.dailyUsdCap} USD`, venueKey, deps.mode);
      }
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
  await deps.commitSpend?.(intent.idempotencyKey)?.catch(() => undefined);
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

async function keepScreened(
  intent: SwapIntent,
  deps: ExecutorDeps,
): Promise<{ ok: false } | { ok: true; alternates: NonNullable<SwapIntent["alternates"]> }> {
  const alternates = intent.alternates ?? [];
  if (deps.mode !== "live" || !deps.screenToken) return { ok: true, alternates };
  const screen = deps.screenToken;
  const primary = await screen({ chainKey: intent.token.chainKey, chain: intent.token.chain, contract: intent.token.address });
  if (primary !== "allow") return { ok: false };
  const kept = [];
  for (const token of alternates) {
    const verdict = await screen({ chainKey: token.chainKey, chain: token.chain, contract: token.address });
    if (verdict === "allow") kept.push(token);
  }
  return { ok: true, alternates: kept };
}

export async function execute(intent: SwapIntent, deps: ExecutorDeps): Promise<ExecutionReport> {
  const existing = reports.get(intent.idempotencyKey);
  if (existing) return existing;
  const now = deps.now ?? Date.now;
  let stopped = false;
  try {
    stopped = (await deps.killSwitchEnabled?.()) === true;
  } catch {
    stopped = true;
  }
  if (stopped) {
    const report = skipped(intent, { alertReceivedMs: intent.receivedAtMs }, "kill switch is on", intent.token.chainKey, deps.mode);
    reports.set(intent.idempotencyKey, report);
    return report;
  }
  const screened = await keepScreened(intent, deps);
  if (!screened.ok) {
    const report = skipped(intent, { alertReceivedMs: intent.receivedAtMs }, "token screening rejected the contract", intent.token.chainKey, deps.mode);
    reports.set(intent.idempotencyKey, report);
    return report;
  }
  const alternates = screened.alternates;
  let latency: Latency = { alertReceivedMs: intent.receivedAtMs };
  latency = stamp(latency, "resolvedMs", now());
  const spec = chainByKey(intent.token.chainKey);
  const liquidity = intent.token.pairMap.top?.liquidityUsd ?? null;
  const liquidAlternate = alternates.some((token) => (token.pairMap.top?.liquidityUsd ?? 0) >= deps.config.minLiquidityUsd);
  const useHyper = intent.hyperliquid !== null && (liquidity === null || liquidity < deps.config.minLiquidityUsd) && !liquidAlternate;
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
  if (!limits.ok && !(limits.reason.startsWith("chain ") && alternates.length > 0)) {
    const report = skipped(intent, latency, limits.reason, venueKey, deps.mode);
    reports.set(intent.idempotencyKey, report);
    return report;
  }
  if (spec?.liveSend === "disabled" && deps.mode === "live" && !useHyper) {
    const other = alternates.some((token) => chainByKey(token.chainKey)?.liveSend !== "disabled");
    if (!other) {
      const report = skipped(intent, latency, spec.gap ?? "live send disabled for this chain", venueKey, deps.mode);
      reports.set(intent.idempotencyKey, report);
      return report;
    }
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
    const limitPx = cappedLimitPx(mark, intent.side === "buy", intent.slippageBps);
    const order = buildOrder({
      asset: intent.hyperliquid.assetIndex,
      isBuy: intent.side === "buy",
      limitPx,
      size: orderSize(intent.notionalUsd, mark),
    });
    const actions: HyperliquidAction[] = [leverage, order];
    if (deps.mode === "dry_run") {
      const report: ExecutionReport = {
        idempotencyKey: intent.idempotencyKey,
        mode: "dry_run",
        decision: "would_send",
        reason: `hypercore ${intent.hyperliquid.coin} leverage 1 isolated limit ${order.orders[0].p} actions ${actions.map((item) => item.type).join(",")}`,
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

  const candidates = [intent.token, ...alternates].filter((token) => deps.config.enabledChainKeys.has(token.chainKey));
  const plannedQuotes: RouteQuote[] = [];
  let unsized = false;
  for (const token of candidates) {
    const liquidity = token.pairMap.top?.liquidityUsd ?? null;
    const allowed = checkLimits(deps.config, {
      notionalUsd: intent.notionalUsd,
      slippageBps: intent.slippageBps,
      leverage: 1,
      spentTodayUsd: deps.spentTodayUsd + spentUsd,
      chain: token.chain,
      chainKey: token.chainKey,
      liquidityUsd: liquidity,
    });
    if (!allowed.ok) continue;
    if (deps.mode === "live" && chainByKey(token.chainKey)?.liveSend === "disabled") continue;
    const planned = await quotePlan(intent, token, deps);
    plannedQuotes.push(...planned.quotes);
    unsized = unsized || planned.unsized;
  }
  latency = stamp(latency, "quotedMs", now());
  const planned = { quotes: plannedQuotes, unsized };
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
  const routeChain = route.chain ?? intent.token.chain;
  const routeVenue = route.chainKey ?? venueKey;
  const note = route.note ? ` ${route.note}` : "";
  if (deps.mode === "dry_run") {
    const report: ExecutionReport = {
      idempotencyKey: intent.idempotencyKey,
      mode: "dry_run",
      decision: "would_send",
      reason: `${route.kind} ${route.hops.join(" then ")} impact ${route.priceImpactPct}${note}`,
      venue: routeVenue,
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
    routeVenue,
    route,
    {
      kind: routeChain.kind === "solana" ? "solana" : "evm",
      description: route.planId,
      chain: routeChain,
      legs: route.legs ?? [],
      hyperliquidActions: [],
      provider: route.provider,
    },
    route.planId,
    now,
  );
}

export function decideWithdraw(input: {
  adminOk: boolean;
  enabled: boolean;
  amount: number | undefined;
  cap: number;
  destinationAllowed: boolean;
  mint: string | undefined;
  recoveryAllowlist: readonly string[];
  live: boolean;
  killSwitch: boolean;
  signerReady: boolean;
  chainKey: string | undefined;
  decimals: number | undefined;
}): { http: number; error?: string; decision?: "would_send" | "send" } {
  if (!input.adminOk) return { http: 401, error: "unauthorized" };
  if (!input.enabled) return { http: 403, error: "withdraw is disabled" };
  if (input.amount !== undefined && !(input.amount > 0 && input.amount <= input.cap)) return { http: 403, error: "withdraw exceeds the per-call cap" };
  if (!input.destinationAllowed) return { http: 403, error: "destination is not allowlisted" };
  if (input.mint) {
    const allowed = input.recoveryAllowlist.some((item) => item.toLowerCase() === input.mint?.toLowerCase());
    if (!allowed) return { http: 403, error: "token is not in the recovery allowlist" };
    if (input.decimals === undefined) return { http: 409, error: "token withdraw needs decimals" };
  }
  if (!input.live || input.killSwitch) return { http: 200, decision: "would_send" };
  if (!input.signerReady || !input.chainKey || !(input.amount && input.amount > 0)) {
    return { http: 409, error: "live withdraw needs a signer, chainKey, and amount" };
  }
  return { http: 200, decision: "send" };
}

export function authorizeWithdraw(to: string, allowlist: readonly string[]): { ok: true } | { ok: false; reason: string } {
  const target = to.toLowerCase();
  const allowed = allowlist.some((item) => item.toLowerCase() === target);
  if (!allowed) return { ok: false, reason: "destination is not allowlisted" };
  return { ok: true };
}
