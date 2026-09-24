# Futures frontier

Status: `OPEN`, one active question, 2026-09-24.

**Question:** Does a simple continuous multi-horizon, volatility-normalized time-series trend forecast have robust out-of-sample expectancy across a broad point-in-time crypto-perpetual universe after realistic costs and funding?

Mechanism: trends can persist over several horizons; volatility normalization makes forecast magnitudes and risk comparable without declaring a binary entry on every bar. This is a new mechanism and contract relative to the rejected single 50-close breakout. A continuous forecast and its portfolio translation must each be scored separately.

**Immediate data subquestion:** Can the research tape represent historical tradability, delisted contracts, complete candles, funding, and costs well enough to test that claim? [Data readiness](DATA_READINESS.md) records the checks. No new trend PnL has been scored. The [FUT-001 contract](experiments/FUT-001.md) and chronological OOS protocol are now frozen before outcomes; row-level acquisition and acceptance remain open.

Next decision: finish the checksum-verified 2022–2025 acquisition, audit bar/funding gaps and historical eligibility, resolve exposed-day data gaps, then run the frozen `FUT-001` cheap gate. If the tape fails acceptance, repair documented source/parser defects or use a defensible alternative; do not move the declared OOS window after seeing outcomes.
