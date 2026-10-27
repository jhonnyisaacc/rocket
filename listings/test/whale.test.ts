import assert from "node:assert/strict";
import test from "node:test";
import type { Alert, TokenRecord } from "../src/domain.js";
import { WatchIndex } from "../src/match.js";
import { buildPairMap } from "../src/pairs.js";
import { assertNoLiveWhale, dryRunWhaleClient, handToWhale, type WhaleClient } from "../src/whale.js";

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

function alert(): Alert {
  return {
    id: "a1",
    ticker: "MPLX",
    projectName: "Metaplex",
    source: "test",
    publishedAt: "2026-10-21",
    receivedAt: "2026-10-21",
  };
}

function assertReadOnlyRefusal(value: string): void {
  assert.throws(
    () => assertNoLiveWhale({ WHALE_URL: "https://whale.example", WHALE_LIVE: value }),
    (error: unknown) => {
      assert.ok(error instanceof Error);
      assert.match(error.message, /read-only/);
      assert.doesNotMatch(error.message, /WHALE_URL/);
      return true;
    },
  );
}

test("a hit builds a dry-run swap and the client does not call Whale", async () => {
  const handed = await handToWhale(alert(), new WatchIndex([record()]), 75_000, dryRunWhaleClient(), {
    WHALE_URL: "https://whale.example",
  });
  assert.equal(handed.outcome.kind, "hit");
  assert.equal(handed.command?.mode, "dry_run");
  assert.equal(handed.command?.buy.address, "mint");
  assert.equal(handed.result?.decision, "skipped");
  assert.match(handed.result?.reason ?? "", /was not sent/);
});

for (const value of ["true", "TRUE", "1", "yes"]) {
  test(`WHALE_LIVE=${value} throws read-only`, () => {
    assertReadOnlyRefusal(value);
  });
}

test("WHALE_LIVE=false does not throw", () => {
  assert.doesNotThrow(() => assertNoLiveWhale({ WHALE_LIVE: "false" }));
});

test("unset WHALE_LIVE does not throw", () => {
  assert.doesNotThrow(() => assertNoLiveWhale({}));
});

test("empty WHALE_LIVE does not throw", () => {
  assert.doesNotThrow(() => assertNoLiveWhale({ WHALE_LIVE: "" }));
});

test("WHALE_URL alone does not throw", () => {
  assert.doesNotThrow(() => assertNoLiveWhale({ WHALE_URL: "https://whale.example" }));
});

test("WHALE_LIVE=TRUE throws before the client swaps", async () => {
  let swaps = 0;
  const client: WhaleClient = {
    async swap() {
      swaps += 1;
      return { decision: "skipped", reason: "dry-run only. a1 was not sent" };
    },
  };
  await assert.rejects(
    () =>
      handToWhale(alert(), new WatchIndex([record()]), 75_000, client, {
        WHALE_LIVE: "TRUE",
        WHALE_URL: "https://whale.example",
      }),
    /read-only/,
  );
  assert.equal(swaps, 0);
});
