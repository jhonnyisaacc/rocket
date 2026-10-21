import type { ChainRef } from "./domain.js";
import type { AppConfig } from "./config.js";
import type { HopQuote } from "./executor.js";
import { chainByEvmId, chainByKey } from "./chains.js";
import { readJupiter, readLifi, readZeroEx } from "./quotes.js";

export type QuoteHop = {
  sellAddress: string;
  buyAddress: string;
  sellAmount: string;
  chain: ChainRef;
};

const AMOUNT = /^[1-9][0-9]{0,77}$/;

export function validSellAmount(amount: string): boolean {
  return AMOUNT.test(amount);
}

export async function quoteHop(
  config: AppConfig,
  hop: QuoteHop,
  reference: { spentUsd: number; priceUsd: number; decimals: number } | null,
  fetchImpl: typeof fetch = fetch,
): Promise<HopQuote> {
  if (!validSellAmount(hop.sellAmount)) return { priceImpactPct: null, feeUsd: 0, buyAmount: "0" };
  const spec =
    hop.chain.kind === "evm"
      ? chainByEvmId(hop.chain.chainId)
      : hop.chain.kind === "solana"
        ? chainByKey("solana")
        : undefined;
  if (!spec) return { priceImpactPct: null, feeUsd: 0, buyAmount: "0" };
  try {
    if (spec.aggregator === "jupiter") return await quoteJupiter(config, hop, fetchImpl);
    if (spec.aggregator === "lifi" && hop.chain.kind === "evm") return await quoteLifi(config, hop, hop.chain.chainId, reference, fetchImpl);
    if (spec.aggregator === "zeroex" && hop.chain.kind === "evm") return await quoteZeroEx(config, hop, hop.chain.chainId, reference, fetchImpl);
  } catch {
    return { priceImpactPct: null, feeUsd: 0, buyAmount: "0" };
  }
  return { priceImpactPct: null, feeUsd: 0, buyAmount: "0" };
}

async function quoteJupiter(config: AppConfig, hop: QuoteHop, fetchImpl: typeof fetch): Promise<HopQuote> {
  const url = new URL(`${config.jupiterBase}/quote`);
  url.searchParams.set("inputMint", hop.sellAddress);
  url.searchParams.set("outputMint", hop.buyAddress);
  url.searchParams.set("amount", hop.sellAmount);
  url.searchParams.set("slippageBps", String(config.maxSlippageBps));
  const headers: Record<string, string> = {};
  if (process.env.JUPITER_API_KEY) headers["x-api-key"] = process.env.JUPITER_API_KEY;
  const response = await fetchImpl(url, { headers });
  if (!response.ok) return { priceImpactPct: null, feeUsd: 0, buyAmount: "0" };
  const body: unknown = await response.json();
  const parsed = readJupiter(body as Parameters<typeof readJupiter>[0], config.jupiterImpactUnit);
  return { priceImpactPct: parsed.priceImpactPct, feeUsd: 0, buyAmount: parsed.buyAmount, raw: body };
}

async function quoteZeroEx(
  config: AppConfig,
  hop: QuoteHop,
  chainId: number,
  reference: { spentUsd: number; priceUsd: number; decimals: number } | null,
  fetchImpl: typeof fetch,
  firmTaker?: string,
): Promise<HopQuote> {
  const path = firmTaker ? "swap/allowance-holder/quote" : "swap/allowance-holder/price";
  const url = new URL(`${config.zeroExBase}/${path}`);
  url.searchParams.set("chainId", String(chainId));
  url.searchParams.set("sellToken", hop.sellAddress);
  url.searchParams.set("buyToken", hop.buyAddress);
  url.searchParams.set("sellAmount", hop.sellAmount);
  if (firmTaker) {
    url.searchParams.set("taker", firmTaker);
    url.searchParams.set("slippageBps", String(config.maxSlippageBps));
  }
  const headers: Record<string, string> = { "0x-version": "v2" };
  if (process.env.ZEROX_API_KEY) headers["0x-api-key"] = process.env.ZEROX_API_KEY;
  const response = await fetchImpl(url, { headers });
  if (!response.ok) return { priceImpactPct: null, feeUsd: 0, buyAmount: "0" };
  const body: unknown = await response.json();
  const parsed = readZeroEx(body as Parameters<typeof readZeroEx>[0], reference);
  return { priceImpactPct: parsed.priceImpactPct, feeUsd: 0, buyAmount: parsed.buyAmount, raw: body, prepared: parsed };
}

async function quoteLifi(
  config: AppConfig,
  hop: QuoteHop,
  chainId: number,
  reference: { spentUsd: number; priceUsd: number; decimals: number } | null,
  fetchImpl: typeof fetch,
): Promise<HopQuote> {
  const url = new URL(`${config.lifiBase}/quote`);
  url.searchParams.set("fromChain", String(chainId));
  url.searchParams.set("toChain", String(chainId));
  url.searchParams.set("fromToken", hop.sellAddress);
  url.searchParams.set("toToken", hop.buyAddress);
  url.searchParams.set("fromAmount", hop.sellAmount);
  const headers: Record<string, string> = {};
  if (process.env.LIFI_API_KEY) headers["x-lifi-api-key"] = process.env.LIFI_API_KEY;
  const response = await fetchImpl(url, { headers });
  if (!response.ok) return { priceImpactPct: null, feeUsd: 0, buyAmount: "0" };
  const body: unknown = await response.json();
  const parsed = readLifi(body as Parameters<typeof readLifi>[0], reference, chainId);
  if (!parsed.sameChain) return { priceImpactPct: null, feeUsd: 0, buyAmount: "0" };
  return { priceImpactPct: parsed.priceImpactPct, feeUsd: parsed.feeUsd, buyAmount: parsed.buyAmount, raw: body };
}

export async function firmZeroEx(
  config: AppConfig,
  hop: QuoteHop,
  chainId: number,
  taker: string,
  reference: { spentUsd: number; priceUsd: number; decimals: number } | null,
  fetchImpl: typeof fetch,
): Promise<HopQuote> {
  return quoteZeroEx(config, hop, chainId, reference, fetchImpl, taker);
}

export async function fetchHyperliquidMid(url: string, coin: string, fetchImpl: typeof fetch = fetch): Promise<number | null> {
  const response = await fetchImpl(`${url.replace(/\/$/, "")}/info`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ type: "allMids" }),
  });
  if (!response.ok) return null;
  const body = (await response.json()) as Record<string, string>;
  const value = Number(body[coin]);
  return Number.isFinite(value) && value > 0 ? value : null;
}
