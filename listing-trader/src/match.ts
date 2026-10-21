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

export function matchAlert(
  index: WatchIndex,
  alert: Pick<Alert, "ticker" | "projectName" | "chainHint">,
  minLiquidityUsd: number,
): MatchOutcome {
  const ticker = normalizeTicker(alert.ticker);
  let candidates = index.lookup(ticker).slice();
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
  if (named.length > 1) {
    return { kind: "ambiguous", ticker, detail: "more than one chain matched the name" };
  }
  const token = named[0];
  const liquidity = token.pairMap.top?.liquidityUsd ?? 0;
  if (liquidity < minLiquidityUsd && !token.hyperliquid) {
    return { kind: "illiquid", ticker, detail: `top pool liquidity ${liquidity} USD` };
  }
  return { kind: "hit", token };
}
