import assert from "node:assert/strict";
import test from "node:test";
import { createWalletMaterial, encryptWallet, decryptWallet, keystoreContainsSecret } from "../src/keystore.js";
import { attachHyperliquid, attachPools, hyperliquidFromMeta, poolsFromDexScreener, readKoreanName, tokensFromCoinList } from "../src/parsers.js";
import { readJupiter, readLifi, readZeroEx, impactPctFromUsd } from "../src/quotes.js";

test("keystore ciphertext does not contain the raw keys", () => {
  const material = createWalletMaterial();
  const file = encryptWallet(material, "correct horse battery");
  assert.equal(keystoreContainsSecret(file, material), false);
  assert.equal(JSON.stringify(file).includes(material.evmPrivateKey.reveal()), false);
  const opened = decryptWallet(file, "correct horse battery");
  assert.equal(opened.evmAddress, material.evmAddress);
  assert.equal(opened.evmPrivateKey.reveal(), material.evmPrivateKey.reveal());
});

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
        quoteToken: { address: "so111", symbol: "SOL" },
        liquidity: { usd: 2_000_000 },
        priceUsd: "0.2",
        priceNative: "0.001",
      },
      {
        chainId: "solana",
        dexId: "orca",
        pairAddress: "pool-usdc",
        baseToken: { address: "mplxMint", symbol: "MPLX" },
        quoteToken: { address: "usdc", symbol: "USDC" },
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
  const withPools = attachPools(token, pools, "2026-10-21T00:00:00.000Z");
  assert.equal(withPools.pairMap.top?.quoteSymbol, "SOL");
  assert.equal(withPools.pairMap.top?.quotePriceUsd, 200);
  assert.equal(withPools.pairMap.pools.length, 2);
  const markets = hyperliquidFromMeta({ universe: [{ name: "MPLX", maxLeverage: 3 }, { name: "GONE", isDelisted: true }] });
  const linked = attachHyperliquid(withPools, markets);
  assert.equal(linked.hyperliquid?.coin, "MPLX");
  assert.equal(linked.hyperliquid?.assetIndex, 0);
});

test("quote readers skip unverifiable impact and reject a cross-chain LI.FI transaction", () => {
  assert.equal(impactPctFromUsd(5, 24, 0.2), 4);
  const jupiter = readJupiter({ outAmount: "10", priceImpactPct: "0.0001" }, "fraction");
  assert.equal(jupiter.priceImpactPct, 0.01);
  const zero = readZeroEx({ liquidityAvailable: true, buyAmount: "1000000" }, { spentUsd: 5, priceUsd: 1, decimals: 6 });
  assert.equal(zero.priceImpactPct, 80);
  const bridged = readLifi(
    { estimate: { toAmount: "1" }, transactionRequest: { chainId: 1 } },
    null,
    324,
  );
  assert.equal(bridged.sameChain, false);
  assert.equal(bridged.priceImpactPct, null);
});
