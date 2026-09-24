# FUT-001 settlement sensitivity: provisional discovery observation

Status: `PROVISIONAL_DATA_RECONSTRUCTION`, 2026-09-24. This is **not** the accepted FUT-001 result or its 2025 OOS cheap gate. The 2025 OOS returns were not requested from the scenario scorer.

The frozen [FUT-001 contract](FUT-001.md) produced 384 exposed outcome issues across the primary and control, all involving 70 symbols around contract cessation. The settlement candidate builder associated those 70 symbol/date events with official Binance notice leads and checksum-verified minute trade and index archives. All 70 have an eligible entry on the cessation day and complete funding coverage from that day's open to the assumed settlement cutoff. During the 2023–2024 discovery period, 35 such positions are closed intraday at the candidate settlement price and 35 next-morning orders receive no fill; the unfilled target weight remains cash. Settlement also adds exit turnover under the frozen 20/40bps round-trip cost model. [Binance's delisting rules](https://www.binance.com/en-BH/support/faq/detail/dd60dfbf654d4055aa6b217ea6d5ddba) say automatic settlement incurs the taker fee. The baseline cost scenario covers the modeled exit turnover; actual account-tier fees remain to be checked before acceptance.

| Discovery scenario | 20bps mean daily net | 20bps compounded | 40bps mean daily net | 40bps compounded |
| --- | ---: | ---: | ---: | ---: |
| Multi-horizon, adverse minute range | -0.01334% | -14.02% | -0.02030% | -18.28% |
| Multi-horizon, minute-close average | -0.01332% | -14.01% | -0.02029% | -18.27% |
| Multi-horizon, favorable minute range | -0.01331% | -14.01% | -0.02028% | -18.26% |
| Single 60-day control, minute-close average | -0.01975% | -19.39% | -0.02763% | -23.89% |

The adverse/favorable prices select the mean of each minute's low/high against the position side over the applicable 30- or 60-minute window. These are sensitivity endpoints **conditional** on the minute index OHLC encompassing every second-level observation. Binance specifies an average of second-level index prices, which the public minute archive does not directly provide. Ten of 70 candidate events have positive-volume trade minutes after their assumed cutoff, including one discovery event (OCEANUSDT), and require source investigation. Group notice publication times and affected contracts still need final audit. No statistic above validates a settlement price or licenses the 2025 gate.

Reproduction inputs are kept outside Git under ignored `.rocket/futures_data/`: normalized SQLite SHA-256 `c6017a5a445578af1a36f82d62478f53336f62c8adbc67b24ce2f08a6b49e9ef`, candidate JSON SHA-256 `44b9dce5203fbf4062d1b55400b72cf491028aa6c7701460110ffed6f6207f40`, and discovery scenario report SHA-256 `7e6af3d8cd31d7a320ae6e05c9a0a5e4b56b14bf938d9d9877fd1344f6ce4b0e`. The scenario code refuses to summarize any unresolved exposure. Next, reconcile late trade minutes and notice publication/cutoffs, establish an accepted settlement bound or source, then run the declared 2025 OOS cheap gate. Discovery weakness alone does not replace the frozen OOS decision rule.
