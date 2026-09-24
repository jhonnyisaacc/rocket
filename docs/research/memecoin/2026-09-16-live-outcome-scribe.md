# SCRIBE live outcome — 2026-09-16

Research-only case study. No trade or signal was issued.

## Observation

At approximately 14:18 UTC on 2026-09-16, the logged-in Fomo SCRIBE page for the canonical Solana mint `6rHkNb7HCtkpvdnVJsBCZHH5dw3AndqEjfmbEGhooR7t` showed:

- market cap: approximately `$131.3K`;
- price: approximately `$0.000134`;
- 24-hour change: `-85.11%`;
- 1-hour change: `-20.90%`;
- 4-hour change: `-52.30%`;
- 5-minute change: `-2.60%`;
- 24-hour volume: approximately `$3M`;
- displayed liquidity: approximately `$25.7K`;
- summary holders: approximately `2K`, while the holder panel showed `768`;
- summary top-10 holding: `13.98%`;
- Fomo warnings: liquidity unlocked at `44.17%` and token unverified.

The visible minimum-size activity panel showed 139 buys versus 86 sells, about `$6.3K` buy volume versus `$8.5K` sell volume, and 88 buyers versus 78 sellers. These figures are panel-scoped and must not be confused with the 24-hour totals.

## Forward outcome relative to the prior live window

The prior observation window on 2026-09-15 saw SCRIBE around `$467K` to `$640K` market cap, with the unlocked-liquidity warning around `40.68%` to `43.64%`. The new `$131.3K` snapshot is approximately:

- `-71.9%` from the earlier `$467K` reference;
- `-79.5%` from the earlier `$640K` reference.

This is a concrete adverse-selection outcome for the earlier “extreme return + high volume/liquidity + unlocked-liquidity warning” configuration. It does not prove that every token with those features will fall, but it validates retaining this pattern as a negative-control case for the future alert engine.

The position feed also showed several long-held entries underwater, including `inyourwalls` at `-84.86%` and `exmakato` at `-91.26%` marked PnL. These are Fomo position observations, not independently verified wallet returns.

## Data-quality findings

1. Fomo's summary holder count and holder-panel count disagree (`2K` versus `768`), so the field needs a source/component label.
2. Activity counts depend on the visible minimum-size configuration; the configuration must be captured with the observation.
3. A dashboard’s current 24-hour percentage is not a substitute for a fixed-horizon return from a stored snapshot.
4. Unlocked-liquidity percentage increased while market cap subsequently collapsed, but this single case cannot establish causality. It is a candidate risk feature to test across rejected and surviving launches.

## Alert-engine implication

The future system should have emitted, at most, a **risk warning / no-alert state** for the earlier SCRIBE configuration unless an independent-participation trigger overcame the integrity gate. The correct retrospective label is:

`high_attention + high_short_term_activity + integrity_warning + severe_forward_drawdown`

Status remains `NO_EDGE_VALIDATED`.

