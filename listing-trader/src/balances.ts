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

export async function holdingsForTrade(
  live: boolean,
  declared: readonly Holding[],
  read: BalanceReader | null,
  tradeChainKey: string,
): Promise<{ ok: true; holdings: Holding[] } | { ok: false; reason: string }> {
  if (!live) return { ok: true, holdings: [...declared] };
  if (!read || !tradeChainKey) return { ok: false, reason: "balance was not read" };
  const holdings: Holding[] = [];
  for (const holding of declared) {
    const scoped = scopeHolding(holding, tradeChainKey);
    const amount = await read(scoped);
    if (amount === null || !Number.isFinite(amount) || amount < 0) return { ok: false, reason: "balance was not read" };
    holdings.push(applyBalance(scoped, amount));
  }
  return { ok: true, holdings };
}
