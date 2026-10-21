import type { ChainRef } from "./domain.js";

export type LiveSend = "eip1559" | "solana" | "hypercore" | "disabled";

export type AggregatorId = "zeroex" | "lifi" | "jupiter" | "none";

export type ChainSpec = {
  key: string;
  chain: ChainRef;
  nativeSymbol: string;
  minNativeReserve: number;
  aggregator: AggregatorId;
  enabledByDefault: boolean;
  liveSend: LiveSend;
  rpcEnv: string;
  defaultRpc: string | null;
  dexscreenerSlug: string | null;
  sources: string[];
  gap: string | null;
};

const evm = (
  key: string,
  chainId: number,
  nativeSymbol: string,
  aggregator: AggregatorId,
  rpcEnv: string,
  defaultRpc: string | null,
  dexscreenerSlug: string | null,
  sources: string[],
  gap: string | null = null,
): ChainSpec => ({
  key,
  chain: { kind: "evm", chainId },
  nativeSymbol,
  minNativeReserve: 0.001,
  aggregator,
  enabledByDefault: true,
  liveSend: key === "zksync" ? "disabled" : "eip1559",
  rpcEnv,
  defaultRpc,
  dexscreenerSlug,
  sources,
  gap,
});

export const CHAINS: readonly ChainSpec[] = [
  evm("ethereum", 1, "ETH", "zeroex", "RPC_URL_1", null, "ethereum", [
    "https://docs.0x.org/docs/introduction/supported-chains",
  ]),
  evm("optimism", 10, "ETH", "zeroex", "RPC_URL_10", null, "optimism", [
    "https://docs.0x.org/docs/introduction/supported-chains",
  ]),
  evm("bnb", 56, "BNB", "zeroex", "RPC_URL_56", null, "bsc", [
    "https://docs.0x.org/docs/introduction/supported-chains",
  ]),
  evm("polygon", 137, "POL", "zeroex", "RPC_URL_137", null, "polygon", [
    "https://docs.0x.org/docs/introduction/supported-chains",
  ]),
  evm(
    "zksync",
    324,
    "ETH",
    "lifi",
    "RPC_URL_324",
    "https://mainnet.era.zksync.io",
    "zksync",
    [
      "https://docs.zksync.io/zksync-network/zksync-era/network-details",
      "https://docs.li.fi/llms.txt",
    ],
    "0x Swap API does not list zkSync. Quotes use LI.FI with fromChain equal to toChain. Live send stays off because zkSync transactions are not standard EIP-1559.",
  ),
  evm("base", 8453, "ETH", "zeroex", "RPC_URL_8453", null, "base", [
    "https://docs.0x.org/docs/introduction/supported-chains",
  ]),
  evm("arbitrum", 42161, "ETH", "zeroex", "RPC_URL_42161", null, "arbitrum", [
    "https://docs.0x.org/docs/introduction/supported-chains",
  ]),
  evm("linea", 59144, "ETH", "zeroex", "RPC_URL_59144", null, "linea", [
    "https://docs.0x.org/docs/introduction/supported-chains",
  ]),
  evm(
    "blast",
    81457,
    "ETH",
    "lifi",
    "RPC_URL_81457",
    "https://rpc.blast.io",
    "blast",
    [
      "https://docs.blast.io/building/network-information",
      "https://docs.li.fi/llms.txt",
    ],
    "0x removed Blast from its swap chain list. Quotes use LI.FI same-chain only.",
  ),
  evm("scroll", 534352, "ETH", "zeroex", "RPC_URL_534352", null, "scroll", [
    "https://docs.0x.org/docs/introduction/supported-chains",
  ]),
  evm(
    "robinhood",
    4663,
    "ETH",
    "zeroex",
    "RPC_URL_4663",
    "https://rpc.mainnet.chain.robinhood.com",
    null,
    [
      "https://docs.robinhood.com/chain/connecting/",
      "https://docs.0x.org/changelog",
    ],
    "DexScreener's slug for Robinhood Chain was not in the sources checked, so pool refresh ignores that slug until DEXSCREENER_CHAIN_SLUGS sets one.",
  ),
  evm(
    "hyperevm",
    999,
    "HYPE",
    "zeroex",
    "RPC_URL_999",
    "https://rpc.hyperliquid.xyz/evm",
    null,
    [
      "https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/hyperevm",
      "https://docs.0x.org/docs/introduction/supported-chains",
    ],
    "DexScreener's slug for HyperEVM was not confirmed. Pool refresh ignores it until DEXSCREENER_CHAIN_SLUGS sets one. 0x lists HyperEVM on the Swap API.",
  ),
  {
    key: "solana",
    chain: { kind: "solana" },
    nativeSymbol: "SOL",
    minNativeReserve: 0.01,
    aggregator: "jupiter",
    enabledByDefault: true,
    liveSend: "solana",
    rpcEnv: "SOLANA_RPC_URL",
    defaultRpc: null,
    dexscreenerSlug: "solana",
    sources: ["https://developers.jup.ag/docs/api-reference/swap/v1/quote"],
    gap: "Jupiter's published quote page says Metis Swap V1 is superseded by Swap V2. The default URL remains the V1 path that page documents. Live mode refuses any other host.",
  },
  {
    key: "hypercore",
    chain: { kind: "hypercore", market: "perp" },
    nativeSymbol: "USDC",
    minNativeReserve: 0,
    aggregator: "none",
    enabledByDefault: true,
    liveSend: "hypercore",
    rpcEnv: "HYPERLIQUID_API_URL",
    defaultRpc: "https://api.hyperliquid.xyz",
    dexscreenerSlug: null,
    sources: [
      "https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/exchange-endpoint",
      "https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/nonces-and-api-wallets",
      "https://github.com/hyperliquid-dex/hyperliquid-python-sdk/blob/master/hyperliquid/utils/signing.py",
    ],
    gap: "The service signs only order, cancel, and updateLeverage. It does not construct withdraw3 or agentSendAsset. Official docs describe API wallets as signers for a master account. They do not state a protocol-level withdraw ban in the pages checked, so the ban is enforced here.",
  },
];

const byKey = new Map(CHAINS.map((chain) => [chain.key, chain]));
const byEvmId = new Map(
  CHAINS.flatMap((chain) => (chain.chain.kind === "evm" ? [[chain.chain.chainId, chain] as const] : [])),
);

export function chainByKey(key: string): ChainSpec | undefined {
  return byKey.get(key);
}

export function chainByEvmId(chainId: number): ChainSpec | undefined {
  return byEvmId.get(chainId);
}

const FEE_RANK: Record<string, number> = {
  solana: 10,
  base: 20,
  arbitrum: 30,
  optimism: 40,
  polygon: 50,
  bnb: 60,
  linea: 70,
  scroll: 80,
  blast: 90,
  zksync: 100,
  robinhood: 110,
  hyperevm: 120,
  hypercore: 150,
  ethereum: 200,
};

const GAS_CEILING_USD: Record<string, number> = {
  solana: 0.02,
  base: 0.03,
  arbitrum: 0.03,
  optimism: 0.03,
  polygon: 0.05,
  bnb: 0.05,
  linea: 0.05,
  scroll: 0.08,
  blast: 0.08,
  zksync: 0.1,
  robinhood: 0.1,
  hyperevm: 0.1,
  hypercore: 0,
  ethereum: 2,
};

export function feeRankOf(key: string): number {
  return FEE_RANK[key] ?? 1_000;
}

export function gasCeilingUsd(key: string): number {
  return GAS_CEILING_USD[key] ?? 1;
}

export function dexscreenerSlugMap(overrides: Record<string, string> = {}): Map<string, string> {
  const map = new Map<string, string>();
  for (const chain of CHAINS) {
    if (chain.dexscreenerSlug) map.set(chain.dexscreenerSlug, chain.key);
  }
  for (const [slug, key] of Object.entries(overrides)) {
    if (chainByKey(key)) map.set(slug, key);
  }
  return map;
}
