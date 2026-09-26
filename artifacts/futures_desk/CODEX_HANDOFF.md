# Rocket futures desk — handoff

Written 2026-09-23 for the next agent (Codex or otherwise). This is the project record. It is not a new strategy and it is not permission to tune a rejected rule.

Operator: Jhonny Vergara.
Repo: https://github.com/jhonnyisaacc/rocket
Model preference for this project: Grok 4.7 high fast only (`grok-4.7-high-fast`). Do not use Opus 5.5.

## What Rocket is trying to become

A discretionary crypto futures method (Elcripto Pana: multi-timeframe direction, pullback after an impulse, a reaction, then a lower-timeframe confirmation, plus COT as market regime) was supposed to become one command whose JSON a bot can act on:

`ENTER_LONG | ENTER_SHORT | WAIT | NO_TRADE`

with zone, invalidation, first objective, and `reasons[]`.

The operator is not sitting the book. `execution_enabled` stays false until a human accepts a contract that survived costs on a tape Hyperliquid actually has. Cava is a separate daily briefing and stays out. No orders, no signing, no JEV, no pstack, no memecoin work, no second Hyperliquid client, no Solana/Helius.

Production preference, not a research filter: a small number of high-conviction swing entries per month on the liquid book. Do not throttle, drop, or keep trades to manufacture that count. A one-position cap is portfolio construction. It is not evidence the signal improved.

## Read these first

1. This file.
2. https://github.com/jhonnyisaacc/rocket/pull/32 — latest research generation. Daily 50-close break. Hypothesis rejected.
3. https://github.com/jhonnyisaacc/rocket/pull/31 — finished bakeoff. Do not edit its contracts or results to rescue them.
4. https://github.com/jhonnyisaacc/rocket/pull/29 — staged live scan. Not the strategy. Do not treat it as complete.
5. https://github.com/jhonnyisaacc/rocket/pull/28 — historical only. Zero primary fills. Do not re-encode it as the live detector and do not relax it because later counts were nonzero.

## Current end state

No compelling technical edge has been validated. The live scan was not switched to any winner. That is correct.

The last formal test, `daily-trb-50d-v1`, is **hypothesis rejected**. Do not tune 50 into 20, 150, or 200. Do not add a 1% band. Do not drop the losing side after seeing the split. Experiments that were allowed only if this test survived (a pullback-versus-break comparison, and relative strength as a ranker) were not run and are not authorized.

`NO_EDGE_ON_AVAILABLE_TAPE` was never the label for the 12-month hourly bakeoff, because that hourly tape does not exist. The daily validation did run, and it failed costs.

## Data you can actually use

Provider: `rocket/providers/hyperliquid.py` `fetch_candles` (`candleSnapshot` on `https://api.hyperliquid.xyz/info`). It already sends `startTime` and `endTime`. No API key. Do not add a second client.

Measured 2026-09-23:

- 1h: about 5000 bars. First BTC/ETH open `2026-02-27T00:00:00Z`. A request ending 2026-02-01 returned an empty HTTP 200. Do not invent hourly bars before that. Do not fill an hourly rule with a 4h open.
- 4h and 1d: about 12 months, from `2025-09-23` through `2026-09-23`. BTC daily: 366 bars in the PR #32 pull. The forming last daily bar is not a signal.
- Funding history paginates and is usable. It was not why the 12-month hourly replay failed.
- CoinGecko in this repo is live-only. There is no vintage market-cap book. Do not stamp today’s top 100 onto old bars.
- Delisted names are absent from `metaAndAssetCtxs`. Do not reconstruct them.
- Open interest and spread history were not available for the bakeoff. Do not fill them from today’s meta.

A new hypothesis may use a native 4h or 1d clock and the longer 4h/1d history. Do not move an hourly rule onto 4h just to lengthen the sample.

k-prefix perps: the venue spelling is `kPEPE`, `kSHIB`. Uppercase `KPEPE` returns HTTP 500. PR #32’s daily run failed candle requests for KPEPE, KSHIB, KBONK, KLUNC, KFLOKI, KNEIRO because `fetch_candles` uppercases the coin.

## PR #28 — historical, not live

Branch `codex/crypto-strategy-research`. Frozen research reading of nave `docs/technical.yaml`. Not user-approved doctrine. The YAML is a project refinement, partly outcome-informed, not authenticated educator text.

Full stacked pullback: weekly velocity ±1.2 with nine weeks, daily HH+HL / LH+LL pivots, locked daily impulse, 75–86% band, BEN zone, confluence ≥ 3, 4h reaction, 1h sweep then break then retest, stop at the hourly swing, two structural objectives, reject if first objective < 1R.

Result: 0 primary hypotheses and 0 fills on 6,480 completed 4h decisions (BTC, ETH, SOL, XRP, HYPE, ZEC). An older looser baseline had fills whose expectancy died at realistic costs. The PR refused to call zero admissions “zero edge” and refused to relax rules after seeing zero. Keep that refusal.

Open doctrine, still unresolved, do not pick after seeing PnL: pullback vs locked daily impulse vs local 4h swing; weekly 1.2 vs 1.5; stop as hourly swing vs a later 1.5× daily ATR floor; flip-candle close vs next hourly open; whether a retest is required. `cot_integration.yaml` is not in the repo.

## PR #29 — staged scan, not an entry engine

https://github.com/jhonnyisaacc/rocket/pull/29
Branch: `cursor/staged-futures-scan-d9f7`
Not merged. Not strategy-complete.

What it shipped:

- `rocket crypto scan --json` fills `payload.candidates` with `NO_BIAS | BIAS | IN_PLAY | ZONE | EXTENDED | NO_TRADE`.
- `payload.final_candidates` is still the legacy 6-bar monotone funnel. A healthy scan can be operational `HEALTHY`, research `NO_SETUP`, `final_candidates` 0. The book a human reads is `payload.candidates`.
- Bias is close-to-close: weekly last vs 4 weeks, daily last vs 6 days. That is not weekly velocity and not daily pivots.
- `ZONE` is agreed weekly+daily direction and last close inside 50–86% of a rolling 4h impulse. Labeled research interpretation. The documented entry band in the YAML is 75–86%, and 50% is an alert.
- `execution_enabled` false. No `ENTER_LONG` / `ENTER_SHORT`.
- Universe: CoinGecko top 100 by market cap intersected with Hyperliquid perps. 57 of 100 map (55 exact, plus SHIB → `kSHIB`, PEPE → `kPEPE`). 43 have no perp and are gaps, not rows.
- COT: live CFTC report. On 2026-09-23 the book was `bearish` (report `https://www.cftc.gov/dea/futures/deacmelf.htm`, as-of 2026-09-15, 8 days old, inside a 0–14 day rule). BTC was `EXTENDED` long, `cot_alignment` against, row kept. `bot_decision.action` was null with reason `cot_alignment_labeled`. Missing or stale COT stays on the row as `unknown` and the decision is `WAIT`, not a silent `NO_TRADE`. The same BTC/ETH regime is stamped on every row. That is market regime, not per-alt COT. No source says what `against` does to an entry. `C9_cot` in the ENTER contract is OPEN.

Tests reported on that branch: `402 passed, 1 deselected` for `python3 -m pytest -q -m 'not integration'`.

Staged-state replay (not entries), 2026-06-25 through 2026-09-23, 57 symbols, 30,737 rows: NO_BIAS 8819, BIAS 22, IN_PLAY 1043, ZONE 1284, EXTENDED 8229, NO_TRADE 11340. COT was unknown for that whole rerun. Today’s liquidity made 21 of 57 `NO_TRADE` on every bar. Today’s top 100 was projected backward. Those ZONE counts are not fills and not expectancy.

Files on that branch:

- `artifacts/futures_desk/FINDINGS.md` — the live 6-bar gate explains empty `final_candidates`.
- `artifacts/futures_desk/STAGED_CONTRACT_v0.md`
- `artifacts/futures_desk/STRATEGY_GAP.md` — ten-row gap. None of the ten pieces is both documented and live.
- `artifacts/futures_desk/ENTER_CONTRACT_v0.md` — **NOT YET FROZEN**. Until a human accepts it, every `ZONE` is `WAIT` with `enter_contract_not_frozen`.
- `artifacts/futures_desk/COT_SLICE.md`
- `artifacts/futures_desk/HOW_TO_RUN_24H.md`
- `artifacts/futures_desk/BACKTEST_TOP100.md`

Strategy gap, short form: weekly velocity, daily pivots, locked impulse, 75–86% confluence zone, 4h reaction, hourly trigger, and stop plus first objective are not what the live scan computes. The scan’s versions of the first four are different objects. COT is a label that does not choose an action when the report is fresh. Point-in-time universe exists for a live scan and is missing from backtests.

## PR #31 — finished bakeoff, do not rescue

https://github.com/jhonnyisaacc/rocket/pull/31
Branch: `cursor/futures-bakeoff-contracts-23d2` (based on the staged-scan branch). Draft. Do not mutate `CONTRACTS.md` or `RESULTS.md` to make a winner.

Five frozen contracts. Clocks that were constraints for that bakeoff: bias may use W/D, setup on 4h, fill at the next 1h open. That clock is why 12 months could not be scored. It is not a law for every future hypothesis.

12-month table: **BLOCKED**. Not zeros. Not `NO_SAMPLE`. Not `NO_EDGE_VALIDATED`.

Available 1h tape only, 2026-02-27 through 2026-09-23, 6.845 months, 56 names, month-start daily quote-volume floor 5,000,000. Not a vintage top 100.

| Contract | Entries | Per month on that tape | 20bps + funding | 40bps + funding |
|---|---:|---:|---|---|
| `trb-50d` | 952 | 139 overlapping 10-day events | net return +0.0131, R undefined | +0.0111, R undefined |
| `cmom-r3-quintile` | 238 | 34.8 memberships | unweighted +0.0006 | unweighted −0.0014 |
| `pana-full` | 0 | NO_SAMPLE | — | — |
| `staged-zone-as-entry` | 625 | 91 | mean R −0.056 | mean R −0.113 |
| `theory-v2-code` | 107 | 15.6 | mean R −0.080 | mean R −0.100 |

How to read that, without crowning anyone:

- Deep confirmation either never fires (`pana-full`) or loses when loosened into an entry (`staged-zone-as-entry`, `theory-v2-code`).
- A standalone three-week long-short quintile is flat after costs. Vintage caps were missing, so it is not the paper’s value-weighted portfolio. Relative strength was not tested as a ranker.
- `trb-50d` is the only positive average. It is screening evidence: overlapping events, no stop, 4h observation, 1h fill, 6.8 months that include the June 2026 rebound and the HYPE high. Brock, Lakonishok, and LeBaron (1992) are a daily event study, not a one-position book. The hourly fill was imposed so the contract would sit on the bakeoff clock.

`swing_4h1h_v0` was searched in rocket and nave and not found. Do not invent it.

Left uncontracted on purpose because they cannot sit on a 4h-setup / 1h-fill clock without a new rule: monthly TSMOM, Jegadeesh-Titman deciles, Moreira-Muir vol scaling, crypto carry, liquidation flushes.

## PR #32 — daily continuation, rejected

https://github.com/jhonnyisaacc/rocket/pull/32
Branch: `cursor/daily-trb-50d-v1-c2f7` from main. Draft.
Files:

- `artifacts/futures_desk/RESEARCH_ASSESSMENT.md`
- `artifacts/futures_desk/generations/daily-trb-50d-v1.md` (frozen before the run)
- `artifacts/futures_desk/generations/daily_trb_50d_v1.py`
- `artifacts/futures_desk/generations/daily-trb-50d-v1-RESULTS.md`

Rule that was frozen: completed 1d close breaks the prior 50 completed daily closes’ high or low. No 1% band. Fill at the next daily open. Outcome is the open 10 sessions later. Costs 20bps and 40bps, half entry and half exit, plus funding. Eligibility: signal-day base volume times close ≥ 5,000,000. Not today’s top 100.

Validation, 2025-09-23 through 2026-09-22 completed dailies. 178 listed perps. 124 eligible names. 1,284 eligible events. 1,188 closed and funded. 96 still open, out of the mean.

Event-study mean (this is the hypothesis):

- All: −0.008253 at 20bps, −0.010253 at 40bps.
- Long: 616 events, −0.023301 / −0.025301.
- Short: 572 events, +0.007953 / +0.005953.
- Gross mean before costs and funding: −0.007945. Funding drag about −0.0017.
- The positive short side does not save the rule. Do not drop longs after the fact.

Per-name non-overlapping book (portfolio construction, not a better signal): 448 closed trades, mean −0.002839 / −0.004839.

June 2026 window and HYPE window were reported. They do not decide the result, because there is no positive combined mean for one episode to explain. HYPE’s high window had 0 closed funded events in the mean.

**Hypothesis rejected.** Experiments 2 and 3 from the research plan were not run. Do not run them. Their precondition was that this event-study mean survived both cost levels and was not one coin or one episode.

## What the next agent may do

Discovery and validation stay separate. Inspect, compare, and reject during discovery. Once a candidate is chosen for a formal test, freeze the page, then run it once. Do not edit it after PnL. A new idea is a new generation with a new name. It is not a silent edit of `trb-50d`, `daily-trb-50d-v1`, `pana-full`, `staged-zone-as-entry`, `theory-v2-code`, or `cmom-r3-quintile`.

Separate the layers in every writeup:

1. Signal edge (the event-study mean).
2. Portfolio construction (one position, overlap rules, ranking).
3. Execution (which open is the fill).
4. Risk (stop, objective, R). Do not mix a nicer portfolio count into the signal mean.

Allowed end states for a future generation: hypothesis rejected; needs more research; promising but forward-shadow only; specified for an ENTER contract after the operator accepts it; no compelling technical edge found yet.

Not allowed without a new operator request:

- Patching Pana or PR #28 onto the live scan.
- Promoting staged `ZONE`.
- Turning the short side of `daily-trb-50d-v1` into a new rule because shorts were green.
- A one-position throttle of the PR #31 contracts, reported as if the signal improved.
- Using 1–2 trades/month as a filter.
- `execution_enabled` true, cron, or a Grok bot. Those come after an accepted ENTER contract.
- JEV, Cava inside the scan, pstack, memecoin files.

If the operator asks for another formal test, the families not yet tested as their own frozen hypotheses are mean reversion / exhaustion, volatility compression, and regime-conditioned momentum. They are not automatically next. Daily continuation-as-a-50-close-break was the indicated next test, and it failed. Do not start those other families in the same breath as “continuing the repo.” Write the mechanism, the native clock, the falsifier, and the structural parameters, freeze them, then run once.

Forward shadow is for a rule that survives costs but is too short to ship. Nothing currently qualifies.

## Live command, if you need to see the book

From a checkout of `cursor/staged-futures-scan-d9f7` (PR #29), not from main, and not from PR #32 (that branch does not contain the staged scan):

```text
rocket crypto scan --json
rocket status --json
```

Read `payload.candidates` and `payload.bot_decision`. Do not treat `final_candidates` or research `NO_SETUP` as the staged book. No private key. Public Hyperliquid and the public CFTC page.

Tests:

```text
python3 -m pytest -q -m 'not integration'
```

`pyproject.toml` already sets `-q`, so a double-quiet run prints only the progress bar. Drop one quiet flag to see the summary line.

## Operator constraints that kept getting lost

- The live 6-bar gate (`setup_from_candles`: last 6 closed 4h bars strictly monotonic, then reject about 2% extension) is why the old scan looked empty. It is not the theory failing.
- Encoding the full theory as an AND-chain produced zero admissions. Silence is not `WAIT` and not an entry.
- Two agents on the same candles will disagree while the doctrine is unfrozen. Do not “fix” that by picking a side after a backtest.
- COT must show up as aligned / against / unknown. Unknown is `WAIT` when regime is required. Against keeps the row. Neither is an entry.

## Keys

No trading key, wallet, or seed. Do not ask for one. Hyperliquid public info and the public CFTC report are enough for research. GitHub access to `jhonnyisaacc/rocket` is what a PR needs.
