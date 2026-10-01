# Market-check experiments

Tuning universe 2024-10-01 to 2026-05-31. Holdout 2026-06-01 to 2026-09-30,
evaluated exactly once at the very end. Variant choices below never look at
the holdout. (Pre-existing context: v4 full-window numbers from BACKTEST.md
were written before this protocol; selection decisions here use only the
tuning universe.)

Free-parameter budget (6 total): VIX combo level (25), credit widening
(50bp), SPY drawdown gate (12%), redeploy holding cash target (30%), BTC
stop (15%), BTC profit-take (30%). Everything else stays at v4 values. VIX
spike (25) and name drawdown (10%) were tested and found non-binding, so
they are fixed, not tuned. The breadth rule (v6) is a fixed structural
majority (4 of 7 core names), never tuned. Selection discipline: where a
parameter is monotonic (more beta = better in this window), the middle
value was taken, never the maximizer.

Conventions: IS = in sample (2024-10-01 to 2025-09-30). Stitched =
quarterly test segments chained from 2024-Q4 through 2026-Q2-. Strategy
Sharpes are risk-free-adjusted; EqW/SPY raw Sharpes are shown for
continuity with BACKTEST.md, with like-for-like rf-adjusted EqW alongside.
Costs: 0.3% per stock trade each way, next-session fills in the portfolio
engine and the v4/v5/v6 BTC engine, perp funding plus fees, puts
Black-Scholes mid with the standing IV-slippage proxy. EqW = equal-weight
buy-and-hold of the 11-name universe. Tune-OOS perp = tuning-universe OOS
(2025-10-01 to 2026-05-31), not the old full-window OOS.

Variant count: 43 logged runs (Exp 0-42).

## Exp 0 — honest execution on v4 (mechanical, not tuned)

Next-session fills plus 30bps. Full window 2024-10-01 to 2026-09-30:

| Version | Full Sharpe | OOS Sharpe | OOS DD | Perp IS / OOS |
|---|---|---|---|---|
| v1 | 0.97 | 1.25 | -24.3% | +23.4% / -14.3% |
| v2 | 0.68 | 0.95 | -11.2% | -12.7% / -23.2% |
| v3 | 0.73 | 0.89 | -11.0% | +12.8% / 0.0% |
| v4 | 0.90 | 0.97 | -16.8% | +29.7% / -43.7% |
| EqW OOS | 1.14 | 1.14 | -16.8% | — |

Mechanical impact is small (v4 OOS 0.96 -> 0.97). Story unchanged: only v1
beats EqW on OOS Sharpe and only with a deeper drawdown. Decision: adopt
honest execution for all further work.

## Exp 1 — v4 in the tuning universe (reference)

v4 strategy IS 17.4% / -16.8% / 0.83; stitched 22.8% / -16.8% / 1.11
(rf-adjusted). EqW IS 26.2% / -28.3% / 0.83 raw (0.834 rf-adjusted);
stitched 32.4% / -28.3% / 1.21 raw (1.055 rf-adjusted). SPY stitched 20.1% /
-18.8% / 1.16 raw. Quarterly v4 Sharpe: 2024-Q4 1.52, 2025-Q1 -2.73,
2025-Q2 2.30, 2025-Q3 1.64, 2025-Q4 0.52, 2026-Q1 0.29, 2026-Q2- 4.27.
EqW quarterly Sharpe: 1.17, -1.87, 2.17, 3.12, 0.92, 0.17, 4.35. The
strategy wins down quarters, ties rebounds, loses rallies (cash drag).

## Exp 2-4 — v5 BTC exits, first cut (stop / take)

| Variant | Perp IS | Tune-OOS perp |
|---|---|---|
| v5 stop 15% / take 30% | +24.9% | 0.0% |
| v5 stop 20% / take 30% | +24.9% | 0.0% |
| v5 stop 15% / take 50% | +29.7% | -45.8% (stops out Feb 2026) |

Take 30% banks the April 2025 long in May 2025 (+~25%) and is flat after:
no OOS bottom signal ever refires. Take 50% never triggers IS and rides
into the Feb-2026 stop. Stocks identical (22.8% / -16.8% / 1.11).
Single-episode evidence so far; economics (bounce trade with exits) carry
the choice, to be checked by sensitivity, not by maximizing IS perp (the IS
maximizer would be take 50% — rejected as overfit direction).

## Exp 5-6 — stop-only (take off)

Stop 15% or 20% alone: perp IS +29.7%, tune-OOS -45.8% (Feb-2026 stop).
The stop fires months too late without a target. A stop without a target
does not fix the secular-hold problem. Rejected as insufficient.

## Exp 7-8 — lower the drawdown gate (10%, 8%)

Gate 10%: IS 15.2% / -17.9% / 0.68, stitch 20.1% / -17.9% / 0.96. Gate 8%:
IS 15.0% / -17.8% / 0.68, stitch 18.2% / -17.8% / 0.89. Lowering the gate
catches the failed March 2025 fade and adds bad episodes. Confirms the
PR note: do not lower the gate. Rejected.

## Exp 9-10 — VIX spike 20 / 30

Identical to base (59 trades, same numbers). The spike level is
non-binding in these episodes; the fade plus drawdown gate bind. Fixed at
25 (round, motivated), outside the tuning budget.

## Exp 11-12 — credit widening 30bp / 50bp (combo)

30bp: IS 12.3% / -16.8% / 0.57, stitch 21.2% / -16.8% / 1.08, 81 trades
(churn on noise). Rejected: tighter credit raises cash on noise. 50bp: IS
17.4% / -16.8% / 0.83, stitch 24.0% / -16.8% / 1.15, 49 trades. IS ties
40bp; stitch slightly better with fewer false alarms. Note 40bp was fit to
the April observation; moving to 50bp moves away from the fit.

## Exp 13-14 — profit-take +-20% (24%, 36%)

Take 24%: perp IS +24.4%, OOS 0.0%. Take 36%: perp IS +33.7%, OOS 0.0%.
Stocks identical. OOS is flat regardless (no OOS longs); IS rises with a
farther target (rides the 2025 rally longer). Chose 30% as the round
middle, explicitly not the IS maximizer.

## Exp 15-16 — stop +-20% (12%, 18%)

No change (stop never binds on the winning leg; it is insurance for a
Feb-2026-type failure, where it did fire in Exp 4). Kept at round 15%.

## Exp 17-18 — name drawdown 15% / 8%

No change (59 trades, identical). The filter never binds: every picked
name had already fallen 15%+ on bottom days. Fixed at 10%, outside the
budget.

## Exp 19 — lighter caution (adds paused, 27.5% cash)

IS 14.2% / -17.8% / 0.63, stitch 16.1% / -17.8% / 0.79. Worse on both
lenses under honest execution. Band confirmed again. Rejected.

## Exp 20 — puts on as insurance

Put sleeve IS -3.8%, tune-OOS 0.0%; stock path unchanged. Cost with no
demonstrated drawdown protection (puts are a separate sleeve; stock DD
-16.8% either way). Puts stay OFF. Revisit only if a crash-month payoff
appears.

## Exp 21-22 — v6 breadth confirm (fixed 4-of-7 majority)

v6 base: IS 16.9% / -16.8% / 0.81, stitch 24.0% / -16.8% / 1.16, 66
trades. v6 cred50: IS 16.9% / -16.8% / 0.81, stitch 25.2% / -16.8% / 1.20,
50 trades. Breadth refines bottom timing (3 April bottom days, not 7) and
helps 2026-Q1 (0.53 vs 0.29). Multi-episode contribution (Q1-26, Q2-26),
not just April (April itself is slightly worse than v5).

## Exp 23-25 — combo VIX level 20 / 30 (cash-raising)

VIX20: IS 13.4% / -16.8% / 0.63, stitch 19.1% / -16.8% / 0.96; perp IS
falls to +14.2% (different warning exits). Rejected: more false alarms.
VIX30: stitch 1.15, same as VIX25 here (non-binding upward). VIX30+cred50:
same. Keep round 25 (IS-best, robust upward).

## Exp 26-28 — cash levels (risk-on 30/25, holding target 30)

risk-on 30%: stitch 1.19, DD -18.7%. risk-on 25%: stitch 1.20, DD -19.3%.
More beta helps Sharpe but pushes DD toward EqW. Holding target 30%
(deploy more fully in episodes): IS 19.5% / -16.8% / 0.93, stitch 27.0% /
-16.8% / 1.24 (v6+cred50). DD unchanged — the DD anchor is Q1, before any
redeploy. Holding-target ladder is monotonic in beta; 30% taken as the
middle (status quo 35, aggressive 25), coherent with the 3-tranche design
(keeps dry powder for a second leg that never came in-window — stated
risk).

## Exp 29-31 — v6 edges (gate14, cred60, VIX30-combo)

v6 gate14: IS collapses to 0.49, 77 trades — breadth x gate14 leaves ZERO
April bottom days (census: v5-g12 7 days, v5-g14 1 day, v6-g12 3 days,
v6-g14 0 days). Fragility flag, see Exp 34/37. v6 cred60: IS 0.93, stitch
1.29. v6 VIX30-combo: stitch 1.35. Both are further beta steps up the same
ladder; not pursued (STOP: no more beta climbing).

## Exp 32 — v5 + cred50 + hold30 without BTC exits (stop 8% default)

IS 0.95, stitch 1.17. Shows the stock leg stands without the BTC exits;
exits only fix the derivatives sleeve.

## Exp 33-35 — final-assembly sensitivity (v5 chassis)

Gate 14: IS 0.62, stitch 1.12 — degrades gracefully (1 April bottom day),
still functional. Cred 40: IS 0.95, stitch 1.13 (vs 1.17 at 50bp).
Hold 25: IS 1.05, stitch 1.19 — the ladder top, declined (see Exp 26-28).

## Exp 36-42 — clean sensitivity grid (explicit versions)

| Cell | IS Sharpe | Stitch Sharpe | DD | Trades |
|---|---|---|---|---|
| v5 base (12, 50bp, hold30) | 0.947 | 1.170 | -16.8% | 49 |
| v5 gate 10 | 0.769 | 1.040 | -18.1% | 45 |
| v5 gate 14 | 0.622 | 1.120 | -16.8% | 45 |
| v5 cred 40 | 0.947 | 1.126 | -16.8% | 59 |
| v5 cred 60 | 0.946 | 1.227 | -16.8% | 51 |
| v5 hold 25 | 1.050 | 1.185 | -16.8% | 49 |
| v5 hold 35 | 0.834 | 1.150 | -16.8% | 49 |
| v5 VIXcombo 20 | 0.916 | 1.106 | -16.8% | 48 |
| v5 VIXcombo 30 | 0.947 | 1.170 | -16.8% | 49 |
| v6 base (FINAL) | 0.928 | 1.241 | -16.8% | 50 |
| v6 gate 14 | 0.495 | 1.103 | -16.8% | 77 |
| EqW rf-adjusted | 0.834 | 1.055 | -28.3% | — |

Reading: the gate is the most tuned-feeling param (IS peaks at 12: the
March-fade/April-low separator; stitch is forgiving). Credit and hold are
beta ladders — middles taken. VIXcombo robust upward, worse downward.
Breadth helps the headline (+0.07 stitch) at tiny IS cost but is fragile
at gate 14 (kept, flagged). DD -16.8% in every cell: the robust half of
the edge (cash + trims-on-strength), structurally present, never tuned.

## April 2025 removed

Stitched Sharpe without April 2025 (raw convention): v4 1.55, v5-base
1.55, v6-cred50 1.63, FINAL (v6+hold30) 1.65, EqW 1.44, SPY 1.55. The edge
does not come from April alone; ex-April the strategy matches SPY and
beats EqW on Sharpe with a smaller DD (-11.7% vs -19.7%).

## Deflated Sharpe (K = 43 logged runs)

v6 FINAL stitched rf-adjusted Sharpe 1.241 on ~415 tuning-universe
returns: data-mining benchmark 1.73, DSR ~0.00. After 43 trials the
Sharpe edge over zero is not statistically distinguishable from mining
luck. The DSR tests Sharpe-vs-zero, not strategy-vs-EqW; the EqW
head-to-head (like-for-like Sharpe 1.24 vs 1.06, DD -16.8% vs -28.3%,
smaller DD in all 7 quarters) is the decision basis, taken with eyes
open. The statistically robust claim is the drawdown edge, present in
every variant without tuning.

## Frozen rule (FINAL = v6)

v6 + VIX >= 25 and HY widening >= 50bp/20d to raise cash; VIX fade off a
25+ spike with SPY >= 12% under its 60d high plus 4-of-7 breadth for
bottoms; 3 tranches into fell-most quality/high-beta rebounders, holding
target 30% cash; BTC longs only at bottoms with 15% stop / 30% target;
puts off. Six tuned params: 25, 50bp, 12%, 30%, 15%, 30%.
