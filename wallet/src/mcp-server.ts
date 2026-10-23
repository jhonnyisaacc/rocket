import { createInterface } from "node:readline";
import { parseApprovalMode, approvalGate, type ApprovalMode } from "./approval-modes.js";

export type McpDeps = {
  executorUrl: string;
  resolverUrl: string;
  executorAuthToken: string | null;
  resolverAuthToken: string | null;
  approvalMode: ApprovalMode;
  live: boolean;
  screenedLiveListing?: boolean;
  fetchImpl?: typeof fetch;
};

export const TOOLS = [
  { name: "wallet_status", description: "Read the executor and resolver status. It shows the mode, the enabled chains, and the caps. It moves no money.", inputSchema: { type: "object", properties: {} } },
  { name: "resolve_alert", description: "Resolve a listing alert to a token and its deepest pool. It stores nothing in live mode.", inputSchema: { type: "object", properties: { ticker: { type: "string" }, projectName: { type: "string" } }, required: ["ticker"] } },
  { name: "request_swap", description: "Quote and dry-run a swap intent. The executor route always runs dry_run, even when the process is live. It broadcasts nothing.", inputSchema: { type: "object", properties: {}, additionalProperties: true } },
  { name: "request_listing", description: "Run the listing path. In live mode a non-autonomous grant returns pending_approval and sends nothing.", inputSchema: { type: "object", properties: {}, additionalProperties: true } },
  { name: "plan_rebalance", description: "Plan a bridge between chains. It returns would_send and broadcasts nothing.", inputSchema: { type: "object", properties: {}, additionalProperties: true } },
] as const;

async function callHttp(deps: McpDeps, base: string, token: string | null, route: string, body?: unknown): Promise<unknown> {
  const fetchImpl = deps.fetchImpl ?? fetch;
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (token) headers.authorization = `Bearer ${token}`;
  const response = await fetchImpl(`${base.replace(/\/$/, "")}${route}`, {
    method: body === undefined ? "GET" : "POST",
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return { status: response.status, text: text.slice(0, 500) };
  }
}

export async function callTool(deps: McpDeps, name: string, args: Record<string, unknown>): Promise<unknown> {
  if (name === "wallet_status") {
    const [executor, resolver] = await Promise.all([
      callHttp(deps, deps.executorUrl, deps.executorAuthToken, "/status"),
      callHttp(deps, deps.resolverUrl, deps.resolverAuthToken, "/status").catch(() => null),
    ]);
    return { executor, resolver, approvalMode: deps.approvalMode };
  }
  if (name === "resolve_alert") return callHttp(deps, deps.resolverUrl, deps.resolverAuthToken, "/alert", args);
  if (name === "request_swap") return callHttp(deps, deps.executorUrl, deps.executorAuthToken, "/execute", args);
  if (name === "plan_rebalance") return callHttp(deps, deps.executorUrl, deps.executorAuthToken, "/rebalance", args);
  if (name === "request_listing") {
    const gate = approvalGate(deps.approvalMode, { live: deps.live, screened: deps.screenedLiveListing ?? false });
    if (gate.action !== "sign") return { status: "pending_approval", action: gate.action, reason: gate.reason };
    return callHttp(deps, deps.executorUrl, deps.executorAuthToken, "/listing", args);
  }
  throw new Error(`unknown tool ${name}`);
}

type JsonRpcRequest = { jsonrpc?: string; id?: unknown; method?: string; params?: { name?: string; arguments?: Record<string, unknown> } };

export function createHandler(deps: McpDeps) {
  return async (request: JsonRpcRequest): Promise<unknown> => {
    if (request.method === "initialize") {
      return { jsonrpc: "2.0", id: request.id ?? null, result: { protocolVersion: "2025-03-26", capabilities: { tools: {} }, serverInfo: { name: "rocket", version: "0.1.0" } } };
    }
    if (request.method === "ping") return { jsonrpc: "2.0", id: request.id ?? null, result: {} };
    if (request.method === "tools/list") return { jsonrpc: "2.0", id: request.id ?? null, result: { tools: TOOLS } };
    if (request.method === "tools/call") {
      const name = request.params?.name ?? "";
      try {
        const value = await callTool(deps, name, request.params?.arguments ?? {});
        return { jsonrpc: "2.0", id: request.id ?? null, result: { content: [{ type: "text", text: JSON.stringify(value) }] } };
      } catch (error) {
        return { jsonrpc: "2.0", id: request.id ?? null, result: { isError: true, content: [{ type: "text", text: error instanceof Error ? error.message : "tool failed" }] } };
      }
    }
    if (request.id === undefined) return null;
    return { jsonrpc: "2.0", id: request.id, error: { code: -32601, message: "method not found" } };
  };
}

const entry = process.argv[1] ?? "";
if (entry.endsWith("mcp-server.js")) {
  const deps: McpDeps = {
    executorUrl: process.env.EXECUTOR_URL ?? "http://127.0.0.1:8788",
    resolverUrl: process.env.RESOLVER_URL ?? "http://127.0.0.1:8787",
    executorAuthToken: process.env.EXECUTOR_AUTH_TOKEN ?? process.env.AUTH_TOKEN ?? null,
    resolverAuthToken: process.env.RESOLVER_AUTH_TOKEN ?? process.env.AUTH_TOKEN ?? null,
    approvalMode: parseApprovalMode(process.env.WALLET_APPROVAL_MODE),
    live: process.env.LISTING_TRADER_LIVE === "true",
    screenedLiveListing: process.env.TOKEN_SCREENING === "true" || (process.env.LISTING_TRADER_LIVE === "true" && process.env.TOKEN_SCREENING !== "false"),
  };
  const handle = createHandler(deps);
  const lines = createInterface({ input: process.stdin });
  lines.on("line", (line) => {
    void (async () => {
      if (!line.trim()) return;
      const reply = await handle(JSON.parse(line) as JsonRpcRequest);
      if (reply !== null) process.stdout.write(`${JSON.stringify(reply)}\n`);
    })();
  });
}
