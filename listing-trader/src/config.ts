import { CHAINS, chainByKey } from "./chains.js";
import type { LimitConfig } from "./limits.js";
import { DEFAULT_MAX_VALUE_WEI, SOLANA_BASE_PROGRAMS } from "./signing-policy.js";

export type ApprovalSeed = { chainId: number; token: string; spender: string; owner: string; amount: string };

export type AppConfig = LimitConfig & {
  live: boolean;
  port: number;
  databaseUrl: string | null;
  notifierUrl: string | null;
  resolverUrl: string | null;
  zeroExBase: string;
  jupiterBase: string;
  lifiBase: string;
  hyperliquidUrl: string;
  jupiterImpactUnit: "fraction" | "percent";
  liveLookupTimeoutMs: number;
  fullRefreshMs: number;
  liquidityRefreshMs: number;
  withdrawAllowlist: string[];
  dexscreenerSlugOverrides: Record<string, string>;
  rpcByChainKey: Record<string, string>;
  refreshEnabled: boolean;
  shortlistLimit: number;
  quoteDecimals: Record<string, number>;
  coingeckoBase: string;
  dexscreenerBase: string;
  quoteTimeoutMs: number;
  quoteDeadlineMs: number;
  providerBudgetPerMinute: number;
  providerFailureThreshold: number;
  providerOpenMs: number;
  maxBridgeUsd: number;
  maxBridgeFeeBps: number;
  dailyBridgeUsdCap: number;
  targetUsdcUsd: number;
  targetNativeUsd: number;
  authToken: string | null;
  allowLocalSigner: boolean;
  allowHotApproval: boolean;
  screening: boolean;
  routerAllowlist: string[];
  solanaProgramAllowlist: string[];
  maxValueWei: bigint;
  mevRpcByChainId: Record<number, string>;
  jitoUrl: string | null;
  oneInchBase: string;
  kyberBase: string;
  veloraBase: string;
  keys: {
    zeroEx: string | null;
    jupiter: string | null;
    lifi: string | null;
    lifiIntegrator: string | null;
    oneInch: string | null;
    okxKey: string | null;
    okxSecret: string | null;
    okxPassphrase: string | null;
    kyberClientId: string;
    veloraPartner: string | null;
    acrossKey: string | null;
    acrossIntegrator: string | null;
    relayKey: string | null;
    debridgeToken: string | null;
    goplus: string | null;
    blockaid: string | null;
  };
  now?: () => number;
  approvalSeed: ApprovalSeed[];
};

function intEnv(env: NodeJS.ProcessEnv, name: string, fallback: number): number {
  const raw = env[name];
  if (raw === undefined || raw === "") return fallback;
  const value = Number(raw);
  if (!Number.isFinite(value)) throw new Error(`invalid ${name}`);
  return value;
}

function enabledKeys(env: NodeJS.ProcessEnv): Set<string> {
  const disabled = new Set(
    (env.DISABLED_CHAINS ?? "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  );
  const extra = (env.ENABLED_CHAINS ?? "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  const keys = new Set(CHAINS.filter((chain) => chain.enabledByDefault && !disabled.has(chain.key)).map((chain) => chain.key));
  for (const key of extra) {
    if (!chainByKey(key)) throw new Error(`unknown chain ${key}`);
    keys.add(key);
  }
  for (const key of disabled) keys.delete(key);
  return keys;
}

function quoteDecimals(env: NodeJS.ProcessEnv): Record<string, number> {
  if (!env.QUOTE_DECIMALS_JSON) return {};
  const parsed: unknown = JSON.parse(env.QUOTE_DECIMALS_JSON);
  if (typeof parsed !== "object" || parsed === null) throw new Error("QUOTE_DECIMALS_JSON must be an object");
  const out: Record<string, number> = {};
  for (const [symbol, decimals] of Object.entries(parsed)) {
    if (typeof decimals !== "number" || !Number.isInteger(decimals) || decimals < 0 || decimals > 18) {
      throw new Error(`invalid quote decimals for ${symbol}`);
    }
    out[symbol.toUpperCase()] = decimals;
  }
  return out;
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): AppConfig {
  const maxSlippageBps = intEnv(env, "MAX_SLIPPAGE_BPS", 100);
  const slippageHardMaxBps = intEnv(env, "SLIPPAGE_HARD_MAX_BPS", 300);
  if (maxSlippageBps > slippageHardMaxBps) {
    throw new Error("MAX_SLIPPAGE_BPS exceeds SLIPPAGE_HARD_MAX_BPS");
  }
  const rpcByChainKey: Record<string, string> = {};
  for (const chain of CHAINS) {
    const raw = env[chain.rpcEnv];
    if (raw) rpcByChainKey[chain.key] = raw;
    else if (chain.defaultRpc) rpcByChainKey[chain.key] = chain.defaultRpc;
  }
  let dexscreenerSlugOverrides: Record<string, string> = {};
  if (env.DEXSCREENER_CHAIN_SLUGS) {
    const parsed: unknown = JSON.parse(env.DEXSCREENER_CHAIN_SLUGS);
    if (typeof parsed !== "object" || parsed === null) throw new Error("DEXSCREENER_CHAIN_SLUGS must be an object");
    dexscreenerSlugOverrides = parsed as Record<string, string>;
  }
  return {
    live: env.LISTING_TRADER_LIVE === "true",
    killSwitch: env.KILL_SWITCH === "1" || env.KILL_SWITCH === "true",
    port: intEnv(env, "PORT", 8080),
    maxUsdPerTrade: intEnv(env, "MAX_USD_PER_TRADE", 5),
    dailyUsdCap: intEnv(env, "DAILY_USD_CAP", 25),
    maxSlippageBps,
    slippageHardMaxBps,
    maxLeverage: intEnv(env, "MAX_LEVERAGE", 1),
    minLiquidityUsd: intEnv(env, "MIN_LIQUIDITY_USD", 75_000),
    enabledChainKeys: enabledKeys(env),
    databaseUrl: env.DATABASE_URL ?? null,
    notifierUrl: env.NOTIFIER_WEBHOOK_URL ?? null,
    resolverUrl: env.RESOLVER_URL ?? null,
    zeroExBase: env.ZEROX_API_BASE ?? "https://api.0x.org",
    jupiterBase: env.JUPITER_API_BASE ?? "https://api.jup.ag/swap/v1",
    lifiBase: env.LIFI_API_BASE ?? "https://li.quest/v1",
    hyperliquidUrl: env.HYPERLIQUID_API_URL ?? "https://api.hyperliquid.xyz",
    jupiterImpactUnit: env.JUPITER_IMPACT_UNIT === "percent" ? "percent" : "fraction",
    liveLookupTimeoutMs: intEnv(env, "LIVE_LOOKUP_TIMEOUT_MS", 400),
    fullRefreshMs: intEnv(env, "FULL_REFRESH_MS", 24 * 60 * 60 * 1000),
    liquidityRefreshMs: intEnv(env, "LIQUIDITY_REFRESH_MS", 10 * 60 * 1000),
    refreshEnabled: env.REFRESH_ENABLED === "true",
    shortlistLimit: intEnv(env, "SHORTLIST_LIMIT", 200),
    quoteDecimals: quoteDecimals(env),
    coingeckoBase: env.COINGECKO_API_BASE ?? "https://api.coingecko.com/api/v3",
    dexscreenerBase: env.DEXSCREENER_API_BASE ?? "https://api.dexscreener.com",
    withdrawAllowlist: (env.OWNER_WITHDRAW_ADDRESSES ?? "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
    dexscreenerSlugOverrides,
    rpcByChainKey,
    quoteTimeoutMs: intEnv(env, "QUOTE_TIMEOUT_MS", 350),
    quoteDeadlineMs: intEnv(env, "QUOTE_DEADLINE_MS", 500),
    providerBudgetPerMinute: intEnv(env, "PROVIDER_BUDGET_PER_MINUTE", 30),
    providerFailureThreshold: intEnv(env, "PROVIDER_FAILURE_THRESHOLD", 3),
    providerOpenMs: intEnv(env, "PROVIDER_OPEN_MS", 30_000),
    maxBridgeUsd: intEnv(env, "MAX_BRIDGE_USD", 25),
    maxBridgeFeeBps: intEnv(env, "MAX_BRIDGE_FEE_BPS", 50),
    dailyBridgeUsdCap: intEnv(env, "DAILY_BRIDGE_USD_CAP", 50),
    targetUsdcUsd: intEnv(env, "TARGET_USDC_USD", 20),
    targetNativeUsd: intEnv(env, "TARGET_NATIVE_USD", 2),
    authToken: env.AUTH_TOKEN ?? null,
    allowLocalSigner: env.ALLOW_LOCAL_SIGNER === "true",
    allowHotApproval: env.ALLOW_HOT_APPROVAL === "true",
    screening: env.TOKEN_SCREENING === "true",
    routerAllowlist: splitList(env.ROUTER_ALLOWLIST),
    solanaProgramAllowlist: env.SOLANA_PROGRAM_ALLOWLIST ? splitList(env.SOLANA_PROGRAM_ALLOWLIST) : [...SOLANA_BASE_PROGRAMS],
    maxValueWei: weiEnv(env.MAX_NATIVE_VALUE_WEI),
    mevRpcByChainId: mevRpcs(env),
    jitoUrl: env.JITO_ENABLED === "true" ? (env.JITO_BLOCK_ENGINE_URL ?? "https://mainnet.block-engine.jito.wtf/api/v1/transactions") : null,
    oneInchBase: env.ONEINCH_API_BASE ?? "https://api.1inch.com",
    kyberBase: env.KYBER_API_BASE ?? "https://aggregator-api.kyberswap.com",
    veloraBase: env.VELORA_API_BASE ?? "https://api.velora.xyz",
    keys: {
      zeroEx: env.ZEROX_API_KEY ?? null,
      jupiter: env.JUPITER_API_KEY ?? null,
      lifi: env.LIFI_API_KEY ?? null,
      lifiIntegrator: env.LIFI_INTEGRATOR ?? null,
      oneInch: env.ONEINCH_API_KEY ?? null,
      okxKey: env.OKX_API_KEY ?? null,
      okxSecret: env.OKX_API_SECRET ?? null,
      okxPassphrase: env.OKX_API_PASSPHRASE ?? null,
      kyberClientId: env.KYBERSWAP_CLIENT_ID ?? "listing-trader",
      veloraPartner: env.VELORA_PARTNER ?? null,
      acrossKey: env.ACROSS_API_KEY ?? null,
      acrossIntegrator: env.ACROSS_INTEGRATOR_ID ?? null,
      relayKey: env.RELAY_API_KEY ?? null,
      debridgeToken: env.DEBRIDGE_ACCESS_TOKEN ?? null,
      goplus: env.GOPLUS_API_KEY ?? null,
      blockaid: env.BLOCKAID_API_KEY ?? null,
    },
    approvalSeed: approvalSeed(env),
  };
}

function approvalSeed(env: NodeJS.ProcessEnv): ApprovalSeed[] {
  if (!env.APPROVAL_CACHE_JSON) return [];
  const parsed: unknown = JSON.parse(env.APPROVAL_CACHE_JSON);
  if (!Array.isArray(parsed)) throw new Error("APPROVAL_CACHE_JSON must be an array");
  return parsed.flatMap((row) => {
    if (typeof row !== "object" || row === null) return [];
    const item = row as Partial<ApprovalSeed>;
    if (typeof item.chainId !== "number" || typeof item.token !== "string" || typeof item.spender !== "string" || typeof item.owner !== "string" || typeof item.amount !== "string") {
      throw new Error("APPROVAL_CACHE_JSON row is invalid");
    }
    return [{ chainId: item.chainId, token: item.token, spender: item.spender, owner: item.owner, amount: item.amount }];
  });
}

function splitList(raw: string | undefined): string[] {
  return (raw ?? "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function weiEnv(raw: string | undefined): bigint {
  if (raw === undefined || raw === "") return DEFAULT_MAX_VALUE_WEI;
  if (!/^\d+$/.test(raw)) throw new Error("invalid MAX_NATIVE_VALUE_WEI");
  return BigInt(raw);
}

function mevRpcs(env: NodeJS.ProcessEnv): Record<number, string> {
  const out: Record<number, string> = {};
  for (const [name, value] of Object.entries(env)) {
    const match = /^MEV_RPC_URL_(\d+)$/.exec(name);
    if (match?.[1] && value) out[Number(match[1])] = value;
  }
  return out;
}

export function publicConfig(config: AppConfig): Record<string, unknown> {
  return {
    live: config.live,
    killSwitch: config.killSwitch,
    maxUsdPerTrade: config.maxUsdPerTrade,
    dailyUsdCap: config.dailyUsdCap,
    maxSlippageBps: config.maxSlippageBps,
    maxLeverage: config.maxLeverage,
    minLiquidityUsd: config.minLiquidityUsd,
    enabledChainKeys: [...config.enabledChainKeys],
    refreshEnabled: config.refreshEnabled,
    shortlistLimit: config.shortlistLimit,
    quoteDeadlineMs: config.quoteDeadlineMs,
    screening: config.screening,
    allowLocalSigner: config.allowLocalSigner,
    jito: config.jitoUrl !== null,
  };
}
