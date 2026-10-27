import assert from "node:assert/strict";
import test from "node:test";
import { QUOTE_ASSETS } from "../src/chains.js";
import { attachHyperliquid, attachPools, hyperliquidFromMeta, poolsFromDexScreener, readKoreanName, tokensFromCoinList } from "../src/parsers.js";


test("parsers keep Korean names, the top DexScreener pair, and Hyperliquid perps", () => {
  assert.equal(readKoreanName({ localization: { ko: "액시 인피니티" } }), "액시 인피니티");
  const [token] = tokensFromCoinList([
    { id: "metaplex", symbol: "mplx", name: "Metaplex", platforms: { solana: "mplxMint" } },
  ]);
  const pools = poolsFromDexScreener({
    pairs: [
      {
        chainId: "solana",
        dexId: "raydium",
        pairAddress: "pool-sol",
        baseToken: { address: "mplxMint", symbol: "MPLX" },
        quoteToken: { address: "So11111111111111111111111111111111111111112", symbol: "SOL" },
        liquidity: { usd: 2_000_000 },
        priceUsd: "0.2",
        priceNative: "0.001",
      },
      {
        chainId: "solana",
        dexId: "orca",
        pairAddress: "pool-usdc",
        baseToken: { address: "mplxMint", symbol: "MPLX" },
        quoteToken: { address: "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", symbol: "USDC" },
        liquidity: { usd: 40_000 },
        priceUsd: "0.19",
      },
      {
        chainId: "not-a-real-slug",
        pairAddress: "ignored",
        baseToken: { address: "mplxMint" },
        quoteToken: { address: "x", symbol: "X" },
        liquidity: { usd: 9_000_000 },
      },
    ],
  });
  const withPools = attachPools(token, pools, "2026-10-21T00:00:00.000Z", QUOTE_ASSETS);
  assert.equal(withPools.pairMap.top?.quoteSymbol, "SOL");
  assert.equal(withPools.pairMap.top?.quotePriceUsd, 200);
  assert.equal(withPools.pairMap.pools.length, 2);
  const markets = hyperliquidFromMeta({ universe: [{ name: "MPLX", maxLeverage: 3 }, { name: "GONE", isDelisted: true }] });
  const linked = attachHyperliquid(withPools, markets);
  assert.equal(linked.hyperliquid?.coin, "MPLX");
  assert.equal(linked.hyperliquid?.assetIndex, 0);
});

