# Fundamentals coverage and recovery

The default dispatch order in `config/providers.toml` is **FMP → SEC EDGAR →
Massive**. FMP and SEC EDGAR are both read when they are in that chain. The gate
EPS prefers GAAP TTM, then GAAP quarterly year-over-year, then the only provider
that returned growth. Massive runs only when neither comparison provider has
eligible EPS. A daily-quota HTTP 429 (including "Limit Reach") opens an in-memory
guard for that FMP client until the next UTC day; the remaining endpoints and
tickers in the scan do not spend requests on an exhausted quota.

`eps_accounting` and `eps_window` name the selected basis. EDGAR us-gaap facts are
`GAAP` with window `TTM` or `QUARTER`. FMP annual `growthEPS` is `UNSPECIFIED` /
`ANNUAL` (not a GAAP tag). The unused forward-estimate mapping is
`FORWARD_ESTIMATE` / `FORWARD`. When both comparison providers return growth,
`eps_provider_disagreement` lists each reading. Opposite signs force the long
gate to `NEEDS_REVIEW` (`EPS providers disagree on sign`). A same-sign absolute
gap of at least 0.25 keeps the preferred basis and sets `reason` to `large_gap`.

Valid FMP valuation fields survive fallback EPS recovery, including the existing
`valuation_support` short veto. `fundamentals_source` names the EPS provider;
`field_provenance` attributes each recovered field, including mixed snapshots.
Diagnostics retain ticker, provider, endpoint, retrieval time, coverage and
`failure_kind`: RateLimit, Entitlement, Empty, NotFound or HardError. Earlier adapter
classifications (such as EmptyData or ExternalOutage) are retained additively as
`original_failure_kind` in merged diagnostics. Credentials and provider error
messages are never retained. Missing values remain null/UNKNOWN; mixed coverage
is PARTIAL rather than a total provider outage.

## Free SEC EDGAR coverage

The adapter uses the official keyless [SEC XBRL APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces):
`https://www.sec.gov/files/company_tickers.json` maps ticker to CIK, and
`https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` supplies facts using
10-digit, zero-padded CIKs. Dot/hyphen ticker spellings are normalized.

Set `ROCKET_SEC_USER_AGENT` to a descriptive project name plus your contact email,
for example `rocket research Your Name you@example.com`. The default identifies
rocket and its public GitHub issue contact URL. SEC may deny access based on the
network or identification; configure your actual contact before VPS verification.
Requests are serialized with at least 350 ms between starts (under three/second),
well below [SEC's ten requests/second limit](https://www.sec.gov/about/developer-resources).
The ticker map, facts and failed responses are cached for one UTC day under
`<research-state-dir>/cache/sec-edgar/`. `--state-dir` selects that directory for
ISM and shorts; otherwise `ROCKET_HOME` / `NAVE_RESEARCH_STATE_DIR` applies.
Cached evidence retains its original retrieval timestamp. Restarting a scan
reuses that day's SEC snapshots; retry a cached failure on the next day or remove
its specific cache file after resolving access.

Supported facts and units:

| Field | Tags / basis | Unit |
| --- | --- | --- |
| EPS | EarningsPerShareDiluted, then EarningsPerShareBasic | USD/shares |
| Revenue | RevenueFromContractWithCustomerExcludingAssessedTax, Revenues, SalesRevenueNet, then RevenuesNetOfInterestExpense | USD |
| Net income | NetIncomeLoss, then ProfitLoss | USD |
| Common shares outstanding | dei:EntityCommonStockSharesOutstanding | shares |
| Trailing P/E | Existing Yahoo price / positive reported TTM EPS | ratio |

`metrics` reports tag, unit, latest quarter, TTM, prior TTM and both TTM and
quarterly YoY growth; EPS also has additive top-level fields. Periods retain filing
date, accession and whether a quarter was derived. The adapter deduplicates each
start/end period using the latest filing visible at observation time, including
amendments. It uses actual fiscal dates rather than the containing filing's `fy`,
`fp` or calendar frame labels. Direct quarterly facts take precedence; cumulative
YTD differences derive missing quarters. Q4 is FY minus nine months, or FY minus
three contiguous quarters if nine-month facts are missing. Non-calendar and
52/53-week fiscal years are supported; gaps and incompatible windows stay UNKNOWN.

TTM prefers reported FY or FY plus current YTD minus comparable prior YTD, with
four contiguous quarters as fallback. Trailing EPS assembled across periods is
an approximation because EPS uses different weighted share counts and rounding.
Latest-quarter evidence must be within 200 days. Growth is `(current-prior) /
abs(prior)`; zero denominators stay UNKNOWN. The gate's EPS growth uses TTM YoY
when available, otherwise same-quarter YoY, with its basis recorded explicitly.

The unchanged `ism_simple` gates remain: ISM contracting, close below the prior
20-session low, and bearish EPS growth. When FMP valuation is missing, EDGAR TTM
EPS plus the already acquired Yahoo price supplies trailing P/E and the same
positive P/E <= 15 valuation-support veto. Its provenance is `sec.edgar+yahoo`.
Nonpositive or unavailable EPS/price leaves valuation UNKNOWN. Instantaneous
shares are reported separately: dividing net income by current common shares
would misstate diluted EPS, especially for multiple share classes.

Limits: this adapter supports US 10-K/10-Q filers and standard USD US-GAAP XBRL
facts only. There are no analyst estimates, forecast revisions or custom issuer
tag inference. Tag variance, changed accounting bases, missing comparatives,
stale tags and incomplete filings can leave individual fields UNKNOWN. JPM's
standard bank revenue tag is supported; unsupported financial-company revenue is
not synthesized from interest components. SEC network restrictions can still
prevent acquisition. Snapshot availability is observation-based and never claims
historical replay availability.

## Actual VPS limitations, October 1, 2026

FMP's daily quota returned HTTP 429 "Limit Reach", leaving NUE, TXN, CAT, DOW,
PEP, F, WMT, GOOGL, UPS and JPM without fundamentals in the observed scan. Massive
financials require [Stocks Advanced or the Financials and Ratios Expansion](https://massive.com/knowledge-base/article/what-fields-can-i-expect-from-massives-financials-api);
setting MASSIVE_API_KEY does not establish entitlement. EDGAR offers a free
recovery path without purchasing a plan. Massive remains the final fallback for
fresh, identified, comparable reported annual diluted EPS; it supplies no P/E or
forecast revisions.

Recorded CAT/JPM/MSFT fixtures test successful EDGAR growth and fiscal periods;
a partial WMT recording tests UNKNOWN comparatives. MockTransport tests cover
FMP 429 → EDGAR, mixed coverage, missing tickers, caching and unchanged gates.
SEC returned HTTP 403 from the development network, so live recovery for all VPS
tickers remains a verification step, not a claimed observed result.

## VPS verification

```bash
cd /home/david/rocket && git fetch && git checkout feat/edgar-fundamentals
set -a && source /home/david/nave/.env && set +a
# Configure ROCKET_SEC_USER_AGENT with your descriptive name and contact email.
/home/david/rocket/.venv/bin/rocket ism --json
/home/david/rocket/.venv/bin/rocket shorts --json
```

Run ISM before shorts to refresh the canonical contracting-industry inputs. With
FMP rate-limited and accessible SEC facts, NUE/TXN/CAT/DOW/PEP/F/WMT/GOOGL/UPS should
show `fundamentals_source: sec.edgar` and non-null EPS growth. This removes missing
fundamentals as the reason for NEEDS_REVIEW; technical, valuation and other
requirements still apply. Inspect JPM's unchanged short gates and valuation veto,
per-ticker attempts, `field_provenance`, UNKNOWN fields and `execution_enabled:
false`. No short selection or long classification is guaranteed by provider
coverage alone. Rocket reads process environment and never loads dotenv itself.
