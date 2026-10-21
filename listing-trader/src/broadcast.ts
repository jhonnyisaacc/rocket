import { Connection, PublicKey, SystemProgram, TransactionInstruction, TransactionMessage, VersionedTransaction } from "@solana/web3.js";
import bs58 from "bs58";
import { TransactionReceiptNotFoundError, createPublicClient, defineChain, encodeFunctionData, erc20Abi, http, keccak256, parseUnits, type Hex } from "viem";
import { z } from "zod";
import type { AppConfig } from "./config.js";
import type { Fill, RouteLeg, SendResult, TxOutcome, TxRecord } from "./domain.js";
import { chainByEvmId, chainByKey } from "./chains.js";
import { allowanceCovers, rememberApproval } from "./approvals.js";
import { firmJupiter, firmKyber, firmLifi, firmZeroEx } from "./aggregators.js";
import { BroadcastError, type SendRequest } from "./executor.js";
import { nextHyperliquidNonce, readExchangeResponse } from "./hyperliquid.js";
import type { EvmSignInput, TransactionSigner } from "./managed-signer.js";
import { evmNonces, isNonceRejection, type NonceManager } from "./nonce.js";
import { readLifi, readZeroEx } from "./quotes.js";
import { redactError } from "./redact.js";
import { sellBaseUnits } from "./routing.js";
import { isSolanaAddress } from "./signer.js";
import { JUPITER_PROGRAM_ID, WSOL_MINT } from "./signing-policy.js";

const NATIVE_ADDRESS = "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee";
const NATIVE_SELL = new Set([NATIVE_ADDRESS, "0x0000000000000000000000000000000000000000"]);

const allowanceSchema = z
  .object({
    issues: z.object({ allowance: z.object({ spender: z.string(), actual: z.string() }).nullish() }).optional(),
  })
  .passthrough();

const jupiterSwapSchema = z.object({ swapTransaction: z.string().min(1), lastValidBlockHeight: z.number().int().optional() }).passthrough();

type EvmCall = { from: Hex; to: Hex; data: Hex; value: bigint };

export type EvmReceipt = { status: "success" | "reverted"; gasUsed: bigint; effectiveGasPrice: bigint };

export type EvmRpc = {
  fees(): Promise<{ maxFeePerGas: bigint; maxPriorityFeePerGas: bigint }>;
  pendingNonce(address: Hex): Promise<number>;
  estimateGas(call: EvmCall): Promise<bigint>;
  simulate(call: EvmCall): Promise<void>;
  sendRaw(signed: Hex): Promise<void>;
  receipt(hash: Hex): Promise<EvmReceipt | null>;
  balance(token: string, owner: Hex): Promise<bigint>;
};

export type SolanaStatus = { err: unknown; confirmationStatus?: string | null } | null;

export type SolanaRpc = {
  simulate(tx: VersionedTransaction): Promise<unknown>;
  sendRaw(signed: Uint8Array): Promise<void>;
  latestBlockhash(): Promise<{ blockhash: string; lastValidBlockHeight: number }>;
  blockHeight(): Promise<number>;
  status(signature: string, searchHistory?: boolean): Promise<SolanaStatus>;
  received(signature: string, owner: string, mint: string): Promise<bigint | null>;
  lamports(owner: string): Promise<bigint>;
  tokenAccount(owner: string, mint: string): Promise<{ source: string; program: string } | null>;
};

export type SendIo = {
  evm(chainId: number, rpc: string): EvmRpc;
  solana(rpc: string): SolanaRpc;
  nonces: NonceManager;
  sleep(ms: number): Promise<void>;
  now(): number;
  confirmTimeoutMs: number;
  pollMs: number;
};

export type SendHooks = { io?: SendIo; onTx?: (tx: TxRecord) => Promise<void> };

type Confirmed = { records: TxRecord[]; received: bigint | null };
type Submitted = { record: TxRecord; confirm(): Promise<Confirmed> };
type PreparedLeg = { impact: number; minOut: bigint; quotedOut: bigint; submit(): Promise<Submitted> };
type PrepareLeg = (leg: RouteLeg, slippageBps: number, next: RouteLeg | undefined) => Promise<PreparedLeg>;

type Ctx = {
  config: AppConfig;
  signer: TransactionSigner;
  io: SendIo;
  onTx: (tx: TxRecord) => Promise<void>;
  fetchImpl: typeof fetch;
  secrets: readonly string[];
};

function rpcTransport(rpc: string) {
  return http(rpc, { retryCount: 0, timeout: 1_500 });
}

function evmChain(chainId: number, rpc: string) {
  const spec = chainByEvmId(chainId);
  return defineChain({
    id: chainId,
    name: spec?.key ?? String(chainId),
    nativeCurrency: { name: spec?.nativeSymbol ?? "ETH", symbol: spec?.nativeSymbol ?? "ETH", decimals: 18 },
    rpcUrls: { default: { http: [rpc] } },
  });
}

function viemRpc(chainId: number, rpc: string): EvmRpc {
  const client = createPublicClient({ chain: evmChain(chainId, rpc), transport: rpcTransport(rpc) });
  return {
    async fees() {
      const fees = await client.estimateFeesPerGas();
      return { maxFeePerGas: fees.maxFeePerGas, maxPriorityFeePerGas: fees.maxPriorityFeePerGas };
    },
    pendingNonce: (address) => client.getTransactionCount({ address, blockTag: "pending" }),
    estimateGas: (call) => client.estimateGas({ account: call.from, to: call.to, data: call.data, value: call.value }),
    async simulate(call) {
      if (typeof client.simulateCalls === "function") {
        const simulated = await client.simulateCalls({ account: call.from, calls: [{ to: call.to, data: call.data, value: call.value }] });
        if (simulated.results.some((result) => result.status !== "success")) throw new Error("simulation reverted");
        return;
      }
      await client.call({ account: call.from, to: call.to, data: call.data, value: call.value });
    },
    async sendRaw(signed) {
      await client.sendRawTransaction({ serializedTransaction: signed });
    },
    async receipt(hash) {
      try {
        const receipt = await client.getTransactionReceipt({ hash });
        return { status: receipt.status, gasUsed: receipt.gasUsed, effectiveGasPrice: receipt.effectiveGasPrice };
      } catch (error) {
        if (error instanceof TransactionReceiptNotFoundError) return null;
        throw error;
      }
    },
    balance(token, owner) {
      if (NATIVE_SELL.has(token.toLowerCase())) return client.getBalance({ address: owner });
      return client.readContract({ address: token as Hex, abi: erc20Abi, functionName: "balanceOf", args: [owner] });
    },
  };
}

type TxMeta = {
  fee: number;
  preBalances: number[];
  postBalances: number[];
  preTokenBalances?: Array<{ mint: string; owner?: string; uiTokenAmount: { amount: string } }> | null;
  postTokenBalances?: Array<{ mint: string; owner?: string; uiTokenAmount: { amount: string } }> | null;
};

export function receivedFromMeta(meta: TxMeta, owner: string, mint: string): bigint {
  const sum = (rows: TxMeta["preTokenBalances"]) =>
    (rows ?? []).filter((row) => row.owner === owner && row.mint === mint).reduce((total, row) => total + BigInt(row.uiTokenAmount.amount), 0n);
  let received = sum(meta.postTokenBalances) - sum(meta.preTokenBalances);
  if (mint === WSOL_MINT) received += BigInt(meta.postBalances[0] ?? 0) - BigInt(meta.preBalances[0] ?? 0) + BigInt(meta.fee);
  return received;
}

const TOKEN_PROGRAM = new PublicKey("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA");
const TOKEN_2022_PROGRAM = new PublicKey("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb");
const ATA_PROGRAM = new PublicKey("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL");

function web3Rpc(rpc: string): SolanaRpc {
  const connection = new Connection(rpc, "confirmed");
  return {
    async simulate(tx) {
      return (await connection.simulateTransaction(tx, { sigVerify: false, replaceRecentBlockhash: true })).value.err;
    },
    async sendRaw(signed) {
      await connection.sendRawTransaction(signed);
    },
    latestBlockhash: () => connection.getLatestBlockhash(),
    blockHeight: () => connection.getBlockHeight(),
    async status(signature, searchHistory = false) {
      const statuses = await connection.getSignatureStatuses([signature], { searchTransactionHistory: searchHistory });
      return statuses.value[0] ?? null;
    },
    async received(signature, owner, mint) {
      const tx = await connection.getTransaction(signature, { commitment: "confirmed", maxSupportedTransactionVersion: 0 });
      if (!tx?.meta) return null;
      return receivedFromMeta(tx.meta, owner, mint);
    },
    async lamports(owner) {
      return BigInt(await connection.getBalance(new PublicKey(owner)));
    },
    async tokenAccount(owner, mint) {
      for (const program of [TOKEN_PROGRAM, TOKEN_2022_PROGRAM]) {
        const accounts = await connection.getParsedTokenAccountsByOwner(new PublicKey(owner), { mint: new PublicKey(mint), programId: program });
        const source = accounts.value[0]?.pubkey;
        if (source) return { source: source.toBase58(), program: program.toBase58() };
      }
      return null;
    },
  };
}

export function defaultIo(config: AppConfig): SendIo {
  return {
    evm: viemRpc,
    solana: web3Rpc,
    nonces: evmNonces,
    sleep: (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
    now: Date.now,
    confirmTimeoutMs: config.confirmTimeoutMs,
    pollMs: 500,
  };
}

function digits(value: unknown): bigint | null {
  return typeof value === "string" && /^\d+$/.test(value) ? BigInt(value) : null;
}

function overCap(impact: number | null, capPct: number): boolean {
  return impact === null || impact > capPct;
}

export function executionSlippageBps(leg: RouteLeg, capBps: number): number {
  return Math.max(0, capBps - Math.ceil((leg.impactPct ?? 0) * 100));
}

export function ourMinOut(leg: RouteLeg, capBps: number): bigint {
  if (leg.priceUsd === null || leg.decimals === null || !(leg.priceUsd > 0) || !(leg.spentUsd > 0)) {
    throw new BroadcastError("no reference price for the minimum output", false);
  }
  const human = (leg.spentUsd / leg.priceUsd) * (1 - Math.min(Math.max(capBps, 0), 10_000) / 10_000);
  const scaled = Math.floor(human * 10 ** leg.decimals);
  if (!Number.isFinite(scaled) || scaled <= 0) throw new BroadcastError("no reference price for the minimum output", false);
  return BigInt(scaled);
}

function assertMinOut(provider: bigint | null, ours: bigint): bigint {
  if (provider === null) throw new BroadcastError("provider gave no checkable minimum output", false);
  if (provider < ours) throw new BroadcastError("provider minimum output is below ours", false);
  return provider;
}

function referenceFor(leg: RouteLeg): { spentUsd: number; priceUsd: number; decimals: number } | null {
  if (leg.priceUsd === null || leg.decimals === null) return null;
  return { spentUsd: leg.spentUsd, priceUsd: leg.priceUsd, decimals: leg.decimals };
}

function asHex(value: string): Hex {
  if (!/^0x[0-9a-fA-F]*$/.test(value)) throw new BroadcastError("firm quote has no transaction", false);
  return value as Hex;
}

function rememberIfFunded(raw: unknown, chainId: number, token: string, owner: string, needed: bigint, spenderHint: string): void {
  if (NATIVE_SELL.has(token.toLowerCase())) return;
  const parsed = allowanceSchema.safeParse(raw);
  const allowance = parsed.success ? parsed.data.issues?.allowance : undefined;
  if (allowance?.spender && /^\d+$/.test(allowance.actual)) {
    const actual = BigInt(allowance.actual);
    if (actual >= needed) {
      rememberApproval({ chainId, token, spender: allowance.spender, owner }, actual);
      return;
    }
  }
  const spender = allowance?.spender || spenderHint;
  if (spender && allowanceCovers({ chainId, token, spender, owner }, needed)) return;
  throw new BroadcastError("approval is not cached", false);
}

async function journal(ctx: Ctx, record: TxRecord): Promise<void> {
  try {
    await ctx.onTx(record);
  } catch (error) {
    throw new BroadcastError(`tx journal failed: ${redactError(error, ctx.secrets)}`, false);
  }
}

async function runLegs(prepare: PrepareLeg, legs: readonly RouteLeg[], capBps: number, ctx: Ctx): Promise<SendResult> {
  const txs: TxRecord[] = [];
  let sellAmount = legs[0]?.sellAmount ?? "0";
  for (const [index, base] of legs.entries()) {
    const leg = { ...base, sellAmount };
    const held = index > 0 ? { token: leg.sellAddress, amount: sellAmount } : null;
    let prepared: PreparedLeg;
    let sent: Submitted;
    try {
      prepared = await prepare(leg, executionSlippageBps(leg, capBps), legs[index + 1]);
      sent = await prepared.submit();
    } catch (error) {
      const broadcast = error instanceof BroadcastError && error.broadcast;
      const message = error instanceof BroadcastError ? error.message : redactError(error, ctx.secrets);
      if (held && !broadcast) return { venue: "chain", outcome: "landed", txs, held, shortfall: false, note: message };
      throw new BroadcastError(message, broadcast || txs.length > 0);
    }
    let confirmed: Confirmed;
    try {
      confirmed = await sent.confirm();
    } catch (error) {
      throw new BroadcastError(redactError(error, ctx.secrets), true);
    }
    const last = index === legs.length - 1;
    const records = [...confirmed.records];
    const winner = records[records.length - 1] ?? { ...sent.record, outcome: "pending" as const };
    const shortfall = last && winner.outcome === "landed" && confirmed.received !== null && confirmed.received < prepared.minOut;
    if (shortfall) records[records.length - 1] = { ...winner, note: `received ${confirmed.received} below minimum ${prepared.minOut}` };
    for (const record of records) await ctx.onTx(record).catch(() => undefined);
    txs.push(...records);
    if (winner.outcome !== "landed") return { venue: "chain", outcome: winner.outcome, txs, held, shortfall: false };
    if (last) return { venue: "chain", outcome: "landed", txs, held: null, shortfall };
    if (confirmed.received === null || confirmed.received <= 0n) {
      return { venue: "chain", outcome: "landed", txs, held: { token: leg.buyAddress, amount: "unknown" }, shortfall: false, note: "intermediate balance was not read" };
    }
    sellAmount = (confirmed.received < prepared.quotedOut ? confirmed.received : prepared.quotedOut).toString();
  }
  throw new BroadcastError("route has no signable leg", false);
}

function solanaSignature(signed: Uint8Array): string {
  const signature = VersionedTransaction.deserialize(signed).signatures[0];
  if (!signature) throw new BroadcastError("signed transaction has no signature", false);
  return bs58.encode(signature);
}

async function sendJito(fetchImpl: typeof fetch, url: string, signed: Uint8Array): Promise<void> {
  const response = await fetchImpl(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "sendTransaction", params: [Buffer.from(signed).toString("base64"), { encoding: "base64" }] }),
  });
  if (!response.ok) throw new Error("jito send failed");
  const body = z.object({ error: z.unknown().optional() }).passthrough().parse(await response.json());
  if (body.error) throw new Error("jito send failed");
}

function landedStatus(status: SolanaStatus | undefined): "landed" | "reverted" | null {
  if (!status || (status.confirmationStatus !== "confirmed" && status.confirmationStatus !== "finalized")) return null;
  return status.err ? "reverted" : "landed";
}

async function confirmSolana(rpc: SolanaRpc, signature: string, lastValidBlockHeight: number, io: SendIo): Promise<TxOutcome> {
  // Blockhash expiry normally decides first; the wall clock only stops a dead RPC from hanging the send.
  const deadline = io.now() + io.confirmTimeoutMs * 3;
  for (;;) {
    const status = await rpc.status(signature).catch(() => undefined);
    const landed = landedStatus(status);
    if (landed) return landed;
    const height = await rpc.blockHeight().catch(() => null);
    if (height !== null && height > lastValidBlockHeight) {
      const final = await rpc.status(signature, true).catch(() => undefined);
      if (final === null) return "expired";
      return landedStatus(final) ?? "pending";
    }
    if (io.now() >= deadline) return "pending";
    await io.sleep(io.pollMs);
  }
}

type SolanaCtx = Ctx & { rpc: SolanaRpc; owner: string };

async function submitSolana(
  ctx: SolanaCtx,
  tx: VersionedTransaction,
  lastValid: number | null,
  shape: { to: string; value: string; buyToken: string | null; jitoUrl: string | null },
): Promise<Submitted> {
  let signed: Uint8Array;
  let expiry: number;
  try {
    signed = await ctx.signer.signSolana(tx.serialize());
    expiry = lastValid ?? (await ctx.rpc.blockHeight()) + 150;
  } catch (error) {
    throw new BroadcastError(redactError(error, ctx.secrets), false);
  }
  const record: TxRecord = { chainKey: "solana", txHash: solanaSignature(signed), from: ctx.owner, to: shape.to, value: shape.value, outcome: "pending" };
  await journal(ctx, record);
  try {
    if (shape.jitoUrl) await sendJito(ctx.fetchImpl, shape.jitoUrl, signed);
    else await ctx.rpc.sendRaw(signed);
  } catch (error) {
    throw new BroadcastError(redactError(error, ctx.secrets), true);
  }
  return {
    record,
    async confirm() {
      const outcome = await confirmSolana(ctx.rpc, record.txHash, expiry, ctx.io);
      const received = outcome === "landed" && shape.buyToken ? await ctx.rpc.received(record.txHash, ctx.owner, shape.buyToken).catch(() => null) : null;
      return { records: [{ ...record, outcome }], received };
    },
  };
}

async function prepareSolanaLeg(ctx: SolanaCtx, leg: RouteLeg, slippageBps: number, capBps: number): Promise<PreparedLeg> {
  const { config, fetchImpl } = ctx;
  const quoted = await firmJupiter(
    config,
    { sellAddress: leg.sellAddress, buyAddress: leg.buyAddress, sellAmount: leg.sellAmount, chain: { kind: "solana" } },
    slippageBps,
    referenceFor(leg),
    fetchImpl,
  );
  if (quoted.signable === false || overCap(quoted.priceImpactPct, capBps / 100) || quoted.raw === undefined) {
    throw new BroadcastError("firm quote outside the slippage cap", false);
  }
  const minOut = assertMinOut(digits((quoted.raw as { otherAmountThreshold?: unknown }).otherAmountThreshold), ourMinOut(leg, capBps));
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (config.keys.jupiter) headers["x-api-key"] = config.keys.jupiter;
  const response = await fetchImpl(`${config.jupiterBase}/swap`, {
    method: "POST",
    headers,
    body: JSON.stringify({ quoteResponse: quoted.raw, userPublicKey: ctx.owner, wrapAndUnwrapSol: true, dynamicComputeUnitLimit: true }),
  });
  if (!response.ok) throw new BroadcastError("jupiter swap build failed", false);
  const parsed = jupiterSwapSchema.safeParse(await response.json());
  if (!parsed.success) throw new BroadcastError("jupiter swap build failed", false);
  const tx = VersionedTransaction.deserialize(Buffer.from(parsed.data.swapTransaction, "base64"));
  const simulated = await ctx.rpc.simulate(tx).catch(() => "unavailable");
  if (simulated) throw new BroadcastError("simulation rejected the transaction", false);
  return {
    impact: quoted.priceImpactPct ?? capBps,
    minOut,
    quotedOut: BigInt(quoted.buyAmount),
    submit: () =>
      submitSolana(ctx, tx, parsed.data.lastValidBlockHeight ?? null, { to: JUPITER_PROGRAM_ID, value: "0", buyToken: leg.buyAddress, jitoUrl: config.jitoUrl }),
  };
}

type EvmCtx = Ctx & { chainId: number; chainKey: string; owner: Hex; read: EvmRpc; send: EvmRpc };
type EvmTx = { to: Hex; data: Hex; value: bigint; gas: bigint | null; purpose: EvmSignInput["purpose"]; nativeSell?: boolean };

function evmRecord(ctx: EvmCtx, signed: Hex, tx: { to: Hex; value: bigint }): TxRecord {
  return { chainKey: ctx.chainKey, txHash: keccak256(signed), from: ctx.owner, to: tx.to, value: tx.value.toString(), outcome: "pending" };
}

async function broadcastEvm(ctx: EvmCtx, signed: Hex): Promise<void> {
  try {
    await ctx.send.sendRaw(signed);
  } catch (error) {
    const message = redactError(error, ctx.secrets);
    if (/already known/i.test(message)) return;
    throw new BroadcastError(message, !isNonceRejection(message));
  }
}

export function bumpFee(fee: bigint): bigint {
  const step = (fee * 125n + 999n) / 1000n;
  return fee + (step > 0n ? step : 1n);
}

async function pollReceipts(ctx: EvmCtx, hashes: readonly string[], deadline: number): Promise<{ hash: string; receipt: EvmReceipt } | null> {
  for (;;) {
    for (const hash of hashes) {
      const receipt = await ctx.read.receipt(hash as Hex).catch(() => null);
      if (receipt) return { hash, receipt };
    }
    if (ctx.io.now() >= deadline) return null;
    await ctx.io.sleep(ctx.io.pollMs);
  }
}

async function replaceEvm(ctx: EvmCtx, input: EvmSignInput): Promise<TxRecord | null> {
  const current = await ctx.read.fees().catch(() => null);
  const maxPriorityFeePerGas = [bumpFee(input.maxPriorityFeePerGas), current?.maxPriorityFeePerGas ?? 0n].reduce((a, b) => (a > b ? a : b));
  const maxFeePerGas = [bumpFee(input.maxFeePerGas), current?.maxFeePerGas ?? 0n, maxPriorityFeePerGas].reduce((a, b) => (a > b ? a : b));
  let signed: Hex;
  try {
    signed = await ctx.signer.signEvm({ ...input, maxFeePerGas, maxPriorityFeePerGas });
  } catch {
    return null;
  }
  const record = evmRecord(ctx, signed, input);
  try {
    await journal(ctx, record);
    await broadcastEvm(ctx, signed);
  } catch (error) {
    if (error instanceof BroadcastError && !error.broadcast) {
      await ctx.onTx({ ...record, outcome: "expired" }).catch(() => undefined);
      return null;
    }
    return record;
  }
  return record;
}

async function confirmEvm(ctx: EvmCtx, input: EvmSignInput, first: TxRecord, before: bigint | null, buyToken: string | null): Promise<Confirmed> {
  const records = [first];
  let found = await pollReceipts(ctx, [first.txHash], ctx.io.now() + ctx.io.confirmTimeoutMs);
  if (!found) {
    const replacement = await replaceEvm(ctx, input);
    if (replacement) records.push(replacement);
    found = await pollReceipts(ctx, records.map((record) => record.txHash), ctx.io.now() + ctx.io.confirmTimeoutMs);
  }
  if (!found) return { records: records.map((record) => ({ ...record, outcome: "pending" })), received: null };
  const outcome: TxOutcome = found.receipt.status === "success" ? "landed" : "reverted";
  const losers = records.filter((record) => record.txHash !== found.hash).map((record) => ({ ...record, outcome: "expired" as const }));
  const won = records.find((record) => record.txHash === found.hash) ?? first;
  let received: bigint | null = null;
  if (outcome === "landed" && buyToken && before !== null) {
    const gasCost = NATIVE_SELL.has(buyToken.toLowerCase()) ? found.receipt.gasUsed * found.receipt.effectiveGasPrice : 0n;
    received = await ctx.read
      .balance(buyToken, ctx.owner)
      .then((after) => after - before + gasCost)
      .catch(() => null);
  }
  return { records: [...losers, { ...won, outcome }], received };
}

async function submitEvm(ctx: EvmCtx, tx: EvmTx, buyToken: string | null): Promise<Submitted> {
  const call = { from: ctx.owner, to: tx.to, data: tx.data, value: tx.value };
  let fees: { maxFeePerGas: bigint; maxPriorityFeePerGas: bigint };
  let gas: bigint;
  let before: bigint | null;
  try {
    [fees, gas, before] = await Promise.all([
      ctx.read.fees(),
      tx.gas ?? ctx.read.estimateGas(call),
      buyToken ? ctx.read.balance(buyToken, ctx.owner).catch(() => null) : Promise.resolve(null),
    ]);
  } catch (error) {
    throw new BroadcastError(redactError(error, ctx.secrets), false);
  }
  try {
    await ctx.read.simulate(call);
  } catch {
    throw new BroadcastError("simulation rejected the transaction", false);
  }
  const sent = await ctx.io.nonces.use(ctx.chainId, ctx.owner, () => ctx.read.pendingNonce(ctx.owner), async (nonce) => {
    const input: EvmSignInput = {
      chainId: ctx.chainId,
      to: tx.to,
      data: tx.data,
      value: tx.value,
      purpose: tx.purpose,
      nativeSell: tx.nativeSell,
      gas,
      nonce,
      ...fees,
    };
    let signed: Hex;
    try {
      signed = await ctx.signer.signEvm(input);
    } catch (error) {
      throw new BroadcastError(redactError(error, ctx.secrets), false);
    }
    const record = evmRecord(ctx, signed, tx);
    await journal(ctx, record);
    await broadcastEvm(ctx, signed);
    return { input, record };
  });
  return { record: sent.record, confirm: () => confirmEvm(ctx, sent.input, sent.record, before, buyToken) };
}

type BuiltEvm = { to: Hex; data: Hex; value: bigint; gas: bigint | null; impact: number; raw: unknown; minOut: bigint | null; quotedOut: bigint };

async function evmTransaction(ctx: EvmCtx, leg: RouteLeg, capPct: number, slippageBps: number, provider: string | undefined): Promise<BuiltEvm> {
  const { config, chainId, owner: taker, fetchImpl } = ctx;
  const hop = { sellAddress: leg.sellAddress, buyAddress: leg.buyAddress, sellAmount: leg.sellAmount, chain: { kind: "evm" as const, chainId } };
  const reference = referenceFor(leg);
  const spec = chainByEvmId(chainId);
  const selected = provider ?? (spec?.aggregator === "lifi" ? "lifi" : "zeroex");
  if (selected === "kyberswap") {
    const quoted = await firmKyber(config, hop, chainId, taker, reference, fetchImpl, slippageBps);
    if (overCap(quoted.priceImpactPct, capPct) || !quoted.prepared?.to || !quoted.prepared.data) {
      throw new BroadcastError("firm quote outside the slippage cap", false);
    }
    const built = (quoted.raw as { build?: { amountOut?: string | null; slippageBps?: number } } | undefined)?.build;
    const amountOut = digits(built?.amountOut);
    return {
      to: asHex(quoted.prepared.to),
      data: asHex(quoted.prepared.data),
      value: BigInt(quoted.prepared.value || "0"),
      gas: null,
      impact: quoted.priceImpactPct ?? capPct + 1,
      raw: quoted.raw,
      minOut: amountOut === null || built?.slippageBps !== slippageBps ? null : (amountOut * BigInt(10_000 - slippageBps)) / 10_000n,
      quotedOut: BigInt(quoted.buyAmount),
    };
  }
  if (selected === "lifi") {
    const quoted = await firmLifi(config, hop, chainId, taker, reference, fetchImpl, slippageBps);
    if (quoted.raw === undefined) throw new BroadcastError("firm quote outside the slippage cap", false);
    const parsed = readLifi(quoted.raw as Parameters<typeof readLifi>[0], reference, chainId);
    if (!parsed.sameChain || overCap(parsed.priceImpactPct, capPct) || parsed.priceImpactPct === null) {
      throw new BroadcastError("firm quote outside the slippage cap", false);
    }
    const raw = quoted.raw as { transactionRequest?: { to?: string; data?: string; value?: string; gasLimit?: string }; estimate?: { toAmountMin?: unknown } };
    const request = raw.transactionRequest;
    if (!request?.to || !request.data) throw new BroadcastError("firm quote has no transaction", false);
    return {
      to: asHex(request.to),
      data: asHex(request.data),
      value: BigInt(request.value ?? "0"),
      gas: request.gasLimit ? BigInt(request.gasLimit) : null,
      impact: parsed.priceImpactPct,
      raw: quoted.raw,
      minOut: digits(raw.estimate?.toAmountMin),
      quotedOut: BigInt(parsed.buyAmount),
    };
  }
  if (selected !== "zeroex") throw new BroadcastError("provider is not signable", false);
  const quoted = await firmZeroEx(config, hop, chainId, taker, reference, fetchImpl, slippageBps);
  if (quoted.raw === undefined) throw new BroadcastError("firm quote outside the slippage cap", false);
  const parsed = readZeroEx(quoted.raw as Parameters<typeof readZeroEx>[0], reference);
  if (overCap(parsed.priceImpactPct, capPct) || parsed.priceImpactPct === null || !parsed.to || !parsed.data) {
    throw new BroadcastError("firm quote outside the slippage cap", false);
  }
  const raw = quoted.raw as { transaction?: { gas?: string }; minBuyAmount?: unknown };
  return {
    to: asHex(parsed.to),
    data: asHex(parsed.data),
    value: BigInt(parsed.value || "0"),
    gas: raw.transaction?.gas ? BigInt(raw.transaction.gas) : null,
    impact: parsed.priceImpactPct,
    raw: quoted.raw,
    minOut: digits(raw.minBuyAmount),
    quotedOut: BigInt(parsed.buyAmount),
  };
}

async function prepareEvmLeg(ctx: EvmCtx, leg: RouteLeg, slippageBps: number, next: RouteLeg | undefined, capBps: number, provider: string | undefined): Promise<PreparedLeg> {
  const built = await evmTransaction(ctx, leg, capBps / 100, slippageBps, provider);
  const minOut = assertMinOut(built.minOut, ourMinOut(leg, capBps));
  rememberIfFunded(built.raw, ctx.chainId, leg.sellAddress, ctx.owner, BigInt(leg.sellAmount), built.to);
  if (next && !NATIVE_SELL.has(next.sellAddress.toLowerCase())) {
    if (!allowanceCovers({ chainId: ctx.chainId, token: next.sellAddress, spender: built.to, owner: ctx.owner }, built.quotedOut)) {
      throw new BroadcastError("approval is not cached", false);
    }
  }
  return {
    impact: built.impact,
    minOut,
    quotedOut: built.quotedOut,
    submit: () =>
      submitEvm(
        ctx,
        { to: built.to, data: built.data, value: built.value, gas: built.gas, purpose: "swap", nativeSell: NATIVE_SELL.has(leg.sellAddress.toLowerCase()) },
        leg.buyAddress,
      ),
  };
}

async function sendHypercore(ctx: Ctx, request: SendRequest): Promise<SendResult> {
  const { config, signer, fetchImpl, secrets } = ctx;
  if (request.hyperliquidActions.length === 0) throw new BroadcastError("hyperliquid action missing", false);
  const txs: TxRecord[] = [];
  let fill: Fill | null = null;
  let note: string | undefined;
  for (const action of request.hyperliquidActions) {
    const order = action.type === "order";
    const nonce = nextHyperliquidNonce();
    let signature;
    try {
      signature = await signer.signHyperliquid(action, nonce, !config.hyperliquidUrl.includes("testnet"));
    } catch (error) {
      throw new BroadcastError(redactError(error, secrets), false);
    }
    const record: TxRecord = { chainKey: "hypercore", txHash: `hl:${nonce}`, from: config.hyperliquidAccount ?? "", to: action.type, value: "0", outcome: "pending" };
    await journal(ctx, record);
    let body: unknown;
    try {
      const response = await fetchImpl(`${config.hyperliquidUrl.replace(/\/$/, "")}/exchange`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ action, nonce, signature, vaultAddress: null }),
      });
      if (!response.ok) throw new Error(`hyperliquid exchange returned ${response.status}`);
      body = await response.json();
    } catch (error) {
      throw new BroadcastError(redactError(error, secrets), order);
    }
    const parsed = readExchangeResponse(body);
    if (parsed.status === "err") {
      await ctx.onTx({ ...record, outcome: "reverted", note: parsed.error }).catch(() => undefined);
      throw new BroadcastError(`hyperliquid rejected the action: ${parsed.error}`, false);
    }
    if (!order) {
      txs.push({ ...record, outcome: "landed" });
      continue;
    }
    if (parsed.statuses.some((status) => status.resting !== undefined)) {
      await ctx.onTx({ ...record, note: "ioc order is resting" }).catch(() => undefined);
      throw new BroadcastError("hyperliquid ioc order is resting", true);
    }
    const filled = parsed.statuses.find((status) => status.filled)?.filled;
    if (filled && Number(filled.totalSz) > 0) {
      fill = filled;
      txs.push({ ...record, outcome: "landed", note: `filled ${filled.totalSz} at ${filled.avgPx}` });
    } else {
      note = parsed.statuses.find((status) => status.error)?.error ?? "order not filled";
      txs.push({ ...record, outcome: "reverted", note });
    }
  }
  for (const record of txs) await ctx.onTx(record).catch(() => undefined);
  return { venue: "hypercore", txs, fill, note };
}

function evmContext(ctx: Ctx, chainKey: string, rpc: string, sendRpc: string): EvmCtx {
  const spec = chainByKey(chainKey);
  if (!spec || spec.chain.kind !== "evm") throw new BroadcastError("evm chain missing", false);
  const owner = ctx.signer.evmAddress();
  if (!owner) throw new BroadcastError("evm signer is not loaded", false);
  const chainId = spec.chain.chainId;
  return { ...ctx, chainId, chainKey, owner: owner as Hex, read: ctx.io.evm(chainId, rpc), send: ctx.io.evm(chainId, sendRpc) };
}

function solanaContext(ctx: Ctx, rpc: string): SolanaCtx {
  const owner = ctx.signer.solanaAddress();
  if (!owner) throw new BroadcastError("solana signer is not loaded", false);
  return { ...ctx, rpc: ctx.io.solana(rpc), owner };
}

export async function broadcastRoute(
  config: AppConfig,
  signer: TransactionSigner | null,
  request: SendRequest,
  capPct: number,
  fetchImpl: typeof fetch = fetch,
  secrets: readonly string[] = [],
  hooks: SendHooks = {},
): Promise<SendResult> {
  if (!signer) throw new BroadcastError("signer is not loaded", false);
  const ctx: Ctx = { config, signer, io: hooks.io ?? defaultIo(config), onTx: hooks.onTx ?? (async () => undefined), fetchImpl, secrets };
  if (request.kind === "hypercore") return sendHypercore(ctx, request);
  if (request.legs.length === 0) throw new BroadcastError("route has no signable leg", false);
  const capBps = Math.round(capPct * 100);
  if (request.kind === "solana") {
    const rpc = config.rpcByChainKey.solana;
    if (!rpc) throw new BroadcastError("solana rpc is not configured", false);
    const solana = solanaContext(ctx, rpc);
    return runLegs((leg, slippageBps) => prepareSolanaLeg(solana, leg, slippageBps, capBps), request.legs, capBps, ctx);
  }
  if (request.chain.kind !== "evm") throw new BroadcastError("evm chain missing", false);
  const spec = chainByEvmId(request.chain.chainId);
  const rpc = spec ? config.rpcByChainKey[spec.key] : undefined;
  if (!spec || !rpc) throw new BroadcastError("evm rpc is not configured", false);
  if (spec.liveSend === "disabled") throw new BroadcastError(spec.gap ?? "live send disabled", false);
  const evm = evmContext(ctx, spec.key, rpc, config.mevRpcByChainId[request.chain.chainId] ?? rpc);
  return runLegs((leg, slippageBps, next) => prepareEvmLeg(evm, leg, slippageBps, next, capBps, request.provider), request.legs, capBps, ctx);
}

export async function lookupAgedTx(config: AppConfig, chainKey: string, txHash: string, io: SendIo = defaultIo(config)): Promise<TxOutcome | null> {
  const spec = chainByKey(chainKey);
  const rpc = config.rpcByChainKey[chainKey];
  if (!spec || !rpc) return null;
  if (spec.chain.kind === "evm") {
    const receipt = await io.evm(spec.chain.chainId, rpc).receipt(txHash as Hex);
    if (!receipt) return "pending";
    return receipt.status === "success" ? "landed" : "reverted";
  }
  if (spec.chain.kind === "solana") {
    const status = await io.solana(rpc).status(txHash, true);
    if (status === null) return "expired";
    return landedStatus(status) ?? "pending";
  }
  return null;
}

type TransferInput = {
  config: AppConfig;
  signer: TransactionSigner;
  chainKey: string;
  to: string;
  amount: number;
  secrets?: readonly string[];
} & SendHooks;

function transferContext(input: TransferInput): Ctx {
  return {
    config: input.config,
    signer: input.signer,
    io: input.io ?? defaultIo(input.config),
    onTx: input.onTx ?? (async () => undefined),
    fetchImpl: fetch,
    secrets: input.secrets ?? [],
  };
}

async function finalRecord(submitted: Submitted, ctx: Ctx): Promise<TxRecord> {
  const confirmed = await submitted.confirm();
  for (const record of confirmed.records) await ctx.onTx(record).catch(() => undefined);
  return confirmed.records[confirmed.records.length - 1] ?? submitted.record;
}

export async function withdrawNative(input: TransferInput): Promise<TxRecord> {
  const spec = chainByKey(input.chainKey);
  if (!spec) throw new Error("unknown chain");
  const rpc = input.config.rpcByChainKey[input.chainKey];
  if (!rpc) throw new Error("rpc is not configured");
  const ctx = transferContext(input);
  if (spec.chain.kind === "solana") {
    if (!isSolanaAddress(input.to)) throw new Error("destination is not a solana address");
    const solana = solanaContext(ctx, rpc);
    const lamports = BigInt(sellBaseUnits(input.amount, 9));
    const reserve = BigInt(sellBaseUnits(spec.minNativeReserve, 9));
    if (lamports <= 0n || (await solana.rpc.lamports(solana.owner)) - lamports < reserve) throw new Error("withdraw would spend the native reserve");
    const { blockhash, lastValidBlockHeight } = await solana.rpc.latestBlockhash();
    const message = new TransactionMessage({
      payerKey: new PublicKey(solana.owner),
      recentBlockhash: blockhash,
      instructions: [SystemProgram.transfer({ fromPubkey: new PublicKey(solana.owner), toPubkey: new PublicKey(input.to), lamports: Number(lamports) })],
    }).compileToV0Message();
    const submitted = await submitSolana(solana, new VersionedTransaction(message), lastValidBlockHeight, { to: input.to, value: lamports.toString(), buyToken: null, jitoUrl: null });
    return finalRecord(submitted, ctx);
  }
  if (spec.chain.kind !== "evm") throw new Error("withdraw is not available on this venue");
  if (!/^0x[0-9a-fA-F]{40}$/.test(input.to)) throw new Error("destination is not an evm address");
  const evm = evmContext(ctx, input.chainKey, rpc, rpc);
  const value = BigInt(sellBaseUnits(input.amount, 18));
  const reserve = BigInt(sellBaseUnits(spec.minNativeReserve, 18));
  if (value <= 0n || (await evm.read.balance(NATIVE_ADDRESS, evm.owner)) - value < reserve) throw new Error("withdraw would spend the native reserve");
  const submitted = await submitEvm(evm, { to: input.to as Hex, data: "0x", value, gas: null, purpose: "withdraw" }, null);
  return finalRecord(submitted, ctx);
}

export function associatedTokenAccount(owner: PublicKey, mint: PublicKey, program: PublicKey): PublicKey {
  return PublicKey.findProgramAddressSync([owner.toBuffer(), program.toBuffer(), mint.toBuffer()], ATA_PROGRAM)[0];
}

export function tokenRecoveryInstructions(input: {
  payer: PublicKey;
  destinationOwner: PublicKey;
  mint: PublicKey;
  source: PublicKey;
  program: PublicKey;
  amount: bigint;
  decimals: number;
}): TransactionInstruction[] {
  const ata = associatedTokenAccount(input.destinationOwner, input.mint, input.program);
  const data = Buffer.alloc(10);
  data.writeUInt8(12, 0);
  data.writeBigUInt64LE(input.amount, 1);
  data.writeUInt8(input.decimals, 9);
  return [
    new TransactionInstruction({
      programId: ATA_PROGRAM,
      data: Buffer.from([1]),
      keys: [
        { pubkey: input.payer, isSigner: true, isWritable: true },
        { pubkey: ata, isSigner: false, isWritable: true },
        { pubkey: input.destinationOwner, isSigner: false, isWritable: false },
        { pubkey: input.mint, isSigner: false, isWritable: false },
        { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
        { pubkey: input.program, isSigner: false, isWritable: false },
      ],
    }),
    new TransactionInstruction({
      programId: input.program,
      keys: [
        { pubkey: input.source, isSigner: false, isWritable: true },
        { pubkey: input.mint, isSigner: false, isWritable: false },
        { pubkey: ata, isSigner: false, isWritable: true },
        { pubkey: input.payer, isSigner: true, isWritable: false },
      ],
      data,
    }),
  ];
}

export async function recoverToken(input: TransferInput & { mint: string; decimals: number }): Promise<TxRecord> {
  const spec = chainByKey(input.chainKey);
  if (!spec) throw new Error("unknown chain");
  const rpc = input.config.rpcByChainKey[input.chainKey];
  if (!rpc) throw new Error("rpc is not configured");
  const ctx = transferContext(input);
  if (spec.chain.kind === "evm") {
    if (!/^0x[0-9a-fA-F]{40}$/.test(input.to) || !/^0x[0-9a-fA-F]{40}$/.test(input.mint)) throw new Error("destination is not an evm address");
    const evm = evmContext(ctx, input.chainKey, rpc, rpc);
    const data = encodeFunctionData({ abi: erc20Abi, functionName: "transfer", args: [input.to as Hex, parseUnits(String(input.amount), input.decimals)] });
    const submitted = await submitEvm(evm, { to: input.mint as Hex, data, value: 0n, gas: null, purpose: "withdraw", nativeSell: false }, null);
    return finalRecord(submitted, ctx);
  }
  if (spec.chain.kind !== "solana" || !input.signer.solanaAddress() || !isSolanaAddress(input.to) || !isSolanaAddress(input.mint)) {
    throw new Error("destination is not a solana address");
  }
  const solana = solanaContext(ctx, rpc);
  const found = await solana.rpc.tokenAccount(solana.owner, input.mint);
  if (!found) throw new Error("token account was not found");
  const ownerKey = new PublicKey(solana.owner);
  const instructions = tokenRecoveryInstructions({
    payer: ownerKey,
    destinationOwner: new PublicKey(input.to),
    mint: new PublicKey(input.mint),
    source: new PublicKey(found.source),
    program: new PublicKey(found.program),
    amount: BigInt(sellBaseUnits(input.amount, input.decimals)),
    decimals: input.decimals,
  });
  const { blockhash, lastValidBlockHeight } = await solana.rpc.latestBlockhash();
  const message = new TransactionMessage({ payerKey: ownerKey, recentBlockhash: blockhash, instructions }).compileToV0Message();
  const submitted = await submitSolana(solana, new VersionedTransaction(message), lastValidBlockHeight, { to: input.to, value: "0", buyToken: null, jitoUrl: null });
  return finalRecord(submitted, ctx);
}
