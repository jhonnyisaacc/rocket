import { encode } from "@msgpack/msgpack";
import { keccak256 } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import type { Hex } from "viem";
import { Secret } from "./redact.js";

export type OrderAction = {
  type: "order";
  orders: Array<{
    a: number;
    b: boolean;
    p: string;
    s: string;
    r: boolean;
    t: { limit: { tif: "Ioc" | "Gtc" | "Alo" } };
  }>;
  grouping: "na";
};

export type CancelAction = {
  type: "cancel";
  cancels: Array<{ a: number; o: number }>;
};

export type LeverageAction = {
  type: "updateLeverage";
  asset: number;
  isCross: boolean;
  leverage: number;
};

export type HyperliquidAction = OrderAction | CancelAction | LeverageAction;

const FORBIDDEN = new Set([
  "withdraw3",
  "usdSend",
  "spotSend",
  "sendAsset",
  "agentSendAsset",
  "usdClassTransfer",
  "vaultTransfer",
  "approveAgent",
]);

export function assertTradableAction(action: { type: string }): asserts action is HyperliquidAction {
  if (FORBIDDEN.has(action.type)) {
    throw new Error(`refusing hyperliquid action ${action.type}`);
  }
  if (action.type !== "order" && action.type !== "cancel" && action.type !== "updateLeverage") {
    throw new Error(`unsupported hyperliquid action ${action.type}`);
  }
}

export function floatToWire(value: number): string {
  const rounded = value.toFixed(8);
  if (Math.abs(Number(rounded) - value) >= 1e-12) {
    throw new Error("floatToWire rounding");
  }
  const trimmed = rounded.replace(/\.?0+$/, "");
  return trimmed === "-0" || trimmed === "" ? "0" : trimmed;
}

export function buildOrder(input: {
  asset: number;
  isBuy: boolean;
  limitPx: number;
  size: number;
  reduceOnly?: boolean;
}): OrderAction {
  return {
    type: "order",
    orders: [
      {
        a: input.asset,
        b: input.isBuy,
        p: floatToWire(input.limitPx),
        s: floatToWire(input.size),
        r: input.reduceOnly ?? false,
        t: { limit: { tif: "Ioc" } },
      },
    ],
    grouping: "na",
  };
}

export function buildLeverage(asset: number, leverage: number): LeverageAction {
  if (!Number.isInteger(leverage) || leverage < 1) throw new Error("leverage must be an integer >= 1");
  return { type: "updateLeverage", asset, isCross: false, leverage };
}

export function cappedLimitPx(mark: number, isBuy: boolean, capBps: number): number {
  if (!(mark > 0)) throw new Error("mark price missing");
  if (!Number.isInteger(capBps) || capBps < 0) throw new Error("slippage cap is negative");
  const factor = capBps / 10_000;
  const raw = isBuy ? mark * (1 + factor) : mark * (1 - factor);
  if (!(raw > 0)) throw new Error("capped limit is not positive");
  return Number(raw.toFixed(8));
}

export async function assertApprovedAgent(url: string, master: string, agent: string, fetchImpl: typeof fetch, nowMs = Date.now()): Promise<void> {
  const response = await fetchImpl(`${url.replace(/\/$/, "")}/info`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ type: "extraAgents", user: master }),
    signal: AbortSignal.timeout(1500),
  });
  if (!response.ok) throw new Error("hyperliquid agent check failed");
  const body: unknown = await response.json();
  if (!Array.isArray(body)) throw new Error("hyperliquid agent is not approved");
  const agents = body.flatMap((row) => {
    if (typeof row !== "object" || row === null || typeof (row as { address?: unknown }).address !== "string") return [];
    const validUntil = (row as { validUntil?: unknown }).validUntil;
    return [{ address: (row as { address: string }).address, validUntil: typeof validUntil === "number" ? validUntil : null }];
  });
  if (!agentIsApproved(agents, agent, nowMs)) throw new Error("hyperliquid agent is not approved");
}

export function agentIsApproved(agents: readonly { address?: string; validUntil?: number | null }[], address: string, nowMs = Date.now()): boolean {
  const target = address.toLowerCase();
  return agents.some((agent) => {
    if (typeof agent.address !== "string" || agent.address.toLowerCase() !== target) return false;
    if (agent.validUntil == null) return true;
    return agent.validUntil > nowMs;
  });
}

function addressToBytes(address: string): Uint8Array {
  const hex = address.startsWith("0x") ? address.slice(2) : address;
  return Uint8Array.from(Buffer.from(hex, "hex"));
}

export function actionHash(action: HyperliquidAction, vaultAddress: string | null, nonce: number, expiresAfter: number | null): Hex {
  assertTradableAction(action);
  const packed = encode(action);
  const nonceBytes = Buffer.alloc(8);
  nonceBytes.writeBigUInt64BE(BigInt(nonce));
  const parts: Uint8Array[] = [packed, nonceBytes];
  if (vaultAddress === null) parts.push(Uint8Array.of(0));
  else parts.push(Uint8Array.of(1), addressToBytes(vaultAddress));
  if (expiresAfter !== null) {
    const expiry = Buffer.alloc(8);
    expiry.writeBigUInt64BE(BigInt(expiresAfter));
    parts.push(Uint8Array.of(0), expiry);
  }
  const data = Buffer.concat(parts.map((part) => Buffer.from(part)));
  return keccak256(data);
}

export async function signL1Action(privateKey: Secret, action: HyperliquidAction, nonce: number, isMainnet: boolean): Promise<{ r: Hex; s: Hex; v: number }> {
  assertTradableAction(action);
  const connectionId = actionHash(action, null, nonce, null);
  const account = privateKeyToAccount(privateKey.reveal() as `0x${string}`);
  const signature = await account.signTypedData({
    domain: {
      name: "Exchange",
      version: "1",
      chainId: 1337,
      verifyingContract: "0x0000000000000000000000000000000000000000",
    },
    types: {
      Agent: [
        { name: "source", type: "string" },
        { name: "connectionId", type: "bytes32" },
      ],
    },
    primaryType: "Agent",
    message: { source: isMainnet ? "a" : "b", connectionId },
  });
  return {
    r: `0x${signature.slice(2, 66)}` as Hex,
    s: `0x${signature.slice(66, 130)}` as Hex,
    v: Number.parseInt(signature.slice(130, 132), 16),
  };
}

export function orderSize(notionalUsd: number, markPx: number): number {
  if (!(markPx > 0)) throw new Error("mark price missing");
  return notionalUsd / markPx;
}
