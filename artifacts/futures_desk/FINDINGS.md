# Futures desk findings — live 6-bar gate vs staged states vs PR #28

Read-only reference: https://github.com/jhonnyisaacc/rocket/pull/28 (`codex/crypto-strategy-research`, not merged). Production lines are `main` at the time of this note (`rocket/workflows/crypto.py`, `rocket/providers/hyperliquid.py`).

## Does the 6-bar gate explain empty live scans?

Yes. A healthy live scan can print research `NO_SETUP` with zero `final_candidates` because `setup_from_candles` almost never returns `valid: true`. That empty book is the detector, not a failed momentum-plus-COT theory, and it is not the PR #28 stack (that stack is not on this branch and is not the live detector).

The live rule requires the last 6 closed 4h bars to be strictly monotonic — every high and every low rising together, or every high and every low falling together — and then rejects a close more than 2% beyond the prior swing. Mixed 4h structure, which is the usual case, is `valid: false` with reason `mixed_or_insufficient_structure`. The funnel drops that coin before a human ever sees a bias, a zone, or a COT alignment. The operator sees `NO_SETUP` and can mistake the gate for the theory.

## File:line map

### Live detector (production, this repo)

| What | Where | Effect |
|---|---|---|
| Window length | `rocket/workflows/crypto.py:38` `STRUCTURE_BARS = 6` | Last 6 closed 4h bars only |
| Warmup before any setup | `rocket/workflows/crypto.py:39` `MIN_SETUP_BARS = 24` | Fewer than 24 parsed 4h bars → invalid |
| Chase cap | `rocket/workflows/crypto.py:40` `NO_CHASE_PCT = 0.02` | Close beyond 2% of the prior swing → invalid |
| Strict HH+HL / LH+LL | `rocket/workflows/crypto.py:416-432` `structure_state` | Anything else is `MIXED` |
| Binary setup | `rocket/workflows/crypto.py:435-487` `setup_from_candles` | Mixed → `valid: false`, `mixed_or_insufficient_structure`. Monotonic but extended → `valid: false`, `extended_beyond_retest_band`. Only a monotonic non-extended print is `valid: true` |
| Applied on the live path | `rocket/workflows/crypto.py:490-528` `apply_setup_candles` | Liquid eligible names get that binary setup |
| Funnel AND | `rocket/workflows/crypto.py:192-225` `build_funnel` | `momentum_pass` and `final_candidates` require `setup.valid is True` plus eligible, liquid, macro, and COT |
| Empty book status | `rocket/workflows/crypto.py:722-730` | No final candidate and no provider/incomplete gap → research `NO_SETUP` |
| Closed 4h fetch (this part is right) | `rocket/providers/hyperliquid.py:236-265` `fetch_setup_candles` | Public `/info` `candleSnapshot`, 4h, drop bars whose close is after the scan cutoff. No signing |

`structure_state` is the strict check: for the last 6 bars, `high[i] > high[i-1]` and `low[i] > low[i-1]` for every i, or the same with `<`. One inside bar fails the coin.

### Staged states (what a decision scan needs)

Not a second engine. The same `rocket crypto scan` payload must keep a row and say where the coin is:

`NO_BIAS | BIAS | IN_PLAY | ZONE | EXTENDED | NO_TRADE`

Mixed 4h structure is a `structure_4h` value on the row, not a drop. Unknown COT does not wipe the row. Known COT against the direction stays on the row as `cot_alignment=against`. Missing candles stay `evaluated=false` instead of a fake setup. The contract for which of those steps are inherited and which are research interpretation is `artifacts/futures_desk/STAGED_CONTRACT_v0.md`.

### PR #28 stacked pullback (do not ship as the live detector)

PR #28 adds no production scan change. Its primary contract is an offline AND-chain in `.rocket/research/full_strategy_v1/engine.py` on `codex/crypto-strategy-research`:

| Gate | Where | Blocker if it fails |
|---|---|---|
| Weekly velocity, nine complete weeks, strict ±1.2 | `engine.py:34-37` `velocity`, `engine.py:127` and `:130-131` | `weekly_warmup_unknown`, `weekly_neutral` |
| Daily pivot HH+HL or LH+LL | `engine.py:40-44` `daily_direction`, `:132-134` | `daily_structure_unknown`, `daily_mixed`, `weekly_daily_disagree` |
| Confirmed daily impulse / BOS lock | `engine.py:46-76` `impulses`, `:135-137` | `impulse_unavailable`, `impulse_daily_disagree` |
| Retracement band 75–86% of the locked **daily** impulse | `engine.py:87-89` `zone_candidates` | (feeds `zone_unavailable`) |
| BEN pivot, institutional scale, confluence ≥ 3 | `engine.py:78-107`, `:149-150` | `zone_unavailable`, `confluence_below_three` |
| 4h reaction (intersect, directional body, wick ≥ body, close beyond midpoint) | `engine.py:109-112` `reaction`, `:151` | `reaction_absent` |
| Two structural objectives and an hourly stop | `engine.py:114-121`, `:152-155` | `two_objectives_unavailable`, `hourly_stop_unknown` |
| Eligible only if every blocker is absent | `engine.py:159` `eligible=not blockers` | snapshot rejected |
| Hourly sweep / break / retest flip after admission | `engine.py:161-179` `flip_step` | not reached when nothing is admitted |

`CONTRACT.md` in that package freezes the same chain (weekly ±1.2, daily pivots, daily-impulse 75–86% band, BEN, confluence, reaction, hourly flip). `REPORT.md` and `funnel.json` record the result: 6,480 completed 4h snapshots (BTC, ETH, SOL, XRP, HYPE, ZEC), **0 primary hypotheses admitted**, 0 fills. That is inconclusive about expectancy. It is not a production threshold to copy, and it must not be tuned until that contract actually fills.

## Live check (2026-09-23, public Hyperliquid, no key)

`setup_from_candles` on the closed BTC 4h series returned `valid: false`, reason `mixed_or_insufficient_structure`, structure `MIXED`. The same candles staged as `EXTENDED` / `long` (weekly and daily bias both long, retrace about 0.06, mixed 4h kept on the row).

A full `rocket crypto scan --json` in that window was operational `HEALTHY` with research `NO_SETUP`, `final_candidates` 0, and `trade_decision` `NO_TRADE`. The decision book was not empty: 30 `EXTENDED`, 2 `ZONE` (PUMP, LIT), 3 `NO_BIAS`, 65 `NO_TRADE`. COT regime was bearish, so the long ZONE rows stayed with `cot_alignment=against`. That is the empty-scan bug: the status line follows the 6-bar gate, while the book already has staged research.

## What this trial changes

The live decision surface becomes staged momentum + market-regime COT on the existing Hyperliquid read path. The PR #28 AND-chain stays unread as production code. The legacy 6-bar `setup_from_candles` result can remain on the old funnel so existing harness fixtures keep their meaning; it is not what a human or a command-running bot uses to decide.
