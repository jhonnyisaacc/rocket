# Futures component ledger

Component states concern incremental value in the current architecture. Historical failures of a whole strategy do not automatically reject a component.

| Component | Role | Status | Evidence / next discriminating test |
| --- | --- | --- | --- |
| Multi-horizon time-series trend | Continuous directional forecast | `UNTESTED` | Active frontier; compare with zero forecast and simple single-horizon controls under the same PIT tape and costs. |
| Realized/EWMA volatility | Forecast normalization and separate risk size | `UNTESTED` | Begin with simple estimators; test forecast normalization separately from risk scaling. |
| Point-in-time universe | Eligibility | `OPEN_DATA_GATE` | Inventory historic listings, first/last actual bars, gaps and delistings; current metadata cannot define old membership. |
| Relative strength | Ranker | `UNTESTED_AS_INCREMENT` | Standalone quintiles failed in PR #31; after a viable base forecast, compare candidate selection with and without ranking. |
| Funding, OI, basis, crowding | Derivatives context | `UNTESTED` | Require timestamped history; condition an already defined signal, measure incremental OOS value. No sign-only funding rule. |
| COT | Context or possible regime feature | `UNTESTED_AS_INCREMENT` | Compare base against base plus causal COT state, with availability and release-time audit; do not make it a mandatory entry gate by default. |
| Staged `ZONE` | State / possible timing | `REJECTED_AS_DIRECT_ENTRY` | Direct entry lost in PR #31. Only test as an incremental feature after a base signal. |
| Pullback / retracement depth | Entry timing | `UNTESTED_AS_INCREMENT` | Full Pana stack had no primary sample. Compare immediate entry against pullback on the same eligible signal. |
| 4h reaction | Entry timing | `UNTESTED_AS_INCREMENT` | Embedded in near-empty stack in PR #28; compare base + pullback against base + pullback + reaction. |
| Sweep / break / retest / hourly flip | Entry timing | `UNTESTED_AS_INCREMENT` | Preserve each step's sample and incremental effect; do not reinstate the entire AND-chain. |
| Correlation breadth / risk target / buffering | Portfolio construction | `UNTESTED` | Only after a signal survives; measure risk and turnover separately from signal expectancy. |
