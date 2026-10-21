export type ChainKind = "solana" | "evm" | "hypercore";

export type ChainRef =
  | { kind: "solana" }
  | { kind: "evm"; chainId: number }
  | { kind: "hypercore"; market: "perp" | "spot" };

export type Pool = {
  poolAddress: string;
  dex: string;
  chainKey: string;
  baseSymbol: string;
  baseAddress: string;
  quoteSymbol: string;
  quoteAddress: string;
  liquidityUsd: number;
  priceUsd: number | null;
  baseDecimals: number | null;
  baseName?: string;
  quotePriceUsd?: number | null;
  quoteDecimals?: number | null;
  createdAtMs?: number | null;
  volume24hUsd?: number | null;
};

export type PairMap = {
  pools: Pool[];
  top: Pool | null;
  bestByQuote: Record<string, Pool>;
};

export type HyperliquidMarket = {
  coin: string;
  assetIndex: number;
  market: "perp" | "spot";
  maxLeverage: number;
};

export type TokenRecord = {
  id: string;
  ticker: string;
  names: string[];
  chainKey: string;
  chain: ChainRef;
  contract: string;
  decimals: number | null;
  pairMap: PairMap;
  hyperliquid: HyperliquidMarket | null;
  refreshedAt: string;
  sourceId?: string;
};

export type Holding = {
  symbol: string;
  address: string;
  amount: number;
  usd: number;
  native: boolean;
  decimals?: number;
  chainKey?: string;
};

export type Alert = {
  id: string;
  ticker: string;
  projectName: string;
  source: string;
  publishedAt: string;
  receivedAt: string;
  chainHint?: string;
};

export type MatchHit = { kind: "hit"; token: TokenRecord; alternates: TokenRecord[] };
export type MatchReject = {
  kind: "lookalike" | "ambiguous" | "unlisted" | "illiquid";
  ticker: string;
  detail: string;
};
export type MatchOutcome = MatchHit | MatchReject;

export type Hop = {
  sellSymbol: string;
  sellAddress: string;
  buySymbol: string;
  buyAddress: string;
  sellAmount: string;
};

export type RoutePlan =
  | { id: string; kind: "aggregator"; hop: Hop }
  | {
      id: string;
      kind: "two_hop";
      first: Hop;
      second: Hop;
      quotePriceUsd: number | null;
      quoteDecimals: number | null;
    };

export type RouteLeg = {
  sellAddress: string;
  buyAddress: string;
  sellAmount: string;
  spentUsd: number;
  priceUsd: number | null;
  decimals: number | null;
};

export type RouteQuote = {
  planId: string;
  kind: "aggregator" | "two_hop";
  hops: string[];
  priceImpactPct: number;
  feeUsd: number;
  buyAmount: string;
  legs?: RouteLeg[];
  provider?: string;
  netOutputUsd?: number;
  gasUsd?: number;
  chainKey?: string;
  feeRank?: number;
  signable?: boolean;
  note?: string;
  chain?: ChainRef;
};

export type SwapIntent = {
  idempotencyKey: string;
  side: "buy" | "sell";
  notionalUsd: number;
  slippageBps: number;
  token: {
    symbol: string;
    address: string;
    decimals: number | null;
    chain: ChainRef;
    chainKey: string;
    pairMap: PairMap;
  };
  holdings: Holding[];
  hyperliquid: HyperliquidMarket | null;
  receivedAtMs: number;
  alternates?: Array<SwapIntent["token"]>;
};

export type Latency = {
  alertReceivedMs: number;
  resolvedMs?: number;
  quotedMs?: number;
  signedMs?: number;
  sentMs?: number;
  confirmedMs?: number;
};

export type ExecutionReport = {
  idempotencyKey: string;
  mode: "dry_run" | "live";
  decision: "would_send" | "sent" | "skipped";
  reason: string;
  venue: string;
  route: RouteQuote | null;
  latency: Latency;
};
