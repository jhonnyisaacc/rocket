# Insufficient-evidence audit (#12)

Baseline: `7b01779` (all workflows, provider implementations, CLI orchestration, PIT,
store and harness inspected). Related issues reviewed: #1–#12; #5/#8/#12 have no
comments at audit time; the repository had no existing PRs. This document supersedes
contradictory status examples in the original design plan. No evidence threshold,
execution permission, human validation gate or caller ownership has been relaxed.

## Contract

JSON schema v2 adds `reasons[] = {code, missing[], retryable}` and `presentation`.
Every IE must name an indispensable missing dimension. Warnings never determine
research status. Codes distinguish caller state, invalid input, required provider
failure, required evidence, corroboration, experimental strategy validation and
expected warm-up. Old schema-v1 IE results decode as `LEGACY_UNCLASSIFIED`; the
engine does not infer a historical cause from warning text. Re-run for classification.

`presentation.silent` means **do not emit an unsolicited market-result notification**.
`diagnostic_only` permits an operator/configuration diagnostic, not a market claim.
An explicitly requested diagnostic or experimental report can always be displayed
as such. `market_result` indicates supported research/context or a human-review
inbox item; it is never a trading permission. Healthy empty watches and first CROSS
baselines are silent. IE and input errors are always diagnostic-only. Macro/ISM
context can be presented even though their research status is `NO_SETUP`.

All entries below have `execution_enabled=false`. Research IE never advances a
research-success cursor. Watch baselines are observations, not research-success
cursors: only accepted fresh quotes can update them. The run journal and Cava retry
attempt counters may persist failures. A retry column means a later bounded retry
can improve the result; it is not a request to retry invalid input indefinitely.

Classification legend: **N** NO_SETUP/nothing requiring research; **C** caller state
missing/invalid; **O** operational failure; **T** true research insufficiency;
**B** implementation deficiency or semantic bug fixed here. `D` presentation is
silent/diagnostic-only; `S` silent success; `R` supported result/human inbox.

## Complete baseline IE branch matrix

Each row identifies a distinct baseline IE condition, including conditional
expressions. “After” is operational/research. Providers and available evidence are
actual paths, not catalog promises. Repeated conditions are separated where their
semantics differ. Retries assume corrected configuration where needed.

| ID / workflow / original condition | Input; providers attempted | Required vs available evidence | Classification and after | Machine reason / warning | Present | State advancement | Retry |
|---|---|---|---|---|---|---|---|
| C1 cava `unavailable()` | RSS HTTP failure; YouTube read (bounded retry on transient errors) | Required valid Atom feed; none | O: UNAVAILABLE/IE | REQUIRED_PROVIDER_UNAVAILABLE: youtube.rss | D | No cursor | Yes |
| C2 cava `parse_rss` exception | Invalid feed/XML; no transcript call | Required video identity/publication; none | O: UNAVAILABLE/IE | REQUIRED_PROVIDER_UNAVAILABLE: valid youtube.rss | D | No cursor | Yes |
| C3 cava transcript exception | Fresh unseen video; RSS then Supadata auto transcript/job polling | RSS available; indispensable transcript unavailable | O: PARTIAL/IE | REQUIRED_PROVIDER_UNAVAILABLE: video transcript | D | Attempts only | Yes after provider/key recovery |
| C4a cava unvalidated overlay: live clocks | Transcript/FRED retrieved after run start | Evidence existed but was made artificially LATE | B: HEALTHY/SETUP_FOUND when all required context passes | No IE; decision clock taken after acquisition | R | Validated context + cursor | Fixed in run |
| C4b cava all detected topics required / substring matches | Transcript mentions gold or incidental `oro`/`tipo`; FRED supported series | Unsupported enrichment or false topic blocked sufficient context | B: HEALTHY/SETUP_FOUND only for explicitly scoped supported indicator context | Excluded commentary topics; forecasts/causes unverified | R | Only fully covered supported context | Fixed in run |
| C4c cava source failure/stale series | Transcript; FRED OpenBB→CSV for supported topics | Transcript available, required indicator missing | O: PARTIAL/IE on failed acquisition; T: HEALTHY/IE for supplied ineligible evidence | REQUIRED_PROVIDER_UNAVAILABLE or CORROBORATION_INSUFFICIENT; missing topics | D | No cursor | Yes |
| C4d cava contradiction, invalid PIT/provenance, no supported topics | Successful acquisition/injected corroboration | Required eligible, noncontradictory supported context absent | T: HEALTHY/IE | CORROBORATION_INSUFFICIENT with missing dimension; unsupported-only commentary is not falsely verified | D | No cursor | Only if new evidence/context |
| C4e cava stale backlog | RSS contains only old/future unseen entries | No video within 3-day overlay horizon | B/N: HEALTHY/NO_SETUP; outside-window count explicit | No research attempted on out-of-window entries | S | No cursor | New eligible video |
| W1 watch only CROSS without prior | Valid watch, fresh quote from Yahoo host fallback or explicit price | Current observation available; expected initial baseline absent | B/N: HEALTHY/NO_SETUP | WARMUP_STATE; per-rule WARMUP | S | Accept baseline only | Next observation |
| W2 watch valid rules but no evaluated quote | Valid caller watch; Yahoo query2→query1 or supplied quote envelope | Required current price missing/stale/late/unproven | O: UNAVAILABLE/IE | REQUIRED_PROVIDER_UNAVAILABLE: quote:ticker | D | No invalid price persisted | Yes |
| W3a watch no valid rules: empty list | Empty caller configuration; no provider attempted | Nothing required | B/N: HEALTHY/NO_SETUP, NOT_APPLICABLE coverage | No warning/error | S | No new baseline | No |
| W3b watch no valid rules: malformed definitions | Missing ticker/condition/threshold/bounds; no provider attempted | Invalid caller configuration, not market evidence | B/C: ERROR/ERROR, INVALID_INPUT coverage | INVALID_INPUT with invalid identifiers | D | No new baseline | Caller repair |
| P1 portfolio no positions | Explicit empty caller portfolio; optional inventory only if requested | Caller positions cannot be inferred from wallet or candidate lists | C: HEALTHY/IE (inventory failure may alter ops) | CALLER_STATE_MISSING: caller portfolio positions | D | Run only; never invent holdings | Caller repair |
| P2 portfolio requested inventory unavailable would otherwise HOLD | Caller portfolio/evidence; requested inventory fetch/address | Requested refreshed quantity unavailable; market evidence retained | O: UNAVAILABLE/IE | REQUIRED_PROVIDER_UNAVAILABLE: requested inventory refresh | D | No caller mutation | Address/provider recovery |
| SH1 shorts required-factor rejection or live outage | Caller replay rows or autonomous Yahoo histories + configured FMP | Required company fundamentals/technical evidence; optional catalyst/revisions/crowding remain UNKNOWN | T: HEALTHY/IE if indispensable factor absent; O: PARTIAL or UNAVAILABLE/IE for provider failures | REQUIRED_EVIDENCE_MISSING or REQUIRED_PROVIDER_UNAVAILABLE; asset/reason/factors and provider attempts | D | Run only | Yes for live provider recovery |
| SH2a shorts no supplied snapshots | Empty replay input (live CLI acquires by default) | Caller PIT snapshots required for replay | C: HEALTHY/IE | CALLER_STATE_MISSING: caller stock snapshots | D | Run only | Caller supply |
| SH2b shorts all snapshots invalid/stale/late | Snapshot dates/provenance fail eligibility | No eligible factor snapshot | T/C: HEALTHY/IE for supplied data; O reflects live attempts | REQUIRED_EVIDENCE_MISSING with rejected asset/reason | D | Run only | New valid data |
| I1 ism no usable headline | Independent publisher manufacturing/services; sitemap→roundup→PR Newswire | Valid current release identity required; headline and rankings independently useful | O/T: UNAVAILABLE/IE only when neither kind supplies usable current content | REQUIRED_PROVIDER_UNAVAILABLE or REQUIRED_EVIDENCE_MISSING with per-kind identity/status | D | Run only | Publication/provider recovery |
| D1 disclosures all sources failed | Official House + OGE; optional configured FMP | No successfully acquired filing coverage | O: UNAVAILABLE/IE | REQUIRED_PROVIDER_UNAVAILABLE with source names/failure kinds | D | No seen cursor | Yes |
| D2 disclosures partial providers + new records | At least one acquired family plus one failed family | Authoritative filing/secondary rows retained in separately labeled families | B: PARTIAL/ACTION_REQUIRED (human inbox, not a trade) | Delayed-context warning; failed source health | R | Only acquired records seen | Retry failed family |
| D3 disclosures healthy + new records | Successful official/secondary reads | Filing evidence sufficient for “new filing”, not an investment conclusion | B: HEALTHY/ACTION_REQUIRED | Independent portfolio evidence still required for investment action | R | New record IDs seen | No |
| CR1a crypto empty candidates + warning | Complete evaluated funnel; optional COT/Cava warning | Required gates evaluated; optional missing overlay irrelevant | B/N: HEALTHY or PARTIAL/NO_SETUP | Optional warnings retained; no IE reason | S | Run only | Optional only |
| CR1b crypto empty candidates + unavailable macro | Candidates pass price/structure gates; macro unavailable | Macro indispensable only to otherwise eligible candidates | T/O: IE with truthful provider ops; NO_SETUP if an earlier deterministic gate already rejects all | REQUIRED_EVIDENCE_MISSING: current macro context | D/S | Run only | Yes |
| CR1c crypto invalid observations | Missing identity/clocks, incomplete per-instrument data | Required eligible universe/features unavailable | T/O: IE unless supported candidates remain; partial coverage retained | REQUIRED_EVIDENCE_MISSING with funnel gap counts | D/R | Run only | Valid observations |
| CR2 crypto aggregate provider unavailable | All required source data unavailable | No trustworthy current universe/instrument evidence | O: UNAVAILABLE/IE | REQUIRED_PROVIDER_UNAVAILABLE | D | Run only | Yes |
| CR3 crypto discovery early return | CoinGecko fails/empty normalized universe | Required current top-100 universe absent; do not substitute a static list | O: UNAVAILABLE/IE | REQUIRED_PROVIDER_UNAVAILABLE: current top-100 universe | D | Run only | Yes |
| CR4 crypto evaluate always IE | Persisted scan + caller outcomes; no live provider | Descriptive metrics exist; costed OOS strategy validation is absent | T: HEALTHY/IE (experimental primitive limitation explicit) | STRATEGY_UNVALIDATED: costed OOS validation/human review | D | Run only; never VALIDATED | Scientific work, not HTTP retry |
| CR5 crypto missed nonempty | Persisted scan + caller later outcomes | Evidence sufficient for hindsight audit, not a signal | B: HEALTHY/ACTION_REQUIRED for human review | Hindsight warning retained | R | Never feeds original scan | No |
| O1a options scan no/malformed/ineligible inputs | Caller-owned snapshot; no autonomous chain provider | Required IV/RV/defined risk/identity/PIT missing | C/T: HEALTHY/IE | CALLER_STATE_MISSING or REQUIRED_EVIDENCE_MISSING; rejected dimensions | D | Run only | Caller supplies eligible snapshot |
| O1b options scan eligible snapshots | Valid supplied volatility snapshot | Volatility observation exists; no validated strategy conclusion implemented | T: HEALTHY/IE; EXPERIMENTAL | STRATEGY_UNVALIDATED; #1 explicitly retains unschedulable primitive | D | Run only | Scientific work |
| O2 options evaluate | Caller outcomes; no provider | Gross metrics do not establish costed OOS edge | T: HEALTHY/IE; GROSS_UNCOSTED | STRATEGY_UNVALIDATED | D | Never VALIDATED | Scientific work |
| M1 memecoin status always IE | No research input required; no provider | Reports known primitive/collector configuration, no edge claim requested | B/N: HEALTHY/NO_SETUP; NO_EDGE_VALIDATED retained | No IE | S | Run only | No |
| M2a memecoin scan empty/invalid | Caller capture-derived snapshots; no network provider | Canonical chain+address/PIT/finite features required | C/T: HEALTHY/IE | CALLER_STATE_MISSING or REQUIRED_EVIDENCE_MISSING; rejected identity/dimensions | D | Run only | Corrected data |
| M2b memecoin scan eligible snapshots | Valid identity and PIT features | Discovery observation exists, strategy edge not validated | T: HEALTHY/IE; NO_EDGE_VALIDATED | STRATEGY_UNVALIDATED | D | Run only | Scientific work |
| M3 memecoin collect always IE | Raw frames→durable spool; no research provider | Durable append receipt fully answers capture request; strategy evidence irrelevant | B/N: HEALTHY/NO_SETUP after append succeeds; NO_EDGE_VALIDATED retained | Storage failures still raise; never acknowledge failed write | S | Durable bytes/receipts only | No after success |
| M4 memecoin evaluate | Persisted scan + outcomes; no provider | Descriptive outcomes not costed prospective edge | T: HEALTHY/IE; NO_EDGE_VALIDATED | STRATEGY_UNVALIDATED | D | Run only; never VALIDATED | Scientific work |

The fixture workflow is the sole additional configurable IE constructor: caller
selects an IE fixture outcome, HEALTHY or injected operational status, with explicit
`REQUIRED_EVIDENCE_MISSING: fixture observation`; no network or state advancement.

## Acquisition and evidence defects fixed

- Live Cava and macro decisions follow acquisition. Explicit injected decision times
  remain fixed and reject future evidence; no availability is clamped backwards.
- FRED falls through from empty/nonnumeric OpenBB output; macro also falls through
  on short history or stale OpenBB observations. A still-short authoritative CSV
  remains insufficient; no four-week zero is imputed.
- Idempotent provider GETs retry transient transport/429/5xx failures once; auth
  errors are not retried. Supadata's existing bounded asynchronous job polling remains.
- Cava processes the full transcript, uses word boundaries, records claim/source
  references, provider health, required indicator topics and excluded commentary.
  Every required supported topic must have fresh eligible provider FACT evidence.
  An optional warning cannot erase complete required context. Missing/invalid transcript content remains a provider failure. No supported topics,
  contradictions or failed required evidence still block the cursor. “Validated”
  here is **supported indicator context**, not verification of forecasts/causation.
- Watch validates before acquisition, normalizes whitespace/case and rejects
  stale/late/unknown-provenance quotes before notifications or baseline persistence.
  Explicit numeric caller prices are labeled CALLER_STATE rather than provider data.
- Portfolio automatically acquires listed quote/history evidence only when the caller
  omits an evidence envelope. Explicit supplied evidence stays offline. The 20-session
  technical rule is recorded. Macro is optional. Dates alone do not establish market
  availability. Fully missing market/technical evidence is typed IE rather than a
  market recommendation. Caller quantity, thesis and position lists are preserved.
- Shorts uses both supported Yahoo hosts, preserves unknown optional factors and
  records acquisition attempts. FMP endpoints fail independently; ratios survive an
  estimates outage. The stable `epsAvg` field is recognized; reported annual EPS
  growth is acquired as a bounded fallback. Different fiscal-period forecasts are
  no longer counted as revisions of one forecast.
- Crypto scans up to the full top-100 set of liquid eligible names instead of quietly
  omitting everything after 25. Candle failures retry once; only closed bars enter
  live setups. Missing candles/unknown liquidity are incomplete evaluations, not
  “mixed structure”. Valid subset candidates survive optional failures. COT is
  optional in both candidate and no-candidate paths. No liquidity/threshold loosening.
- ISM roundup selection is chronological, not lexicographic month order. Unknown,
  stale, future and mismatched release identities cannot become current evidence.
  Missing rankings give partial coverage without invalidating a valid headline.
  A caller NAPM fallback must identify its matching reference month and only fills
  a missing manufacturing headline; it never overwrites valid publisher data.
- Disclosures new-record evidence supports a review inbox, not IE. Fully failed runs
  do not update seen state. Successful capture/status and hindsight-review requests
  no longer inherit unrelated unvalidated-strategy IE.

## Deliberate limits and follow-ups

The available implementations do not support an autonomous options chain or a
validated memecoin strategy. #1/#2 already document those research primitives;
we keep their actual analysis outputs fail-closed, explicitly scientific IE, rather
than pretending a volatility snapshot or hit rate is an edge. No model fills facts.

New narrowly scoped issues:

- [#13](https://github.com/jhonnyisaacc/rocket/issues/13): executable capability
  dispatch and advertised-but-unimplemented Massive/OpenBB CFTC fallbacks. Catalog
  entries now describe only implemented paths. A slot is not an attempted provider.
- [#14](https://github.com/jhonnyisaacc/rocket/issues/14): inventory RPC agreement,
  token-program/parser coverage and zero-balance reconciliation. This is a separate
  inventory integrity project; caller holdings remain authoritative.
- [#15](https://github.com/jhonnyisaacc/rocket/issues/15): exact Cava factual
  claim-to-measure/time-window verification (including reliable gold acquisition).
  Broad FRED topic context must never be described as proof of every video claim.

FMP structured fallback references:
[annual income statement growth](https://site.financialmodelingprep.com/developer/docs/stable/income-statement-growth)
and [financial estimates](https://site.financialmodelingprep.com/developer/docs/stable/financial-estimates).
These describe different kinds of evidence; estimates across fiscal periods are not
historical revisions. This PR does not claim new strategy validation from them.

## Validation

`tests/workflows/test_ie_matrix.py` exercises status, typed missing dimensions,
presentation, required/optional coverage and state effects. Provider regressions in
`tests/providers/test_evidence_acquisition.py` exercise HTTP retries, auth failure,
Yahoo fallback, partial FMP recovery, FRED fallback, full transcript conversion and
advancing live clocks. Existing harness round-trips every result through JSON.

For replay primitives, provider outage/optional-provider/retry dimensions are not
applicable: they must never acquire live context. They instead test malformed,
missing, late and insufficient supplied evidence. For macro there is no caller
setup to validate: the fixed four-series request always requires acquisition. For
ISM rankings alone and headline alone are separate coverage dimensions.

Live validation uses separate `/tmp/rocket-12-validation` state directories. No
production cursor, user watch file, portfolio state or environment is modified.
Provider results and final check counts are recorded below after the final audit.

### Added fail-closed paths discovered by the audit

| Workflow / condition | Classification | Operational / research | Missing evidence and provider attempts | Presentation / state / retry |
|---|---|---|---|---|
| Portfolio supplied positions but every row lacks eligible market/technical evidence | T for supplied incomplete envelope; O for failed acquisition | HEALTHY/IE for offline inputs; PARTIAL or UNAVAILABLE/IE for live attempts | REQUIRED_EVIDENCE_MISSING or REQUIRED_PROVIDER_UNAVAILABLE; per-position gaps, quote/history attempts | Diagnostic-only; no holdings mutation; retry live failures or supply correct envelope |
| Crypto eligible liquid instruments without usable candles or liquidity dimensions | O/T | PARTIAL/IE in live mode without any complete candidate | Candle health and incomplete-evaluation counts; bounded retry before IE | Diagnostic-only; journal only; retry can recover |
| Crypto source universe availability absent/late even though a candidate has valid features | T | HEALTHY/IE for caller replay | REQUIRED_EVIDENCE_MISSING: invalid observation count | Diagnostic-only; cannot promote candidate using an ineligible universe; corrected replay input required |

### Final read-only checks (2026-09-08 UTC)

- Full suite: **208 passed**; `ruff check rocket tests` passes; Python bytecode
  compilation and `git diff --check` pass. No separate type-check configuration or
  type-check command is defined by this repository.
- `rocket macro --json`: **HEALTHY / NO_SETUP**, four eligible FRED series, no warnings.
  The first live run exposed the date-only EFFR boundary bug; the fix and a regression
  prove the fifth calendar day is accepted and the sixth is still stale. Context
  expiry remains six hours, and source availability must precede the decision.
- `rocket shorts --json`: **PARTIAL / IE**. All four stock histories and benchmark/
  sector histories were acquired (64 observations each). No FMP/Massive credential
  is exported in this process; required company fundamentals remain unavailable,
  with `NotConfigured` provider health and asset-specific typed reasons. This is
  not a claim that sufficient fundamentals could not exist elsewhere.
- `rocket cava --json`: **UNAVAILABLE / IE**, YouTube RSS HTTP 404; zero usable feeds,
  `REQUIRED_PROVIDER_UNAVAILABLE`, diagnostic-only and no cursor advancement.
  Separate read-only checks of the same channel's uploads feed also returned 404.
  Supadata key/token is not exported in this process. Today's video could therefore
  **not** be independently fetched/analyzed here; no live Cava success is claimed.
- `rocket ism --json`: **UNAVAILABLE / IE** for both releases, explicit parser/source
  failure health. Read-only inspection encountered an HTTP-200 CAPTCHA page from
  ISM, not a valid release. A later services-roundup read exposed the authoritative
  PR Newswire link, but this does not establish a successful full workflow run.
  The implementation does not bypass access controls or turn a numeric URL slug
  into headline evidence. Publisher-to-official-roundup fallback is fixture-tested.

Live JSON was inspected in `/tmp/rocket-12-validation/{workflow}.json`, with isolated
run journals under that directory. These files contain no production state or keys.
The PR includes the executable fixtures/tests rather than environment-specific run
IDs as golden fixtures. Existing #5 and #8 remain open; no adapter is implemented.
