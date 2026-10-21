import { z } from "zod";
import type { AppConfig } from "./config.js";
import type { ChainRef } from "./domain.js";
const BLOCKAID_CHAIN: Record<string, string> = {
  ethereum: "ethereum",
  optimism: "optimism",
  bnb: "bsc",
  polygon: "polygon",
  base: "base",
  arbitrum: "arbitrum",
  linea: "linea",
  blast: "blast",
  scroll: "scroll",
  zksync: "zksync",
  solana: "solana",
};

const goplusSchema = z
  .object({
    code: z.union([z.number(), z.string()]),
    result: z
      .record(
        z.string(),
        z
          .object({
            is_honeypot: z.string().optional(),
            cannot_sell_all: z.string().optional(),
            buy_tax: z.string().optional(),
            sell_tax: z.string().optional(),
          })
          .passthrough(),
      )
      .optional(),
  })
  .passthrough();

const blockaidSchema = z.object({ result_type: z.enum(["Benign", "Warning", "Malicious", "Spam"]) }).passthrough();

export async function screenToken(
  config: AppConfig,
  token: { chainKey: string; chain: ChainRef; contract: string },
  fetchImpl: typeof fetch = fetch,
): Promise<"allow" | "deny"> {
  if (!config.screening) return "allow";
  try {
    const goplus = await screenGoPlus(config, token, fetchImpl);
    if (goplus !== "allow") return "deny";
    if (!config.keys.blockaid) return "allow";
    return await screenBlockaid(config, token, fetchImpl);
  } catch {
    return "deny";
  }
}

async function screenGoPlus(config: AppConfig, token: { chainKey: string; chain: ChainRef; contract: string }, fetchImpl: typeof fetch): Promise<"allow" | "deny"> {
  const url =
    token.chain.kind === "solana"
      ? `https://api.gopluslabs.io/api/v1/solana/token_security?contract_addresses=${encodeURIComponent(token.contract)}`
      : token.chain.kind === "evm"
        ? `https://api.gopluslabs.io/api/v1/token_security/${token.chain.chainId}?contract_addresses=${encodeURIComponent(token.contract)}`
        : "";
  if (!url) return "deny";
  const headers: Record<string, string> = {};
  if (config.keys.goplus) headers.authorization = `Bearer ${config.keys.goplus}`;
  const response = await fetchImpl(url, { headers, signal: AbortSignal.timeout(config.liveLookupTimeoutMs) });
  if (!response.ok) return "deny";
  const parsed = goplusSchema.safeParse(await response.json());
  if (!parsed.success || String(parsed.data.code) !== "1" || !parsed.data.result) return "deny";
  const row = parsed.data.result[token.contract] ?? parsed.data.result[token.contract.toLowerCase()];
  if (!row) return "deny";
  if (row.is_honeypot === "1" || row.cannot_sell_all === "1") return "deny";
  if (config.live && (!row.buy_tax || !row.sell_tax)) return "deny";
  if (taxTooHigh(row.buy_tax, config.maxTokenTax) || taxTooHigh(row.sell_tax, config.maxTokenTax)) return "deny";
  return "allow";
}

function taxTooHigh(raw: string | undefined, cap: number): boolean {
  if (raw === undefined || raw === "") return false;
  const value = Number(raw);
  if (!Number.isFinite(value) || value < 0) return true;
  return value > cap;
}

async function screenBlockaid(config: AppConfig, token: { chainKey: string; chain: ChainRef; contract: string }, fetchImpl: typeof fetch): Promise<"allow" | "deny"> {
  const chain = BLOCKAID_CHAIN[token.chainKey] ?? (token.chain.kind === "solana" ? "solana" : undefined);
  if (!chain) return "deny";
  const response = await fetchImpl("https://api.blockaid.io/v0/token/scan", {
    method: "POST",
    headers: { "content-type": "application/json", "x-api-key": config.keys.blockaid ?? "" },
    body: JSON.stringify({ chain, address: token.contract }),
    signal: AbortSignal.timeout(config.liveLookupTimeoutMs),
  });
  if (!response.ok) return "deny";
  const parsed = blockaidSchema.safeParse(await response.json());
  if (!parsed.success) return "deny";
  return parsed.data.result_type === "Benign" ? "allow" : "deny";
}
