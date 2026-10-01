# Fundamentals coverage and recovery

FMP is primary and Massive is invoked when the required EPS flag is missing.
Observed false flags are data, not missing data. Provider order is configured in
config/providers.toml. Endpoint attempts include ticker, provider, endpoint,
retrieval time, coverage and failure_kind, including attempts from providers whose
rows were rejected. ISM candidate context and operational providers, and shorts
operational providers, retain these diagnostics.

EmptyData means a successful endpoint returned no rows. InsufficientCoverage means
rows could not supply eligible required evidence (for example stale/incomparable
EPS periods). Entitlement means paid-plan access was denied; authentication, rate
limits, transport outages and malformed provider data remain distinct. HTTP-200
error envelopes are classified without retaining their text or credentials.

Validated EPS fields recover together from one source. Observed FMP valuation
fields survive Massive EPS recovery, including valuation_support's existing
shorts veto. field_provenance attributes mixed fields; fundamentals_source names
the EPS source when available. Snapshot availability is retrieval-based and never
claims historical replay availability. Missing values remain UNKNOWN and candidates
remain NEEDS_REVIEW; mixed coverage is PARTIAL rather than a total provider outage.

## Actual VPS limitations, October 1, 2026

FMP provided EPS/P-E for F. CAT's profile worked, while ratios, estimates and income
growth returned Entitlement. CAT, NUE, TXN, UPS and DOW attempted Massive and returned
Entitlement; VLO encountered a Massive rate limit after FMP entitlement failure.
These are observed plan restrictions, not proof that the symbols lack filings.
A later isolated smoke run encountered FMP/Massive RateLimit as well: both ISM
reports were CURRENT with PARTIAL overall health; shorts was PARTIAL with
INSUFFICIENT_EVIDENCE. Successful EPS recovery is fixture-tested, not claimed
for entitlement-blocked live symbols.

Massive's current adapter supplies reported annual diluted EPS growth from fresh,
identified consecutive fiscal years. It does not supply P/E or forecast revisions.
EPS-only recovery can support the unchanged ism_simple EPS gate, but ISM long
ranking still needs observed valuation, otherwise it remains NEEDS_REVIEW.
No paid-plan upgrade or alternative provider is automatically purchased.

[Massive coverage documentation](https://massive.com/knowledge-base/article/what-fields-can-i-expect-from-massives-financials-api)
states that these financials require Stocks Advanced or the Financials and Ratios
Expansion. Setting MASSIVE_API_KEY alone does not establish entitlement.

## VPS verification

```bash
set -a && source /home/david/nave/.env && set +a
/home/david/rocket/.venv/bin/rocket ism --json
/home/david/rocket/.venv/bin/rocket shorts --json
```

Run ISM before shorts; use --state-dir <isolated-directory> for review. Inspect
per-ticker attempts, field provenance, UNKNOWN factors and NEEDS_REVIEW candidates.
Confirm execution_enabled=false. Rocket reads process environment, never dotenv.
