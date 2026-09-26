# `daily-trb-50d-v1`

New generation. Frozen before any validation PnL. This page does not edit `trb-50d` and does not sit on the PR #31 clock.

Screening label: the PR #31 hourly `trb-50d` result. That result is not validation.

Validation label: the single run recorded in `daily-trb-50d-v1-RESULTS.md`. After that table exists, 50, 10, the absent band, and the two cost levels stay as written. No filter is added.

`execution_enabled` stays false. No `ENTER_*`. No live-scan change.

## Signal

A completed Hyperliquid `1d` close breaks the prior 50 completed daily closes' high or low.

- Long when that close is strictly above the maximum of the prior 50 completed daily closes.
- Short when that close is strictly below the minimum of the prior 50 completed daily closes.
- The signal day is not inside those 50 closes. Channel prices are closes, because the series being broken is the daily close. Intraday high and low are not the channel.
- Length is 50. There is no 1% band. A close one tick through the extreme is a break. A close equal to the extreme is not.
- The prior 50 include the previous close, so the previous close cannot itself sit beyond today's channel. Each signal is a new 50-day closing extreme. No extra freshness knob is applied.
- Fewer than 50 completed daily closes: no signal. That is warmup, not a guessed channel.

## Fill

The next daily open after the signal close. That open is the daily bar whose open timestamp is exactly one day after the signal bar's open.

If that open is missing, the signal is unresolved. It is not filled on a later daily bar, and it is not filled on 4h or 1h. An unresolved signal is not a position.

The open of a bar that has already opened may be used even when that bar has not yet closed. Its high, low, and close may not be used as a signal or as channel history.

## Outcome

Return from the fill open to the daily open 10 sessions later.

A session is the next returned daily bar. The exit is ten steps of exactly one day. If any of those ten bars is missing, the outcome is unresolved. It is not scored on a shorter or longer hold. If the tenth open has not printed yet, the event stays open and is out of the mean.

There is no stop and no price target. R is undefined.

## Costs

Both columns are required.

- 20bps of entry notional, and 40bps of entry notional.
- Half of each total is charged at entry and half at exit. Both halves are sized on entry notional, so the round trip is 20bps or 40bps of entry notional, not 20bps per side.
- Plus funding across the hold. Hourly funding prints in `(fill open, exit open]` are summed. A positive rate is paid by longs and received by shorts. A missing hour drops that trade from the mean. Missing hours are not filled with zero.

Net return for one event is

`direction * (exit_open - fill_open) / fill_open - bps/10000 - direction * sum(funding rates in the window)`.

## Two accountings, not mixed

(a) Overlapping event-study mean. Every eligible, filled, closed, fully funded event is equal-weighted. Overlaps stay overlaps. This is the hypothesis.

(b) A per-name book that skips a new signal in that name while its prior 10-day window is still open. The window runs from the fill open until the exit open. A new fill at the prior exit open may start. A fill before that open is skipped. This book is portfolio construction. It is not a claim the signal improved. Its count is not the falsifier. It does not replace the event-study mean.

## Other reports

On the event study, and labeled separately from the per-name book:

- Long versus short.
- By asset.
- By calendar month of the fill open.
- Drawdown: peak to trough of the sum of closed funded net returns ordered by exit time, then coin. Each event is one unit of entry notional, including overlaps. This is not a capital-constrained account.
- Fraction of days in a position: for each name in the eligible universe, the share of its opened daily sessions that sit inside at least one hold, then the average across those names. Names with no trade contribute zero. Open holds count as in a position. They do not enter the mean.
- Concentration, at 20bps, using sums of event net returns. These shares are a report. They do not delete trades from the primary mean.
  - Largest coin: the name with the greatest summed event-study net return. Share is that sum divided by the sum of all event net returns.
  - June 2026 BTC rebound window: fills from the session that opened 2026-06-25 (daily low 58062) through 2026-08-31T23:59:59Z, all names.
  - HYPE completed-daily high window: HYPE fills from seven days before the session that opened 2026-09-22 (high 97.816) through seven days after, clipped to the tape. That interval is 2026-09-15T00:00:00Z through 2026-09-29T23:59:59Z, intersected with bars the provider returned.

The same concentration figures are shown at 40bps. The falsifier below uses 20bps.

## Universe

Hyperliquid perps with daily bars only.

- Names come from `fetch_perp_markets` in `rocket/providers/hyperliquid.py`. The provider already drops `isDelisted`. Delisted names are not reconstructed. Today's top 100 is not stamped backward. Open interest, spread, and market-cap vintages are not invented.
- Candles come from `fetch_candles` on that same module, interval `1d` only. One `httpx.Client` is passed into `fetch_candles` and `fetch_perp_markets`. There is no second candle client.
- Main's `fetch_candles` uppercases the coin. A venue name that the uppercase request rejects is missing history and is excluded. This page does not bypass `fetch_candles` to recover it.
- A coin with no daily bars, a failed candle request, or fewer than 51 completed daily bars contributes no events.
- Eligibility rule actually used: on the signal day's completed bar, base volume times close is at least 5,000,000. That is the live scan's 24h quote-volume floor (`MIN_QUOTE_VOLUME_24H` in `rocket/workflows/crypto.py`) applied to the one daily bar that has just closed. It is knowable at the signal close. It is not today's `dayNtlVlm`. A break on a thinner day is not an event. The floor is not searched. This generation does not import or modify the live scan.

## Tape

The 12 months of `1d` bars the provider returns for a request from the run's UTC date minus 365 days, at 00:00 UTC, through the retrieval time.

A daily bar is completed when its open plus one day is at or before the retrieval time. The forming bar is not a signal and is not inside the 50 closes. No 1h price bars are invented. This daily rule is not converted onto 4h.

Funding is not a price bar. The same HTTP client reads public `fundingHistory` on `https://api.hyperliquid.xyz/info` because this generation does not add a funding helper to `rocket/providers/hyperliquid.py`. The venue returns at most 500 rows per call; the runner pages. Rates are not fabricated.

## What rejects the hypothesis

The event-study mean is the only mean that can reject or support the hypothesis.

Reject if any of these is true:

- The event-study mean net return at 20bps is less than or equal to zero.
- That mean is positive, and removing the largest coin leaves a complement mean less than or equal to zero, or that coin's share of the summed 20bps net return is greater than one half, or the complement is empty.
- That mean is positive, and the same test fires for the June window.
- That mean is positive, and the same test fires for the HYPE window.

Promising, forward shadow only, if that mean is positive at both 20bps and 40bps and none of those concentration tests fire. Twelve months is still too short for production. No live `ENTER_*`.

If the 20bps mean is positive, concentration does not fire, and the 40bps mean is not positive, the result is ambiguous: the sign depends on the cost. That ambiguity is stated. It is not resolved by adding a filter.

A book-level trade count cannot reject or rescue the signal.

## Out of scope

Experiments 2 and 3. `ENTER_CONTRACT_v1`. Any edit to the PR #31 contracts, results, or universe. Any change to `rocket/workflows/crypto.py` or `rocket/providers/hyperliquid.py`. `execution_enabled` true.
