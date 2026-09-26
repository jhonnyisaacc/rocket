# Rocket futures research assessment

PR #31 is a completed experiment. Its five contracts, results, and limitations stay intact. Nothing in this assessment mutates them, throttles them into a winner, or installs them on the live scan. This file records what those pulls taught and which single next test was authorized. It is not a second strategy.

## What the three PRs taught

[PR #28](https://github.com/jhonnyisaacc/rocket/pull/28) encoded the full multi-timeframe pullback as one AND-chain. On 6,480 completed 4h decisions it admitted zero primary hypotheses. The stack dies on weekly neutral or unknown, mixed daily structure, missing impulse, missing zone, and almost always a missing reaction. That is a sample-size collapse. It is not a measurement of pullback edge, because a rule that never fires has no trades to score. It is also not a reason to relax those gates after the fact.

[PR #29](https://github.com/jhonnyisaacc/rocket/pull/29) made the book readable. Staged states, a close-to-close weekly and daily sign, and a 50–86% band on a rolling 4h swing are research labels. The live scan still has no `ENTER_*`. On 2026-09-23 BTC was `EXTENDED` long with COT bearish and `against`, and `bot_decision.action` was null. A fresh COT report labels the book. It does not choose an entry. Unknown COT becomes `WAIT` rather than a silent drop. Treating `ZONE` as an entry was left to the bakeoff, where it lost money.

[PR #31](https://github.com/jhonnyisaacc/rocket/pull/31) is the empirical baseline. Twelve months of 1h fills do not exist: `candleSnapshot` returns about 5000 hourly bars, first BTC/ETH open 2026-02-27. Twelve months of 4h and 1d bars do exist. On the 6.845-month hourly tape, 56 names, 20bps and 40bps plus funding:

- `pana-full`: zero hypotheses. The confirmation stack still contributes no measurable trades.
- `theory-v2-code`: 15.6 trades/month, mean R about −0.08 / −0.10. A looser multi-timeframe engine than Pana, with a moving-average 4h gate the YAML told engines not to use, loses after costs.
- `staged-zone-as-entry`: 91/month, mean R about −0.06 / −0.11. “Agreed close-to-close bias and price inside a rolling 4h retrace” is not an entry edge on this tape.
- `cmom-r3-quintile`: about 35 memberships/month, unweighted net return about 0 at 20bps and negative at 40bps. A standalone long-short quintile book is not useful here. Vintage market cap was missing, so this is not the paper’s value-weighted portfolio.
- `trb-50d`: about 139 overlapping 10-day events per month, net return about +0.013 / +0.011. No stop, so R is undefined. This is the only positive average after costs. It is an event study of a daily range break, not a swing book. The 6.8-month window includes the June 2026 rebound and the HYPE high. That result is screening evidence only.

Read as market behavior, not as a leaderboard: the rules that wait for deep multi-timeframe confirmation either never trade or lose. The simple “price went through the prior 50-day extreme” event has a small positive average return on a short, overlapping sample. Cross-sectional momentum as its own portfolio is flat after costs. None of this validates a production strategy. None of it says the 50-day break is the winner. It says the next informative question is whether medium-horizon continuation exists once signal, clock, and portfolio are separated.

## Assumptions that stay frozen

- Hyperliquid only, through `rocket/providers/hyperliquid.py`. No fabricated hourly bars, delistings, liquidity, or market-cap membership.
- Completed bars only. Fill at the next open of the hypothesis’s native clock.
- Costs at 20bps and 40bps plus funding on every formal test.
- A frozen hypothesis is not edited after its validation PnL. A failure stays a failure.
- PR #31 files stay as they are. A new hypothesis is a new generation with a new name.
- `execution_enabled` stays false. The live scan stays frozen until an ENTER contract is accepted. Cava stays out. COT is not the setup. No JEV, pstack, memecoin work, cron, or bot.

## Assumptions that should stop constraining new research

- New work does not have to be a 4h setup with a 1h fill. A hypothesis whose mechanism is daily may use the 12-month daily tape and fill at the next daily open. A hypothesis whose mechanism is 4h may fill at the next 4h open. An hourly rule is not rewritten onto 4h just to lengthen the tape.
- One to two book-level trades per month is a production preference. It is not a research filter. Throttling entries until the count looks right is portfolio construction. It is not evidence the signal improved.
- Weekly velocity ±1.2, daily pivot structure, a 75–86% band, a 1h flip, and the staged 50–86% zone are not mandatory ingredients of the next hypothesis.
- “Rescue one of the five contracts” is not the goal.

## What is worth investigating

Most informative next family: trend continuation expressed as a break of a prior range, at the daily horizon.

Why this one, and not another AND-chain: it is the only tested behavior with a positive average after costs, and the test that produced that average was the wrong clock and the wrong accounting. Brock, Lakonishok, and LeBaron (1992) predict a different return over a fixed window after a daily close breaks the prior 50-day high or low. They do not predict a one-position book. PR #31 observed that break on a 4h close and filled the next 1h open so the contract would sit on the bakeoff clock. That imposed clock is why the 12-month daily history was unused. Re-running the paper on daily bars is not a conversion of an hourly strategy onto 4h to chase a better number. The hourly fill was the conversion.

Mechanism that could persist: stops and breakout orders cluster beyond obvious prior extremes, and a multi-day drift can follow. Crypto perps can reverse that through funding and crowding, which is why both cost levels and funding stay in the test, and why a tiny overlapping gain on six months is not enough.

Falsifier: on the 12-month daily tape, a frozen non-tuned rule whose average return dies at 20bps, or whose gains sit in one coin or one episode (the June 2026 rebound or the HYPE high), is rejected. A book-level trade count is not the falsifier.

Structural parameters, not knobs: 50 daily closes, no 1% band, 10-day outcome window, next daily open fill. The paper’s other lengths (150, 200) and the 1% band stay unused. They are not searched after the result.

Different from what was tested: new generation, daily signal, daily fill, 12-month daily history. Overlapping event returns and per-name non-overlapping trades are both reported, and they are not mixed. The non-overlapping count is portfolio construction. It is not allowed to replace the event-study mean, and a nicer count is not called better edge.

Families not next, and why:

- Deep pullback confirmation. Already either empty (`pana-full`) or a losing entry (`staged-zone-as-entry`, `theory-v2-code`). Another stack of the same gates will not tell us whether continuation exists.
- Standalone cross-sectional quintiles. Already flat after costs. Relative strength may still be a ranking feature later. It is not the next portfolio.
- Mean reversion, volatility compression, regime filters. Not tested. They are alternatives if daily continuation is rejected, not parallel strategies started from the same short tape. A regime slice may be reported on the frozen daily test. Losing regimes are not dropped after seeing them.
- One-position throttles of `trb-50d`, `theory-v2-code`, or `staged-zone-as-entry`. That draft was withdrawn. It would manufacture a cadence and then misread portfolio design as signal edge.

## Discriminating experiments

Only the first is authorized as the next formal test. The others are the sequence if that test earns them. Each one is frozen before its own validation. None of them modify PR #31.

1. Signal versus clock. New contract `daily-trb-50d-v1`. Completed daily close breaks the prior 50 daily highs or lows. Fill is the next daily open. Outcome is the return to the daily open 10 sessions later. Report the overlapping event-study mean and, separately, a per-name book that skips a new signal while that name is still inside its 10-day window. Long and short separately. By asset. By calendar month. Concentration: share of net return from the largest coin and from the June 2026 rebound window and the HYPE high window. Drawdown and fraction of days in a position. Costs 20bps and 40bps plus funding. Screening label: the existing `trb-50d` hourly result. Validation label: this run only. No parameter is changed after the table exists.

2. Only if experiment 1’s event-study mean survives both cost levels and is not one coin or one episode: a second generation that enters on a predeclared retrace of that same daily break, versus entering on the break. Same exit clock, same costs. If the retrace does not improve the distribution, pullback confirmation is not the missing piece. If experiment 1 fails, this comparison is not run.

3. Only if experiment 1 survives: condition the same daily break on prior three-week relative strength, as a ranker, not as a new quintile portfolio. If the conditional distribution does not separate, cross-sectional strength is not how this book should pick names.

No experiment searches hold length, channel length, or a volatility cutoff. A predeclared volatility report slice is allowed on experiment 1. It cannot delete trades.

## Sequence and end states

1. File this assessment.
2. Write `daily-trb-50d-v1` as its own contract page. Freeze it. Then run it once.
3. Stop at one of these states, in writing:
   - Hypothesis rejected. The daily break does not survive costs or is one episode. Do not tune 50 days into 20.
   - Needs more research. The result is ambiguous on a 12-month tape. Say what is ambiguous. Do not add a filter to resolve it.
   - Promising, but the history is too short for production. Forward shadow: log each later decision and score it later against the frozen rule. No live `ENTER_*`.
   - Specified for an ENTER contract. Only if the operator accepts the frozen page after validation. `execution_enabled` still starts false.
   - No compelling technical edge found yet. Allowed. The live scan keeps printing research states.

Production cadence, a Grok bot, and cron stay after an accepted contract or an explicit request. They are not part of this research.

The authorized files are this assessment, then `artifacts/futures_desk/generations/daily-trb-50d-v1.md`, then one results note beside it. The runner stays out of the live scan.

## What will not be done

- Edit `trb-50d`, `pana-full`, `staged-zone-as-entry`, `theory-v2-code`, or `cmom-r3-quintile`.
- Interpret a one-position throttle as signal improvement.
- Use the 1–2 trades/month target to drop or keep trades.
- Re-encode PR #28. Patch Pana. Promote staged `ZONE`.
- Pretend hourly history exists before 2026-02-27.
- Set `execution_enabled` true. Touch Cava, JEV, pstack, memecoin, cron, or the bot.
- Write `ENTER_CONTRACT_v1`. Implement experiments 2 or 3.
