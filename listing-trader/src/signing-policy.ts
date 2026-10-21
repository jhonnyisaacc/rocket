import { decodeFunctionData, erc20Abi, type Hex } from "viem";
import { CHAINS } from "./chains.js";
import { assertTradableAction, type HyperliquidAction } from "./hyperliquid.js";

export const JUPITER_PROGRAM_ID = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4";

export const SOLANA_BASE_PROGRAMS = [
  JUPITER_PROGRAM_ID,
  "11111111111111111111111111111111",
  "ComputeBudget111111111111111111111111111111",
  "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
  "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
  "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
] as const;

export const DEFAULT_MAX_VALUE_WEI = 2_000_000_000_000_000n;

export type EvmPurpose = "swap" | "approve" | "withdraw";

export function evmChainIds(): number[] {
  return CHAINS.flatMap((chain) => (chain.chain.kind === "evm" ? [chain.chain.chainId] : []));
}

export function routersForChain(allowlist: Readonly<Record<number, readonly string[]>>, chainId: number): readonly string[] {
  return allowlist[chainId] ?? [];
}

export function assertEvmSigning(input: {
  chainId: number;
  to: string;
  data: Hex;
  value: bigint;
  purpose: EvmPurpose;
  routers: readonly string[];
  withdrawAllowlist: readonly string[];
  maxValueWei: bigint;
  allowHotApproval: boolean;
  nativeSell?: boolean;
  recoveryTokens?: readonly string[];
}): void {
  if (!evmChainIds().includes(input.chainId)) throw new Error("chain is not in the signing policy");
  if (input.value < 0n || input.value > input.maxValueWei) throw new Error("native value exceeds the signing policy");
  const to = input.to.toLowerCase();
  const allowlisted = (address: string) => input.withdrawAllowlist.some((item) => item.toLowerCase() === address.toLowerCase());
  if (input.purpose === "withdraw") {
    if (input.data === "0x") {
      if (!allowlisted(to)) throw new Error("withdraw destination is not allowlisted");
      return;
    }
    if (input.value !== 0n) throw new Error("token withdraw must not attach native value");
    let destination = "";
    try {
      const decoded = decodeFunctionData({ abi: erc20Abi, data: input.data });
      if (decoded.functionName !== "transfer") throw new Error("withdraw calldata is not a transfer");
      destination = String(decoded.args[0]);
    } catch (error) {
      if (error instanceof Error && error.message === "withdraw calldata is not a transfer") throw error;
      throw new Error("withdraw calldata is not a transfer");
    }
    if (!allowlisted(destination)) throw new Error("withdraw destination is not allowlisted");
    const recovery = new Set((input.recoveryTokens ?? []).map((item) => item.toLowerCase()));
    if (!recovery.has(to)) throw new Error("token is not in the recovery allowlist");
    return;
  }
  if (input.purpose === "swap" && input.nativeSell !== true && input.value !== 0n) {
    throw new Error("token sell must not attach native value");
  }
  const routers = new Set(input.routers.map((item) => item.toLowerCase()));
  if (routers.size === 0) throw new Error("router allowlist is empty");
  if (input.purpose === "swap") {
    if (!routers.has(to)) throw new Error("transaction destination is not an allowlisted router");
    return;
  }
  if (!input.allowHotApproval) throw new Error("approval is not cached");
  let spender = "";
  try {
    const decoded = decodeFunctionData({ abi: erc20Abi, data: input.data });
    if (decoded.functionName !== "approve") throw new Error("approval calldata is not approve");
    spender = String(decoded.args[0]).toLowerCase();
  } catch (error) {
    if (error instanceof Error && error.message === "approval calldata is not approve") throw error;
    throw new Error("approval calldata is not approve");
  }
  if (!routers.has(spender)) throw new Error("approval spender is not an allowlisted router");
}

export function assertSolanaSigning(input: {
  programIds: readonly string[];
  allowlist: readonly string[];
  feePayer: string;
  expectedFeePayer: string;
  nativeTransferTo: readonly string[];
  tokenTransferTo?: readonly string[];
  withdrawAllowlist: readonly string[];
}): void {
  if (input.feePayer !== input.expectedFeePayer) throw new Error("solana fee payer is not the hot wallet");
  const allowed = new Set(input.allowlist);
  for (const program of input.programIds) {
    if (!allowed.has(program)) throw new Error(`solana program is not allowlisted ${program}`);
  }
  const owners = new Set(input.withdrawAllowlist);
  owners.add(input.expectedFeePayer);
  for (const dest of input.nativeTransferTo) {
    if (!owners.has(dest)) throw new Error("solana native transfer destination is not allowlisted");
  }
  for (const dest of input.tokenTransferTo ?? []) {
    if (!input.withdrawAllowlist.includes(dest)) throw new Error("solana token transfer destination is not allowlisted");
  }
}

export function assertHyperliquidSigning(action: { type: string }, maxLeverage: number): asserts action is HyperliquidAction {
  assertTradableAction(action);
  if (action.type === "updateLeverage" && action.leverage > maxLeverage) throw new Error("leverage exceeds the signing policy");
}

export function turnkeyPolicyDocument(userId = "<TURNKEY_API_USER_ID>"): unknown[] {
  const chains = evmChainIds().map((id) => `eth.tx.chain_id == ${id}`).join(" || ");
  const programs = SOLANA_BASE_PROGRAMS.map((id) => `p == '${id}'`).join(" || ");
  const consensus = `approvers.any(user, user.id == '${userId}')`;
  return [
    {
      policyName: "EVM swaps on allowlisted chains and routers",
      notes: "Replace <ROUTER_ALLOWLIST> with the router addresses from ROUTER_ALLOWLIST_JSON. Native value cap is 2000000000000000 wei. One-time token approvals are a root-quorum ceremony, not this policy.",
      effect: "EFFECT_ALLOW",
      consensus,
      condition: `activity.kind == 'SIGN_TRANSACTION' && (${chains}) && eth.tx.value <= 2000000000000000 && (eth.tx.to == '<ROUTER_ALLOWLIST>')`,
    },
    {
      policyName: "Solana swaps through Jupiter and the base programs",
      notes: "Add each DEX program id Jupiter puts in the transaction, or Turnkey denies the sign. Program ids must be static. Address lookup tables cannot supply program ids.",
      effect: "EFFECT_ALLOW",
      consensus,
      condition: `activity.kind == 'SIGN_TRANSACTION' && solana.tx.program_keys.all(p, ${programs})`,
    },
    {
      policyName: "Hyperliquid agent typed data",
      notes: "The L1 action is hashed into connectionId before EIP-712, so this policy can pin the Agent domain and cannot see withdraw3. The app rejects non-tradable actions before it submits.",
      effect: "EFFECT_ALLOW",
      consensus,
      condition:
        "eth.eip_712.primary_type == 'Agent' && eth.eip_712.domain.name == 'Exchange' && eth.eip_712.domain.version == '1' && eth.eip_712.domain.chain_id == 1337 && eth.eip_712.message['source'] == 'a'",
    },
  ];
}
