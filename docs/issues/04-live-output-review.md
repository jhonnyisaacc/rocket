# Live output review — filters, display, and polish

Status: open tracking issue. Human reviews each live output. Agent uses this issue as the work list for display/filter polish. Not a second engine. Not a VALIDATED claim.

Capture: `2026-09-07T17:35:46Z` on `main` @ `2eaa8e9`.
Commands: `rocket macro`, `rocket crypto scan`, `rocket shorts`, `rocket disclosures`, `rocket ism`.
Secrets were not copied into this issue.

Related: #1 options (primitives only), #2 memecoin (NO EDGE VALIDATED), #3 crypto strategy polish (edge still unproven).

---

## Mental model (how we use Rocket)

```
any bot / agent / human
    → rocket <workflow> --json
    → ResearchResult { operational, research, funnel/filters, candidates, warnings }
    → adapter presents
    → human decides
```

Hard rules the output must keep visible:

- Operational health ≠ research conclusion. `HEALTHY` + `NO_SETUP` is a valid empty tape. `UNAVAILABLE` cannot claim `NO_SETUP`.
- Missing stays UNKNOWN. Do not impute.
- `execution_enabled` is always false. Human-gated.
- Evaluate never writes `VALIDATED`.
- JSON is the contract. Markdown (`--human`) is optional presentation.

What each workflow is *for*:

| Workflow | Job | Empty result means |
|---|---|---|
| `macro` | US rates/liquidity context | Context OK; not a trade |
| `crypto scan` | One funnel: top-100 + liquid perps | No setup passed every nested gate |
| `shorts` | Multi-factor short research | Missing required factor or not enough non-macro flags |
| `disclosures` | Official filings + secondary FMP rows | New rows = review, not a buy |
| `ism` | Headline PMI ≠ industry rankings | Publisher miss or unpublished |
| `options` / `memecoin` | Research primitives only | Never schedule as a strategy |

---

## Filters currently applied (what the agent should display)

### Crypto funnel (nested)

`universe ⊇ eligible ⊇ liquid ⊇ momentum/derivatives ⊇ macro ⊇ COT → final`

| Stage | Gate | Current rule |
|---|---|---|
| Universe | CoinGecko top 100 + unmatched HL perps | Identity by canonical id, never ticker-only |
| Eligible | Top-100 **and** unambiguous Hyperliquid perp | Ambiguous tickers stay `UNKNOWN` |
| Liquid | 24h notional ≥ $5M, USD OI ≥ $1M, spread ≤ 20 bps, slippage ≤ 25 bps | Missing spread = `UNKNOWN`, not imputed |
| Momentum | 4h structure: 6-bar HHHL → long, LHLL → short | MIXED / thin history = no setup |
| No-chase | Last close within 2% of **prior** swing | Extended print rejected |
| Derivatives | Same names that passed liquid+setup | Nested with momentum |
| Macro | `current_macro_v1` usable; rates regime vs direction | Neutral allows both; unknown does not pass as a regime |
| COT | BTC+ETH CFTC specs, contrarian, both must agree | Unknown/stale **fails open** (gate not applied) |
| Cava | Overlay only | Missing does not block |

Cap: 25 liquid names get 4h candles per scan.

### Shorts factors

Required to even score: `company_fundamentals`, `technical_breakdown` (must be present, not None).
Counted toward selection: sector weakness, earnings revision, technical breakdown, crowding, **bearish fundamentals**.
Catalyst is optional / UNKNOWN (no catalyst provider).
Valuation support True **rejects** (too cheap to short).
Bearish macro alone cannot select (`non_macro >= 2` and `total >= 3`).
Yahoo quote must be PIT-eligible (`available_at` ≤ decision time, not stale >5d).

### Disclosures

Official House + OGE = filings, not trade rows.
FMP `house-latest` / `senate-latest` = secondary transaction rows.
Dedup by stable id. `NEW_RECORDS` is human review. Never a buy signal.

### Macro

EFFR / TGA / RRP / WALCL. Need a print ≥28 days before latest or factor is `INSUFFICIENT` (no fake 4w change). Freshness windows 5–10 days by series.

### ISM

Headline PMI and industry rankings are separate. Never NMFBAI-as-services-composite. Live path: sitemap roundup → PR Newswire.

---

## Live outputs to review (this capture)

### 1. Macro — `HEALTHY` / `NO_SETUP` / contract OK / regime **neutral**

| Factor | Value | 4w change | Status | Observation |
|---|---:|---:|---|---|
| EFFR | 3.63 | 0.0 | OK | 2026-09-03 |
| WDTGAL (TGA) | 944,364 | +15,039 | OK | 2026-09-02 |
| RRPONTSYD | 0.675 | −0.775 | OK | 2026-09-04 |
| WALCL | 6,737,204 | −11,363 | OK | 2026-09-02 |

Net liquidity (WALCL − TGA − RRP×1000): **5,792,165**.

**Review / polish**

- [ ] Show operational vs research on one line so `NO_SETUP` is not read as “macro broken”.
- [ ] Display 4w direction in words (unchanged / falling / rising) next to the number.
- [ ] Confirm net-liquidity units are labeled (million USD).

### 2. Crypto scan — `HEALTHY` / `NO_SETUP`

Providers: coingecko, hyperliquid, cftc, fred:EFFR/WDTGAL/RRPONTSYD/WALCL — all HEALTHY.
Cava: unavailable (overlay; OK).
COT: **OK, bearish**, as-of 2026-09-01 (CFTC futures-only). Specs net long: BTC +3.57% OI, ETH +6.55% OI. That would only pass **short** setups.

**Funnel**

| Stage | n |
|---|---:|
| Universe | 224 |
| Eligible | 53 |
| Liquid | 29 |
| Momentum | 0 |
| Derivatives | 0 |
| Macro | 0 |
| COT | 0 |
| Final | 0 |

Join: 53 CoinGecko names matched to Hyperliquid; 124 unresolved perps (ticker-only, not eligible). Ranking `ELIGIBLE=53`, `UNKNOWN=47`. Liquidity `PASS=29`, `REJECT=71`.

Setup reasons on the 29 liquid-eligible names:

- `mixed_or_insufficient_structure` = 25 (4h MIXED)
- not candle-scored (cap 25) = 4 (`JUP`, `TRUMP`, `CRV`, `INJ`)

**Liquid names the agent would show (all MIXED / no direction)**

| Symbol | 24h notional | OI USD | spread bps | Structure |
|---|---:|---:|---:|---|
| BTC | 1.55e9 | 2.75e9 | 0.13 | MIXED |
| ETH | 8.36e8 | 2.41e9 | 0.40 | MIXED |
| BNB | 1.94e7 | 5.78e7 | 1.07 | MIXED |
| XRP | 4.28e7 | 2.28e8 | 0.72 | MIXED |
| SOL | 1.46e8 | 6.02e8 | 0.96 | MIXED |
| ZEC | 3.78e8 | 6.74e8 | 1.37 | MIXED |
| HYPE | 3.29e8 | 2.02e9 | 1.82 | MIXED |
| DOGE | 1.47e7 | 7.59e7 | 0.78 | MIXED |
| XMR | 3.06e7 | 8.85e7 | 5.96 | MIXED |
| LINK | 3.30e7 | 8.94e7 | 4.92 | MIXED |
| ADA | 5.15e6 | 3.22e7 | 4.31 | MIXED |
| LTC | 1.47e7 | 2.76e7 | 3.83 | MIXED |
| UNI | 2.71e7 | 6.12e7 | 4.93 | MIXED |
| SUI | 1.33e7 | 3.91e7 | 4.04 | MIXED |
| NEAR | 3.82e7 | 1.40e8 | 4.90 | MIXED |
| TAO | 5.82e7 | 6.26e7 | 5.17 | MIXED |
| ASTER | 1.33e7 | 3.28e7 | 6.43 | MIXED |
| AAVE | 6.38e6 | 7.85e7 | 4.08 | MIXED |
| ONDO | 1.16e7 | 2.86e7 | 4.05 | MIXED |
| DOT | 5.72e6 | 6.42e6 | 9.39 | MIXED |
| WLD | 3.32e7 | 5.66e7 | 2.76 | MIXED |
| PUMP | 1.45e8 | 2.42e8 | 9.08 | MIXED |
| ENA | 2.22e7 | 6.42e7 | 3.36 | MIXED |
| LIT | 3.14e7 | 1.94e8 | 11.00 | MIXED |
| ARB | 4.59e7 | 2.98e7 | 3.03 | MIXED |
| JUP / TRUMP / CRV / INJ | liquid | — | — | not scored (candle cap) |

Final candidates: **[]**. Empty is correct given MIXED 4h and nested gates.

**Review / polish**

- [ ] Display the funnel as a nested drop-off, not a flat JSON blob.
- [ ] Show COT regime + “shorts only / longs only / both / gate not applied” in one line.
- [ ] List liquid names with reject reason (`MIXED`, `extended`, `unscored-cap`) so empty final is explainable.
- [ ] Decide whether the 25-candle cap should prefer rank order (it does) and whether unscored names should say `not_evaluated` instead of the old “does not impute” string.
- [ ] Confirm 6-bar HHHL is the structure we want to keep, or whether a less strict 4h/1d mix belongs in #3.

### 3. Shorts — `HEALTHY` / `INSUFFICIENT_EVIDENCE`

This capture: **all four names rejected `available_after_decision_time`** (Yahoo `available_at` after decision clock). PIT fail-closed. No factor matrix this run.

A prior same-day run (keys on, healthy quotes) had PE from FMP and `company_fundamentals=UNKNOWN` (no EPS growth on this FMP plan):

| Ticker | Tech | Fundamentals | Earnings rev. | Valuation | Macro | Sector | Result |
|---|---|---|---|---|---|---|---|
| AAPL | no | unknown | no | no (PE ~36.5) | neutral | no | insufficient evidence |
| NVDA | no | unknown | no | no (PE ~29) | neutral | no | insufficient evidence |
| TSLA | no | unknown | no | no (PE ~300) | neutral | yes | insufficient evidence |
| JPM | no | unknown | no | no (PE ~15.4) | neutral | no | insufficient evidence |

**Review / polish**

- [ ] Show PIT reject (`available_after_decision_time` / stale) separately from “not enough factors”.
- [ ] Factor matrix: OBSERVED vs UNKNOWN vs failed flag.
- [ ] Label FMP PE even when EPS growth is missing, so “unknown fundamentals” is not read as “FMP down”.
- [ ] Confirm universe `AAPL NVDA TSLA JPM` is the live set we want.

### 4. Disclosures — `HEALTHY` / `INSUFFICIENT_EVIDENCE` / `NEW_RECORDS`

Not a buy signal. `fetched_total=131`, `new_total=131` (fresh state dir).

| Source | Status | Rows in result |
|---|---|---:|
| Official House | OK | 3 |
| Official OGE | OK | 21 |
| FMP secondary | OK (200 fetched, then deduped) | 107 |

Sample secondary (FMP):

| Filer | Asset | Type | Date |
|---|---|---|---|
| Jonathan Jackson | VSAT | Sale | 2026-08-28 |
| Cleo Fields | AAPL | Purchase | 2026-08-13 |
| Michael Rulli | ALL | Sale | 2026-08-12 |
| Michael Rulli | EQIX | Purchase | 2026-08-07 |
| John J. McGuire | AAPL | Sale | 2026-08-18 |
| John McGuire | NVDA | Purchase | 2026-08-18 |
| Kevin Hern | NKE | Sale | 2026-08-13 |
| Kevin Hern | MSFT | Sale | 2026-08-21 |
| Kevin Hern | BA | Sale | 2026-08-13 |
| Kevin Hern | DIS | Sale | 2026-08-10 |

**Review / polish**

- [ ] Split official filings vs secondary transaction rows in the presentation.
- [ ] Dedup display of `John McGuire` / `John J. McGuire` / `Michael Rulli` / `Michael A. Rulli` without merging identities in the engine.
- [ ] Banner: delayed context, independent portfolio evidence required.
- [ ] `NEW_RECORDS` should look like “inbox”, not “error”. Research status `INSUFFICIENT_EVIDENCE` is the contract for “human must look”.

### 5. ISM — live publisher fetch **failed closed**

Sitemap found August 2026 roundup URLs, but HTML month parsed as `Unknown` (would crash `release_identity` if passed through). Workflow then correctly reported both series UNAVAILABLE.

Roundups resolved:

- manufacturing: `.../ism-pmi-reports-roundup-august-2026-manufacturing/`
- services: `.../ism-pmi-reports-roundup-august-2026-services/`

**Review / polish**

- [ ] Parser must not emit `report_month=Unknown`; fail the fetch instead of crashing.
- [ ] Follow PR Newswire from those roundup pages (fixture tests already cover unique-link selection).
- [ ] Display headline PMI and industry lists on separate lines.

### 6. Options / memecoin (no live snapshot this capture)

- `rocket options scan --input-file` still requires a hand-built IV/RV snapshot. No autonomous chain. Keep unschedulable. See #1.
- `rocket memecoin collect --spool --input` appends frames; `evaluate` never VALIDATED. See #2.

**Review / polish**

- [ ] CLI help should say “research primitive / not a live job” in one sentence each.

---

## Agent tasks (what to accomplish from this issue)

Work the checkboxes above. Do not add a second crypto engine. Do not schedule options or memecoin.

Priority for presentation (adapter / `--human` / JSON summary fields):

1. Funnel drop-off + reject reasons for crypto (so empty `final_candidates` is readable).
2. Shorts PIT vs factor-matrix split.
3. Disclosures official vs secondary + “not a buy”.
4. Macro one-liner: HEALTHY / NO_SETUP / regime / net liquidity.
5. ISM: don’t crash on `Unknown` month; then fetch PR Newswire body.

Strategy science (fees, OOS, 4h vs 1d structure, FMP EPS growth) stays on #1 / #2 / #3.

---

## How to re-capture

```bash
set -a && source /path/to/env && set +a   # FRED_API_KEY FMP_API_KEY; do not commit
rocket macro
rocket crypto scan
rocket shorts
rocket disclosures
rocket ism
```

Paste a new capture under a dated heading in this issue when reviewing again. Redact keys.
