# Winning-case comparison completed

Two bounded public-chain requests around the two observed entries of the largest positive cashflow group, Solana mint `EcPhZph4VXgHW279x5bYX2VjvWBHW5TTQingCAtEpump`. Estimated Helius cost 20 credits, no pagination. Each window spans two seconds before entry through 35 seconds after. Curve window: 34 records, one failed. AMM window: 41 records, four failed. Both known owner buys independently appear in the market captures.

Realized reserve exchange ratios relative to each owner entry:

| Entry venue | First trade at/after +5s | At/after +15s | At/after +30s |
| --- | --- | --- | --- |
| Curve | +6.58% | +20.24–21.06% | +31.74% (first observation at +32s) |
| AMM / wrapped SOL | +1.55% | +10.63% | +15.03% |

The previously sampled losing entry had +0.71%, +3.11%, and +11.66–14.79% observed ratio changes at these delays. Thus a short-term rise after an observed buy occurred in both selected winning and losing cases. It cannot by itself distinguish profitable eventual exits. The winning case shows larger changes already at five seconds, making same-price leader-copy backtests particularly suspect.

These are diagnostics, not returns or executable quotes. Different trade sizes/directions traverse the curve differently; latency here is measured from block timestamps, not when a subscriber could have received a signal. Same-second order is unresolved. The winner was selected after knowing its outcome, so neither comparison is validation or an unbiased predictive test. Entry windows do not cover exits. No migration event or uninterrupted venue transition is asserted.

## Counterfactual experiment specification, version 0 (not yet runnable)

- Keep these already inspected examples as decoder/calibration fixtures, excluded from a claimed unseen test set.
- Use a fixed hypothetical 0.1 SOL quote budget; sensitivity at 0.01 and 0.5 SOL. These are simulation settings, not a recommendation or authority to trade.
- Evaluate receipt-to-submission delay separately from chain timestamp: historical +5/+15/+30 seconds are scenarios, not measured live latency.
- First diagnostic exit: fixed 60 seconds after the hypothetical entry, with the same delay and execution rules applied to sells. No hindsight peak exit or following the leader's future sell unless explicitly tested as a separate rule.
- Require historical reserve/curve state, contemporaneous fee parameters and ordering to compute size-dependent quotes. Apply fees once, price impact, tip/network cost and failure scenarios. Preserve no-quote/illiquid/failed outcomes instead of dropping them.
- Unknown curve virtual reserves, historical fee parameters, ordering or exit state means outcome unavailable—not zero return and not an interpolated executable fill.
- Current captures support ratio diagnostics only. Next acquisition should target state/exit coverage, not collect more entry-price anecdotes.

Artifacts: `winner_entry_curve*`, `winner_entry_amm*`, `winner_entry_delay_probes.json` under `data/helius-pilot-2026-09-16/`. Scripts: `capture_winner_entry_windows.py`, `analyze_winner_entry_windows.py`. NO_EDGE_VALIDATED unchanged.
