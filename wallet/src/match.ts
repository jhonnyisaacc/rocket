import { feeRankOf } from "./chains.js";
import type { Alert, MatchOutcome, TokenRecord } from "./domain.js";

export function normalizeTicker(value: string): string {
  return value.trim().toUpperCase();
}

export function normalizeName(value: string): string {
  return value
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim()
    .replace(/\s+/g, " ");
}

export function nameMatches(projectName: string, aliases: readonly string[]): boolean {
  const alertName = normalizeName(projectName);
  if (!alertName) return false;
  return aliases.some((alias) => normalizeName(alias) === alertName);
}

export class WatchIndex {
  private readonly byTicker = new Map<string, TokenRecord[]>();

  constructor(tokens: readonly TokenRecord[] = []) {
    this.replace(tokens);
  }

  replace(tokens: readonly TokenRecord[]): void {
    this.byTicker.clear();
    for (const token of tokens) {
      const key = normalizeTicker(token.ticker);
      const list = this.byTicker.get(key);
      if (list) list.push(token);
      else this.byTicker.set(key, [token]);
    }
  }

  lookup(ticker: string): readonly TokenRecord[] {
    return this.byTicker.get(normalizeTicker(ticker)) ?? [];
  }
}

function liquid(token: TokenRecord, minLiquidityUsd: number): boolean {
  return (token.pairMap.top?.liquidityUsd ?? 0) >= minLiquidityUsd || token.hyperliquid !== null;
}

export function matchAlert(
  index: WatchIndex,
  alert: Pick<Alert, "ticker" | "projectName" | "chainHint">,
  minLiquidityUsd: number,
  allowedChains?: ReadonlySet<string>,
): MatchOutcome {
  const ticker = normalizeTicker(alert.ticker);
  let candidates = index.lookup(ticker).slice();
  if (allowedChains) candidates = candidates.filter((token) => allowedChains.has(token.chainKey));
  if (alert.chainHint) {
    candidates = candidates.filter((token) => token.chainKey === alert.chainHint);
  }
  if (candidates.length === 0) {
    return { kind: "unlisted", ticker, detail: "no exact ticker in the watchlist" };
  }
  const named = candidates.filter((token) => nameMatches(alert.projectName, token.names));
  if (named.length === 0) {
    return {
      kind: "lookalike",
      ticker,
      detail: "ticker matched a different project name",
    };
  }
  const ranked = named.slice().sort((a, b) => feeRankOf(a.chainKey) - feeRankOf(b.chainKey) || (b.pairMap.top?.liquidityUsd ?? 0) - (a.pairMap.top?.liquidityUsd ?? 0));
  const tradable = ranked.filter((token) => liquid(token, minLiquidityUsd));
  if (tradable.length === 0) {
    const deepest = ranked[0];
    const liquidity = deepest?.pairMap.top?.liquidityUsd ?? 0;
    return { kind: "illiquid", ticker, detail: `top pool liquidity ${liquidity} USD` };
  }
  const [token, ...alternates] = tradable;
  if (!token) return { kind: "illiquid", ticker, detail: "top pool liquidity 0 USD" };
  if (named.length > 1 && tradable.length > 1 && new Set(tradable.map((item) => item.chainKey)).size === 1) {
    return { kind: "ambiguous", ticker, detail: "more than one contract matched the name on the same chain" };
  }
  return { kind: "hit", token, alternates };
}
