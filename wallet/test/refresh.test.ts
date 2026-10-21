import assert from "node:assert/strict";
import test from "node:test";
import { QUOTE_ASSETS } from "../src/chains.js";
import { applyLiquidity, mergeWatchlist, rebuildIdentities, shortlistTokens } from "../src/refresh.js";
import { tokenFromDexSearch } from "../src/parsers.js";
import { buildPairMap } from "../src/pairs.js";
import type { TokenRecord } from "../src/domain.js";
import { quoteHop } from "../src/clients.js";
import { loadConfig } from "../src/config.js";

function token(contract: string, liquidity = 0): TokenRecord {
  return {
    id: `solana:${contract.toLowerCase()}`,
    ticker: "MPLX",
    names: ["Metaplex"],
    chainKey: "solana",
    chain: { kind: "solana" },
    contract,
    decimals: 6,
    pairMap: buildPairMap(
      liquidity > 0
        ? [
            {
              poolAddress: `${contract}-pool`,
              dex: "raydium",
              chainKey: "solana",
              baseSymbol: "MPLX",
              baseAddress: contract,
              quoteSymbol: "SOL",
              quoteAddress: "So11111111111111111111111111111111111111112",
              liquidityUsd: liquidity,
              priceUsd: 0.2,
              baseDecimals: 6,
            },
          ]
        : [],
    ),
    hyperliquid: null,
    refreshedAt: "2026-01-01T00:00:00.000Z",
    sourceId: "metaplex",
  };
}

test("a rebuild keeps the stored pair map and a liquidity refresh replaces it", () => {
  const previous = [token("mplxMint", 2_000_000)];
  const rebuilt = rebuildIdentities(previous, [{ id: "metaplex", symbol: "mplx", name: "Metaplex", platforms: { solana: "mplxMint" } }], []);
  assert.equal(rebuilt[0]?.pairMap.top?.quoteSymbol, "SOL");
  assert.equal(rebuilt[0]?.names[0], "Metaplex");
  const refreshed = applyLiquidity(
    rebuilt,
    [
      {
        poolAddress: "pool-usdc",
        dex: "orca",
        chainKey: "solana",
        baseSymbol: "MPLX",
        baseAddress: "mplxMint",
        quoteSymbol: "USDC",
        quoteAddress: "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        liquidityUsd: 80_000,
        priceUsd: 0.2,
        baseDecimals: 6,
      },
      {
        poolAddress: "pool-sol",
        dex: "raydium",
        chainKey: "solana",
        baseSymbol: "MPLX",
        baseAddress: "mplxMint",
        quoteSymbol: "SOL",
        quoteAddress: "So11111111111111111111111111111111111111112",
        liquidityUsd: 3_000_000,
        priceUsd: 0.21,
        baseDecimals: 6,
      },
    ],
    "2026-10-21T00:00:00.000Z",
    QUOTE_ASSETS,
    200,
  );
  assert.equal(refreshed[0]?.pairMap.top?.quoteSymbol, "SOL");
  assert.equal(refreshed[0]?.pairMap.pools.length, 2);
  assert.equal(shortlistTokens([token("thin", 1), token("deep", 50)], 1)[0]?.contract, "deep");
});

test("a live search keeps one name match and rejects two contracts", () => {
  const one = tokenFromDexSearch(
    {
      pairs: [
        {
          chainId: "solana",
          dexId: "raydium",
          pairAddress: "p",
          baseToken: { address: "mplxMint", symbol: "MPLX", name: "Metaplex" },
          quoteToken: { address: "So11111111111111111111111111111111111111112", symbol: "SOL" },
          liquidity: { usd: 2_000_000 },
          priceUsd: "0.2",
        },
      ],
    },
    { ticker: "mplx", projectName: "Metaplex" },
    "2026-10-21T00:00:00.000Z",
    QUOTE_ASSETS,
  );
  assert.equal(one.kind, "token");
  if (one.kind === "token") assert.equal(one.token.pairMap.top?.quoteSymbol, "SOL");
  const two = tokenFromDexSearch(
    {
      pairs: [
        {
          chainId: "solana",
          pairAddress: "a",
          baseToken: { address: "one", symbol: "MPLX", name: "Metaplex" },
          quoteToken: { address: "So11111111111111111111111111111111111111112", symbol: "SOL" },
          liquidity: { usd: 10 },
        },
        {
          chainId: "base",
          pairAddress: "b",
          baseToken: { address: "two", symbol: "MPLX", name: "Metaplex" },
          quoteToken: { address: "0x4200000000000000000000000000000000000006", symbol: "WETH" },
          liquidity: { usd: 10 },
        },
      ],
    },
    { ticker: "MPLX", projectName: "Metaplex" },
    "2026-10-21T00:00:00.000Z",
    QUOTE_ASSETS,
  );
  assert.equal(two.kind, "ambiguous");
});

test("quote requests carry the sized sell amount and skip a zero amount", async () => {
  const config = loadConfig({});
  let called = false;
  const skipped = await quoteHop(
    config,
    { sellAddress: "usdc", buyAddress: "mplx", sellAmount: "0", chain: { kind: "solana" } },
    null,
    async () => {
      called = true;
      return new Response("{}", { status: 200 });
    },
  );
  assert.equal(called, false);
  assert.equal(skipped.priceImpactPct, null);
  let seen = "";
  const quoted = await quoteHop(
    config,
    { sellAddress: "usdc", buyAddress: "mplx", sellAmount: "5000000", chain: { kind: "solana" } },
    null,
    async (input) => {
      seen = String(input);
      return new Response(JSON.stringify({ outAmount: "10", priceImpactPct: "0.01" }), { status: 200 });
    },
  );
  assert.match(seen, /amount=5000000/);
  assert.equal(quoted.priceImpactPct, 1);
});

test("merge keeps a discovered token that the coin list does not know", () => {
  const discovered = token("fallback", 10_000);
  discovered.ticker = "NEW";
  const merged = mergeWatchlist([discovered], []);
  assert.equal(merged.length, 1);
  assert.equal(merged[0]?.ticker, "NEW");
});
