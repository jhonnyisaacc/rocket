import assert from "node:assert/strict";
import test from "node:test";
import { assertTradableAction, buildLeverage, buildOrder, floatToWire } from "../src/hyperliquid.js";

test("order wire and leverage default to 1x, and withdraw is refused", () => {
  assert.equal(floatToWire(1), "1");
  assert.equal(floatToWire(1.5), "1.5");
  const order = buildOrder({ asset: 3, isBuy: true, limitPx: 1.25, size: 2 });
  assert.equal(order.type, "order");
  assert.equal(order.orders[0].t.limit.tif, "Ioc");
  assert.deepEqual(buildLeverage(3, 1), { type: "updateLeverage", asset: 3, isCross: true, leverage: 1 });
  assert.throws(() => assertTradableAction({ type: "withdraw3" }));
  assert.throws(() => assertTradableAction({ type: "agentSendAsset" }));
  assert.throws(() => assertTradableAction({ type: "usdSend" }));
});
