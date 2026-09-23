# Primary pullback contract v1 — frozen research interpretation

This is a testable interpretation, NOT user-approved doctrine, a validated edge,
or a complete test of all Cryptopana branches. Freeze this file and engine.py
before historical outcomes are computed. No outcome-driven parameter search.

## Sources and precedence

Sources: `/Users/jhonny/nave/docs/technical.yaml` (T),
`/Users/jhonny/nave/docs/elcriptopanavideos.md` (V), and the prior local
`theory_alignment_v1/RECOVERED_RULES.md`. These include previously tuned project
refinements, not independently authenticated educator prescriptions.

| Condition | Source | Classification / precise v1 interpretation |
|---|---|---|
| Direction | T637–692 | Inherited tuned velocity: last complete Monday-UTC weekly close minus close four weeks earlier, divided by mean of eight true ranges; strict ±1.2. Nine contiguous complete weeks required. Do not change to prose's conflicting 1.5. |
| Daily premise | T677–692 | Research interpretation: last two confirmed daily highs AND lows increase for long, decrease for short; both required. Daily pivots are strict extrema with three closed candles on each side. |
| Impulse | T1127–1160 | Research interpretation: daily close crosses last already-confirmed directional swing. Origin is latest confirmed opposite swing preceding the breakout. Lock origin; extend terminal on new same-direction BOS, invalidate on opposite BOS. Terminal is breakout bar extreme, usable after three subsequent daily closes without violating that extreme. Extension is unavailable until confirmed. No automatic weekly re-anchor. |
| Pullback | T693–750, 779–784 | Previously tuned documented choice: 75–86% of the locked DAILY impulse. This resolves the conflicting local-4h versus daily-anchor prescriptions in favor of explicit lock guidance; no 90% branch. |
| BEN zone | T1214–1261 | Research: strict 4h pivot (two bars each side) inside the retracement band; nearest institutional level on the adverse side. Zone is their interval, clipped to retracement band. Most recent qualifying pivot wins; no search for best historical return. |
| Institutional scale | T institutional digits underspecified | Research: unit=10^(floor(log10(impulse origin))-3); repeating endings 00,20,50,80 times that unit. Scale is locked with impulse. This is a hypothesis, not an established cross-asset convention. |
| Confluence | T1214–1229 | Swing and institutional endpoint count as two. Third distinct factor: most recent completed daily/weekly/monthly open or close lies in BEN; or a directional three-candle 4h FVG overlaps BEN; or two nonadjacent older 4h pivot touches lie inside BEN. All available past history, no future confirmation. Distinct reference prices count as ONE factor family. Unrecognized block/session factors remain unevaluated. |
| Reaction | T693–705,1263–1279 | Research: closed 4h bar intersects entry band, directional body, adverse wick >= body, close beyond band midpoint in direction of premise. Not moving-average agreement. |
| Hourly flip | T880–891 plus T750–763 | Research: after zone admission, sweep an already confirmed adverse hourly pivot and close back across it. Then close through a previously confirmed opposing hourly pivot whose price is inside the frozen zone; a later candle retests that flip level and closes beyond it inside the zone. Hourly pivots use two bars each side. Sweep precedes break, break precedes retest. No touch-only entry. |
| Entry | T889 versus executable timing | Research: market entry at NEXT hourly open after retest confirmation. Missing next candle => unresolved. Recheck positive risk, entry still in zone, and first objective >=1R; otherwise reject, without moving target or stop. |
| Stop | T890, stop conflicts T983–1092 | Research: last confirmed adverse hourly swing at trigger, buffered by 1bp of its price. The later tuned 1.5 daily ATR floor is NOT included. Buffer is not claimed to be a venue tick or measured spread. Passive comparator freezes last available adverse hourly swing at admission, same buffer. |
| Objectives | T1230–1240; V7496–7518 | Research: nearest then next distinct already-confirmed opposing daily/4h pivots beyond the favorable zone edge, ordered by price. These are STRUCTURAL proxies, not fully certified confluence zones. Never skip nearer objective for 1R; never synthesize R targets. Require both objectives for this partial-exit branch. |
| Management | T1230–1240 | 80% at first target, 10% at second, final 10% trails confirmed adverse hourly swings after second target; trailing changes take effect next bar only. Keep original protective stop until then. |
| Thesis invalidation | T retroceso definition and T1127 | Pre-entry: 4h close beyond frozen impulse origin or opposite daily BOS. In position: protective stop intrabar; thesis invalidation schedules residual market exit at next hourly open. Frozen setup not canceled by a MIXED rescan. |
| Expiry | research, not theory | Pending expires at eight days after admission, exactly at boundary (no new entries then). No forced 48h or 192h holding change: positions end at structural exits, stop or thesis invalidation; data-end remaining quantity is unresolved, NOT a win/loss. |
| Re-entry | T916–943 | At most one hypothesis per asset per policy; no repeated impulse-origin/direction after admission in v1. This is conservative research treatment of ambiguous re-entry reset, not full documented reset logic. Suppressed cases retained. |

## Comparisons frozen before outcomes

1. Exact old simulator/ledger reproduction, with original known limitations
   retained solely for reproducibility, not promoted as corrected economics.
2. New price-only primary workflow: passive zone-boundary entry vs hourly flip,
   same admitted hypotheses. Each hypothesis reserves its asset for the maximum
   lifecycle across both policies and both OHLC paths, so matched comparison is
   not two separately optimized opportunity sets. Reservation begins at admission.
3. Single-rule diagnostics report eligibility with exactly one blocker omitted;
   these are COUNTS, not compounded relaxed-strategy profits.

Full historical macro/COT, historical spread/liquidity, venue quantity/tick-size
precision and true confluence target certification remain UNKNOWN unless evidence
exists with availability timestamps. Price-only results are conditional research,
not executable order recommendations or a full-context profitability claim.

## Execution and measurement conventions

Hourly paths O-L-H-C and O-H-L-C provide alternative barrier orderings, with fills,
partials and gap stops simulated along each path. These are path sensitivities,
not rigorous bounds over every possible OHLC path or a portfolio-wide worst case.
Use any available finer bars only when they exactly aggregate to the hour; otherwise
retain hourly uncertainty. No fabricated intrabar timestamps: touch times bracketed
by hour open/close, funding charged with endpoint sensitivity.

Costs are round-trip 10/20/40bps of entry notional for continuity. Each scenario
separately records assumed fee/spread/slippage contributions: (8,1,1), (8,4,8),
(8,8,24). These are scenarios, NOT measured fees or quotes. Charge half at entry
and half proportionally on exits. Funding uses hourly rate buckets, entry-notional
approximation times remaining quantity, upper/lower boundary exposure sensitivity;
missing rates make net results unavailable, never zero-filled.

Equal-risk R and equal-entry-notional returns are not leveraged account returns.
No account sizing, liquidation model or shared capital is asserted. Closed-trade
drawdown is explicitly distinguished from portfolio mark-to-market drawdown.
Split by existing 4h indices <660 development, 660–719 embargo, >=720 later;
exclude trades crossing either boundary from development/evaluation summaries.
All this history has been inspected: later means chronological, NOT unseen.
Bootstrap whole Monday-UTC admission weeks jointly across assets (seed 20260921,
2000 resamples), report occupied weeks and no-trade weeks; intervals descriptive.

Former schedule 08/14/20 America/Argentina/Buenos_Aires (=11/17/23 UTC): a setup
is observable if the first scheduled run >= its admission is no later than trigger
close (flip) or entry-hour start (passive). This tests opportunity visibility ONLY,
not executable delayed fills; no false claim to have replayed historical automation.

## Acceptance and scope inventory

Do not promote unless benefit remains at 40bps, both path assumptions, both sizing
views and removal of HYPE/strongest asset, with enough independent weeks and
uncertainty excluding no benefit. Small samples => INCONCLUSIVE. No minimum-N
shortcut proves reliability. No threshold changes after replay.

Excluded: countertrend/reset, ZC2 reversal entry, micro-PFQ entry, weekly range
breakout alternative, climax cooldown, exact institutional order blocks/session
confluence, macro/COT reconstruction without release evidence, real order queue,
full re-entry resets, leverage/liquidation. These exclusions prevent calling this
the entire theory. They are recorded for later work, not silently considered passes.
