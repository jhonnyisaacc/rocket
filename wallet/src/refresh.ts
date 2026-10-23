import type { QuoteAssets } from "./chains.js";
import type { HyperliquidMarket, Pool, TokenRecord } from "./domain.js";
import { attachHyperliquid, attachPools, tokensFromCoinList, type CoinListRow } from "./parsers.js";

export function mergeWatchlist(previous: readonly TokenRecord[], fresh: readonly TokenRecord[]): TokenRecord[] {
  const prev = new Map(previous.map((token) => [token.id, token]));
  const freshIds = new Set(fresh.map((token) => token.id));
  const merged = fresh.map((token) => {
    const old = prev.get(token.id);
    if (!old) return token;
    const names = token.names.slice();
    for (const name of old.names) {
      if (!names.includes(name)) names.push(name);
    }
    const keepPools = old.pairMap.pools.length > 0;
    return {
      ...token,
      names,
      pairMap: keepPools ? old.pairMap : token.pairMap,
      decimals: token.decimals ?? old.decimals,
      refreshedAt: keepPools ? old.refreshedAt : token.refreshedAt,
      hyperliquid: token.hyperliquid ?? old.hyperliquid,
    };
  });
  return merged.concat(previous.filter((token) => !freshIds.has(token.id)));
}

export function shortlistTokens(tokens: readonly TokenRecord[], limit: number): TokenRecord[] {
  return tokens
    .filter((token) => token.pairMap.pools.length > 0)
    .slice()
    .sort((a, b) => (b.pairMap.top?.liquidityUsd ?? 0) - (a.pairMap.top?.liquidityUsd ?? 0))
    .slice(0, Math.max(0, limit));
}

export function addressChunks(tokens: readonly TokenRecord[], limit: number, size = 30): string[][] {
  const addresses = shortlistTokens(tokens, limit).map((token) => token.contract);
  const chunks: string[][] = [];
  for (let index = 0; index < addresses.length; index += size) chunks.push(addresses.slice(index, index + size));
  return chunks;
}

export function withKoreanName(token: TokenRecord, korean: string | null): TokenRecord {
  if (!korean || token.names.includes(korean)) return token;
  return { ...token, names: [...token.names, korean] };
}

export function rebuildIdentities(
  previous: readonly TokenRecord[],
  rows: readonly CoinListRow[],
  markets: readonly HyperliquidMarket[],
  koreanById: ReadonlyMap<string, string> = new Map(),
): TokenRecord[] {
  const fresh = tokensFromCoinList(rows, koreanById).map((token) => attachHyperliquid(token, markets));
  return mergeWatchlist(previous, fresh);
}

export function applyLiquidity(
  tokens: readonly TokenRecord[],
  pools: readonly Pool[],
  refreshedAt: string,
  quoteAssets: QuoteAssets,
  limit: number,
): TokenRecord[] {
  const chosen = new Set(shortlistTokens(tokens, limit).map((token) => token.id));
  return tokens.map((token) => (chosen.has(token.id) ? attachPools(token, pools, refreshedAt, quoteAssets) : token));
}
