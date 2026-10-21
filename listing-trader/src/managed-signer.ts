import { createHash, timingSafeEqual } from "node:crypto";
import { VersionedTransaction } from "@solana/web3.js";
import { type Hex } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import type { AppConfig } from "./config.js";
import { actionHash, signL1Action, type HyperliquidAction } from "./hyperliquid.js";
import { loadSigner, signerSecrets, solanaSigner, type SignerMaterial } from "./signer.js";
import { assertEvmSigning, assertHyperliquidSigning, assertSolanaSigning, routersForChain, type EvmPurpose } from "./signing-policy.js";
import { assertLiveEdges } from "./config.js";

export type EvmSignInput = {
  chainId: number;
  to: Hex;
  data: Hex;
  value: bigint;
  gas: bigint;
  nonce: number;
  maxFeePerGas: bigint;
  maxPriorityFeePerGas: bigint;
  purpose: EvmPurpose;
  nativeSell?: boolean;
};

export interface TransactionSigner {
  readonly backend: "turnkey" | "keystore";
  evmAddress(): string | null;
  solanaAddress(): string | null;
  signEvm(input: EvmSignInput): Promise<Hex>;
  signSolana(serialized: Uint8Array): Promise<Uint8Array>;
  signHyperliquid(action: HyperliquidAction, nonce: number, isMainnet: boolean): Promise<{ r: Hex; s: Hex; v: number }>;
}

export type TurnkeyApi = {
  signEvm(unsigned: Hex, address: string): Promise<Hex>;
  signSolana(unsignedBase64: string, address: string): Promise<string>;
  signEip712(payload: string, address: string): Promise<{ r: string; s: string; v: string }>;
};

function policyConfig(config: AppConfig) {
  return {
    withdrawAllowlist: config.withdrawAllowlist,
    maxValueWei: config.maxValueWei,
    allowHotApproval: config.allowHotApproval,
    solanaPrograms: config.solanaProgramAllowlist,
    maxLeverage: config.maxLeverage,
    recoveryTokens: config.tokenRecoveryAllowlist,
  };
}

export function withPolicy(inner: TransactionSigner, config: AppConfig): TransactionSigner {
  const policy = policyConfig(config);
  return {
    backend: inner.backend,
    evmAddress: () => inner.evmAddress(),
    solanaAddress: () => inner.solanaAddress(),
    async signEvm(input) {
      assertEvmSigning({
        ...input,
        ...policy,
        routers: routersForChain(config.routerAllowlist, input.chainId),
        nativeSell: input.nativeSell === true,
      });
      return inner.signEvm(input);
    },
    async signSolana(serialized) {
      const tx = VersionedTransaction.deserialize(serialized);
      const keys = tx.message.staticAccountKeys;
      const instructions = tx.message.compiledInstructions;
      const programIds = instructions.map((ix) => keys[ix.programIdIndex]?.toBase58() ?? "");
      const expected = inner.solanaAddress();
      if (!expected) throw new Error("solana signer is not loaded");
      const nativeTransferTo = instructions.flatMap((ix) => {
        const program = keys[ix.programIdIndex]?.toBase58();
        if (program !== "11111111111111111111111111111111") return [];
        const data = Buffer.from(ix.data);
        const indexes = ix.accountKeyIndexes;
        if (data.length < 12 || data.readUInt32LE(0) !== 2 || indexes.length < 2) return [];
        return [keys[indexes[1]]?.toBase58() ?? ""];
      });
      const tokenPrograms = new Set(["TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA", "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"]);
      const tokenTransferTo = instructions.flatMap((ix) => {
        const program = keys[ix.programIdIndex]?.toBase58() ?? "";
        if (!tokenPrograms.has(program)) return [];
        const data = Buffer.from(ix.data);
        const indexes = ix.accountKeyIndexes;
        if (data.length < 1) return [];
        if (data[0] === 3 && indexes.length >= 2) return [keys[indexes[1]]?.toBase58() ?? ""];
        if (data[0] === 12 && indexes.length >= 3) return [keys[indexes[2]]?.toBase58() ?? ""];
        return [];
      });
      assertSolanaSigning({
        programIds,
        allowlist: policy.solanaPrograms,
        feePayer: keys[0]?.toBase58() ?? "",
        expectedFeePayer: expected,
        nativeTransferTo,
        tokenTransferTo,
        withdrawAllowlist: policy.withdrawAllowlist,
      });
      return inner.signSolana(serialized);
    },
    async signHyperliquid(action, nonce, isMainnet) {
      assertHyperliquidSigning(action, policy.maxLeverage);
      return inner.signHyperliquid(action, nonce, isMainnet);
    },
  };
}

export function keystoreSigner(material: SignerMaterial): TransactionSigner {
  return {
    backend: "keystore",
    evmAddress: () => material.evmAddress,
    solanaAddress: () => material.solanaAddress,
    async signEvm(input) {
      if (!material.evm) throw new Error("evm signer is not loaded");
      const raw = material.evm.reveal();
      const account = privateKeyToAccount((raw.startsWith("0x") ? raw : `0x${raw}`) as Hex);
      return account.signTransaction({
        type: "eip1559",
        chainId: input.chainId,
        to: input.to,
        data: input.data,
        value: input.value,
        gas: input.gas,
        nonce: input.nonce,
        maxFeePerGas: input.maxFeePerGas,
        maxPriorityFeePerGas: input.maxPriorityFeePerGas,
      });
    },
    async signSolana(serialized) {
      const tx = VersionedTransaction.deserialize(serialized);
      tx.sign([solanaSigner(material)]);
      return tx.serialize();
    },
    async signHyperliquid(action, nonce, isMainnet) {
      if (!material.hyperliquid) throw new Error("hyperliquid agent key is not loaded");
      return signL1Action(material.hyperliquid, action, nonce, isMainnet);
    },
  };
}

export function turnkeySigner(api: TurnkeyApi, addresses: { evm: string | null; solana: string | null; hyperliquid: string | null }): TransactionSigner {
  return {
    backend: "turnkey",
    evmAddress: () => addresses.evm,
    solanaAddress: () => addresses.solana,
    async signEvm(input) {
      if (!addresses.evm) throw new Error("evm signer is not loaded");
      const unsigned = await unsignedEvm(input);
      return api.signEvm(unsigned, addresses.evm);
    },
    async signSolana(serialized) {
      if (!addresses.solana) throw new Error("solana signer is not loaded");
      const signed = await api.signSolana(Buffer.from(serialized).toString("base64"), addresses.solana);
      return Buffer.from(signed, "base64");
    },
    async signHyperliquid(action, nonce, isMainnet) {
      if (!addresses.hyperliquid) throw new Error("hyperliquid agent key is not loaded");
      const connectionId = actionHash(action, null, nonce, null);
      const payload = JSON.stringify({
        domain: { name: "Exchange", version: "1", chainId: 1337, verifyingContract: "0x0000000000000000000000000000000000000000" },
        types: { Agent: [{ name: "source", type: "string" }, { name: "connectionId", type: "bytes32" }] },
        primaryType: "Agent",
        message: { source: isMainnet ? "a" : "b", connectionId },
      });
      const signature = await api.signEip712(payload, addresses.hyperliquid);
      return { r: signature.r as Hex, s: signature.s as Hex, v: recoveryId(signature.v) };
    },
  };
}

async function unsignedEvm(input: EvmSignInput): Promise<Hex> {
  const { serializeTransaction } = await import("viem");
  return serializeTransaction({
    type: "eip1559",
    chainId: input.chainId,
    to: input.to,
    data: input.data,
    value: input.value,
    gas: input.gas,
    nonce: input.nonce,
    maxFeePerGas: input.maxFeePerGas,
    maxPriorityFeePerGas: input.maxPriorityFeePerGas,
  });
}

export function turnkeyApiFromEnv(env: NodeJS.ProcessEnv): TurnkeyApi | null {
  if (!env.TURNKEY_ORGANIZATION_ID || !env.TURNKEY_API_PUBLIC_KEY || !env.TURNKEY_API_PRIVATE_KEY) return null;
  return {
    async signEvm(unsigned, address) {
      const { Turnkey } = await import("@turnkey/sdk-server");
      const client = new Turnkey({
        apiBaseUrl: env.TURNKEY_API_BASE ?? "https://api.turnkey.com",
        apiPublicKey: env.TURNKEY_API_PUBLIC_KEY ?? "",
        apiPrivateKey: env.TURNKEY_API_PRIVATE_KEY ?? "",
        defaultOrganizationId: env.TURNKEY_ORGANIZATION_ID ?? "",
      }).apiClient();
      const result = await client.signTransaction({ signWith: address, unsignedTransaction: unsigned, type: "TRANSACTION_TYPE_ETHEREUM" });
      const signed = "signedTransaction" in result ? result.signedTransaction : "";
      if (!signed) throw new Error("turnkey evm sign returned no transaction");
      return signed as Hex;
    },
    async signSolana(unsignedBase64, address) {
      const { Turnkey } = await import("@turnkey/sdk-server");
      const client = new Turnkey({
        apiBaseUrl: env.TURNKEY_API_BASE ?? "https://api.turnkey.com",
        apiPublicKey: env.TURNKEY_API_PUBLIC_KEY ?? "",
        apiPrivateKey: env.TURNKEY_API_PRIVATE_KEY ?? "",
        defaultOrganizationId: env.TURNKEY_ORGANIZATION_ID ?? "",
      }).apiClient();
      const result = await client.signTransaction({ signWith: address, unsignedTransaction: unsignedBase64, type: "TRANSACTION_TYPE_SOLANA" });
      const signed = "signedTransaction" in result ? result.signedTransaction : "";
      if (!signed) throw new Error("turnkey solana sign returned no transaction");
      return signed;
    },
    async signEip712(payload, address) {
      const { Turnkey } = await import("@turnkey/sdk-server");
      const client = new Turnkey({
        apiBaseUrl: env.TURNKEY_API_BASE ?? "https://api.turnkey.com",
        apiPublicKey: env.TURNKEY_API_PUBLIC_KEY ?? "",
        apiPrivateKey: env.TURNKEY_API_PRIVATE_KEY ?? "",
        defaultOrganizationId: env.TURNKEY_ORGANIZATION_ID ?? "",
      }).apiClient();
      const result = await client.signRawPayload({
        signWith: address,
        payload,
        encoding: "PAYLOAD_ENCODING_EIP712",
        hashFunction: "HASH_FUNCTION_NO_OP",
      });
      return { r: result.r, s: result.s, v: result.v };
    },
  };
}

export function loadManagedSigner(env: NodeJS.ProcessEnv, config: AppConfig): TransactionSigner | null {
  const api = turnkeyApiFromEnv(env);
  if (api && env.TURNKEY_EVM_ADDRESS) {
    delete env.KEYSTORE_PASSPHRASE;
    return withPolicy(
      turnkeySigner(api, {
        evm: env.TURNKEY_EVM_ADDRESS,
        solana: env.TURNKEY_SOLANA_ADDRESS ?? null,
        hyperliquid: env.TURNKEY_HYPERLIQUID_ADDRESS ?? null,
      }),
      config,
    );
  }
  if (config.live) {
    delete env.KEYSTORE_PASSPHRASE;
    throw new Error("live mode requires Turnkey");
  }
  const material = loadSigner(env);
  delete env.KEYSTORE_PASSPHRASE;
  if (!material) return null;
  return withPolicy(keystoreSigner(material), config);
}

export function hyperliquidAgentAddress(env: NodeJS.ProcessEnv): string | null {
  if (env.TURNKEY_HYPERLIQUID_ADDRESS) return env.TURNKEY_HYPERLIQUID_ADDRESS;
  if (!env.HYPERLIQUID_AGENT_KEY) return null;
  const raw = env.HYPERLIQUID_AGENT_KEY;
  const hex = (raw.startsWith("0x") ? raw : `0x${raw}`) as Hex;
  return privateKeyToAccount(hex).address;
}

export function signingSecrets(env: NodeJS.ProcessEnv, material: SignerMaterial | null): string[] {
  return [env.TURNKEY_API_PRIVATE_KEY, env.TURNKEY_API_PUBLIC_KEY, env.OKX_API_SECRET, env.OKX_API_PASSPHRASE, ...signerSecrets(material)].filter(
    (item): item is string => Boolean(item),
  );
}

export function tokenMatches(left: string, right: string): boolean {
  const a = createHash("sha256").update(left).digest();
  const b = createHash("sha256").update(right).digest();
  return timingSafeEqual(a, b);
}

function recoveryId(v: string): number {
  const parsed = Number.parseInt(v.replace(/^0x/i, ""), 16);
  if (parsed === 0 || parsed === 1) return parsed + 27;
  if (parsed === 27 || parsed === 28) return parsed;
  throw new Error("turnkey hyperliquid signature v is not a recovery id");
}

export function assertBoot(config: AppConfig, env: NodeJS.ProcessEnv = process.env): void {
  if (!config.authToken || config.authToken.length < 16) throw new Error("AUTH_TOKEN must be at least 16 characters");
  if (env.RAILWAY_PUBLIC_DOMAIN) throw new Error("a public Railway domain is set. Remove it and use the private network.");
  assertLiveEdges(config, env);
}
