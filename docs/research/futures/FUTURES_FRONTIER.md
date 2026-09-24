# Futures frontier

Status: `OPEN`, one active question, 2026-09-24.

**Question:** Does a simple continuous multi-horizon, volatility-normalized time-series trend forecast have robust out-of-sample expectancy across a broad point-in-time crypto-perpetual universe after realistic costs and funding?

Mechanism: trends can persist over several horizons; volatility normalization makes forecast magnitudes and risk comparable without declaring a binary entry on every bar. This is a new mechanism and contract relative to the rejected single 50-close breakout. A continuous forecast and its portfolio translation must each be scored separately.

**Immediate blocking subquestion:** Can the research tape represent historical tradability, delisted contracts, complete candles, funding, and costs well enough to test that claim? [Data readiness](DATA_READINESS.md) records the checks. No new trend PnL has been scored or parameters selected. The first experiment `FUT-001` in the [experiment ledger](EXPERIMENT_LEDGER.md) remains `OPEN_DATA_GATE` until its universe and validation contract are frozen.

Next decision: build and audit a historical USD-M archive inventory and a small raw-data sample. If coverage supports point-in-time membership and funding, freeze `FUT-001` before calculating returns. If it does not, document the specific gap and use a defensible alternative dataset or narrow the question explicitly. Do not fall back to today's Hyperliquid list or a short suffix and call it broad OOS evidence.
