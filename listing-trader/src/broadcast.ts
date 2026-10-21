import { Connection, PublicKey, SystemProgram, Transaction, VersionedTransaction } from "@solana/web3.js";
import { createPublicClient, createWalletClient, defineChain, http, type Hex } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import type { AppConfig } from "./config.js";
import type { RouteLeg } from "./domain.js";
import { chainByEvmId, chainByKey } from "./chains.js";
import { firmZeroEx, quoteHop } from "./clients.js";
import { BroadcastError, type HopQuote, type SendRequest } from "./executor.js";
import { signL1Action } from "./hyperliquid.js";
import { readLifi, readZeroEx } from "./quotes.js";
import { redactError } from "./redact.js";
import { combineHopImpact, sellBaseUnits } from "./routing.js";
import { evmSigner, hyperliquidSigner, isSolanaAddress, signerSecrets, solanaSigner, type SignerMaterial } from "./signer.js";

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
  if (quoted.priceImpactPct === null || quoted.priceImpactPct > capPct || quoted.raw === undefined) {
    throw new BroadcastError("firm quote outside the slippage cap", false);
  }
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (process.env.JUPITER_API_KEY) headers["x-api-key"] = process.env.JUPITER_API_KEY;
  const response = await fetchImpl(`${config.jupiterBase}/swap`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      quoteResponse: quoted.raw,
      userPublicKey: user,
      wrapAndUnwrapSol: true,
      dynamicComputeUnitLimit: true,
    }),
  });
  if (!response.ok) throw new BroadcastError("jupiter swap build failed", false);
  const body = (await response.json()) as { swapTransaction?: string };
  if (!body.swapTransaction) throw new BroadcastError("jupiter swap build failed", false);
  return { transaction: body.swapTransaction, impact: quoted.priceImpactPct };
}

async function evmTransaction(
  config: AppConfig,
  leg: RouteLeg,
  chainId: number,
  taker: string,
  capPct: number,
  fetchImpl: typeof fetch,
): Promise<{ to: Hex; data: Hex; value: bigint; gas: bigint | null; impact: number }> {
  const spec = chainByEvmId(chainId);
  let quoted: HopQuote;
  if (spec?.aggregator === "lifi") {
    quoted = await quoteHop(
      config,
      { sellAddress: leg.sellAddress, buyAddress: leg.buyAddress, sellAmount: leg.sellAmount, chain: { kind: "evm", chainId } },
      referenceFor(leg),
      fetchImpl,
    );
    if (quoted.raw === undefined) throw new BroadcastError("firm quote outside the slippage cap", false);
    const parsed = readLifi(quoted.raw as Parameters<typeof readLifi>[0], referenceFor(leg), chainId);
    if (!parsed.sameChain || overCap(parsed.priceImpactPct, capPct) || parsed.priceImpactPct === null) {
      throw new BroadcastError("firm quote outside the slippage cap", false);
    }
    const request = (quoted.raw as { transactionRequest?: { to?: string; data?: string; value?: string; gasLimit?: string } } | undefined)
      ?.transactionRequest;
    if (!request?.to || !request.data) throw new BroadcastError("firm quote has no transaction", false);
    return {
      to: request.to as Hex,
      data: request.data as Hex,
      value: BigInt(request.value ?? "0"),
      gas: request.gasLimit ? BigInt(request.gasLimit) : null,
      impact: parsed.priceImpactPct,
    };
  }
  quoted = await firmZeroEx(
    config,
    { sellAddress: leg.sellAddress, buyAddress: leg.buyAddress, sellAmount: leg.sellAmount, chain: { kind: "evm", chainId } },
    chainId,
    taker,
    referenceFor(leg),
    fetchImpl,
  );
  if (quoted.raw === undefined) throw new BroadcastError("firm quote outside the slippage cap", false);
  const parsed = readZeroEx(quoted.raw as Parameters<typeof readZeroEx>[0], referenceFor(leg));
  if (overCap(parsed.priceImpactPct, capPct) || parsed.priceImpactPct === null || !parsed.to || !parsed.data) {
    throw new BroadcastError("firm quote outside the slippage cap", false);
  }
  const gas = (quoted.raw as { transaction?: { gas?: string } } | undefined)?.transaction?.gas;
  return { to: parsed.to as Hex, data: parsed.data as Hex, value: BigInt(parsed.value || "0"), gas: gas ? BigInt(gas) : null, impact: parsed.priceImpactPct };
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

async function sendEvm(material: SignerMaterial, chainId: number, rpc: string, tx: { to: Hex; data: Hex; value: bigint; gas: bigint | null }): Promise<void> {
  const account = privateKeyToAccount(evmSigner(material));
  const chain = evmChain(chainId, rpc);
  const client = createWalletClient({ account, chain, transport: http(rpc) });
  try {
    await client.sendTransaction({
      to: tx.to,
      data: tx.data,
      value: tx.value,
      gas: tx.gas ?? undefined,
      chain,
    });
  } catch (error) {
    throw new BroadcastError(redactError(error, signerSecrets(material)), true);
  }
}

async function sendSolana(material: SignerMaterial, rpc: string, swapTransaction: string): Promise<void> {
  const keypair = solanaSigner(material);
  const tx = VersionedTransaction.deserialize(Buffer.from(swapTransaction, "base64"));
  tx.sign([keypair]);
  const connection = new Connection(rpc, "confirmed");
  try {
    await connection.sendRawTransaction(tx.serialize());
  } catch (error) {
    throw new BroadcastError(redactError(error, signerSecrets(material)), true);
  }
}

async function sendHypercore(config: AppConfig, material: SignerMaterial, request: SendRequest, fetchImpl: typeof fetch): Promise<void> {
  const key = hyperliquidSigner(material);
  let nonce = Date.now();
  let broadcast = false;
  try {
    for (const action of request.hyperliquidActions) {
      const signature = await signL1Action(key, action, nonce, !config.hyperliquidUrl.includes("testnet"));
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
    throw new BroadcastError(redactError(error, signerSecrets(material)), broadcast);
  }
  if (!broadcast) throw new BroadcastError("hyperliquid action missing", false);
}

export async function broadcastRoute(
  config: AppConfig,
  material: SignerMaterial | null,
  request: SendRequest,
  capPct: number,
  fetchImpl: typeof fetch = fetch,
): Promise<void> {
  if (!material) throw new BroadcastError("signer is not loaded", false);
  if (request.kind === "hypercore") {
    await sendHypercore(config, material, request, fetchImpl);
    return;
  }
  if (request.legs.length === 0) throw new BroadcastError("route has no signable leg", false);
  if (request.kind === "solana") {
    if (!material.solanaAddress) throw new BroadcastError("solana signer is not loaded", false);
    const rpc = config.rpcByChainKey.solana;
    if (!rpc) throw new BroadcastError("solana rpc is not configured", false);
    const transactions = [];
    for (const leg of request.legs) transactions.push(await jupiterTransaction(config, leg, material.solanaAddress, capPct, fetchImpl));
    combinedImpact(transactions.map((item) => item.impact), capPct);
    let sent = false;
    for (const transaction of transactions) {
      try {
        await sendSolana(material, rpc, transaction.transaction);
        sent = true;
      } catch (error) {
        if (error instanceof BroadcastError) throw error;
        throw new BroadcastError(redactError(error, signerSecrets(material)), sent);
      }
    }
    return;
  }
  if (request.chain.kind !== "evm") throw new BroadcastError("evm chain missing", false);
  if (!material.evmAddress) throw new BroadcastError("evm signer is not loaded", false);
  const spec = chainByEvmId(request.chain.chainId);
  const rpc = spec ? config.rpcByChainKey[spec.key] : undefined;
  if (!rpc) throw new BroadcastError("evm rpc is not configured", false);
  if (spec?.liveSend === "disabled") throw new BroadcastError(spec.gap ?? "live send disabled", false);
  const txs = [];
  for (const leg of request.legs) {
    txs.push(await evmTransaction(config, leg, request.chain.chainId, material.evmAddress, capPct, fetchImpl));
  }
  combinedImpact(txs.map((item) => item.impact), capPct);
  let sent = false;
  for (const tx of txs) {
    try {
      await sendEvm(material, request.chain.chainId, rpc, tx);
      sent = true;
    } catch (error) {
      if (error instanceof BroadcastError) throw error;
      throw new BroadcastError(redactError(error, signerSecrets(material)), sent);
    }
  }
}

export async function withdrawNative(input: {
  config: AppConfig;
  material: SignerMaterial;
  chainKey: string;
  to: string;
  amount: number;
}): Promise<void> {
  const spec = chainByKey(input.chainKey);
  if (!spec) throw new Error("unknown chain");
  const rpc = input.config.rpcByChainKey[input.chainKey];
  if (!rpc) throw new Error("rpc is not configured");
  if (spec.chain.kind === "solana") {
    if (!isSolanaAddress(input.to)) throw new Error("destination is not a solana address");
    const keypair = solanaSigner(input.material);
    const connection = new Connection(rpc, "confirmed");
    const balance = await connection.getBalance(keypair.publicKey);
    const lamports = BigInt(sellBaseUnits(input.amount, 9));
    const reserve = BigInt(sellBaseUnits(spec.minNativeReserve, 9));
    if (lamports <= 0n || BigInt(balance) - lamports < reserve) throw new Error("withdraw would spend the native reserve");
    const tx = new Transaction().add(
      SystemProgram.transfer({ fromPubkey: keypair.publicKey, toPubkey: new PublicKey(input.to), lamports: Number(lamports) }),
    );
    await connection.sendTransaction(tx, [keypair]);
    return;
  }
  if (spec.chain.kind !== "evm") throw new Error("withdraw is not available on this venue");
  if (!/^0x[0-9a-fA-F]{40}$/.test(input.to)) throw new Error("destination is not an evm address");
  const account = privateKeyToAccount(evmSigner(input.material));
  const chain = evmChain(spec.chain.chainId, rpc);
  const client = createWalletClient({ account, chain, transport: http(rpc) });
  const reader = createPublicClient({ chain, transport: http(rpc) });
  const balance = await reader.getBalance({ address: account.address });
  const value = BigInt(sellBaseUnits(input.amount, 18));
  const reserve = BigInt(sellBaseUnits(spec.minNativeReserve, 18));
  if (value <= 0n || balance - value < reserve) throw new Error("withdraw would spend the native reserve");
  await client.sendTransaction({ to: input.to as Hex, value, chain });
}
