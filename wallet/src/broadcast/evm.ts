import { TransactionReceiptNotFoundError, createPublicClient, type Hex } from "viem";
import { encodeFunctionData, erc20Abi, keccak256, parseUnits } from "viem";
import type { RouteLeg, TxRecord } from "../domain.js";
import type { EvmSignInput } from "../managed-signer.js";
import { firmJupiter, firmKyber, firmLifi, firmZeroEx, jupiterQuote, jupiterSwap, kyberFromRoute } from "../aggregators.js";
import { chainByEvmId } from "../chains.js";
import { anyOk } from "../rpc.js";
import { isNonceRejection } from "../nonce.js";
import type { RaceQuote, TxOutcome } from "../domain.js";
import { BroadcastError } from "../executor.js";
import { allowanceCovers, rememberApproval } from "../approvals.js";
import { readLifi, readZeroEx } from "../quotes.js";
import { redactError } from "../redact.js";
import { sellBaseUnits } from "../routing.js";
import { approvalSpender, asHex, assertMinOut, executionSlippageBps, journal, ourMinOut, referenceFor, rememberIfFunded, reusableQuote, reuseOrFirm, type Confirmed, type Ctx, type EvmCtx, type EvmReceipt, type EvmRpc, type EvmTx, type PreparedLeg, type Submitted, NATIVE_SELL, digits, overCap } from "./shared.js";

export function evmRecord(ctx: EvmCtx, signed: Hex, tx: { to: Hex; value: bigint }): TxRecord {
  return { chainKey: ctx.chainKey, txHash: keccak256(signed), from: ctx.owner, to: tx.to, value: tx.value.toString(), outcome: "pending" };
}

export async function sendOnce(rpc: EvmRpc, signed: Hex): Promise<void> {
  try {
    await rpc.sendRaw(signed);
  } catch (error) {
    if (/already known/i.test(error instanceof Error ? error.message : String(error))) return;
    throw error;
  }
}

export async function broadcastEvm(ctx: EvmCtx, signed: Hex): Promise<void> {
  try {
    await anyOk(ctx.senders.map((rpc) => () => sendOnce(rpc, signed)));
  } catch (error) {
    const message = redactError(error, ctx.secrets);
    throw new BroadcastError(message, !isNonceRejection(message));
  }
}

export function bumpFee(fee: bigint): bigint {
  const step = (fee * 125n + 999n) / 1000n;
  return fee + (step > 0n ? step : 1n);
}

export async function pollReceipts(ctx: EvmCtx, hashes: readonly string[], deadline: number): Promise<{ hash: string; receipt: EvmReceipt } | null> {
  for (;;) {
    for (const hash of hashes) {
      const receipt = await ctx.read.receipt(hash as Hex).catch(() => null);
      if (receipt) return { hash, receipt };
    }
    if (ctx.io.now() >= deadline) return null;
    await ctx.io.sleep(ctx.io.pollMs);
  }
}

export async function replaceEvm(ctx: EvmCtx, input: EvmSignInput): Promise<TxRecord | null> {
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

export async function confirmEvm(ctx: EvmCtx, input: EvmSignInput, first: TxRecord, before: bigint | null, buyToken: string | null): Promise<Confirmed> {
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

export async function submitEvm(ctx: EvmCtx, tx: EvmTx, buyToken: string | null): Promise<Submitted> {
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

type BuiltEvm = { provider: string; to: Hex; data: Hex; value: bigint; gas: bigint | null; impact: number; raw: unknown; minOut: bigint | null; quotedOut: bigint };

export async function evmTransaction(ctx: EvmCtx, leg: RouteLeg, capPct: number, slippageBps: number, selected: string, stored: RaceQuote | null): Promise<BuiltEvm> {
  const { config, chainId, owner: taker, fetchImpl } = ctx;
  const hop = { sellAddress: leg.sellAddress, buyAddress: leg.buyAddress, sellAmount: leg.sellAmount, chain: { kind: "evm" as const, chainId } };
  const reference = referenceFor(leg);
  if (selected === "kyberswap") {
    const quoted = stored
      ? await kyberFromRoute(config, stored.raw, chainId, taker, reference, fetchImpl, slippageBps)
      : await firmKyber(config, hop, chainId, taker, reference, fetchImpl, slippageBps);
    if (overCap(quoted.priceImpactPct, capPct) || !quoted.prepared?.to || !quoted.prepared.data) {
      throw new BroadcastError("firm quote outside the slippage cap", false);
    }
    const built = (quoted.raw as { build?: { amountOut?: string | null; slippageBps?: number } } | undefined)?.build;
    const amountOut = digits(built?.amountOut);
    return {
      provider: selected,
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
    const quoted = stored ? { raw: stored.raw } : await firmLifi(config, hop, chainId, taker, reference, fetchImpl, slippageBps);
    if (quoted.raw === undefined) throw new BroadcastError("firm quote outside the slippage cap", false);
    const parsed = readLifi(quoted.raw as Parameters<typeof readLifi>[0], reference, chainId);
    if (!parsed.sameChain || overCap(parsed.priceImpactPct, capPct) || parsed.priceImpactPct === null) {
      throw new BroadcastError("firm quote outside the slippage cap", false);
    }
    const raw = quoted.raw as { transactionRequest?: { to?: string; data?: string; value?: string; gasLimit?: string }; estimate?: { toAmountMin?: unknown } };
    const request = raw.transactionRequest;
    if (!request?.to || !request.data) throw new BroadcastError("firm quote has no transaction", false);
    return {
      provider: selected,
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
  const quoted = stored ? { raw: stored.raw } : await firmZeroEx(config, hop, chainId, taker, reference, fetchImpl, slippageBps);
  if (quoted.raw === undefined) throw new BroadcastError("firm quote outside the slippage cap", false);
  const parsed = readZeroEx(quoted.raw as Parameters<typeof readZeroEx>[0], reference);
  if (overCap(parsed.priceImpactPct, capPct) || parsed.priceImpactPct === null || !parsed.to || !parsed.data) {
    throw new BroadcastError("firm quote outside the slippage cap", false);
  }
  const raw = quoted.raw as { transaction?: { gas?: string }; minBuyAmount?: unknown };
  return {
    provider: selected,
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

export async function prepareEvmLeg(ctx: EvmCtx, leg: RouteLeg, slippageBps: number, next: RouteLeg | undefined, capBps: number, provider: string | undefined): Promise<PreparedLeg> {
  const reuse = reusableQuote(ctx.config, leg, ctx.owner);
  const selected = leg.quote?.provider ?? provider ?? (chainByEvmId(ctx.chainId)?.aggregator === "lifi" ? "lifi" : "zeroex");
  const { built, minOut } = await reuseOrFirm(reuse, async (stored) => {
    const built = await evmTransaction(ctx, leg, capBps / 100, slippageBps, selected, stored);
    return { built, minOut: assertMinOut(built.minOut, ourMinOut(leg, capBps)) };
  });
  rememberIfFunded(built.provider, built.raw, ctx.chainId, leg.sellAddress, ctx.owner, BigInt(leg.sellAmount), built.to);
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
