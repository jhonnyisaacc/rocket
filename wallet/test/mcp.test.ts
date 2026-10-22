import assert from "node:assert/strict";
import test from "node:test";
import { createHandler, type McpDeps } from "../src/mcp-server.js";

function deps(mode: McpDeps["approvalMode"], live: boolean): McpDeps {
  return {
    executorUrl: "http://executor",
    resolverUrl: "http://resolver",
    executorAuthToken: "executor-token",
    resolverAuthToken: "resolver-token",
    approvalMode: mode,
    live,
    fetchImpl: async (url) => new Response(JSON.stringify({ url: String(url) }), { status: 200 }),
  };
}

test("tools/list names the rocket tools", async () => {
  const handle = createHandler(deps("always_approve", false));
  const reply = (await handle({ jsonrpc: "2.0", id: 1, method: "tools/list" })) as { result: { tools: { name: string }[] } };
  assert.deepEqual(reply.result.tools.map((tool) => tool.name), ["wallet_status", "resolve_alert", "request_swap", "request_listing", "plan_rebalance"]);
});

test("a live listing under always_approve parks at pending_approval", async () => {
  const handle = createHandler(deps("always_approve", true));
  const reply = (await handle({ jsonrpc: "2.0", id: 2, method: "tools/call", params: { name: "request_listing", arguments: {} } })) as { result: { content: { text: string }[] } };
  const value = JSON.parse(reply.result.content[0].text) as { status: string; action: string };
  assert.equal(value.status, "pending_approval");
  assert.equal(value.action, "passkey");
});

test("the listing matrix reaches the executor only on an allowed cell", async () => {
  const calls: string[] = [];
  const matrixDeps = (mode: McpDeps["approvalMode"], live: boolean, screened: boolean): McpDeps => ({
    ...deps(mode, live),
    screenedLiveListing: screened,
    fetchImpl: async (url) => {
      calls.push(String(url));
      return new Response(JSON.stringify({ url: String(url) }), { status: 200 });
    },
  });
  const call = async (mode: McpDeps["approvalMode"], live: boolean, screened: boolean) => {
    calls.length = 0;
    const handle = createHandler(matrixDeps(mode, live, screened));
    const reply = (await handle({ jsonrpc: "2.0", id: 9, method: "tools/call", params: { name: "request_listing", arguments: {} } })) as { result: { content: { text: string }[] } };
    return JSON.parse(reply.result.content[0].text) as { status?: string; url?: string };
  };
  assert.equal((await call("autonomous", true, true)).url, "http://executor/listing");
  assert.deepEqual(calls, ["http://executor/listing"]);
  assert.equal((await call("autonomous", true, false)).status, "pending_approval");
  assert.deepEqual(calls, []);
  assert.equal((await call("iframe", true, true)).status, "pending_approval");
  assert.deepEqual(calls, []);
  assert.equal((await call("always_approve", true, true)).status, "pending_approval");
  assert.deepEqual(calls, []);
  assert.equal((await call("iframe", false, false)).url, "http://executor/listing");
  assert.equal((await call("always_approve", false, false)).url, "http://executor/listing");
});

test("a dry-run listing reaches the executor", async () => {
  const handle = createHandler(deps("always_approve", false));
  const reply = (await handle({ jsonrpc: "2.0", id: 3, method: "tools/call", params: { name: "request_listing", arguments: {} } })) as { result: { content: { text: string }[] } };
  const value = JSON.parse(reply.result.content[0].text) as { url: string };
  assert.equal(value.url, "http://executor/listing");
});
