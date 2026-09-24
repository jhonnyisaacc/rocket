# Positioning-data source scout after FUT-004

Status: `SAMPLE_ONLY`, 2026-09-24. This is a return-free source investigation, not FUT-005 or an open-interest signal. No open-interest change, price-conditioned factor, forecast-times-return, portfolio outcome, or new parameter was selected.

The [Binance USD-M open-interest-statistics API](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest-Statistics) currently documents only the latest **one month** of history. It therefore does not provide Rocket's 2022–2025 historical cross-section by itself. [Bybit's open-interest API](https://bybit-exchange.github.io/docs/v5/market/open-interest) documents daily intervals, a 200-row page limit, and queries back toward each symbol's launch. Its `openInterest` is the **sum of both sides**; for linear USDT contracts the unit is the base asset. It is a participation measure, not a long-minus-short positioning signal. Historical completeness and point-in-time publication delay need direct audit.

`research/futures/bybit_oi_probe.py` requested five fixed one-month windows without computing returns. The ignored raw responses are retained with individual hashes in the local report, SHA-256 `2e1a1a1344075701efa277bfc29735e4c570cae9f0b2e23921395c22aeb0dba4`.

| Symbol | UTC month | Returned daily rows | First–last listed day |
| --- | --- | ---: | --- |
| BTCUSDT | 2022-01 | 31 | Jan 1–31 |
| ETHUSDT | 2022-01 | 31 | Jan 1–31 |
| FTTUSDT | 2022-11 | 30 | Nov 1–30 |
| BTCUSDT | 2024-01 | 31 | Jan 1–31 |
| BTCUSDT | 2025-01 | 31 | Jan 1–31 |

The FTT response reports zero OI from November 14 onward after trading ceased. Those rows cannot be treated as ongoing tradable-contract observations. A separate checksum-equivalent raw-response hash `f32f29e1f63501ec540342ff70c6827a5bb9baa08a7fbcc5cd55ad1f3218a73d` covers a 24-row BTCUSDT hourly OI query on January 1, 2022. Its 00:00 UTC observation exactly matches the daily observation timestamped 00:00 UTC that day. This is one timestamp-semantics check, not proof of when every daily value became available to a trading bot; a conservative later decision lag would be needed.

The five windows establish a feasible older Bybit OI source, including a now-closed symbol, but do not establish a broad historical universe, pagination integrity, absence of revisions, correct post-delisting treatment, or any predictive mechanism. A full source gate would acquire and hash daily OI for the observed active/closed symbol candidates, check continuity and units against price/funding/listing history, and reserve a chronology not already used to select a factor. A distinct positioning hypothesis must explain why a **change in aggregate OI**, in combination with independently defined market information if needed, forecasts directional returns; an OI level alone gives no side. [Research on exchange OI measurement](https://arxiv.org/abs/2310.14973) also motivates cross-checking reported values before interpreting them. Do not invert FUT-004 or fit an OI threshold to inspected 2022–2023 factor returns.
