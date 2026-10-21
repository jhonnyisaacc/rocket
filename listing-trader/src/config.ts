import { CHAINS, chainByKey } from "./chains.js";
import type { LimitConfig } from "./limits.js";

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
  };
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
  };
}
