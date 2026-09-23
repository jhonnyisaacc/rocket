# Bakeoff contracts

Phase 2 only. Five contracts. No replay in this turn. No `RESULTS.md`. No change to `rocket crypto scan`, to `execution_enabled`, or to PR #28 or PR #29. These pages are the later runner's spec. They are not installed.

Shared clock, for every contract. `decision_time` is the close of a completed 1h bar. A bar is unseen if its open plus its interval is after `decision_time`. Bias may use the last completed 1d or 1w bar. The setup fact must be knowable from a completed 4h bar. The fill is the open of the next 1h bar after the triggering 1h close. If that open is missing, the signal is unresolved. It is not filled at the 4h, 1d, or 1w close.

Shared book. A name is eligible only if, at `decision_time`, it is a Hyperliquid perpetual and the liquidity inputs that `assess_live_liquidity` already uses are known as of that time: 24h quote volume at least 5_000_000, open interest at least 1_000_000 USD, spread at most 20 bps, slippage at most 25 bps (`rocket/workflows/crypto.py`). Missing history is `NO_TRADE`, not "assume today's book." Today's CoinGecko top 100 projected backward is not eligibility. Delisted names stay out.

Shared data. Candles and current metadata come from `rocket/providers/hyperliquid.py`: `fetch_candles`, `fetch_closed_candles`, `fetch_perp_markets`. Intervals already allowed include `1h`, `4h`, `1d`, `1w`. `fetch_setup_candles` is the live 4h/14-day helper and is too short for these lookbacks. The later runner passes a longer `lookback_days` into the same functions. No second client. No key. No signing. Funding and open interest are not inputs unless a contract below says so. None of them do.

Shared bot object, one per name per `decision_time`:

```json
{
  "action": "ENTER_LONG | ENTER_SHORT | WAIT | NO_TRADE",
  "zone": null,
  "invalidation": null,
  "first_objective": null,
  "reasons": []
}
```

`zone` is `[low, high]` in price when the contract has a price zone, else null. COT may be copied onto `reasons` as an overlay. It does not change `action` except inside `theory-v2-code` when a point-in-time COT history is supplied and that code blocks. No contract is sized, leveraged, or sent.

Inherited means a source sentence or a source function states it. Interpretation means this page had to pin a clock, a tie, or a missing exit so a later runner can execute one path. Interpretations are not available for tuning after PnL.

## 1. `trb-50d`

Family: 1, time-series breakout. Not an incumbent.

Source: Brock, Lakonishok, LeBaron (1992), trading-range break, the 50-day length, no band, 10-day window. The paper also specifies 150 days, 200 days, and a 1% band. Those are not this contract.

Predicts: a daily close that penetrates the prior 50-day high or low is followed by a different 10-day return. Here the penetration is observed on a 4h close so the fill can be a 1h open.

Inherited:

- Local maximum and minimum from the preceding 50 days.
- Buy on penetration of the maximum. Sell on penetration of the minimum.
- No 1% band.
- Outcome window is 10 days. The paper has no stop and no price target.

Interpretation:

- "Day" is a completed Hyperliquid `1d` candle. The channel uses closes, because their Dow series is one price per day, not an intraday high.
- The setup bar is the first completed 4h bar whose close is above that maximum or below that minimum, and whose previous 4h close was not already through the same level. The channel's last day must be closed at or before that 4h close. The signal 4h bar is not inside the 50 days.
- Fill is the next 1h open. Exit is the first 1h open at or after 10 UTC days from the fill. A later close back through the broken level does not exit.
- Each fresh cross is its own event, including overlaps. The paper averages overlapping 10-day windows. This contract does not net them into one account position. A later replay that nets them is a different book.
- Fewer than 50 completed daily closes: `NO_TRADE`, reason `trb_warmup`.

Entry, stop, exit:

- `ENTER_LONG` when the 4h close breaks the 50-day maximum. `ENTER_SHORT` on the minimum. Else `NO_TRADE` on a 4h boundary that was evaluated, or `WAIT` if the 4h bar is not closed yet.
- `zone` is `[level, level]` where `level` is the broken maximum or minimum.
- `invalidation` is that same level, and `reasons` includes `invalidation_is_the_broken_level_not_a_stop`.
- `first_objective` is null. `reasons` includes `no_price_objective_10d_hold` and the exit timestamp.

Data at `decision_time`: completed `1d` closes (at least 50) and completed `4h` bars, plus the next `1h` open after the signal. No funding.

Failure modes to keep attached to the result: Dow cash index versus perp funding, survivor index versus this perp filter, and overlapping events versus a single position.

## 2. `cmom-r3-quintile`

Family: 2, cross-sectional momentum. Not an incumbent.

Source: Liu, Tsyvinski, and Wu, NBER 25882 section 3.2, three-week momentum quintiles, value-weighted, rebalanced weekly. Not the 30/40/30 factor, not the one-, two-, or four-week rows, not Jegadeesh-Titman deciles.

Predicts: the top quintile of prior three-week returns beats the bottom quintile over the next week, inside the cross-section defined at decision time.

Inherited:

- Sort once a week on the three-week return.
- Long the highest quintile, short the lowest, value-weighted.
- Hold until the next week's rebalance.
- No skip week. `r_{3,0}` includes the latest week.

Interpretation:

- The week is the venue `1w` candle from `fetch_candles`. The paper does not name Hyperliquid's week boundary. Do not rebuild weeks from 4h bars to hunt a better boundary.
- Three-week return is `close_t / close_{t-3} - 1` on completed weekly candles. Need four completed weekly closes. Else that name is out of the sort.
- The cross-section is the eligible liquid perps at `decision_time`, not every coin above $1 million. Names outside that set are not ranked.
- If fewer than five names have a return, the whole book is `NO_TRADE`, reason `cmom_book_below_five`.
- Quintile edges use rank order `(return, coin)` ascending. Bottom and top buckets have size `floor(n/5)`. Extra names stay in the middle. The middle is `NO_TRADE`.
- Value weight is market cap known at `decision_time`. If that vintage is missing, membership still emits `ENTER_LONG` or `ENTER_SHORT`, and `reasons` includes `weight_unknown_do_not_equal_weight`. Equal weight is not a silent substitute.
- The 4h setup is the first completed 4h bar whose close time is at or after the weekly bar's close. It is a clock. It is not a price filter. Fill is the next 1h open. Exit is the next week's rebalance fill. Intraweek bars are `WAIT`, reason `not_rebalance_bar`, and do not open a new event.

Entry, stop, exit:

- On the rebalance bar: `ENTER_LONG` in the top quintile, `ENTER_SHORT` in the bottom, `NO_TRADE` otherwise.
- `zone` is null. There is no price zone.
- `invalidation` is null. The paper has no stop. `reasons` includes `no_stop_weekly_rebalance`.
- `first_objective` is null. The exit is the next rebalance timestamp, written in `reasons`.

Data at `decision_time`: completed `1w` closes for every eligible name, the first `4h` bar after the week close, the next `1h` open, and a point-in-time market cap only if a weight is claimed. No funding.

Failure modes: their sample is 2014–2018 coins above $1 million and they flag costs and shorting; this book is today's venue's liquid perps, and only when those facts are known historically. A missing cap vintage means the long-short is unweighted and must be reported that way.

## 3. `pana-full`

Family: 3, 4h pullback / 1h confirm. Role: incumbent baseline, not the winner, not the live detector.

Source: PR #28 `CONTRACT.md` and `engine.py` `frame` / `flip_step` on `codex/crypto-strategy-research`. That file is a research interpretation of nave `docs/technical.yaml`, not educator doctrine. This page does not re-pick the open items in `artifacts/futures_desk/ENTER_CONTRACT_v0.md`. It runs the PR #28 reading as already frozen.

Inherited from that reading:

- Weekly velocity: last Monday-UTC weekly close minus the close four weeks earlier, divided by the mean of eight true ranges. Long if strictly above +1.2, short if strictly below −1.2, else neutral. Nine contiguous complete weeks or the velocity is unknown.
- Daily premise: last two confirmed daily highs and last two confirmed daily lows all rise (long) or all fall (short). Pivots are strict extrema with three closed daily bars on each side.
- Impulse: daily close crosses the last already-confirmed directional swing. Origin locks. Terminal extends on a new same-direction break and dies on an opposite daily break. Terminal is usable only after three later daily closes do not violate it. No weekly re-anchor. No 90% branch. Band is 75–86% of that locked daily leg.
- BEN: nearest strict 4h pivot (two bars each side) inside the band, plus the institutional level on the adverse side. Zone is that interval clipped to the band. Most recent qualifying pivot wins.
- Institutional level: `unit = 10^(floor(log10(origin)) - 3)`, endings 00, 20, 50, 80 in that unit. PR #28 marks this a hypothesis.
- Confluence at least 3. Swing and institutional count as two. The third is one of: a completed daily, weekly, or monthly open or close inside the BEN; a directional three-candle 4h gap overlapping the BEN; or two non-adjacent older 4h pivot touches inside the BEN. Unrecognized block and session factors stay unevaluated, not imputed.
- Reaction: the last closed 4h bar intersects the zone, body in the premise direction, adverse wick at least the body, close beyond the zone midpoint.
- Then, on closed 1h bars: sweep an already-confirmed adverse 1h pivot and close back across it; then close through an opposing 1h pivot whose price is inside the zone; then a later 1h bar retests that level and closes beyond it inside the zone. Pivot width is two 1h bars. Order is sweep, then break, then retest.
- Fill: next 1h open after the retest close. Recheck that the fill is still inside the zone, risk is positive, and the first objective is at least 1R from the fill. Else reject.
- Stop: last confirmed adverse 1h swing at the trigger, times `1 - direction * 0.0001`. The 1.5× daily ATR floor is not used.
- Objectives: nearest two already-confirmed opposing daily or 4h pivots beyond the favorable zone edge. Do not skip a nearer pivot to manufacture 1R. Do not invent an R multiple. Both objectives are required for this branch.
- Pre-entry death: 4h close beyond the frozen origin, or an opposite daily break. Pending admission expires eight days after admission, on the boundary, with no new entry then.
- In position: stop is intrabar on the two path assumptions PR #28 already froze (O-L-H-C and O-H-L-C). Thesis invalidation exits the residual at the next 1h open. Partials: 80% at the first objective, 10% at the second, 10% trails. That management is the PR #28 branch, not a new one.

Interpretation, only the bot words:

- `ENTER_LONG` or `ENTER_SHORT` only when `flip_step` returns a trigger and the recheck passes.
- `WAIT` when weekly and daily directions exist and agree, the name is eligible, and a later blocker or an unfinished flip remains (`zone_unavailable`, `confluence_below_three`, `reaction_absent`, sweep not done, retest not done, pending not expired).
- `NO_TRADE` when the name is ineligible, velocity is unknown or neutral, daily structure is unknown or mixed, weekly and daily disagree, or the impulse is unavailable or disagrees with the daily premise.
- `zone` is the clipped BEN. `invalidation` is the stop price. `first_objective` is the nearer structural pivot. `reasons` lists every blocker or the trigger id.

Data at `decision_time`: completed `1h` bars long enough to build 4h, 1d, and Monday-offset 1w aggregates the way `engine.py` `aggregate` does, with no partial period treated as closed. No funding. No COT input. PR #28 left COT `UNKNOWN` on every snapshot; this contract does not fill that hole.

Not inherited, and not added: YAML entry on the flip-candle close, the prose 1.5 velocity, the 4h-impulse anchor, the 90% branch, the ATR stop floor, and any relaxation because PR #28 admitted nobody.

## 4. `staged-zone-as-entry`

Family: none as a published rule. Role: incumbent baseline. It is the live staged scan's `ZONE` state scored as if it were an entry. The live scan does not do that, and this file does not make it do that.

Source: `stage_symbol` in `rocket/workflows/crypto.py` and `artifacts/futures_desk/STAGED_CONTRACT_v0.md`. Research interpretation, already labeled there. Weekly close versus four completed weeks earlier. Daily close versus six completed days earlier. Rolling 4h impulse: terminal is the extreme of closed 4h bars excluding the last bar; origin is the opposite extreme from the start through that terminal. Retrace 0 is the extreme, 1 is the origin. Band is 50% to 86% inclusive. `ZONE` requires both biases equal and the last 4h close inside the band. Invalidation in the scanner is the impulse origin, "a research level, not a stop order."

Inherited, unchanged, including the parts that disagree with the YAML:

- The close-to-close signs, not ±1.2 and not daily pivot structure.
- The rolling 4h anchor, recomputed every bar. The YAML calls weekly re-anchoring an engine bug. This baseline keeps the re-anchor because removing it would no longer be the staged scan.
- The 50% edge. The YAML says 50% is an alert, not an entry. `reasons` on every entry includes `research_interpretation_retracement_50_86`.
- Mixed 4h structure does not remove the row.
- COT `against` does not remove the row. COT is not an entry filter.

Interpretation, required so the baseline has an exit and not before:

- On the 4h close that produces `ZONE`, the triggering 1h bar is the 1h close at that same timestamp. Fill is the next 1h open. `ENTER_LONG` or `ENTER_SHORT` matches `direction`.
- `NO_BIAS`, `BIAS`, `IN_PLAY`, and `EXTENDED` are `WAIT`. `NO_TRADE` in the scanner stays `NO_TRADE`.
- `zone` is `entry_research_zone`. `invalidation` is the impulse origin.
- There is no inherited target. `first_objective` is null. `reasons` includes `no_inherited_objective`.
- Exit, interpretation: the next 1h open after a later completed 4h bar whose staged state is no longer `ZONE` in the same direction, or whose 4h close is beyond the origin that was stored at entry. Using the origin as an exit is not what `STAGED_CONTRACT_v0.md` authorizes for the live scanner. It is only this baseline's holding rule.

Data at `decision_time`: the same completed 4h, 1d, and 1w series `stage_symbol` already consumes, plus the next 1h open. No funding. Do not refit 0.50, 0.86, the four-week lookback, or the six-day lookback to any later count.

## 5. `theory-v2-code`

Family: nave incumbent. Not family 3's YAML rule, and not the winner. The 4h gate in this code is a moving-average match, which `technical.yaml` tells engines not to implement.

Source: `TheoryV2Engine.evaluate` at the nave blob `f1a833ea60c859a3a4a600df2b97569a4b8e0c6a`. Where the docstring and the code disagree, the code is the contract. Where the code and the YAML disagree, the code stays, because this row exists to replay the engine that actually ran.

Inherited from that function, defaults only:

- `momentum_bias(lookback=4, min_velocity=1.2, atr_window=8)`. Neutral falls through to `range_breakout_bias(range_window=8, max_range_atrs=1.5, breakout_buffer_atrs=0.5, atr_window=8)`.
- `daily_confirms` is `trend(close, window=10)` with deadband 0.5%, not the docstring's 20.
- `detect_climax_cooldown`: block if any of the last 10 daily true ranges exceeds 3× the ATR-20 measured at that bar.
- `chase_gate`: retrace of the latest daily swing leg must lie in `[0.50, 0.95]`. If `find_impulse_leg` returns nothing, the gate passes. That permissive pass is the code. It is not repaired.
- `four_h_setup_valid` is `trend(close, window=8)` with deadband 0.5%, not the docstring's 12, and not a confluence zone.
- `one_h_entry`: signal price is the last 1h close. Structural risk is the distance from that close to the min low (long) or max high (short) of the last 24 1h bars. Risk is the max of that distance and 1.5× daily ATR-14. Stop is close minus risk (long) or close plus risk (short). Targets are daily swings beyond 1R, so a nearer swing under 1R is skipped; if none remain, targets are 1.5R and 2.5R. PR #28 forbids both the skip and the synthetic R. This incumbent does them. Do not "correct" it inside this contract.
- `cross_asset_fn`, recovery, and squeeze stay off. `evaluate_squeeze_daily` is out of scope.
- COT: if no history is passed, do not block (`COT unavailable — permissive pass`). If a history with `report_date <= decision_time` is passed, call `weekly_cot_filter` with cutoffs 0.60 and 0.85 unchanged. A `block` becomes `NO_TRADE`, reason the filter's reason. COT is still not the setup.

Interpretation:

- The CLI default coins are BTC and ETH. This contract evaluates each eligible perp with the same pure functions. That wider book is not what the historical nave runs were. `reasons` includes `theory_v2_book_scope_interpretation` on every row.
- Fill is the next 1h open, not the 1h close the code stores as `entry_price`. The stop price stays the code's stop. R is measured from the fill to that stop. If the next open is already through the stop, `NO_TRADE`, reason `gap_through_stop`.
- `ENTER_LONG` or `ENTER_SHORT` when `stage == "fired"`. Any earlier stage on an eligible name is `WAIT` with `reasons` equal to `stage` and `reason`. Ineligible names are `NO_TRADE`.
- `zone` is null. This engine does not emit a 4h price zone. Do not borrow the YAML BEN.
- `invalidation` is the stop price. `first_objective` is `targets[0]`.
- Exit: the stop price, then the first objective as the price target the code actually computed. The 80/20 split is only in `_format_decision`. It is not in `Signal`. Do not apply YAML 80/10/10 to this row. A later replay that needs a partial rule records `partials_unspecified_in_signal` and exits the whole position at the first objective. That flat exit is interpretation.

Data at `decision_time`: completed `1w`, `1d`, `4h`, and `1h` bars covering the windows above (weekly ATR warmup, 60 daily bars for the leg, 24 1h bars). No funding. The ±1.2 threshold is the iter-14 sweep the YAML already disclosed. It is frozen as found. It is not evidence.

## Out of scope on purpose

No sixth contract. Monthly TSMOM, Jegadeesh-Titman deciles, Moreira-Muir scaling, crypto carry, and liquidation flushes cannot sit on this clock without a new rule. `swing_4h1h_v0` was not found. Parameter search, family merges, and a 12-month replay are not this phase.
