import assert from "node:assert/strict";
import test from "node:test";
import { Keypair, PublicKey, TransactionMessage, VersionedTransaction } from "@solana/web3.js";
import { raceProviderQuotes, resetProviderGuards } from "../src/aggregators.js";
import { holdingsForTrade } from "../src/balances.js";
import { associatedTokenAccount, tokenRecoveryInstructions } from "../src/broadcast.js";
import { loadConfig } from "../src/config.js";
import type { SwapIntent, TokenRecord } from "../src/domain.js";
import { execute, resetExecutorState, type ExecutorDeps } from "../src/executor.js";
import { withPolicy, type TransactionSigner } from "../src/managed-signer.js";
import { buildPairMap } from "../src/pairs.js";
import { holdingsSchema } from "../src/schemas.js";
import { JUPITER_PROGRAM_ID } from "../src/signing-policy.js";
import { fillTokenDecimals, resetTokenDecimals } from "../src/token-decimals.js";

const contract = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";

function evmToken(decimals: number | null): TokenRecord {
  return {
    id: `base:${contract}`,
    ticker: "MPLX",
    names: ["Metaplex"],
    chainKey: "base",
    chain: { kind: "evm", chainId: 8453 },
    contract,
    decimals,
    pairMap: buildPairMap([
      {
        poolAddress: "pool",
        dex: "uniswap",
        chainKey: "base",
        baseSymbol: "MPLX",
        baseAddress: contract,
        quoteSymbol: "USDC",
        quoteAddress: "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        liquidityUsd: 200_000,
        priceUsd: 0.2,
        baseDecimals: null,
      },
    ]),
    hyperliquid: null,
    refreshedAt: "2026-10-21T00:00:00.000Z",
  };
}

function buyIntent(decimals: number | null): SwapIntent {
  return {
    idempotencyKey: `id-${Math.random()}`,
    side: "buy",
    notionalUsd: 5,
    slippageBps: 50,
    token: {
      symbol: "MPLX",
      address: contract,
      decimals,
      chain: { kind: "evm", chainId: 8453 },
      chainKey: "base",
      pairMap: evmToken(decimals).pairMap,
    },
    holdings: [{ symbol: "USDC", address: "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", amount: 20, usd: 20, native: false, decimals: 6, chainKey: "base" }],
    hyperliquid: null,
    receivedAtMs: 0,
  };
}

function deps(read: (() => Promise<number | null>) | null, seen: Array<number | null>): ExecutorDeps {
  return {
    config: {
      maxUsdPerTrade: 5,
      dailyUsdCap: 25,
      maxSlippageBps: 100,
      slippageHardMaxBps: 300,
      maxLeverage: 1,
      minLiquidityUsd: 75_000,
      killSwitch: false,
      enabledChainKeys: new Set(["base"]),
    },
    mode: "dry_run",
    spentTodayUsd: 0,
    quoteHop: async (_hop, context) => {
      seen.push(context.decimals);
      if (context.decimals !== 6) return { priceImpactPct: null, feeUsd: 0, buyAmount: "0" };
      return { priceImpactPct: 0.2, feeUsd: 0.01, buyAmount: "10", signable: true };
    },
    markPrice: async () => null,
    send: async () => {
      throw new Error("dry-run must not send");
    },
    readTokenDecimals: read ? async () => read() : undefined,
  };
}

function signer(calls: string[], address: string): TransactionSigner {
  return {
    backend: "keystore",
    evmAddress: () => null,
    solanaAddress: () => address,
    async signEvm() {
      return "0x";
    },
    async signSolana() {
      calls.push("solana");
      return new Uint8Array();
    },
    async signHyperliquid() {
      return { r: "0x01", s: "0x02", v: 27 };
    },
  };
}

test("an evm quote uses cached erc-20 decimals and skips when they stay unknown", async () => {
  resetTokenDecimals();
  resetExecutorState();
  let reads = 0;
  const filled = await fillTokenDecimals([evmToken(null)], { base: "https://rpc.example" }, async () => {
    reads += 1;
    return 6;
  });
  assert.equal(filled[0]?.decimals, 6);
  await fillTokenDecimals([evmToken(null)], { base: "https://rpc.example" }, async () => {
    reads += 1;
    return 6;
  });
  assert.equal(reads, 1);
  resetTokenDecimals();
  const unknown = await fillTokenDecimals([evmToken(null)], { base: "https://rpc.example" }, async () => null);
  assert.equal(unknown[0]?.decimals, null);

  const seen: Array<number | null> = [];
  const quoted = await execute(buyIntent(null), deps(async () => 6, seen));
  assert.equal(quoted.decision, "would_send");
  assert.deepEqual(seen, [6]);

  resetTokenDecimals();
  resetExecutorState();
  const missed: Array<number | null> = [];
  const skipped = await execute(buyIntent(null), deps(async () => null, missed));
  assert.equal(skipped.decision, "skipped");
  assert.equal(skipped.reason, "no route inside the slippage cap");
  assert.deepEqual(missed, [null]);
});

test("a holding without chainKey is read on the buy chain", async () => {
  const row = { symbol: "USDC", address: "usdc", amount: 20, usd: 20, native: false, decimals: 6 };
  assert.equal(holdingsSchema.safeParse([row]).success, true);
  assert.equal(holdingsSchema.safeParse([{ ...row, chainKey: "base" }]).success, true);
  assert.equal(holdingsSchema.safeParse([{ ...row, chainKey: "nope" }]).success, false);
  const seen: Array<string | undefined> = [];
  const read = await holdingsForTrade(
    true,
    [row],
    async (holding) => {
      seen.push(holding.chainKey);
      return holding.chainKey === "base" ? 4 : null;
    },
    "base",
  );
  assert.equal(read.ok, true);
  if (read.ok) {
    assert.equal(read.holdings[0]?.amount, 4);
    assert.equal(read.holdings[0]?.chainKey, "base");
  }
  const tagged = await holdingsForTrade(
    true,
    [{ ...row, chainKey: "solana" }],
    async (holding) => {
      seen.push(holding.chainKey);
      return 2;
    },
    "base",
  );
  assert.equal(tagged.ok, true);
  if (tagged.ok) assert.equal(tagged.holdings[0]?.chainKey, "solana");
  assert.deepEqual(seen, ["base", "solana"]);
});

test("SOLANA_PROGRAM_ALLOWLIST adds to the base programs", () => {
  const extra = "Extra111111111111111111111111111111111111";
  const config = loadConfig({ SOLANA_PROGRAM_ALLOWLIST: extra });
  assert.equal(config.solanaProgramAllowlist.includes(JUPITER_PROGRAM_ID), true);
  assert.equal(config.solanaProgramAllowlist.includes(extra), true);
});

test("a bad jupiter body does not abort the other quotes", async () => {
  resetProviderGuards();
  const config = loadConfig({ OKX_API_KEY: "k", OKX_API_SECRET: "s", OKX_API_PASSPHRASE: "p" });
  const quote = await raceProviderQuotes(
    config,
    { sellAddress: "in", buyAddress: "out", sellAmount: "1000", chain: { kind: "solana" } },
    { spentUsd: 5, priceUsd: 1, decimals: 6 },
    async (input) => {
      const host = new URL(String(input)).hostname;
      if (host === "api.jup.ag") return new Response(JSON.stringify({ outAmount: "10", priceImpactPct: "nope" }), { status: 200 });
      return new Response(JSON.stringify({ code: "0", data: [{ toTokenAmount: "1000" }] }), { status: 200 });
    },
  );
  assert.equal(quote.provider, "okx");
  assert.equal(quote.priceImpactPct !== null, true);
});

test("spl recovery pays the destination associated token account", async () => {
  const payer = Keypair.generate();
  const destination = Keypair.generate().publicKey;
  const mint = Keypair.generate().publicKey;
  const source = Keypair.generate().publicKey;
  const program = new PublicKey("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA");
  const input = {
    payer: payer.publicKey,
    destinationOwner: destination,
    mint,
    source,
    program,
    amount: 1000n,
    decimals: 6,
  };
  const instructions = tokenRecoveryInstructions(input);
  const again = tokenRecoveryInstructions(input);
  const ata = associatedTokenAccount(destination, mint, program);
  assert.notEqual(ata.toBase58(), destination.toBase58());
  assert.equal(instructions[0]?.data[0], 1);
  assert.equal(instructions[1]?.data[0], 12);
  assert.equal(instructions[1]?.data[9], 6);
  assert.equal(instructions[1]?.keys[2]?.pubkey.toBase58(), ata.toBase58());
  assert.deepEqual(
    again.map((item) => item.data.toString("hex")),
    instructions.map((item) => item.data.toString("hex")),
  );
  const raw = new VersionedTransaction(
    new TransactionMessage({
      payerKey: payer.publicKey,
      recentBlockhash: "11111111111111111111111111111111",
      instructions,
    }).compileToV0Message(),
  ).serialize();
  const calls: string[] = [];
  const allowed = withPolicy(signer(calls, payer.publicKey.toBase58()), loadConfig({ OWNER_WITHDRAW_ADDRESSES: destination.toBase58() }));
  await allowed.signSolana(raw);
  assert.deepEqual(calls, ["solana"]);
  const stranger = Keypair.generate().publicKey;
  const denied = withPolicy(signer(calls, payer.publicKey.toBase58()), loadConfig({ OWNER_WITHDRAW_ADDRESSES: stranger.toBase58() }));
  await assert.rejects(() => denied.signSolana(raw), /not allowlisted/);
  assert.deepEqual(calls, ["solana"]);
});
