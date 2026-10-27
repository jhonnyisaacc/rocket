import type { Alert, ChainRef, MatchOutcome } from "./domain.js";
import { matchAlert, type WatchIndex } from "./match.js";

export type WhaleAsset = {
  chain: ChainRef;
  chainKey: string;
  address: string;
  symbol: string;
  decimals: number | null;
};

export type WhaleSwap = {
  kind: "swap";
  idempotencyKey: string;
  sell: WhaleAsset;
  buy: WhaleAsset;
  sellAmount: string;
  slippageBps: number;
  mode: "dry_run";
};

export type WhaleResult = { decision: "skipped"; reason: string };

export interface WhaleClient {
  swap(command: WhaleSwap): Promise<WhaleResult>;
}

export const WHALE_REPO = "https://github.com/jhonnyisaacc/whale";

export function dryRunWhaleClient(): WhaleClient {
  return {
    async swap(command) {
      return { decision: "skipped", reason: `dry-run only. ${command.idempotencyKey} was not sent` };
    },
  };
}

export function assertNoLiveWhale(env: NodeJS.ProcessEnv): void {
  const live = env.WHALE_LIVE;
  if (live === undefined || live === "" || live === "false") return;
  throw new Error("Rocket stays read-only.");
}

export function receiveListing(alert: Alert, index: WatchIndex, minLiquidityUsd: number): { outcome: MatchOutcome; command: WhaleSwap | null } {
  const outcome = matchAlert(index, alert, minLiquidityUsd);
  if (outcome.kind !== "hit") return { outcome, command: null };
  const token = outcome.token;
  const top = token.pairMap.top;
  return {
    outcome,
    command: {
      kind: "swap",
      idempotencyKey: alert.id,
      mode: "dry_run",
      slippageBps: 50,
      sellAmount: "0",
      sell: {
        chain: token.chain,
        chainKey: token.chainKey,
        address: top?.quoteAddress ?? "",
        symbol: top?.quoteSymbol ?? "",
        decimals: null,
      },
      buy: {
        chain: token.chain,
        chainKey: token.chainKey,
        address: token.contract,
        symbol: token.ticker,
        decimals: token.decimals,
      },
    },
  };
}

export async function handToWhale(
  alert: Alert,
  index: WatchIndex,
  minLiquidityUsd: number,
  client: WhaleClient,
  env: NodeJS.ProcessEnv,
): Promise<{ outcome: MatchOutcome; command: WhaleSwap | null; result: WhaleResult | null }> {
  assertNoLiveWhale(env);
  const received = receiveListing(alert, index, minLiquidityUsd);
  if (!received.command) return { ...received, result: null };
  return { ...received, result: await client.swap(received.command) };
}
