# Shorts v2

Research-only short discovery. This does **not** replace the canonical
`ism_simple` live gate. `rocket shorts` still defaults to that three-factor
path. `--strategy shorts_v2` is the new research path.

## Mental model

```text
ISM decides where to look.
Company deterioration decides what deserves investigation.
A catalyst explains why a repricing may happen.
Momentum decides when the thesis is being confirmed.
Regime and risk determine whether the setup is attractive.
Tokenized-market availability determines whether it is executable for the caller.
```

Monthly ISM reports select **up to three** worst contracting industries from
Manufacturing and **up to three** from Services. Fewer than three contracting
industries are used as-is. Those industries are mapped to a reviewed equity
universe. Technical breakdown is a **timing** state, not the discovery filter.

```text
ISM weak + company decay + relative weakness + no breakdown  → WATCH
later 20-session breakdown                                   → ARMED or TRIGGERED
failed retest (optional confirmation)                        → TRIGGERED
```

States: `RESEARCH`, `WATCH`, `ARMED`, `TRIGGERED`, `BLOCKED`, `REJECTED`.

`SETUP_FOUND` is only emitted for `TRIGGERED`. `WATCH`/`ARMED` stay on the
watchlist. Numerical selection is deterministic. An LLM must not generate the
short signal.

## Factors

| Factor | Role | Missing |
|---|---|---|
| ISM contracting industry, rank 1–3 per series | universe | name stays unmapped |
| Reviewed issuer exposure mapping | universe | unmapped, not guessed |
| Estimate revisions, same fiscal period | deterioration | `UNKNOWN`; not reconstructed from today's consensus |
| Reported EPS / net-income trend | deterioration context | `UNKNOWN` if no 10-K pair filed yet |
| Operating cash flow, NI vs OCF, share count, operating margin | 2–4 quality flags | `UNKNOWN` |
| 20-session relative vs sector ETF and SPY | confirmation | `UNKNOWN` |
| 20-session close below prior low | timing | `UNKNOWN` |
| Failed retest of broken low | optional timing | `UNKNOWN` |
| Structured catalyst (`direction=BEARISH` only: 2.06, 4.02, earnings miss, guidance/estimate cut) | explanation, not a gate | absent, never invented; generic 8-K/S-1 stay UNKNOWN |
| SPY + sector vs 20-session average | regime / risk class | `UNKNOWN` |
| Invalidation vs defensible downside reference | R/R context | `UNKNOWN` |
| Cheap valuation (`valuation_support`) | veto / warning | not a short reason |
| Tokenized short availability | execution overlay | `UNKNOWN`; never inferred backward |

Expensive valuation is **not** a short. The preferred combination is business
deterioration + expectation deterioration + price confirmation.

## Point-in-time

Every material datapoint carries `event_time`, `available_at`, `decision_time`,
and `source`.

- ISM identity uses the existing first/third US business-day 10:00 New York
  publication clock.
- Yahoo daily bars are eligible only when NYSE session close ≤ decision time.
  That is an approximation: Yahoo does not publish a true vendor `available_at`.
- SEC 10-K facts and 8-K filings use `filed` / `filingDate`. Restatements after
  the decision are excluded.
- FMP `/analyst-estimates` is a **current** consensus keyed by fiscal period,
  not a vintage. Revisions exist only after Rocket stores two snapshots of the
  **same** fiscal period. Incompatible periods are rejected.
- `industry_exposure.json` `reviewed_at` is the mapping-knowledge timestamp.
  Underlying exposure can be older; Rocket did not have the mapping until that
  date. Fixed-universe backtests must be labeled as such.

Operational health stays separate from research conclusions. Missing stays
`UNKNOWN`, never silently false.

## Tokenized-equity abstraction

Research eligibility and caller-executable eligibility are different:

```text
RESEARCH_ELIGIBLE     listed-equity research may proceed
EXECUTION_ELIGIBLE    a venue snapshot proves short_available at decision_time
```

The provider can represent venue, token symbol, long/short availability,
spot/perp, funding, spread, volume, open interest, mark, basis, and clocks
when known. xStocks public listings and the current ONDO mint registry are
**present-tense**. Tokenized spot never implies a short. Kraken xStock perps
and Ondo perps can mark `short_available` only on a current snapshot; Kraken
`openingDate` is a listing vintage, not a historical short book. Historical
execution eligibility is not inferred backward.

Traditional borrow (fee, shares available, days to cover) and tokenized-perp
constraints (funding, OI, spread, basis) share the names `short_availability`,
`short_liquidity`, `short_carry_cost`, and `squeeze_risk`. Unavailable fields
stay `UNKNOWN`.

## Providers

- `rocket/providers/ism_universe.py` — up-to-3 contracting industries and reviewed mappings
- `rocket/providers/short_quality.py` — relative strength, breakdown, retest, regime, R/R, cash-flow quality
- `rocket/providers/estimate_revisions.py` — same-period snapshot comparison
- `rocket/providers/short_events.py` — structured catalysts
- `rocket/providers/sec_facts.py` — PIT 10-K facts and 8-K filings
- `rocket/providers/tokenized_equities.py` — current venue snapshots
- `rocket/providers/short_research_ai.py` — qualitative contract only

Live `rocket shorts` still defaults to `ism_simple`: ISM contracting +
20-session breakdown + bearish reported fundamentals, with cheap valuation as a
veto. That gate is not replaced.

Live `rocket ism --research-companies` short seeds now come from **up to three**
worst contracting industries per Manufacturing/Services series, not every
contracting industry. That is an intentional universe change so ISM decides
where to look. Expanding industries are still mapped in full for the long path.

## Limitations

- January–September 2026 is a small sample. Results are exploratory.
- Estimate revisions cannot be backfilled from a current FMP pull.
- Tokenized short availability cannot be backfilled from today's listings.
- R/R targets use a swing low in the eligible Yahoo window (not the
  full-history low). If no material downside reference exists, R/R is `UNKNOWN`.
- Research P&amp;L may use next-session open; it is measured and does not
  degrade the sample versus close-of-signal.
- No portfolio sizing is implemented. Regime changes confidence/risk class only.
- Historical edge vs the sparse `ism_simple` book is **`EDGE_NOT_VALIDATED`**.
  Keep the architecture; do not switch the live default.

See `docs/analysis/shorts_v2_backtest.md` for the incremental comparison.
