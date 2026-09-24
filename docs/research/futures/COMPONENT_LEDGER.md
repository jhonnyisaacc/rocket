# Futures component ledger

Component states concern incremental value in the current architecture. Historical failures of a whole strategy do not automatically reject a component.

| Component | Role | Status | Evidence / next discriminating test |
| --- | --- | --- | --- |
| Multi-horizon time-series trend | Continuous directional forecast | `COST_SENSITIVE_NOT_PROMOTED` | [FUT-001 OOS](experiments/FUT-001-OOS.md) found a small positive 20bps mean, negative compounding, and negative 40bps mean across settlement bounds; monthly uncertainty spans zero. No validated directional engine. |
| 60-day time-series control | Selected directional comparator | `REPLICATION_FAILED_2022` | [FUT-002](experiments/FUT-002-RESULT.md) replicated on 2021–2022 with the exact frozen weights and costs. Positive 2021 gross information was concentrated early; 2022 gross was almost flat and net negative under every settlement bound. Do not tune the horizon or side to recover it. |
| Realized/EWMA volatility | Forecast normalization and separate risk size | `TESTED_WITH_WEAK_BASE` | FUT-001 fixed EWMA 0.94 and 5% annual floor. Its net portfolio failed cost robustness; this does not isolate the volatility component. A future ablation needs independent validation. |
| Point-in-time universe | Eligibility | `DATA_AUDIT` | 864 paired USDT archive directories; 635 symbols with 2022–2025 rows and 517 with at least one eligible signal day. The [FUT-002 extension](experiments/FUT-002-DATA.md) adds 2020–2021 coverage and 247 checksum-verified daily repairs. Post-cessation flat bars are ineligible. Exact second-level settlement prices remain unaudited. Current metadata cannot define old membership. |
| Forced settlement | Exit/data handling | `BOUNDED_PROVISIONAL` | Seventy event/date candidates have checksum-verified minute trade/index archives and official notice leads. The [bounded OOS score](experiments/FUT-001-OOS.md) models forced exits and failed next-day orders; ten late-trade cases, exact second-level prices and account-tier fees still need audit. |
| Relative strength | Ranker | `UNTESTED_AS_INCREMENT` | Standalone quintiles failed in PR #31; after a viable base forecast, compare candidate selection with and without ranking. |
| Funding, OI, basis, crowding | Derivatives context | `UNTESTED` | Require timestamped history; condition an already defined signal, measure incremental OOS value. No sign-only funding rule. |
| COT | Context or possible regime feature | `UNTESTED_AS_INCREMENT` | Compare base against base plus causal COT state, with availability and release-time audit; do not make it a mandatory entry gate by default. |
| Staged `ZONE` | State / possible timing | `REJECTED_AS_DIRECT_ENTRY` | Direct entry lost in PR #31. Only test as an incremental feature after a base signal. |
| Pullback / retracement depth | Entry timing | `UNTESTED_AS_INCREMENT` | Full Pana stack had no primary sample. Compare immediate entry against pullback on the same eligible signal. |
| 4h reaction | Entry timing | `UNTESTED_AS_INCREMENT` | Embedded in near-empty stack in PR #28; compare base + pullback against base + pullback + reaction. |
| Sweep / break / retest / hourly flip | Entry timing | `UNTESTED_AS_INCREMENT` | Preserve each step's sample and incremental effect; do not reinstate the entire AND-chain. |
| Correlation breadth / risk target / buffering | Portfolio construction | `UNTESTED` | Only after a signal survives; measure risk and turnover separately from signal expectancy. |
