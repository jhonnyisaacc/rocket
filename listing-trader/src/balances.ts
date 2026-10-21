import type { Holding } from "./domain.js";

export type BalanceReader = (holding: Holding) => Promise<number | null>;

export function applyBalance(holding: Holding, amount: number): Holding {
  const price = holding.amount > 0 ? holding.usd / holding.amount : 0;
  return { ...holding, amount, usd: amount * price };
}

export async function holdingsForTrade(
  live: boolean,
  declared: readonly Holding[],
  read: BalanceReader | null,
): Promise<{ ok: true; holdings: Holding[] } | { ok: false; reason: string }> {
  if (!live) return { ok: true, holdings: [...declared] };
  if (!read) return { ok: false, reason: "balance was not read" };
  const holdings: Holding[] = [];
  for (const holding of declared) {
    const amount = await read(holding);
    if (amount === null || !Number.isFinite(amount) || amount < 0) return { ok: false, reason: "balance was not read" };
    holdings.push(applyBalance(holding, amount));
  }
  return { ok: true, holdings };
}
