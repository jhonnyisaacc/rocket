# Staged detector backtest and top-100 universe

Rules were not changed after these counts. This is not the PR #28 7-gate chain, and it is not an entry signal. `execution_enabled` stays false.

## Pytest

Command: `python3 -m pytest -q -m 'not integration'`

`pyproject.toml` already sets `-q`, so this invocation is quiet twice. pytest 9.1.1 printed only the progress bar and exit code 0. No failures. The same suite with the quiet flag removed printed:

```text
====================== 396 passed, 1 deselected in 0.89s =======================
```

The deselected test is the integration smoke test.

## Universe before vs after

Same public sources, no API key: CoinGecko `coins/markets` ordered by `market_cap_desc` (page size 100) and Hyperliquid `metaAndAssetCtxs`. No ranking was invented.

| | Before | After |
|---|---:|---:|
| Top 100 rows | 100 | 100 |
| Mapped to a Hyperliquid perp | 55 exact ticker matches | 57 |
| Candidate rows | 100 (45 were unmapped placeholders) | 57 |
| Extra perps outside the top 100 | 123 universe members | 0 |
| Reported gaps | not separated | 43 `no_hyperliquid_perp` |

The two new maps are venue names, not new tickers: SHIB → `kSHIB`, PEPE → `kPEPE`. That alias is only the unique Hyperliquid 1000-unit `k` prefix. Candle requests now send that venue spelling. `KPEPE` returns HTTP 500; `kPEPE` returns candles.

## Backtest

Detector: `stage_symbol` on `payload.candidates` states only. Completed candles only. At each decision the inputs are the live lookbacks: 14 days of 4h, 120 days of 1d, 210 days of 1w, ending at that decision. No later bar is included.

Grid, chosen before the run: every completed 4h close in the 90 days ending at the run. Bar size 4h. Range of decision closes: 2026-06-25T08:00:00+00:00 through 2026-09-23T04:00:00+00:00. 540 decisions per symbol that had a full series.

Symbol set: the 57 mapped names. Current liquidity (not historical open interest) decides `eligible_liquid`. 36 pass that gate today; the other 21 stay `NO_TRADE` on every bar. COT is `unknown` and does not change the state. The universe is today's top 100, not a historical market-cap vintage. CoinGecko in this repo is live-only.

Six names missed the first candle fetch (`kSHIB` / `kPEPE` because of the uppercase bug, and WLD, VVV, ETC, LIT on a retry). They were staged with the same function and the same grid after the venue-name fix. Thresholds were not edited. Counts below include them.

| State | Rows |
|---|---:|
| NO_BIAS | 8819 |
| BIAS | 22 |
| IN_PLAY | 1043 |
| ZONE | 1284 |
| EXTENDED | 8229 |
| NO_TRADE | 11340 |
| Total | 30737 |

ZONE rows: 1284. IN_PLAY rows: 1043. Symbols with at least one ZONE row: 36. Symbols with at least one IN_PLAY row: 34. Every mapped symbol produced rows. No candle series was left missing after the retry.
