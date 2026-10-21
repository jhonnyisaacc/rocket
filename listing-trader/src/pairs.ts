import type { PairMap, Pool } from "./domain.js";

export function buildPairMap(pools: readonly Pool[]): PairMap {
  const sorted = pools.slice().sort((a, b) => b.liquidityUsd - a.liquidityUsd);
  const bestByQuote: Record<string, Pool> = {};
  for (const pool of sorted) {
    const key = pool.quoteSymbol.toUpperCase();
    if (!bestByQuote[key]) bestByQuote[key] = pool;
  }
  return { pools: sorted, top: sorted[0] ?? null, bestByQuote };
}

export function topQuoteSymbol(pairMap: PairMap): string | null {
  return pairMap.top ? pairMap.top.quoteSymbol.toUpperCase() : null;
}
