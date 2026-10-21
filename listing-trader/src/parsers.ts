import { chainByKey, dexscreenerSlugMap } from "./chains.js";
import type { HyperliquidMarket, Pool, TokenRecord } from "./domain.js";
import { buildPairMap } from "./pairs.js";
import { nameMatches, normalizeTicker } from "./match.js";

export type CoinListRow = {
  id: string;
  symbol: string;
  name: string;
  platforms?: Record<string, string>;
};

const PLATFORM_TO_CHAIN: Record<string, string> = {
  ethereum: "ethereum",
  "optimistic-ethereum": "optimism",
  "binance-smart-chain": "bnb",
  "polygon-pos": "polygon",
  "zksync": "zksync",
  base: "base",
  "arbitrum-one": "arbitrum",
  linea: "linea",
  blast: "blast",
  scroll: "scroll",
  solana: "solana",
};

export function coingeckoPlatform(chainKey: string): string | null {
  const found = Object.entries(PLATFORM_TO_CHAIN).find(([, key]) => key === chainKey);
  return found?.[0] ?? null;
}

export function listedContract(
  rows: readonly CoinListRow[],
  alert: { ticker: string; projectName: string },
  chainKey: string,
  contract: string,
): boolean {
  const platform = coingeckoPlatform(chainKey);
  if (!platform) return false;
  const target = contract.toLowerCase();
  return rows.some((row) => {
    if (normalizeTicker(row.symbol) !== normalizeTicker(alert.ticker)) return false;
    if (!nameMatches(alert.projectName, [row.name])) return false;
    const listed = row.platforms?.[platform];
    return typeof listed === "string" && listed.toLowerCase() === target;
  });
}

export function poolMeetsFloor(pools: readonly Pool[], nowMs: number, minAgeHours: number, minVolumeUsd: number): boolean {
  if (pools.length === 0) return false;
  const top = [...pools].sort((left, right) => right.liquidityUsd - left.liquidityUsd)[0];
  if (top.createdAtMs == null || top.volume24hUsd == null) return false;
  const ageHours = (nowMs - top.createdAtMs) / 3_600_000;
  return ageHours >= minAgeHours && top.volume24hUsd >= minVolumeUsd;
}

export function readKoreanName(detail: unknown): string | null {
  if (typeof detail !== "object" || detail === null) return null;
  const localization = (detail as { localization?: unknown }).localization;
  if (typeof localization !== "object" || localization === null) return null;
  const ko = (localization as { ko?: unknown }).ko;
  if (typeof ko !== "string") return null;
  const trimmed = ko.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export function tokensFromCoinList(rows: readonly CoinListRow[], koreanById: ReadonlyMap<string, string> = new Map()): TokenRecord[] {
  const out: TokenRecord[] = [];
  for (const row of rows) {
    const platforms = row.platforms ?? {};
    for (const [platform, address] of Object.entries(platforms)) {
      if (!address) continue;
      const chainKey = PLATFORM_TO_CHAIN[platform];
      if (!chainKey) continue;
      const spec = chainByKey(chainKey);
      if (!spec) continue;
      const names = [row.name];
      const korean = koreanById.get(row.id);
      if (korean && korean !== row.name) names.push(korean);
      out.push({
        id: `${chainKey}:${address.toLowerCase()}`,
        ticker: normalizeTicker(row.symbol),
        names,
        chainKey,
        chain: spec.chain.kind === "hypercore" ? { kind: "hypercore", market: "perp" } : spec.chain,
        contract: address,
        decimals: null,
        pairMap: buildPairMap([]),
        hyperliquid: null,
        refreshedAt: new Date(0).toISOString(),
        sourceId: row.id,
      });
    }
  }
  return out;
}

type DexPair = {
  chainId?: string;
  dexId?: string;
  pairAddress?: string;
  baseToken?: { address?: string; symbol?: string; name?: string };
  quoteToken?: { address?: string; symbol?: string };
  liquidity?: { usd?: number };
  priceUsd?: string;
  priceNative?: string;
  pairCreatedAt?: number;
  volume?: { h24?: number };
};

export function poolsFromDexScreener(body: unknown, slugOverrides: Record<string, string> = {}): Pool[] {
  const slugs = dexscreenerSlugMap(slugOverrides);
  const pairs = (body as { pairs?: DexPair[] } | null)?.pairs;
  if (!Array.isArray(pairs)) return [];
  const pools: Pool[] = [];
  for (const pair of pairs) {
    if (!pair.chainId || !pair.pairAddress || !pair.baseToken?.address || !pair.quoteToken?.address) continue;
    const chainKey = slugs.get(pair.chainId);
    if (!chainKey) continue;
    const liquidity = pair.liquidity?.usd;
    if (typeof liquidity !== "number") continue;
    const price = pair.priceUsd === undefined ? null : Number(pair.priceUsd);
    const priceUsd = price !== null && Number.isFinite(price) ? price : null;
    const native = pair.priceNative === undefined ? null : Number(pair.priceNative);
    const quotePriceUsd = priceUsd !== null && native !== null && Number.isFinite(native) && native > 0 ? priceUsd / native : null;
    pools.push({
      poolAddress: pair.pairAddress,
      dex: pair.dexId ?? "unknown",
      chainKey,
      baseSymbol: pair.baseToken.symbol ?? "",
      baseAddress: pair.baseToken.address,
      quoteSymbol: pair.quoteToken.symbol ?? "",
      quoteAddress: pair.quoteToken.address,
      liquidityUsd: liquidity,
      priceUsd,
      baseDecimals: null,
      baseName: pair.baseToken.name,
      quotePriceUsd,
      createdAtMs: typeof pair.pairCreatedAt === "number" ? pair.pairCreatedAt : null,
      volume24hUsd: typeof pair.volume?.h24 === "number" ? pair.volume.h24 : null,
    });
  }
  return pools;
}

export function annotateQuoteDecimals(pools: readonly Pool[], decimalsBySymbol: Readonly<Record<string, number>>): Pool[] {
  return pools.map((pool) => {
    const decimals = decimalsBySymbol[pool.quoteSymbol.toUpperCase()];
    if (decimals === undefined) return pool;
    return { ...pool, quoteDecimals: decimals };
  });
}

export function attachPools(token: TokenRecord, pools: readonly Pool[], refreshedAt: string): TokenRecord {
  const own = pools.filter((pool) => pool.chainKey === token.chainKey && pool.baseAddress.toLowerCase() === token.contract.toLowerCase());
  return { ...token, pairMap: buildPairMap(own), refreshedAt };
}

export function tokenFromDexSearch(
  body: unknown,
  alert: { ticker: string; projectName: string; chainHint?: string },
  refreshedAt: string,
  slugOverrides: Record<string, string> = {},
): { kind: "token"; token: TokenRecord } | { kind: "ambiguous" } | { kind: "none" } {
  const pools = poolsFromDexScreener(body, slugOverrides).filter((pool) => {
    if (normalizeTicker(pool.baseSymbol) !== normalizeTicker(alert.ticker)) return false;
    if (!pool.baseName) return false;
    if (alert.chainHint && pool.chainKey !== alert.chainHint) return false;
    return nameMatches(alert.projectName, [pool.baseName]);
  });
  const groups = new Map<string, Pool[]>();
  for (const pool of pools) {
    const id = `${pool.chainKey}:${pool.baseAddress.toLowerCase()}`;
    const list = groups.get(id);
    if (list) list.push(pool);
    else groups.set(id, [pool]);
  }
  if (groups.size === 0) return { kind: "none" };
  if (groups.size > 1) return { kind: "ambiguous" };
  const [id, grouped] = [...groups.entries()][0];
  const spec = chainByKey(grouped[0].chainKey);
  if (!spec || spec.chain.kind === "hypercore") return { kind: "none" };
  const baseName = grouped[0].baseName ?? alert.projectName;
  return {
    kind: "token",
    token: {
      id,
      ticker: normalizeTicker(alert.ticker),
      names: baseName === alert.projectName ? [alert.projectName] : [alert.projectName, baseName],
      chainKey: grouped[0].chainKey,
      chain: spec.chain,
      contract: grouped[0].baseAddress,
      decimals: grouped[0].baseDecimals,
      pairMap: buildPairMap(grouped),
      hyperliquid: null,
      refreshedAt,
    },
  };
}

export function hyperliquidFromMeta(body: unknown): HyperliquidMarket[] {
  const universe = (body as { universe?: { name?: string; maxLeverage?: number; isDelisted?: boolean }[] } | null)?.universe;
  if (!Array.isArray(universe)) return [];
  const markets: HyperliquidMarket[] = [];
  universe.forEach((row, index) => {
    if (!row.name || row.isDelisted) return;
    markets.push({
      coin: row.name,
      assetIndex: index,
      market: "perp",
      maxLeverage: row.maxLeverage ?? 1,
    });
  });
  return markets;
}

export function attachHyperliquid(token: TokenRecord, markets: readonly HyperliquidMarket[]): TokenRecord {
  const market = markets.find((item) => item.coin.toUpperCase() === token.ticker);
  return { ...token, hyperliquid: market ?? null };
}
