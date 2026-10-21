import { PublicKey } from "@solana/web3.js";
import { decodeFunctionData, erc20Abi, type Hex } from "viem";
import { CHAINS } from "./chains.js";
import { assertTradableAction, type HyperliquidAction } from "./hyperliquid.js";

export const JUPITER_PROGRAM_ID = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4";
const SYSTEM_PROGRAM = "11111111111111111111111111111111";
const COMPUTE_BUDGET_PROGRAM = "ComputeBudget111111111111111111111111111111";
const TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA";
const TOKEN_2022_PROGRAM = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb";
const ATA_PROGRAM = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL";

export const SOLANA_BASE_PROGRAMS = [JUPITER_PROGRAM_ID, SYSTEM_PROGRAM, COMPUTE_BUDGET_PROGRAM, TOKEN_PROGRAM, TOKEN_2022_PROGRAM, ATA_PROGRAM] as const;

export const DEFAULT_MAX_VALUE_WEI = 2_000_000_000_000_000n;
export const WSOL_MINT = "So11111111111111111111111111111111111111112";
const SOLANA_QUOTE_MINTS = [WSOL_MINT, "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"] as const;
export const JITO_TIP_ACCOUNTS = [
  "96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmNhvrZU5",
  "HFqU5x63VTqvQss8hp11i4wVV8bD44PvwucfZ2bU7gRe",
  "Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLvLkY",
  "ADaUMid9yfUytqMBgopwjb2DTLSokTSzL1zt6iGPaS49",
  "DfXygSm4jCyNCybVYYK6DwvWqjKee8pbDmJGcLWNDXjh",
  "ADuUkR4vqLUMWXxW9gh6D6L8pMSawimctcNZ5pGwDcEt",
  "DttWaMuVvTiduZRnguLF7jNxTgiMBZ1hyAumKUiL2KRL",
  "3AVi9Tg9Uo68tJfuvoKvqKNWKkC5wPdSSdeBnizKZ6jT",
] as const;

export function wrappedSolAccount(owner: string): string {
  return associatedTokenAddress(owner, WSOL_MINT, TOKEN_PROGRAM);
}

export function associatedTokenAddress(owner: string, mint: string, program: string): string {
  return PublicKey.findProgramAddressSync(
    [new PublicKey(owner).toBuffer(), new PublicKey(program).toBuffer(), new PublicKey(mint).toBuffer()],
    new PublicKey(ATA_PROGRAM),
  )[0].toBase58();
}

export type EvmPurpose = "swap" | "approve" | "revoke" | "withdraw";
export type EvmApproval = { token: string; amount: bigint };

const EXACT_APPROVAL_LIMIT = 2n ** 255n;

export function evmChainIds(): number[] {
  return CHAINS.flatMap((chain) => (chain.chain.kind === "evm" ? [chain.chain.chainId] : []));
}

export function routersForChain(allowlist: Readonly<Record<number, readonly string[]>>, chainId: number): readonly string[] {
  return allowlist[chainId] ?? [];
}

type EvmSigningInput = {
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
  approval?: EvmApproval;
};

export function assertEvmSigning(input: EvmSigningInput): void {
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
  if (input.purpose === "approve" || input.purpose === "revoke") {
    assertApproval(input, to);
    return;
  }
  if (input.nativeSell !== true && input.value !== 0n) throw new Error("token sell must not attach native value");
  const routers = new Set(input.routers.map((item) => item.toLowerCase()));
  if (routers.size === 0) throw new Error("router allowlist is empty");
  if (!routers.has(to)) throw new Error("transaction destination is not an allowlisted router");
}

function assertApproval(input: EvmSigningInput, to: string): void {
  if (input.value !== 0n) throw new Error("approval must not attach native value");
  if (!input.approval || input.approval.token.toLowerCase() !== to) throw new Error("approval target is not the sold token");
  let spender = "";
  let amount = 0n;
  try {
    const decoded = decodeFunctionData({ abi: erc20Abi, data: input.data });
    if (decoded.functionName !== "approve") throw new Error("approval calldata is not approve");
    spender = String(decoded.args[0]).toLowerCase();
    amount = decoded.args[1];
  } catch {
    throw new Error("approval calldata is not approve");
  }
  if (input.purpose === "revoke") {
    if (amount !== 0n) throw new Error("revoke amount is not zero");
    return;
  }
  if (!input.allowHotApproval) throw new Error("approval is not cached");
  if (amount === 0n || amount >= EXACT_APPROVAL_LIMIT || amount !== input.approval.amount) throw new Error("approval amount is not the exact sell amount");
  if (!input.routers.some((item) => item.toLowerCase() === spender)) throw new Error("approval spender is not an allowlisted router");
}

export type SolanaInstruction = { program: string; accounts: readonly (string | null)[]; data: Uint8Array };
export type SolanaMessage = { feePayer: string; staticKeys: readonly string[]; instructions: readonly SolanaInstruction[] };

type SolanaContext = {
  payer: string;
  owners: ReadonlySet<string>;
  wrappedSol: string;
  staticKeys: readonly string[];
};

type InstructionRule = (ix: SolanaInstruction, context: SolanaContext) => void;

type ProgramRules = { discriminator: (data: Uint8Array) => string; rules: Readonly<Record<string, InstructionRule>> };

const firstByte = (data: Uint8Array) => (data.length === 0 ? "empty" : String(data[0]));

function account(ix: SolanaInstruction, index: number): string {
  const key = ix.accounts[index];
  if (!key) throw new Error("solana instruction account is not a static key");
  return key;
}

function ownedTokenAccount(destination: string, owners: Iterable<string>, mints: Iterable<string>): boolean {
  for (const owner of owners) {
    for (const mint of mints) {
      for (const program of [TOKEN_PROGRAM, TOKEN_2022_PROGRAM]) {
        try {
          if (associatedTokenAddress(owner, mint, program) === destination) return true;
        } catch {
          continue;
        }
      }
    }
  }
  return false;
}

function systemTransfer(ix: SolanaInstruction, context: SolanaContext): void {
  if (account(ix, 0) !== context.payer) throw new Error("solana native transfer source is not the hot wallet");
  const destination = account(ix, 1);
  const tips = new Set<string>(JITO_TIP_ACCOUNTS);
  if (!context.owners.has(destination) && destination !== context.wrappedSol && !tips.has(destination)) {
    throw new Error("solana native transfer destination is not allowlisted");
  }
}

function tokenTransfer(destinationIndex: number, mintIndex: number | null): InstructionRule {
  return (ix, context) => {
    const destination = account(ix, destinationIndex);
    if (context.owners.has(destination)) return;
    const mints = mintIndex === null ? [...context.staticKeys, ...SOLANA_QUOTE_MINTS] : [account(ix, mintIndex)];
    if (!ownedTokenAccount(destination, context.owners, mints)) throw new Error("solana token transfer destination is not allowlisted");
  };
}

function closeToPayer(ix: SolanaInstruction, context: SolanaContext): void {
  if (account(ix, 1) !== context.payer) throw new Error("solana close account destination is not the hot wallet");
}

function initializeForPayer(ix: SolanaInstruction, context: SolanaContext): void {
  if (ix.data.length < 33 || new PublicKey(ix.data.subarray(1, 33)).toBase58() !== context.payer) {
    throw new Error("solana token account owner is not the hot wallet");
  }
}

const TOKEN_RULES: ProgramRules = {
  discriminator: firstByte,
  rules: {
    "3": tokenTransfer(1, null),
    "9": closeToPayer,
    "12": tokenTransfer(2, 1),
    "17": () => {},
    "18": initializeForPayer,
  },
};

type JupiterLayout = { authority: number; destinations: readonly number[]; mint: number; platformFee: number };

function jupiterRoute(layout: JupiterLayout): InstructionRule {
  return (ix, context) => {
    if (account(ix, layout.authority) !== context.payer) throw new Error("jupiter transfer authority is not the hot wallet");
    if (account(ix, layout.platformFee) !== JUPITER_PROGRAM_ID) throw new Error("jupiter platform fee account is set");
    const mint = ix.accounts[layout.mint];
    const mints = mint ? [mint] : SOLANA_QUOTE_MINTS;
    for (const index of layout.destinations) {
      const destination = account(ix, index);
      if (destination === JUPITER_PROGRAM_ID && index !== layout.destinations[0]) continue;
      if (destination !== context.wrappedSol && !ownedTokenAccount(destination, [context.payer], mints)) {
        throw new Error("jupiter destination is not a hot wallet token account");
      }
    }
  };
}

const ROUTE = jupiterRoute({ authority: 1, destinations: [3, 4], mint: 5, platformFee: 6 });
const SHARED_ROUTE = jupiterRoute({ authority: 2, destinations: [6], mint: 8, platformFee: 9 });

// Account layouts follow the published Jupiter v6 IDL. Instructions not listed here, such as exactOutRoute and the v2 routes, are denied.
const SOLANA_INSTRUCTION_TABLE: Readonly<Record<string, ProgramRules>> = {
  [SYSTEM_PROGRAM]: {
    discriminator: (data) => (data.length >= 4 ? String(Buffer.from(data).readUInt32LE(0)) : "short"),
    rules: { "2": systemTransfer },
  },
  [COMPUTE_BUDGET_PROGRAM]: { discriminator: firstByte, rules: { "2": () => {}, "3": () => {}, "4": () => {} } },
  [TOKEN_PROGRAM]: TOKEN_RULES,
  [TOKEN_2022_PROGRAM]: TOKEN_RULES,
  [ATA_PROGRAM]: {
    discriminator: firstByte,
    rules: {
      "1": (ix, context) => {
        if (account(ix, 0) !== context.payer) throw new Error("associated account funder is not the hot wallet");
        if (!context.owners.has(account(ix, 2))) throw new Error("associated account owner is not allowlisted");
      },
    },
  },
  [JUPITER_PROGRAM_ID]: {
    discriminator: (data) => Buffer.from(data.subarray(0, 8)).toString("hex"),
    rules: {
      e517cb977ae3ad2a: ROUTE,
      "96564774a75d0e68": ROUTE,
      c1209b3341d69c81: SHARED_ROUTE,
      e6798f50779f6aaa: SHARED_ROUTE,
      b0d169a89a7d453e: SHARED_ROUTE,
    },
  },
};

export function assertSolanaSigning(input: {
  message: SolanaMessage;
  expectedFeePayer: string;
  allowlist: readonly string[];
  withdrawAllowlist: readonly string[];
}): void {
  const payer = input.expectedFeePayer;
  if (input.message.feePayer !== payer) throw new Error("solana fee payer is not the hot wallet");
  const allowed = new Set(input.allowlist);
  const context: SolanaContext = {
    payer,
    owners: new Set([payer, ...input.withdrawAllowlist]),
    wrappedSol: wrappedSolAccount(payer),
    staticKeys: input.message.staticKeys,
  };
  for (const ix of input.message.instructions) {
    if (!allowed.has(ix.program)) throw new Error(`solana program is not allowlisted ${ix.program}`);
    const table = SOLANA_INSTRUCTION_TABLE[ix.program];
    if (!table) continue;
    const kind = table.discriminator(ix.data);
    const rule = table.rules[kind];
    if (!rule) throw new Error(`solana instruction is not allowed ${ix.program} ${kind}`);
    rule(ix, context);
  }
}

export function assertHyperliquidSigning(action: { type: string }, maxLeverage: number): asserts action is HyperliquidAction {
  assertTradableAction(action);
  if (action.type === "updateLeverage" && action.leverage > maxLeverage) throw new Error("leverage exceeds the signing policy");
}

export type TurnkeyPolicyInput = {
  userId: string;
  wallets: { evm: string; solana: string; hyperliquid: string | null };
  solanaAddress: string;
  routers: Readonly<Record<number, readonly string[]>>;
  selectors?: readonly string[];
  maxValueWei: bigint;
  solanaPrograms?: readonly string[];
};

const TURNKEY_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const NIL_ID = "00000000-0000-0000-0000-000000000000";

function turnkeyId(value: string, name: string): string {
  if (!TURNKEY_ID.test(value) || value === NIL_ID) throw new Error(`turnkey ${name} is empty or has a placeholder`);
  return value;
}

export function turnkeyPolicyDocument(input: TurnkeyPolicyInput): unknown[] {
  const userId = turnkeyId(input.userId, "user id");
  const wallets = {
    evm: turnkeyId(input.wallets.evm, "evm wallet id"),
    solana: turnkeyId(input.wallets.solana, "solana wallet id"),
    hyperliquid: input.wallets.hyperliquid === null ? null : turnkeyId(input.wallets.hyperliquid, "hyperliquid wallet id"),
  };
  const routers: Record<number, string[]> = {};
  for (const id of evmChainIds()) {
    const list = [...new Set((input.routers[id] ?? []).map((item) => item.toLowerCase()))];
    if (list.some((item) => !/^0x[0-9a-f]{40}$/.test(item))) throw new Error("router address is invalid");
    if (list.length > 0) routers[id] = list;
  }
  const selectors = (input.selectors ?? []).map((item) => item.toLowerCase());
  if (selectors.some((item) => !/^0x[0-9a-f]{8}$/.test(item))) throw new Error("router selector is invalid");
  if (input.maxValueWei < 0n) throw new Error("max native value is negative");
  const solanaPrograms = [...new Set([...SOLANA_BASE_PROGRAMS, ...(input.solanaPrograms ?? [])])];
  for (const program of solanaPrograms) new PublicKey(program);
  return renderTurnkeyPolicy({
    userId,
    wallets,
    solanaAddress: new PublicKey(input.solanaAddress).toBase58(),
    wrappedSol: wrappedSolAccount(input.solanaAddress),
    routers,
    selectors,
    maxValueWei: input.maxValueWei,
    solanaPrograms,
  });
}

export function turnkeyPolicyTemplate(): unknown[] {
  return renderTurnkeyPolicy({
    userId: "<TURNKEY_API_USER_ID>",
    wallets: { evm: "<TURNKEY_EVM_WALLET_ID>", solana: "<TURNKEY_SOLANA_WALLET_ID>", hyperliquid: "<TURNKEY_HYPERLIQUID_WALLET_ID>" },
    solanaAddress: "<TURNKEY_SOLANA_ADDRESS>",
    wrappedSol: "<TURNKEY_SOLANA_WSOL_ACCOUNT>",
    routers: {},
    selectors: [],
    maxValueWei: DEFAULT_MAX_VALUE_WEI,
  });
}

function renderTurnkeyPolicy(input: {
  userId: string;
  wallets: { evm: string; solana: string; hyperliquid: string | null };
  solanaAddress: string;
  wrappedSol: string;
  routers: Readonly<Record<number, readonly string[]>>;
  selectors: readonly string[];
  maxValueWei: bigint;
  solanaPrograms?: readonly string[];
}): unknown[] {
  const clauses = Object.entries(input.routers).map(([id, list]) => `(eth.tx.chain_id == ${id} && (${list.map((item) => `eth.tx.to == '${item}'`).join(" || ")}))`);
  const evmMatch = clauses.length === 0 ? "eth.tx.chain_id == 0" : clauses.join(" || ");
  const selector = input.selectors.length === 0 ? "" : ` && (${input.selectors.map((item) => `eth.tx.data[0..10] == '${item}'`).join(" || ")})`;
  const programs = [...new Set([...SOLANA_BASE_PROGRAMS, ...(input.solanaPrograms ?? [])])].map((id) => `p == '${id}'`).join(" || ");
  const recipients = [input.solanaAddress, input.wrappedSol, ...JITO_TIP_ACCOUNTS].map((item) => `t.to == '${item}'`).join(" || ");
  const consensus = `approvers.any(user, user.id == '${input.userId}')`;
  const policies = [
    {
      policyName: "EVM swaps on allowlisted chains and routers",
      notes: `Scoped to the EVM wallet. Routers, selectors, and the ${input.maxValueWei} wei native cap come from turnkeyPolicyDocument. An empty router map matches no chain. Withdrawals and token approvals are a root-quorum ceremony, not this policy.`,
      effect: "EFFECT_ALLOW",
      consensus,
      condition: `activity.action == 'SIGN' && wallet.id == '${input.wallets.evm}' && (${evmMatch}) && eth.tx.value <= ${input.maxValueWei}${selector}`,
    },
    {
      policyName: "Solana swaps through Jupiter and the base programs",
      notes: "Scoped to the Solana wallet. Native transfers may pay only the hot wallet, its wrapped SOL account, or a Jito tip account. A transfer to a lookup-table address reads as ADDRESS_TABLE_LOOKUP and is denied. Top-level SPL transfers are denied, so SPL recovery is a root-quorum ceremony. Add each DEX program id Jupiter puts in the transaction, or Turnkey denies the sign.",
      effect: "EFFECT_ALLOW",
      consensus,
      condition: `activity.action == 'SIGN' && wallet.id == '${input.wallets.solana}' && solana.tx.program_keys.all(p, ${programs}) && solana.tx.transfers.all(t, ${recipients}) && solana.tx.spl_transfers.count() == 0`,
    },
  ];
  if (input.wallets.hyperliquid === null) return policies;
  return [
    ...policies,
    {
      policyName: "Hyperliquid agent typed data",
      notes: "Scoped to the agent wallet. The L1 action is hashed into connectionId before EIP-712, so this policy can pin the Agent domain and cannot see withdraw3. The app rejects non-tradable actions before it submits.",
      effect: "EFFECT_ALLOW",
      consensus,
      condition: `activity.action == 'SIGN' && wallet.id == '${input.wallets.hyperliquid}' && eth.eip_712.primary_type == 'Agent' && eth.eip_712.domain.name == 'Exchange' && eth.eip_712.domain.version == '1' && eth.eip_712.domain.chain_id == 1337 && eth.eip_712.message['source'] == 'a'`,
    },
  ];
}
