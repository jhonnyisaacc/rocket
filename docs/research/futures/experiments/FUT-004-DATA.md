# FUT-004 pre-result data amendment and selected closure gate

Status: `FROZEN_BEFORE_BASIS_OUTCOMES`, 2026-09-24. The [FUT-004 strategy rule and falsifier](FUT-004.md) are unchanged. No basis-ranked future return, side contribution, portfolio PnL, or 2024/2025 factor result has been inspected.

## Why the futures tape changed

The first selected-exposure preflight used the FUT-001 normalized futures database named in the original FUT-004 freeze. It found 46 held missing next opens, 39 rejected entries and two incomplete funding intervals on the 2022–2023 discovery ranks. Many missing opens clustered on February 26, 2022 across unrelated contracts. The already versioned [FUT-002 data tape](FUT-002-DATA.md) had independently repaired **247 active futures daily bars** from checksum-verified daily archives, including the February 26–28 and April 1–2, 2022 gaps. Those source repairs predated FUT-004 and were not selected from its returns. We therefore replace the FUT-001 futures tape, **before any FUT-004 outcome score**, with `fut002.sqlite` at SHA-256 `e42cfcfc5d244293a9a3327a5009c05723c541b1d86ed3a5050a08c7f97e863b`. The separate spot tape remains SHA-256 `32e9f95a3a4a4773faaab4724d06aa66def137dc56457f063de0308c40f65de8`.

The unchanged return-free 30-day dual-market eligibility rule yields a new local daily-list SHA-256 `1da30a992c2fd0778f7ac865f33a775884b1d227db350db7498f019c8d894888`. It adds 2,557 causal eligible symbol-days in 2022 (29,182 instead of 26,625), without changing 2023–2025 counts (31,187; 54,835; 47,069). There are still at least 20 names on every scoreable day. This is a **data-version correction**, not a sign, window, rank or outcome-driven strategy revision. The original source and eligibility hashes remain in the frozen FUT-004 page for audit.

## Selected-exposure preflight

`research/futures/fut004_candidates.py` checked all three frozen input fingerprints, built basis ranks without reading a future return, and saved fixed 2022–2023 weights. The local candidate manifest SHA-256 is `9dc451efc91cca893f45b29791896fc608e9f55e5132692da8409b2927cfe4c2`: 698 ranked days, 60,369 ranked symbol-days, 29,652 selected symbol-days, **seven** held missing next opens, **five** rejected next-day entries, and **two** held incomplete full-day funding windows. The last two are KEEP and ANC; their funding through the earlier automatic-settlement cutoff has been checked separately. The prior unrepaired-tape preflight is retained locally at SHA-256 `70f4145f0aa7f2ab08d87d13d53ed36765135a722c552a2d1c1cc49d8856083e` to explain the source change, not as an alternate strategy trial.

| Held entry day | Symbol | Source status |
| --- | --- | --- |
| 2022-02-15 | KEEPUSDT | Prior FUT-002 notice/minute candidate; funding through cutoff checked |
| 2022-05-12 | LUNAUSDT | Prior FUT-002 candidate; late trade minutes after notice, wider cutoff envelope required |
| 2022-05-13 | ANCUSDT | [Official Binance automatic settlement notice at 04:00 UTC](https://www.binance.com/en/support/announcement/detail/0bfb6cfd10aa4d26926260c0159ef58d); new minute sources |
| 2022-11-14 | FTTUSDT | Prior FUT-002 notice/minute candidate |
| 2022-11-15 | SRMUSDT | Prior FUT-002 notice/minute candidate |
| 2023-05-25 | COCOSUSDT | [Official Binance automatic settlement notice at 09:00 UTC](https://www.binance.com/en/support/announcement/detail/45852dc155b641bc9e1c23bc41d8ded6); new minute sources |
| 2023-11-14 | TOMOUSDT | Prior FUT-001 notice/minute candidate |

The dated ANC and COCOS notice leads are preserved in [`fut004_settlement_notices.json`](../fut004_settlement_notices.json). Their new trade and index minute archives passed source checksums; local probe SHA-256 `117e22ba7ebe20d5c6abaf93031f994638b3f772d4fe47848240037ded5d5fc6`, candidate report SHA-256 `b43c64f2ee77a9e0b70953b2268144a5ef9c9c8fa5e9ec39fcd6cc63835e8313`. At both official cutoffs the last active trade minute did not extend later; complete 60-minute index OHLC windows provide provisional price envelopes. Exact second-level settlement remains unverified.

`research/futures/fut004_event_pack.py` assembled **exactly seven** selected events from the prior and new candidate sources. It verified each price envelope is positive and ordered, each cutoff falls within its held day, and funding cadence covers entry through the cutoff. Local pack SHA-256 `1ff17aa4f3c3ea4f4fc1787764a2684d83ec4326fa8bb2747595c924ff6a75d7`. Its prices are minute-index approximations; LUNA retains the earlier late-trade caveat. The frozen FUT-004 score must include every admitted position, reject the five unavailable next-day entries to cash without redistribution, and report adverse/middle/favorable price and funding scenarios with an extra 5% price stress. If a selected exposure remains outside these bounds, the gross gate is incomplete. No 2024/2025 ranks or outcomes have been formed.
