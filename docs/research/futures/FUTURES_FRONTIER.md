# Futures frontier

Status: `OPEN`, one active question, 2026-09-24.

**Question:** Can a simple, causal crypto-perpetual trend forecast retain economically useful directional information across independent periods and the intended execution venue after funding and realistic turnover costs?

The frozen [FUT-001 2025 OOS cheap gate](experiments/FUT-001-OOS.md) is the first answer for one portfolio construction: multi-horizon 20/60/120-day trend had a small, uncertain positive arithmetic mean at 20bps, negative compounding, and a negative mean at 40bps across predeclared settlement bounds. It is cost-sensitive and not promoted. The 60-day control's stronger one-year point estimate has a wide interval crossing zero and negative discovery performance; it is not a selected winner. The prior rejected 50-close breakout remains a separate exact contract. No result validates trend broadly or Hyperliquid execution.

**Immediate discriminating question:** Is the weak net result mainly absence of stable gross forecast information, or does turnover/funding/cost consume information that transfers poorly across periods? FUT-001's equal-weight gross predictive statistic was near zero in 2023–2024 discovery and small positive in 2025 OOS, while cost robustness failed. Audit actual settlement and account-tier taker costs, then freeze an independent replication and a single causal portfolio-cost question before inspecting its outcomes. Do not pick the best 2025 side, coin, quarter, or horizon slice as a new signal. The 2026 final holdout stays untouched until a candidate earns promotion.

Next work: preserve the Binance result and raw hashes; verify the remaining historical settlement-price assumption and late-trade discrepancies; secure an independent chronological or Hyperliquid overlap tape with its own point-in-time symbol map, prices, funding and venue costs; freeze the next experiment and falsifier; only then run it. Keep production `rocket crypto scan --json` unchanged while no validated `ENTER_*` contract exists.
