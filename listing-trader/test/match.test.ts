import assert from "node:assert/strict";
import test from "node:test";
import { matchAlert, WatchIndex } from "../src/match.js";
import { buildPairMap } from "../src/pairs.js";
import type { Pool, TokenRecord } from "../src/domain.js";

function pool(quote: string, liquidity: number): Pool {
  return {
    poolAddress: `${quote}-pool`,
    dex: "raydium",
    chainKey: "solana",
    baseSymbol: "MPLX",
    baseAddress: "mplx",
    quoteSymbol: quote,
    quoteAddress: `${quote}-mint`,
    liquidityUsd: liquidity,
    priceUsd: 1,
    baseDecimals: 6,
  };
}

function token(partial: Partial<TokenRecord> & Pick<TokenRecord, "ticker" | "names" | "chainKey">): TokenRecord {
  return {
    id: partial.id ?? `${partial.chainKey}:${partial.ticker}`,
    ticker: partial.ticker,
    names: partial.names,
    chainKey: partial.chainKey,
    chain: partial.chain ?? { kind: "solana" },
    contract: partial.contract ?? partial.ticker,
    decimals: 6,
    pairMap: partial.pairMap ?? buildPairMap([pool("SOL", 1_000_000)]),
    hyperliquid: partial.hyperliquid ?? null,
    refreshedAt: "2026-01-01T00:00:00.000Z",
  };
}

const index = new WatchIndex([
  token({ ticker: "AXS", names: ["Axie Infinity", "액시 인피니티"], chainKey: "ethereum", chain: { kind: "evm", chainId: 1 }, contract: "0xaxs" }),
  token({ ticker: "AXIS", names: ["Axis Robotics"], chainKey: "solana", contract: "axis" }),
  token({ ticker: "MPLX", names: ["Metaplex"], chainKey: "solana", contract: "mplx", pairMap: buildPairMap([pool("SOL", 2_000_000), pool("USDC", 50_000)]) }),
]);

test("exact ticker and project name hit, including a Korean alias", () => {
  const hit = matchAlert(index, { ticker: "axs", projectName: "액시 인피니티" }, 75_000);
  assert.equal(hit.kind, "hit");
  if (hit.kind === "hit") assert.equal(hit.token.contract, "0xaxs");
});

test("AXIS does not match AXS", () => {
  const robotics = matchAlert(index, { ticker: "AXIS", projectName: "Axis Robotics" }, 75_000);
  assert.equal(robotics.kind, "hit");
  if (robotics.kind === "hit") assert.equal(robotics.token.ticker, "AXIS");
  const lookalike = matchAlert(index, { ticker: "AXS", projectName: "Axis Robotics" }, 75_000);
  assert.equal(lookalike.kind, "lookalike");
});

test("ticker alone is not a match", () => {
  const outcome = matchAlert(index, { ticker: "AXS", projectName: "Something Else" }, 75_000);
  assert.equal(outcome.kind, "lookalike");
});

test("top pool is the most liquid pair", () => {
  const mplx = index.lookup("MPLX")[0];
  assert.equal(mplx.pairMap.top?.quoteSymbol, "SOL");
  assert.equal(mplx.pairMap.pools[1]?.liquidityUsd, 50_000);
});

test("a thousand lookups stay in memory and finish well under a millisecond each", () => {
  const tokens: TokenRecord[] = [];
  for (let i = 0; i < 2000; i += 1) {
    tokens.push(token({ ticker: `T${i}`, names: [`Token ${i}`], chainKey: "solana", contract: `c${i}` }));
  }
  const large = new WatchIndex(tokens);
  const start = performance.now();
  for (let i = 0; i < 1000; i += 1) {
    const outcome = matchAlert(large, { ticker: "T1500", projectName: "Token 1500" }, 1);
    assert.equal(outcome.kind, "hit");
  }
  const elapsed = performance.now() - start;
  assert.ok(elapsed < 1000, `1000 lookups took ${elapsed} ms`);
});
