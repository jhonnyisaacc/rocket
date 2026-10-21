import { Connection, PublicKey, SystemProgram, TransactionInstruction, TransactionMessage, VersionedTransaction } from "@solana/web3.js";
import { createPublicClient, defineChain, encodeFunctionData, erc20Abi, http, parseUnits, type Hex } from "viem";
import { z } from "zod";
import type { AppConfig } from "./config.js";
import type { RouteLeg } from "./domain.js";
import { chainByEvmId, chainByKey } from "./chains.js";
import { allowanceCovers, rememberApproval } from "./approvals.js";
import { firmKyber, firmLifi, firmZeroEx } from "./aggregators.js";
import { quoteHop } from "./clients.js";
import { BroadcastError, type SendRequest } from "./executor.js";
import type { TransactionSigner } from "./managed-signer.js";
import { readLifi, readZeroEx } from "./quotes.js";
import { redactError } from "./redact.js";
import { combineHopImpact, sellBaseUnits } from "./routing.js";
import { isSolanaAddress } from "./signer.js";

const NATIVE_SELL = new Set(["0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee", "0x0000000000000000000000000000000000000000"]);

const allowanceSchema = z
  .object({
    issues: z.object({ allowance: z.object({ spender: z.string(), actual: z.string() }).nullish() }).optional(),
  })
  .passthrough();

const jupiterSwapSchema = z.object({ swapTransaction: z.string().min(1) }).passthrough();

function referenceFor(leg: RouteLeg): { spentUsd: number; priceUsd: number; decimals: number } | null {
  if (leg.priceUsd === null || leg.decimals === null) return null;
  return { spentUsd: leg.spentUsd, priceUsd: leg.priceUsd, decimals: leg.decimals };
}

function overCap(impact: number | null, capPct: number): boolean {
  return impact === null || impact > capPct;
}

function combinedImpact(impacts: number[], capPct: number): void {
  const total = impacts.reduce((acc, impact) => combineHopImpact(acc, impact), 0);
  if (total > capPct) throw new BroadcastError("firm quote outside the slippage cap", false);
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

async function jupiterTransaction(
  config: AppConfig,
  leg: RouteLeg,
  user: string,
  capPct: number,
  fetchImpl: typeof fetch,
): Promise<{ transaction: string; impact: number }> {
  const quoted = await quoteHop(
    config,
    { sellAddress: leg.sellAddress, buyAddress: leg.buyAddress, sellAmount: leg.sellAmount, chain: { kind: "solana" } },
    null,
    fetchImpl,
  );
  if (quoted.provider !== "jupiter" || quoted.signable === false || overCap(quoted.priceImpactPct, capPct) || quoted.raw === undefined) {
    throw new BroadcastError("firm quote outside the slippage cap", false);
  }
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (config.keys.jupiter) headers["x-api-key"] = config.keys.jupiter;
  const response = await fetchImpl(`${config.jupiterBase}/swap`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      quoteResponse: quoted.raw,
      userPublicKey: user,
      slippageBps: config.maxSlippageBps,
      wrapAndUnwrapSol: true,
      dynamicComputeUnitLimit: true,
    }),
  });
  if (!response.ok) throw new BroadcastError("jupiter swap build failed", false);
  const parsed = jupiterSwapSchema.safeParse(await response.json());
  if (!parsed.success) throw new BroadcastError("jupiter swap build failed", false);
  return { transaction: parsed.data.swapTransaction, impact: quoted.priceImpactPct ?? capPct + 1 };
}

type BuiltEvm = { to: Hex; data: Hex; value: bigint; gas: bigint | null; impact: number; raw: unknown };

async function evmTransaction(
  config: AppConfig,
  leg: RouteLeg,
  chainId: number,
  taker: string,
  capPct: number,
  fetchImpl: typeof fetch,
  provider: string | undefined,
): Promise<BuiltEvm> {
  const hop = { sellAddress: leg.sellAddress, buyAddress: leg.buyAddress, sellAmount: leg.sellAmount, chain: { kind: "evm" as const, chainId } };
  const reference = referenceFor(leg);
  const spec = chainByEvmId(chainId);
  const selected = provider ?? (spec?.aggregator === "lifi" ? "lifi" : "zeroex");
  if (selected === "kyberswap") {
    const quoted = await firmKyber(config, hop, chainId, taker, reference, fetchImpl);
    if (overCap(quoted.priceImpactPct, capPct) || !quoted.prepared?.to || !quoted.prepared.data) {
      throw new BroadcastError("firm quote outside the slippage cap", false);
    }
    return {
      to: asHex(quoted.prepared.to),
      data: asHex(quoted.prepared.data),
      value: BigInt(quoted.prepared.value || "0"),
      gas: null,
      impact: quoted.priceImpactPct ?? capPct + 1,
      raw: quoted.raw,
    };
  }
  if (selected === "lifi") {
    const quoted = await firmLifi(config, hop, chainId, taker, reference, fetchImpl);
    if (quoted.raw === undefined) throw new BroadcastError("firm quote outside the slippage cap", false);
    const parsed = readLifi(quoted.raw as Parameters<typeof readLifi>[0], reference, chainId);
    if (!parsed.sameChain || overCap(parsed.priceImpactPct, capPct) || parsed.priceImpactPct === null) {
      throw new BroadcastError("firm quote outside the slippage cap", false);
    }
    const request = (quoted.raw as { transactionRequest?: { to?: string; data?: string; value?: string; gasLimit?: string } }).transactionRequest;
    if (!request?.to || !request.data) throw new BroadcastError("firm quote has no transaction", false);
    return {
      to: asHex(request.to),
      data: asHex(request.data),
      value: BigInt(request.value ?? "0"),
      gas: request.gasLimit ? BigInt(request.gasLimit) : null,
      impact: parsed.priceImpactPct,
      raw: quoted.raw,
    };
  }
  if (selected !== "zeroex") throw new BroadcastError("provider is not signable", false);
  const quoted = await firmZeroEx(config, hop, chainId, taker, reference, fetchImpl);
  if (quoted.raw === undefined) throw new BroadcastError("firm quote outside the slippage cap", false);
  const parsed = readZeroEx(quoted.raw as Parameters<typeof readZeroEx>[0], reference);
  if (overCap(parsed.priceImpactPct, capPct) || parsed.priceImpactPct === null || !parsed.to || !parsed.data) {
    throw new BroadcastError("firm quote outside the slippage cap", false);
  }
  const gas = (quoted.raw as { transaction?: { gas?: string } }).transaction?.gas;
  return {
    to: asHex(parsed.to),
    data: asHex(parsed.data),
    value: BigInt(parsed.value || "0"),
    gas: gas ? BigInt(gas) : null,
    impact: parsed.priceImpactPct,
    raw: quoted.raw,
  };
}

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

async function sendRawEvm(chainId: number, rpc: string, signed: Hex, secrets: readonly string[]): Promise<void> {
  const chain = evmChain(chainId, rpc);
  const client = createPublicClient({ chain, transport: rpcTransport(rpc) });
  try {
    await client.sendRawTransaction({ serializedTransaction: signed });
  } catch (error) {
    throw new BroadcastError(redactError(error, secrets), true);
  }
}

async function prepareEvm(chainId: number, rpc: string, from: Hex, tx: { to: Hex; data: Hex; value: bigint; gas: bigint | null }) {
  const chain = evmChain(chainId, rpc);
  const reader = createPublicClient({ chain, transport: rpcTransport(rpc) });
  const fees = await reader.estimateFeesPerGas();
  const nonce = await reader.getTransactionCount({ address: from });
  const gas = tx.gas ?? (await reader.estimateGas({ account: from, to: tx.to, data: tx.data, value: tx.value }));
  try {
    if (typeof reader.simulateCalls === "function") {
      await reader.simulateCalls({ account: from, calls: [{ to: tx.to, data: tx.data, value: tx.value }] });
    } else {
      await reader.call({ account: from, to: tx.to, data: tx.data, value: tx.value });
    }
  } catch {
    throw new BroadcastError("simulation rejected the transaction", false);
  }
  return { gas, nonce, maxFeePerGas: fees.maxFeePerGas, maxPriorityFeePerGas: fees.maxPriorityFeePerGas };
}

async function sendSolana(
  signer: TransactionSigner,
  rpc: string,
  jitoUrl: string | null,
  swapTransaction: string,
  fetchImpl: typeof fetch,
  secrets: readonly string[],
): Promise<void> {
  const tx = VersionedTransaction.deserialize(Buffer.from(swapTransaction, "base64"));
  const connection = new Connection(rpc, "confirmed");
  const simulation = await connection.simulateTransaction(tx, { sigVerify: false, replaceRecentBlockhash: true });
  if (simulation.value.err) throw new BroadcastError("simulation rejected the transaction", false);
  let signed: Uint8Array;
  try {
    signed = await signer.signSolana(tx.serialize());
  } catch (error) {
    throw new BroadcastError(redactError(error, secrets), false);
  }
  try {
    if (jitoUrl) {
      const response = await fetchImpl(jitoUrl, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          jsonrpc: "2.0",
          id: 1,
          method: "sendTransaction",
          params: [Buffer.from(signed).toString("base64"), { encoding: "base64" }],
        }),
      });
      if (!response.ok) throw new Error("jito send failed");
      const body = z.object({ error: z.unknown().optional() }).passthrough().parse(await response.json());
      if (body.error) throw new Error("jito send failed");
      return;
    }
    await connection.sendRawTransaction(signed);
  } catch (error) {
    if (error instanceof BroadcastError) throw error;
    throw new BroadcastError(redactError(error, secrets), true);
  }
}

async function sendHypercore(
  config: AppConfig,
  signer: TransactionSigner,
  request: SendRequest,
  fetchImpl: typeof fetch,
  secrets: readonly string[],
): Promise<void> {
  let nonce = Date.now();
  let broadcast = false;
  try {
    for (const action of request.hyperliquidActions) {
      const signature = await signer.signHyperliquid(action, nonce, !config.hyperliquidUrl.includes("testnet"));
      broadcast = true;
      const response = await fetchImpl(`${config.hyperliquidUrl.replace(/\/$/, "")}/exchange`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ action, nonce, signature, vaultAddress: null }),
      });
      if (!response.ok) throw new BroadcastError("hyperliquid exchange rejected the action", true);
      nonce += 1;
    }
  } catch (error) {
    if (error instanceof BroadcastError) throw error;
    throw new BroadcastError(redactError(error, secrets), broadcast);
  }
  if (!broadcast) throw new BroadcastError("hyperliquid action missing", false);
}

export async function broadcastRoute(
  config: AppConfig,
  signer: TransactionSigner | null,
  request: SendRequest,
  capPct: number,
  fetchImpl: typeof fetch = fetch,
  secrets: readonly string[] = [],
): Promise<void> {
  if (!signer) throw new BroadcastError("signer is not loaded", false);
  if (request.kind === "hypercore") {
    await sendHypercore(config, signer, request, fetchImpl, secrets);
    return;
  }
  if (request.legs.length === 0) throw new BroadcastError("route has no signable leg", false);
  if (request.kind === "solana") {
    const owner = signer.solanaAddress();
    if (!owner) throw new BroadcastError("solana signer is not loaded", false);
    const rpc = config.rpcByChainKey.solana;
    if (!rpc) throw new BroadcastError("solana rpc is not configured", false);
    const transactions = [];
    for (const leg of request.legs) transactions.push(await jupiterTransaction(config, leg, owner, capPct, fetchImpl));
    combinedImpact(transactions.map((item) => item.impact), capPct);
    let sent = false;
    for (const transaction of transactions) {
      try {
        await sendSolana(signer, rpc, config.jitoUrl, transaction.transaction, fetchImpl, secrets);
        sent = true;
      } catch (error) {
        if (error instanceof BroadcastError) throw error;
        throw new BroadcastError(redactError(error, secrets), sent);
      }
    }
    return;
  }
  if (request.chain.kind !== "evm") throw new BroadcastError("evm chain missing", false);
  const owner = signer.evmAddress();
  if (!owner) throw new BroadcastError("evm signer is not loaded", false);
  const spec = chainByEvmId(request.chain.chainId);
  const rpc = spec ? config.rpcByChainKey[spec.key] : undefined;
  if (!rpc) throw new BroadcastError("evm rpc is not configured", false);
  if (spec?.liveSend === "disabled") throw new BroadcastError(spec.gap ?? "live send disabled", false);
  const sendRpc = config.mevRpcByChainId[request.chain.chainId] ?? rpc;
  const txs = [];
  for (const leg of request.legs) {
    const built = await evmTransaction(config, leg, request.chain.chainId, owner, capPct, fetchImpl, request.provider);
    rememberIfFunded(built.raw, request.chain.chainId, leg.sellAddress, owner, BigInt(leg.sellAmount), built.to);
    txs.push(built);
  }
  combinedImpact(txs.map((item) => item.impact), capPct);
  let sent = false;
  for (const [index, tx] of txs.entries()) {
    try {
      const prepared = await prepareEvm(request.chain.chainId, rpc, owner as Hex, tx);
      const sell = request.legs[index]?.sellAddress.toLowerCase() ?? "";
      const signed = await signer.signEvm({
        chainId: request.chain.chainId,
        to: tx.to,
        data: tx.data,
        value: tx.value,
        purpose: "swap",
        nativeSell: NATIVE_SELL.has(sell),
        ...prepared,
      });
      await sendRawEvm(request.chain.chainId, sendRpc, signed, secrets);
      sent = true;
    } catch (error) {
      if (error instanceof BroadcastError) throw error;
      throw new BroadcastError(redactError(error, secrets), sent);
    }
  }
}

export async function withdrawNative(input: {
  config: AppConfig;
  signer: TransactionSigner;
  chainKey: string;
  to: string;
  amount: number;
  secrets?: readonly string[];
}): Promise<void> {
  const spec = chainByKey(input.chainKey);
  if (!spec) throw new Error("unknown chain");
  const rpc = input.config.rpcByChainKey[input.chainKey];
  if (!rpc) throw new Error("rpc is not configured");
  const secrets = input.secrets ?? [];
  if (spec.chain.kind === "solana") {
    const owner = input.signer.solanaAddress();
    if (!owner || !isSolanaAddress(input.to)) throw new Error("destination is not a solana address");
    const connection = new Connection(rpc, "confirmed");
    const balance = await connection.getBalance(new PublicKey(owner));
    const lamports = BigInt(sellBaseUnits(input.amount, 9));
    const reserve = BigInt(sellBaseUnits(spec.minNativeReserve, 9));
    if (lamports <= 0n || BigInt(balance) - lamports < reserve) throw new Error("withdraw would spend the native reserve");
    const { blockhash } = await connection.getLatestBlockhash();
    const message = new TransactionMessage({
      payerKey: new PublicKey(owner),
      recentBlockhash: blockhash,
      instructions: [SystemProgram.transfer({ fromPubkey: new PublicKey(owner), toPubkey: new PublicKey(input.to), lamports: Number(lamports) })],
    }).compileToV0Message();
    const signed = await input.signer.signSolana(new VersionedTransaction(message).serialize());
    await connection.sendRawTransaction(signed);
    return;
  }
  if (spec.chain.kind !== "evm") throw new Error("withdraw is not available on this venue");
  const owner = input.signer.evmAddress();
  if (!owner || !/^0x[0-9a-fA-F]{40}$/.test(input.to)) throw new Error("destination is not an evm address");
  const value = BigInt(sellBaseUnits(input.amount, 18));
  const prepared = await prepareEvm(spec.chain.chainId, rpc, owner as Hex, { to: input.to as Hex, data: "0x", value, gas: null });
  const chain = evmChain(spec.chain.chainId, rpc);
  const reader = createPublicClient({ chain, transport: rpcTransport(rpc) });
  const balance = await reader.getBalance({ address: owner as Hex });
  const reserve = BigInt(sellBaseUnits(spec.minNativeReserve, 18));
  if (value <= 0n || balance - value < reserve) throw new Error("withdraw would spend the native reserve");
  const signed = await input.signer.signEvm({
    chainId: spec.chain.chainId,
    to: input.to as Hex,
    data: "0x",
    value,
    purpose: "withdraw",
    ...prepared,
  });
  await sendRawEvm(spec.chain.chainId, rpc, signed, secrets);
}

const TOKEN_PROGRAM = new PublicKey("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA");
const TOKEN_2022_PROGRAM = new PublicKey("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb");
const ATA_PROGRAM = new PublicKey("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL");

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

export async function recoverToken(input: {
  config: AppConfig;
  signer: TransactionSigner;
  chainKey: string;
  to: string;
  amount: number;
  mint: string;
  decimals: number;
  secrets?: readonly string[];
}): Promise<void> {
  const spec = chainByKey(input.chainKey);
  if (!spec) throw new Error("unknown chain");
  const rpc = input.config.rpcByChainKey[input.chainKey];
  if (!rpc) throw new Error("rpc is not configured");
  const secrets = input.secrets ?? [];
  if (spec.chain.kind === "evm") {
    const owner = input.signer.evmAddress();
    if (!owner || !/^0x[0-9a-fA-F]{40}$/.test(input.to) || !/^0x[0-9a-fA-F]{40}$/.test(input.mint)) throw new Error("destination is not an evm address");
    const data = encodeFunctionData({ abi: erc20Abi, functionName: "transfer", args: [input.to as Hex, parseUnits(String(input.amount), input.decimals)] });
    const prepared = await prepareEvm(spec.chain.chainId, rpc, owner as Hex, { to: input.mint as Hex, data, value: 0n, gas: null });
    const signed = await input.signer.signEvm({
      chainId: spec.chain.chainId,
      to: input.mint as Hex,
      data,
      value: 0n,
      purpose: "withdraw",
      nativeSell: false,
      ...prepared,
    });
    await sendRawEvm(spec.chain.chainId, rpc, signed, secrets);
    return;
  }
  if (spec.chain.kind !== "solana" || !input.signer.solanaAddress() || !isSolanaAddress(input.to) || !isSolanaAddress(input.mint)) {
    throw new Error("destination is not a solana address");
  }
  const owner = input.signer.solanaAddress() as string;
  const connection = new Connection(rpc, "confirmed");
  const ownerKey = new PublicKey(owner);
  const mintKey = new PublicKey(input.mint);
  const found = await tokenAccount(connection, ownerKey, mintKey);
  if (!found) throw new Error("token account was not found");
  const raw = BigInt(sellBaseUnits(input.amount, input.decimals));
  const instructions = tokenRecoveryInstructions({
    payer: ownerKey,
    destinationOwner: new PublicKey(input.to),
    mint: mintKey,
    source: found.source,
    program: found.program,
    amount: raw,
    decimals: input.decimals,
  });
  const { blockhash } = await connection.getLatestBlockhash();
  const message = new TransactionMessage({ payerKey: ownerKey, recentBlockhash: blockhash, instructions }).compileToV0Message();
  const signed = await input.signer.signSolana(new VersionedTransaction(message).serialize());
  await connection.sendRawTransaction(signed);
}

async function tokenAccount(connection: Connection, owner: PublicKey, mint: PublicKey): Promise<{ source: PublicKey; program: PublicKey } | null> {
  for (const program of [TOKEN_PROGRAM, TOKEN_2022_PROGRAM]) {
    const accounts = await connection.getParsedTokenAccountsByOwner(owner, { mint, programId: program });
    const source = accounts.value[0]?.pubkey;
    if (source) return { source, program };
  }
  return null;
}
