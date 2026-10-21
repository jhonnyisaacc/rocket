import { CHAINS, chainByKey } from "./chains.js";
import type { LimitConfig } from "./limits.js";
import { isSolanaAddress } from "./signer.js";
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
  adminToken: string | null;
  withdrawEnabled: boolean;
  maxWithdrawAmount: number;
  tokenRecoveryAllowlist: string[];
  spendTimezone: string;
  minPoolAgeHours: number;
  minVolume24hUsd: number;
  hyperliquidAccount: string | null;
  allowHotApproval: boolean;
  screening: boolean;
  maxTokenTax: number;
  routerAllowlist: Record<number, string[]>;
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

function screeningEnabled(env: NodeJS.ProcessEnv, live: boolean): boolean {
  if (env.TOKEN_SCREENING === "false") return false;
  if (env.TOKEN_SCREENING === "true") return true;
  return live;
}

function taxCap(env: NodeJS.ProcessEnv): number {
  const raw = env.MAX_TOKEN_TAX;
  if (raw === undefined || raw === "") return 0.1;
  const value = Number(raw);
  if (!Number.isFinite(value) || value < 0 || value > 1) throw new Error("invalid MAX_TOKEN_TAX");
  return value;
}

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
    adminToken: env.ADMIN_TOKEN ?? null,
    withdrawEnabled: env.WITHDRAW_ENABLED === "true",
    maxWithdrawAmount: intEnv(env, "MAX_WITHDRAW_AMOUNT", 1),
    tokenRecoveryAllowlist: splitList(env.TOKEN_RECOVERY_ALLOWLIST),
    spendTimezone: spendTimezone(env.SPEND_TIMEZONE),
    minPoolAgeHours: intEnv(env, "MIN_POOL_AGE_HOURS", 24),
    minVolume24hUsd: intEnv(env, "MIN_VOLUME_24H_USD", 10_000),
    hyperliquidAccount: env.HYPERLIQUID_ACCOUNT_ADDRESS ?? null,
    allowHotApproval: env.ALLOW_HOT_APPROVAL === "true",
    screening: screeningEnabled(env, env.LISTING_TRADER_LIVE === "true"),
    maxTokenTax: taxCap(env),
    routerAllowlist: routerAllowlist(env),
    solanaProgramAllowlist: [...new Set([...SOLANA_BASE_PROGRAMS, ...splitList(env.SOLANA_PROGRAM_ALLOWLIST)])],
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

export const OFFICIAL_HTTP = {
  zeroExBase: "https://api.0x.org",
  jupiterBase: "https://api.jup.ag/swap/v1",
  lifiBase: "https://li.quest/v1",
  oneInchBase: "https://api.1inch.com",
  kyberBase: "https://aggregator-api.kyberswap.com",
  veloraBase: "https://api.velora.xyz",
  hyperliquidUrl: "https://api.hyperliquid.xyz",
  coingeckoBase: "https://api.coingecko.com/api/v3",
  dexscreenerBase: "https://api.dexscreener.com",
  jitoUrl: "https://mainnet.block-engine.jito.wtf/api/v1/transactions",
  turnkey: "https://api.turnkey.com",
} as const;

function sameBase(actual: string, official: string): boolean {
  try {
    const left = new URL(actual);
    const right = new URL(official);
    if (left.origin !== right.origin) return false;
    return left.pathname === right.pathname || left.pathname.startsWith(`${right.pathname}/`);
  } catch {
    return false;
  }
}

function spendTimezone(raw: string | undefined): string {
  const timeZone = raw && raw.length > 0 ? raw : "UTC";
  try {
    new Intl.DateTimeFormat("en-CA", { timeZone }).format(new Date());
  } catch {
    throw new Error("invalid SPEND_TIMEZONE");
  }
  return timeZone;
}

function routerAllowlist(env: NodeJS.ProcessEnv): Record<number, string[]> {
  if (env.ROUTER_ALLOWLIST_JSON) {
    const parsed: unknown = JSON.parse(env.ROUTER_ALLOWLIST_JSON);
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) throw new Error("ROUTER_ALLOWLIST_JSON must be an object");
    const map: Record<number, string[]> = {};
    for (const [id, list] of Object.entries(parsed)) {
      if (!/^\d+$/.test(id) || !Array.isArray(list) || list.some((item) => typeof item !== "string" || item.length === 0)) {
        throw new Error("ROUTER_ALLOWLIST_JSON is invalid");
      }
      map[Number(id)] = list;
    }
    return map;
  }
  const global = splitList(env.ROUTER_ALLOWLIST);
  const map: Record<number, string[]> = {};
  if (global.length === 0) return map;
  for (const chain of CHAINS) {
    if (chain.chain.kind === "evm") map[chain.chain.chainId] = [...global];
  }
  return map;
}

function isOwnerAddress(value: string): boolean {
  return /^0x[0-9a-fA-F]{40}$/.test(value) || isSolanaAddress(value);
}

export function assertLiveEdges(config: AppConfig, env: NodeJS.ProcessEnv): void {
  if (config.withdrawEnabled) {
    if (config.withdrawAllowlist.length === 0) throw new Error("WITHDRAW_ENABLED requires OWNER_WITHDRAW_ADDRESSES");
    for (const address of config.withdrawAllowlist) {
      if (!isOwnerAddress(address)) throw new Error("OWNER_WITHDRAW_ADDRESSES has an invalid address");
    }
    for (const token of config.tokenRecoveryAllowlist) {
      if (!isOwnerAddress(token)) throw new Error("TOKEN_RECOVERY_ALLOWLIST has an invalid address");
    }
  }
  if (!config.live) return;
  const fields = ["zeroExBase", "jupiterBase", "lifiBase", "oneInchBase", "kyberBase", "veloraBase", "hyperliquidUrl", "coingeckoBase", "dexscreenerBase"] as const;
  for (const field of fields) {
    if (!sameBase(config[field], OFFICIAL_HTTP[field])) throw new Error(`live mode pins ${field} to ${OFFICIAL_HTTP[field]}`);
  }
  if (config.jitoUrl && !sameBase(config.jitoUrl, OFFICIAL_HTTP.jitoUrl)) throw new Error(`live mode pins jitoUrl to ${OFFICIAL_HTTP.jitoUrl}`);
  if (env.TURNKEY_API_BASE && !sameBase(env.TURNKEY_API_BASE, OFFICIAL_HTTP.turnkey)) {
    throw new Error(`live mode pins TURNKEY_API_BASE to ${OFFICIAL_HTTP.turnkey}`);
  }
  assertServiceUrl(config.notifierUrl);
  assertServiceUrl(config.resolverUrl);
}

function assertServiceUrl(value: string | null): void {
  if (!value) return;
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error("notifier and resolver URLs must be https or a railway.internal host");
  }
  const railway = url.hostname === "railway.internal" || url.hostname.endsWith(".railway.internal");
  if (url.protocol === "https:") return;
  if (url.protocol === "http:" && railway) return;
  throw new Error("notifier and resolver URLs must be https or a railway.internal host");
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

export function configSecrets(config: AppConfig): string[] {
  const { zeroEx, jupiter, lifi, oneInch, okxKey, okxSecret, okxPassphrase, acrossKey, relayKey, debridgeToken, goplus, blockaid } = config.keys;
  return [
    zeroEx,
    jupiter,
    lifi,
    oneInch,
    okxKey,
    okxSecret,
    okxPassphrase,
    acrossKey,
    relayKey,
    debridgeToken,
    goplus,
    blockaid,
    config.authToken,
    config.adminToken,
    config.notifierUrl,
    config.databaseUrl,
    ...Object.values(config.rpcByChainKey),
    ...Object.values(config.mevRpcByChainId),
  ].filter((item): item is string => typeof item === "string" && item.length >= 8);
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
    maxTokenTax: config.maxTokenTax,
    jito: config.jitoUrl !== null,
  };
}
