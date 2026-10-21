import { PublicKey } from "@solana/web3.js";
import { chainByKey } from "./chains.js";
import type { Holding } from "./domain.js";

export type BalanceReader = (holding: Holding) => Promise<number | null>;

export function applyBalance(holding: Holding, amount: number): Holding {
  const price = holding.amount > 0 ? holding.usd / holding.amount : 0;
  return { ...holding, amount, usd: amount * price };
}

export function scopeHolding(holding: Holding, tradeChainKey: string): Holding {
  if (holding.chainKey) return holding;
  return { ...holding, chainKey: tradeChainKey };
}

export function holdingFitsChain(holding: Holding, tradeChainKey: string): boolean {
  if (holding.native) return true;
  const kind = chainByKey(tradeChainKey)?.chain.kind;
  if (kind === "evm") return /^0x[0-9a-fA-F]{40}$/.test(holding.address);
  if (kind === "solana") {
    try {
      new PublicKey(holding.address);
      return true;
    } catch {
      return false;
    }
  }
  return false;
}

export async function holdingsForTrade(
  live: boolean,
  declared: readonly Holding[],
  read: BalanceReader | null,
  tradeChainKey: string,
): Promise<{ ok: true; holdings: Holding[] } | { ok: false; reason: string }> {
  if (!live) return { ok: true, holdings: [...declared] };
  if (!read || !tradeChainKey) return { ok: false, reason: "balance was not read" };
  const holdings: Holding[] = [];
  let failed = false;
  for (const holding of declared) {
    if (holding.chainKey && holding.chainKey !== tradeChainKey) continue;
    if (!holdingFitsChain(holding, tradeChainKey)) continue;
    const scoped = scopeHolding(holding, tradeChainKey);
    let amount: number | null;
    try {
      amount = await read(scoped);
    } catch {
      failed = true;
      continue;
    }
    if (amount === null || !Number.isFinite(amount) || amount < 0) {
      failed = true;
      continue;
    }
    holdings.push(applyBalance(scoped, amount));
  }
  if (holdings.length === 0 && failed) return { ok: false, reason: "balance was not read" };
  return { ok: true, holdings };
}
