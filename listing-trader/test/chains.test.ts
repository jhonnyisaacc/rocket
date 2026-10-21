import assert from "node:assert/strict";
import test from "node:test";
import { chainByKey } from "../src/chains.js";
import { loadConfig } from "../src/config.js";

test("Robinhood Chain and HyperEVM use the published chain ids and RPCs", () => {
  const robinhood = chainByKey("robinhood");
  assert.ok(robinhood);
  assert.deepEqual(robinhood?.chain, { kind: "evm", chainId: 4663 });
  assert.equal(robinhood?.defaultRpc, "https://rpc.mainnet.chain.robinhood.com");
  assert.equal(robinhood?.aggregator, "zeroex");
  const hyper = chainByKey("hyperevm");
  assert.equal(hyper?.chain.kind === "evm" ? hyper.chain.chainId : 0, 999);
  assert.equal(hyper?.defaultRpc, "https://rpc.hyperliquid.xyz/evm");
  assert.equal(chainByKey("zksync")?.liveSend, "disabled");
  assert.equal(chainByKey("blast")?.aggregator, "lifi");
  assert.equal(chainByKey("hypercore")?.defaultRpc, "https://api.hyperliquid.xyz");
});

test("live mode is off unless the flag is the exact string true", () => {
  const dry = loadConfig({} as NodeJS.ProcessEnv);
  assert.equal(dry.live, false);
  assert.equal(dry.maxUsdPerTrade, 5);
  assert.equal(dry.maxLeverage, 1);
  const live = loadConfig({ LISTING_TRADER_LIVE: "true" } as NodeJS.ProcessEnv);
  assert.equal(live.live, true);
  assert.throws(() => loadConfig({ MAX_SLIPPAGE_BPS: "400" } as NodeJS.ProcessEnv));
});
