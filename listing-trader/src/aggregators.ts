import { createHmac } from "node:crypto";
import { z } from "zod";
import type { AppConfig } from "./config.js";
import type { ChainRef } from "./domain.js";
import { chainByEvmId, gasCeilingUsd } from "./chains.js";
import { validSellAmount, type QuoteHop } from "./quote-hop.js";
import type { HopQuote } from "./executor.js";
import { ProviderGuard, classifyHttp } from "./provider-guard.js";
import { impactPctFromUsd, readJupiter, readLifi, readZeroEx } from "./quotes.js";

const ZEROEX = new Set([1, 10, 56, 137, 143, 8453, 42161, 59144, 534352, 4663, 999]);
const ONEINCH = new Set([1, 10, 56, 137, 324, 8453, 42161, 59144, 999, 4663]);
const VELORA = new Set([1, 10, 56, 137, 8453, 42161]);
const OKX_EVM = new Set([1, 10, 56, 137, 324, 8453, 42161, 59144, 81457, 534352, 4663, 999]);
const KYBER_SLUG: Record<number, string> = {
  1: "ethereum",
  56: "bsc",
  42161: "arbitrum",
  137: "polygon",
  10: "optimism",
  8453: "base",
  59144: "linea",
  999: "hyperevm",
  4663: "robinhood",
  143: "monad",
};

export const PROVIDER_REGISTRY = {
  odos: { calls: false, reason: "Odos shut down trading and API services." },
  jumper: { calls: false, reason: "Jumper is the LI.FI interface. Bridge quotes call LI.FI once." },
} as const;

export type QuoteProviderId = "jupiter" | "zeroex" | "oneinch" | "kyberswap" | "velora" | "okx" | "lifi";

type Reference = { spentUsd: number; priceUsd: number; decimals: number };

const guards = new Map<string, ProviderGuard>();

export function resetProviderGuards(): void {
  guards.clear();
}

export function guardFor(config: AppConfig): ProviderGuard {
  const existing = guards.get("app");
  if (existing) return existing;
  const created = new ProviderGuard({
    budget: config.providerBudgetPerMinute,
    windowMs: 60_000,
    failureThreshold: config.providerFailureThreshold,
    openMs: config.providerOpenMs,
    now: () => config.now?.() ?? Date.now(),
  });
  guards.set("app", created);
  return created;
}

export function providersFor(chain: ChainRef, config: AppConfig): QuoteProviderId[] {
  if (chain.kind === "solana") {
    const out: QuoteProviderId[] = ["jupiter"];
    if (config.keys.okxKey && config.keys.okxSecret && config.keys.okxPassphrase) out.push("okx");
    return out;
  }
  if (chain.kind !== "evm") return [];
  const id = chain.chainId;
  const out: QuoteProviderId[] = [];
  if (ZEROEX.has(id)) out.push("zeroex");
  if (ONEINCH.has(id) && config.keys.oneInch) out.push("oneinch");
  if (KYBER_SLUG[id]) out.push("kyberswap");
  if (VELORA.has(id)) out.push("velora");
  if (OKX_EVM.has(id) && config.keys.okxKey && config.keys.okxSecret && config.keys.okxPassphrase) out.push("okx");
  out.push("lifi");
  return out;
}

const oneInchSchema = z.object({ dstAmount: z.string() }).passthrough();
const kyberSchema = z
  .object({
    data: z.object({
      routeSummary: z.object({ amountOut: z.string(), gasUsd: z.string().optional(), routerAddress: z.string() }).passthrough(),
    }),
  })
  .passthrough();
const kyberBuildSchema = z
  .object({ data: z.object({ data: z.string(), routerAddress: z.string(), transactionValue: z.string().optional() }) })
  .passthrough();
const veloraSchema = z.object({ priceRoute: z.object({ destAmount: z.string(), gasCostUSD: z.string().optional() }).passthrough() }).passthrough();
const okxSchema = z
  .object({
    code: z.string(),
    data: z.array(z.object({ toTokenAmount: z.string(), tradeFee: z.string().optional() }).passthrough()),
  })
  .passthrough();

export const lifiBridgeSchema = z
  .object({
    estimate: z.object({ toAmount: z.string(), feeCosts: z.array(z.object({ amountUSD: z.string().optional() })).optional() }).optional(),
    action: z.object({ toAddress: z.string().optional() }).optional(),
  })
  .passthrough();
export const relayBridgeSchema = z
  .object({
    details: z.object({ recipient: z.string(), currencyOut: z.object({ amountUsd: z.string().optional() }).optional() }),
    fees: z.record(z.object({ amountUsd: z.string().optional() }).passthrough()),
  })
  .passthrough();
export const debridgeSchema = z
  .object({
    estimation: z.object({
      srcChainTokenIn: z.object({ approximateUsdValue: z.number().optional() }).optional(),
      dstChainTokenOut: z.object({ amount: z.string(), approximateUsdValue: z.number().optional() }),
    }),
  })
  .passthrough();
export const acrossSchema = z
  .object({ expectedOutputAmount: z.string(), fees: z.object({ total: z.object({ amountUsd: z.string() }) }) })
  .passthrough();

function empty(): HopQuote {
  return { priceImpactPct: null, feeUsd: 0, buyAmount: "0", signable: false };
}

function withNet(quote: HopQuote, reference: Reference | null, chainKey: string, gasUsd: number | null): HopQuote {
  if (quote.priceImpactPct === null || !reference || !/^\d+$/.test(quote.buyAmount)) return quote;
  const human = Number(quote.buyAmount) / 10 ** reference.decimals;
  if (!Number.isFinite(human)) return quote;
  const gas = gasUsd ?? gasCeilingUsd(chainKey);
  return { ...quote, gasUsd: gas, netOutputUsd: human * reference.priceUsd - quote.feeUsd - gas };
}

function chainKeyOf(chain: ChainRef): string {
  if (chain.kind === "solana") return "solana";
  if (chain.kind === "evm") return chainByEvmId(chain.chainId)?.key ?? String(chain.chainId);
  return "hypercore";
}

async function callProvider(config: AppConfig, id: string, url: string, init: RequestInit, fetchImpl: typeof fetch, signal: AbortSignal): Promise<unknown | null> {
  const guard = guardFor(config);
  if (guard.before(id) !== "allow") return null;
  try {
    const response = await fetchImpl(url, { ...init, signal });
    const text = await response.text();
    const kind = classifyHttp(response.status, text);
    if (kind === "compliance") {
      guard.compliance(id);
      return null;
    }
    if (kind !== "ok") {
      guard.failure(id);
      return null;
    }
    guard.success(id);
    return JSON.parse(text) as unknown;
  } catch {
    guard.failure(id);
    return null;
  }
}

async function quoteOne(config: AppConfig, id: QuoteProviderId, hop: QuoteHop, reference: Reference | null, fetchImpl: typeof fetch, signal: AbortSignal): Promise<HopQuote> {
  const key = chainKeyOf(hop.chain);
  if (id === "jupiter") {
    const url = new URL(`${config.jupiterBase}/quote`);
    url.searchParams.set("inputMint", hop.sellAddress);
    url.searchParams.set("outputMint", hop.buyAddress);
    url.searchParams.set("amount", hop.sellAmount);
    url.searchParams.set("slippageBps", String(config.maxSlippageBps));
    const headers: Record<string, string> = {};
    if (config.keys.jupiter) headers["x-api-key"] = config.keys.jupiter;
    const body = await callProvider(config, id, url.toString(), { headers }, fetchImpl, signal);
    if (!body) return empty();
    const parsed = readJupiter(body as Parameters<typeof readJupiter>[0], config.jupiterImpactUnit);
    return withNet({ priceImpactPct: parsed.priceImpactPct, feeUsd: 0, buyAmount: parsed.buyAmount, raw: body, provider: id, signable: true }, reference, key, null);
  }
  if (hop.chain.kind !== "evm") {
    if (id !== "okx") return empty();
    return quoteOkx(config, "501", hop, reference, fetchImpl, signal, key);
  }
  const chainId = hop.chain.chainId;
  if (id === "zeroex") return quoteZeroExPrice(config, hop, chainId, reference, fetchImpl, signal, key);
  if (id === "lifi") return quoteLifiSame(config, hop, chainId, reference, fetchImpl, signal, key);
  if (id === "oneinch") return quoteOneInch(config, hop, chainId, reference, fetchImpl, signal, key);
  if (id === "kyberswap") return quoteKyber(config, hop, chainId, reference, fetchImpl, signal, key);
  if (id === "velora") return quoteVelora(config, hop, chainId, reference, fetchImpl, signal, key);
  return quoteOkx(config, String(chainId), hop, reference, fetchImpl, signal, key);
}

async function quoteZeroExPrice(config: AppConfig, hop: QuoteHop, chainId: number, reference: Reference | null, fetchImpl: typeof fetch, signal: AbortSignal, key: string): Promise<HopQuote> {
  const url = new URL(`${config.zeroExBase}/swap/allowance-holder/price`);
  url.searchParams.set("chainId", String(chainId));
  url.searchParams.set("sellToken", hop.sellAddress);
  url.searchParams.set("buyToken", hop.buyAddress);
  url.searchParams.set("sellAmount", hop.sellAmount);
  const headers: Record<string, string> = { "0x-version": "v2" };
  if (config.keys.zeroEx) headers["0x-api-key"] = config.keys.zeroEx;
  const body = await callProvider(config, "zeroex", url.toString(), { headers }, fetchImpl, signal);
  if (!body) return empty();
  const parsed = readZeroEx(body as Parameters<typeof readZeroEx>[0], reference);
  return withNet({ priceImpactPct: parsed.priceImpactPct, feeUsd: 0, buyAmount: parsed.buyAmount, raw: body, prepared: parsed, provider: "zeroex", signable: true }, reference, key, null);
}

async function quoteLifiSame(config: AppConfig, hop: QuoteHop, chainId: number, reference: Reference | null, fetchImpl: typeof fetch, signal: AbortSignal, key: string): Promise<HopQuote> {
  const url = new URL(`${config.lifiBase}/quote`);
  url.searchParams.set("fromChain", String(chainId));
  url.searchParams.set("toChain", String(chainId));
  url.searchParams.set("fromToken", hop.sellAddress);
  url.searchParams.set("toToken", hop.buyAddress);
  url.searchParams.set("fromAmount", hop.sellAmount);
  if (config.keys.lifiIntegrator) url.searchParams.set("integrator", config.keys.lifiIntegrator);
  const headers: Record<string, string> = {};
  if (config.keys.lifi) headers["x-lifi-api-key"] = config.keys.lifi;
  const body = await callProvider(config, "lifi", url.toString(), { headers }, fetchImpl, signal);
  if (!body) return empty();
  const parsed = readLifi(body as Parameters<typeof readLifi>[0], reference, chainId);
  if (!parsed.sameChain) return empty();
  return withNet({ priceImpactPct: parsed.priceImpactPct, feeUsd: parsed.feeUsd, buyAmount: parsed.buyAmount, raw: body, provider: "lifi", signable: true }, reference, key, null);
}

async function quoteOneInch(config: AppConfig, hop: QuoteHop, chainId: number, reference: Reference | null, fetchImpl: typeof fetch, signal: AbortSignal, key: string): Promise<HopQuote> {
  const url = new URL(`${config.oneInchBase}/swap/v6.1/${chainId}/quote`);
  url.searchParams.set("src", hop.sellAddress);
  url.searchParams.set("dst", hop.buyAddress);
  url.searchParams.set("amount", hop.sellAmount);
  const body = await callProvider(config, "oneinch", url.toString(), { headers: { Authorization: `Bearer ${config.keys.oneInch}` } }, fetchImpl, signal);
  const parsed = oneInchSchema.safeParse(body);
  if (!parsed.success) return empty();
  const impact = reference ? impactPctFromUsd(reference.spentUsd, Number(parsed.data.dstAmount) / 10 ** reference.decimals, reference.priceUsd) : null;
  return withNet({ priceImpactPct: impact, feeUsd: 0, buyAmount: parsed.data.dstAmount, provider: "oneinch", signable: false, raw: body }, reference, key, null);
}

async function quoteKyber(config: AppConfig, hop: QuoteHop, chainId: number, reference: Reference | null, fetchImpl: typeof fetch, signal: AbortSignal, key: string): Promise<HopQuote> {
  const slug = KYBER_SLUG[chainId];
  if (!slug) return empty();
  const url = new URL(`${config.kyberBase}/${slug}/api/v1/routes`);
  url.searchParams.set("tokenIn", hop.sellAddress);
  url.searchParams.set("tokenOut", hop.buyAddress);
  url.searchParams.set("amountIn", hop.sellAmount);
  const body = await callProvider(config, "kyberswap", url.toString(), { headers: { "x-client-id": config.keys.kyberClientId } }, fetchImpl, signal);
  const parsed = kyberSchema.safeParse(body);
  if (!parsed.success) return empty();
  const summary = parsed.data.data.routeSummary;
  const gas = summary.gasUsd ? Number(summary.gasUsd) : null;
  const impact = reference ? impactPctFromUsd(reference.spentUsd, Number(summary.amountOut) / 10 ** reference.decimals, reference.priceUsd) : null;
  return withNet({ priceImpactPct: impact, feeUsd: 0, buyAmount: summary.amountOut, provider: "kyberswap", signable: true, raw: body }, reference, key, Number.isFinite(gas ?? NaN) ? gas : null);
}

async function quoteVelora(config: AppConfig, hop: QuoteHop, chainId: number, reference: Reference | null, fetchImpl: typeof fetch, signal: AbortSignal, key: string): Promise<HopQuote> {
  const url = new URL(`${config.veloraBase}/prices`);
  url.searchParams.set("srcToken", hop.sellAddress);
  url.searchParams.set("destToken", hop.buyAddress);
  url.searchParams.set("amount", hop.sellAmount);
  url.searchParams.set("side", "SELL");
  url.searchParams.set("network", String(chainId));
  if (config.keys.veloraPartner) url.searchParams.set("partner", config.keys.veloraPartner);
  const body = await callProvider(config, "velora", url.toString(), {}, fetchImpl, signal);
  const parsed = veloraSchema.safeParse(body);
  if (!parsed.success) return empty();
  const gas = parsed.data.priceRoute.gasCostUSD ? Number(parsed.data.priceRoute.gasCostUSD) : null;
  const impact = reference ? impactPctFromUsd(reference.spentUsd, Number(parsed.data.priceRoute.destAmount) / 10 ** reference.decimals, reference.priceUsd) : null;
  return withNet(
    { priceImpactPct: impact, feeUsd: 0, buyAmount: parsed.data.priceRoute.destAmount, provider: "velora", signable: false, raw: body },
    reference,
    key,
    Number.isFinite(gas ?? NaN) ? gas : null,
  );
}

async function quoteOkx(config: AppConfig, chainIndex: string, hop: QuoteHop, reference: Reference | null, fetchImpl: typeof fetch, signal: AbortSignal, key: string): Promise<HopQuote> {
  const path = `/api/v6/dex/aggregator/quote?${new URLSearchParams({
    chainIndex,
    amount: hop.sellAmount,
    fromTokenAddress: hop.sellAddress,
    toTokenAddress: hop.buyAddress,
    swapMode: "exactIn",
  }).toString()}`;
  const timestamp = new Date().toISOString();
  const sign = createHmac("sha256", config.keys.okxSecret ?? "")
    .update(`${timestamp}GET${path}`)
    .digest("base64");
  const body = await callProvider(
    config,
    "okx",
    `https://web3.okx.com${path}`,
    {
      headers: {
        "OK-ACCESS-KEY": config.keys.okxKey ?? "",
        "OK-ACCESS-SIGN": sign,
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-PASSPHRASE": config.keys.okxPassphrase ?? "",
      },
    },
    fetchImpl,
    signal,
  );
  const parsed = okxSchema.safeParse(body);
  if (!parsed.success || parsed.data.code !== "0" || !parsed.data.data[0]) return empty();
  const row = parsed.data.data[0];
  const fee = row.tradeFee ? Number(row.tradeFee) : 0;
  const impact = reference ? impactPctFromUsd(reference.spentUsd, Number(row.toTokenAmount) / 10 ** reference.decimals, reference.priceUsd) : null;
  return withNet(
    { priceImpactPct: impact, feeUsd: Number.isFinite(fee) ? fee : 0, buyAmount: row.toTokenAmount, provider: "okx", signable: false, raw: body },
    reference,
    key,
    null,
  );
}

export function chooseQuote(quotes: readonly HopQuote[]): HopQuote {
  const usable = quotes.filter((quote) => quote.priceImpactPct !== null);
  if (usable.length === 0) return empty();
  const signable = usable.filter((quote) => quote.signable !== false);
  const pool = signable.length > 0 ? signable : usable;
  pool.sort((a, b) => {
    if (a.netOutputUsd !== undefined && b.netOutputUsd !== undefined && a.netOutputUsd !== b.netOutputUsd) return b.netOutputUsd - a.netOutputUsd;
    return (a.priceImpactPct ?? 0) - (b.priceImpactPct ?? 0) || a.feeUsd - b.feeUsd;
  });
  const winner = pool[0];
  if (!winner) return empty();
  const unsigned = usable
    .filter((quote) => quote.signable === false && quote.netOutputUsd !== undefined && (winner.netOutputUsd === undefined || quote.netOutputUsd > winner.netOutputUsd))
    .sort((a, b) => (b.netOutputUsd ?? 0) - (a.netOutputUsd ?? 0))[0];
  if (!unsigned?.provider) return winner;
  return { ...winner, note: `unsigned ${unsigned.provider} net ${unsigned.netOutputUsd}` };
}

export async function raceProviderQuotes(config: AppConfig, hop: QuoteHop, reference: Reference | null, fetchImpl: typeof fetch = fetch): Promise<HopQuote> {
  if (!validSellAmount(hop.sellAmount)) return empty();
  const ids = providersFor(hop.chain, config);
  if (ids.length === 0) return empty();
  const deadline = AbortSignal.timeout(config.quoteDeadlineMs);
  const quotes = await Promise.all(
    ids.map((id) => quoteOne(config, id, hop, reference, fetchImpl, AbortSignal.any([deadline, AbortSignal.timeout(config.quoteTimeoutMs)]))),
  );
  return chooseQuote(quotes);
}

export async function firmZeroEx(config: AppConfig, hop: QuoteHop, chainId: number, taker: string, reference: Reference | null, fetchImpl: typeof fetch): Promise<HopQuote> {
  const url = new URL(`${config.zeroExBase}/swap/allowance-holder/quote`);
  url.searchParams.set("chainId", String(chainId));
  url.searchParams.set("sellToken", hop.sellAddress);
  url.searchParams.set("buyToken", hop.buyAddress);
  url.searchParams.set("sellAmount", hop.sellAmount);
  url.searchParams.set("taker", taker);
  url.searchParams.set("slippageBps", String(config.maxSlippageBps));
  const headers: Record<string, string> = { "0x-version": "v2" };
  if (config.keys.zeroEx) headers["0x-api-key"] = config.keys.zeroEx;
  const response = await fetchImpl(url, { headers });
  if (!response.ok) return empty();
  const body: unknown = await response.json();
  const parsed = readZeroEx(body as Parameters<typeof readZeroEx>[0], reference);
  return { priceImpactPct: parsed.priceImpactPct, feeUsd: 0, buyAmount: parsed.buyAmount, raw: body, prepared: parsed, provider: "zeroex", signable: true };
}

export async function firmLifi(
  config: AppConfig,
  hop: QuoteHop,
  chainId: number,
  taker: string,
  reference: Reference | null,
  fetchImpl: typeof fetch,
): Promise<HopQuote> {
  const url = new URL(`${config.lifiBase}/quote`);
  url.searchParams.set("fromChain", String(chainId));
  url.searchParams.set("toChain", String(chainId));
  url.searchParams.set("fromToken", hop.sellAddress);
  url.searchParams.set("toToken", hop.buyAddress);
  url.searchParams.set("fromAmount", hop.sellAmount);
  url.searchParams.set("fromAddress", taker);
  if (config.keys.lifiIntegrator) url.searchParams.set("integrator", config.keys.lifiIntegrator);
  const headers: Record<string, string> = {};
  if (config.keys.lifi) headers["x-lifi-api-key"] = config.keys.lifi;
  const response = await fetchImpl(url, { headers });
  if (!response.ok) return empty();
  const body: unknown = await response.json();
  const parsed = readLifi(body as Parameters<typeof readLifi>[0], reference, chainId);
  if (!parsed.sameChain) return empty();
  return { priceImpactPct: parsed.priceImpactPct, feeUsd: parsed.feeUsd, buyAmount: parsed.buyAmount, raw: body, provider: "lifi", signable: true };
}

export async function firmKyber(
  config: AppConfig,
  hop: QuoteHop,
  chainId: number,
  sender: string,
  reference: Reference | null,
  fetchImpl: typeof fetch,
): Promise<HopQuote> {
  const slug = KYBER_SLUG[chainId];
  if (!slug) return empty();
  const url = new URL(`${config.kyberBase}/${slug}/api/v1/routes`);
  url.searchParams.set("tokenIn", hop.sellAddress);
  url.searchParams.set("tokenOut", hop.buyAddress);
  url.searchParams.set("amountIn", hop.sellAmount);
  const response = await fetchImpl(url, { headers: { "x-client-id": config.keys.kyberClientId } });
  if (!response.ok) return empty();
  const body: unknown = await response.json();
  const parsed = kyberSchema.safeParse(body);
  if (!parsed.success) return empty();
  const built = await buildKyberSwap(config, chainId, parsed.data.data.routeSummary, sender, fetchImpl);
  if (!built) return empty();
  const summary = parsed.data.data.routeSummary;
  const gas = summary.gasUsd ? Number(summary.gasUsd) : null;
  const impact = reference ? impactPctFromUsd(reference.spentUsd, Number(summary.amountOut) / 10 ** reference.decimals, reference.priceUsd) : null;
  return {
    priceImpactPct: impact,
    feeUsd: 0,
    buyAmount: summary.amountOut,
    provider: "kyberswap",
    signable: true,
    raw: body,
    gasUsd: Number.isFinite(gas ?? NaN) ? (gas as number) : undefined,
    prepared: { to: built.to, data: built.data, value: built.value },
  };
}

export async function buildKyberSwap(config: AppConfig, chainId: number, routeSummary: unknown, sender: string, fetchImpl: typeof fetch): Promise<{ to: string; data: string; value: string } | null> {
  const slug = KYBER_SLUG[chainId];
  if (!slug) return null;
  const response = await fetchImpl(`${config.kyberBase}/${slug}/api/v1/route/build`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-client-id": config.keys.kyberClientId },
    body: JSON.stringify({ routeSummary, sender, recipient: sender, slippageTolerance: config.maxSlippageBps, source: config.keys.kyberClientId }),
  });
  if (!response.ok) return null;
  const parsed = kyberBuildSchema.safeParse(await response.json());
  if (!parsed.success) return null;
  return { to: parsed.data.data.routerAddress, data: parsed.data.data.data, value: parsed.data.data.transactionValue ?? "0" };
}
