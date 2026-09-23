# Checkpoint — 2026-09-21

## Executed

- Created the isolated capture/verify/replay/report workflow and a source-to-rule
  contract. Sealed contract and engine hashes at 19:49:20 UTC before historical
  primary outcomes. No subsequent strategy-code or contract changes.
- Passed 22 pre-replay fixtures, then 11 additional lifecycle/audit fixtures:
  **33 tests**, including an actual synthetic sweep → break → retest → next-open
  entry → 80%/10% targets → residual stop, censoring, missing funding and gaps.
- Preserved six-asset normalized inputs and source hashes. Confirmed 4,320 complete
  hourly bars / 1,080 four-hour bars per asset and 4,320 unique funding buckets.
  Exact hourly aggregation for all six. Original raw exchange acquisition absent;
  provenance limitation retained. Saved BTC five-minute data exactly refines 293 hours.
- Network-restricted provider probe failed and was retained. Public read-only
  network-enabled retry succeeded: current instrument metadata and BTC candles.
  The 4,320 completed in-window bars match the frozen sample exactly. No paid calls.
- Reproduced all 316 original baseline policy/path ledger rows and summary exactly,
  preserving their known funding and admission-boundary limitations.
- Replayed **6,480 decisions, zero admitted primary hypotheses**. Full rejection
  ledger and null economic summaries saved. Later chronological period remains
  exploratory; no observations relabeled prospective.
- Isolated 58 snapshots with only the reaction blocker, representing TWO
  coin/origin/zone combinations. ALL 58 lack a zone touch; deleting a wick/body
  condition would not solve that. Only three actual reaction snapshots occur
  anywhere (XRP), all blocked by weekly neutral and daily mixed conditions.
- Produced nine real annotated charts: six initial specification/rejection charts
  plus explicitly labeled baseline success, failure and untriggered illustrations.
  No primary success chart invented when no primary trade exists.
- Independently recomputed all 6,480 frames and tested 18 actual cutoffs with
  adversarial future candles. Source, raw-response and frozen-contract hashes
  verified. Automation PAUSED; tracked diff empty. Final audit 19:54:23 UTC.

## Actual decision

**INCONCLUSIVE, not deployable.** This contract lacks a trade sample; costs,
bootstrap intervals, drawdown and sizing comparisons cannot establish primary
edge. The data connection works. The key current constraint is interpretation:
the daily locked-impulse deep-retracement interpretation produces zones far from
current price, whereas another source section describes a local 4h impulse.

Do NOT simply loosen velocity, remove reaction, increase holding time or add JEV
to force admissions. The illustrative HYPE candidate waits near 59.5–59.78 while
the displayed market is in the 80s; that is a different setup from buying its
ongoing continuation. Source-to-code fidelity must be settled before profitability.

## Specific next action

Audit the daily-versus-local-4h impulse and terminal-confirmation definitions
against the original source examples using outcome-hidden multitimeframe anchors.
Write a separately versioned interpretation decision supported by source evidence.
Only then freeze a successor contract, if warranted. Do not repeatedly tune v1
against its zero-trade result. Existing BTC/SOL examples are already seen and can
support specification checks, never predictive validation.

## Remaining acceptance limits / unfinished scope

- No complete historical COT/macro/liquidity reconstruction; archived observations
  are sparse (24 asset-decision macro availability joins), not broad historic passes.
- Institution-level scaling, targets as swing proxies, daily terminal confirmation
  and conservative re-entry need semantic validation. Multiple strategy branches
  remain explicitly excluded from this primary-branch test.
- Two intrabar path sensitivities are NOT rigorous bounds over every possible
  candle path. No historical primary fills exist to evaluate ambiguity economically.
- No capital-constrained leveraged portfolio or mark-to-market account drawdown.
- The comparison framework supports costs, sizing, assets and chronological groups,
  but with zero admissions paired economic superiority and uncertainty cannot be
  estimated. Prospective validation and collector remain unstarted.
- Original restriction-probe failure, a raw five-minute response-wrapper parsing
  error before feature computation, and initial chart label reuse were corrected
  or retained transparently. No failed run modified the frozen trading contract.

No production changes, commits, PR changes, orders, paid-provider usage or automation
restart. No Helius credits used. Prior research preserved.
