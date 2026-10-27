import assert from "node:assert/strict";
import test from "node:test";
import type { TokenRecord } from "../src/domain.js";
import { WatchIndex } from "../src/match.js";
import { buildPairMap } from "../src/pairs.js";
import { assertNoLiveWhale, dryRunWhaleClient, handToWhale } from "../src/whale.js";

function record(): TokenRecord {
  return {
    id: "solana:mint",
    ticker: "MPLX",
    names: ["Metaplex"],
    chainKey: "solana",
    chain: { kind: "solana" },
    contract: "mint",
    decimals: 6,
    pairMap: buildPairMap([
      {
        poolAddress: "pool",
        dex: "raydium",
        chainKey: "solana",
        baseSymbol: "MPLX",
        baseAddress: "mint",
        quoteSymbol: "USDC",
        quoteAddress: "usdc",
        liquidityUsd: 200_000,
        priceUsd: 1,
        baseDecimals: 6,
      },
    ]),
    hyperliquid: null,
    refreshedAt: "2026-10-21T00:00:00.000Z",
  };
}

test("a hit builds a dry-run swap and the client does not call Whale", async () => {
  const handed = await handToWhale(
    { id: "a1", ticker: "MPLX", projectName: "Metaplex", source: "test", publishedAt: "2026-10-21", receivedAt: "2026-10-21" },
    new WatchIndex([record()]),
    75_000,
    dryRunWhaleClient(),
    { WHALE_URL: "https://whale.example" },
  );
  assert.equal(handed.outcome.kind, "hit");
  assert.equal(handed.command?.mode, "dry_run");
  assert.equal(handed.command?.buy.address, "mint");
  assert.equal(handed.result?.decision, "skipped");
});

test("live whale calls are refused", () => {
  assert.throws(() => assertNoLiveWhale({ WHALE_URL: "https://whale.example", WHALE_LIVE: "true" }), /read-only/);
});
