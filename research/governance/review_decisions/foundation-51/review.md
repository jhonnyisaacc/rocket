# Independent FOUNDATION review of Rocket #51

**Decision: REQUEST_CHANGES. Required #51 scope is not accepted.** Reconciliation of the supplied MOM-000 code and artifacts is supported with explicit source limitations. Overlap documentation needs correction. Tier-B readiness, underlying source authenticity, and historical publication authentication remain **BLOCKED**. `scoring_authorized=false`; `new_real_mom002_outcomes_accessed=false`.

Reviewer: `/root/foundation_51_review`, independent technical/adversarial reviewer. Model family: GPT-6, as identified by the runtime instructions; the exact variant is unavailable. Decision timestamp: `2026-10-05T21:25:30Z`.

## Scope and independence

This was a fresh reviewer subagent with no prior root conversation and no contribution to the experiment design, implementation, reconciliation artifacts, provider corrections, or packet preparation. The reviewer did not delegate, modify the repository, publish a GitHub comment, or approve work on the implementer's behalf. The only authored files are reviewer probes and review records in `/private/tmp`.

Authority reads were restricted to `AGENTS.md` and `docs/research/{RESEARCH_CHARTER,AUTONOMOUS_RESEARCH_PROTOCOL,AGENT_ROLES,TRIAL_LEDGER}.md`. Evidence reads were restricted to the supplied `research/governance/review_packets/foundation-51.json` and the exact `foundation-51.zip`, extracted to a new directory at `/private/tmp/rocket-foundation-51-independent-2br1p126`. No other working-tree research data, raw tape, private database, new MOM-002 outcome, association, fitted prediction, or unrestricted research result was inspected.

This is instruction-scoped fresh-context isolation on a shared filesystem and existing virtual environment, not a hermetic OS boundary. It cannot cryptographically prove that some other actor did not access outcomes. The exact model variant and distinct model family from the preparer cannot be asserted. These limitations are recorded, rather than replaced with invented reviewer identity evidence.

Old MOM-000 labels and descriptive diagnostics were deliberately accessed for the permitted reconciliation. This report is therefore **not** an isolated pre-result MOM-002 admission review. MOM-000 remains `STOP_INSUFFICIENT_FEASIBILITY`; MOM-001 remains unadmitted; this review consumes no predictive trial and grants no MOM-002 admission, freeze, fitting, scoring, or trading permission.

## Exact artifacts

| Artifact | Independently computed SHA-256 |
| --- | --- |
| Outer `foundation-51.json` | `4d2844fbe11d1f774cb47ad885f61c16e218f62507e13248a93fb126bcf7e3e2` |
| `foundation-51.zip` (334,283 bytes) | `98abe6107e8016c34724233aa97a0ac14090907f14fd92473f4d53d4285e7603` |
| Extracted `source_manifest.json` | `ac1ba623d5ee761576e643e53ee999b42f1ac33fcae123b3e664277149509c4e` |

The outer hash and byte count matched before extraction. ZIP member paths were checked for absolute paths and traversal. The bundled `verify_packet.py` verified **42 pinned files**. The reviewed source revision declared for those files is `7c42582168e7538cfac00393bc3ffce54beb21b1`.

The packet separately references historical #49 revision `c8f22be5a7f065382d01d4fa167a0b9eacdb67c3` and #50 revision `b8ddbd0d1f477f82f96b26298885b97b0f95e063`. Those Git objects were not fetched or inspected outside the packet. The review verifies exact packaged bytes; revision binding is the packet's declared identity. The JSON review includes every reviewed source filename, declared revision, and SHA-256, rather than relying on a mutable branch name.

## Decisions by scope

| Scope | Decision | Evidence boundary |
| --- | --- | --- |
| MOM-000 mathematical/artifact reconciliation | APPROVE_WITH_LIMITATIONS | Code and supplied artifacts support the corrected labels and complete accounting. Full raw-source replication and pre-touch absence were not reproduced. |
| Overlap semantics and required documentation | REQUEST_CHANGES | Canonical 128/47 and cutoff-based 117/45 are reproduced; prose incorrectly says both 14-day conventions have 47. |
| Tier-B source inventory | QUALIFIED | Inventory and sample metadata are internally coherent, but the underlying vendor/catalog/sidecar bytes are absent. |
| Tier-B feature readiness | BLOCKED | Only 3 of 1,948 metrics days were content-sampled. Full parser and candidate feature-window evidence is missing. |
| Underlying raw-source authenticity | BLOCKED | A verified review ZIP and internally matching source digests do not authenticate omitted vendor ZIPs. |
| Historical publication/vintage authentication | BLOCKED | Current corrected archives and assumed clocks are explicit; actual historical receipts are null. |
| Authentic publication of this review | NOT_PUBLISHED | Exact local reviewer-authored evidence exists. No GitHub publishing operation was authorized or performed. |

Overall approval requires genuinely supported required scope. A supported subfinding is not full #51 acceptance. A shared GitHub actor can publish this genuine unchanged reviewer record without becoming its scientific author; publication itself would not convert the decision to approval.

## Finding F51-01: incorrect 14-day cutoff-based overlap count

**P2 / REQUEST_CHANGES.** `docs/research/momentum/REPLICATION_REPORT.md:159–162` correctly distinguishes the 7-day boundary conventions but then says, “At 14d both conventions have 47.” The machine artifact at `reconciliation/RECONCILIATION.json:2584–2585` records cutoff-start 14-day components as **45**, and `:2639–2640` records canonical decision-start components as **47**.

The reviewer independently sorted all 354 supplied event geometries and computed the transitive union of closed intervals, separately from `rocket.momentum.core.interval_groups`. The calculations also agree with that bundled helper at `rocket/momentum/core.py:287–294`.

| Interval convention | 7-day components | 14-day components |
| --- | ---: | ---: |
| `[data_cutoff + 5m, data_cutoff + horizon]` | 128 | 47 |
| `[data_cutoff, data_cutoff + horizon]` | 117 | 45 |

Cutoff-start intervals connect 11 exact 7-day boundary contacts and two exact 14-day contacts that are separated by five minutes under the canonical decision-start convention. The two 14-day contacts occur at the later candidate cutoffs:

- `2024-12-05T04:00:00+00:00`, event `94ad996f62acde4733b5b3980db5c087091e8aed0be89c9c746a58ecc1efecc5`.
- `2025-12-15T16:00:00+00:00`, event `1e36c2db5a5734639e2c4c0fa2ccaca5ab25c6907b9c208106f9bc08395d338e`.

The canonical 14-day cooldown is independently reproduced as **107**, using a global greedy first-crossing rule based only on decision times. It is a different geometric quantity from either component count. Neither quantity proves stochastic independence or provides a scalar effective sample size. The report's warnings at `REPLICATION_REPORT.md:167–172` are appropriate.

Required correction: preserve historical packet/source bytes and publish a reviewable exact-artifact erratum distinguishing **128/47 decision-start** from **117/45 cutoff-start**, with the boundary convention and contacts explicit. No population change, label change, rescore, or gate change is necessary. Until that correction is independently verified, overlap documentation is not accepted.

## Finding F51-02: Tier-B feature readiness is not established

**P1 / BLOCKED.** `TIER_B_SOURCE_AUDIT.md:24–33` distinguishes file names from row validity. Only **3 of 1,948** daily metrics files were content-sampled. The first sample contains **576 rows / 288 unique timestamps**, with 288 identical duplicate rows (`:75–81`). The remaining history's gaps, conflicting duplicates, finite values, and complete feature windows remain unverified.

Internal source-manifest checks support the inventory claims, conditionally on the supplied evidence:

| Source | Requested names reported present | Content-verified files reported |
| --- | ---: | ---: |
| Perpetual 1h klines | 72 / 72 | 72 |
| Realized funding | 72 / 72 | 72 |
| Daily metrics / OI | 1,948 / 1,948 | 3 |
| Premium-index 1h klines | 72 / 72 | 2 |

The reported monthly row counts sum to 52,608 perp rows and 6,576 funding events. Funding-offset frequencies sum to 6,576, with 2,882 nonzero offsets, consistent with the audit. The premium category correction is internally supported by the inventory metadata and adds no feature or permission.

These checks do not establish a working Tier-B feature path. `rocket/momentum/core.py:183–226` initializes `funding_24h`, `oi_change_24h`, and `spot_perp_volume_ratio` to `None` and never fills them. The supplied canonical snapshot is spot-only. There is no full candidate-level evidence for causal aligned quote-volume windows, actual funding event-clock eligibility, matched OI endpoints, exact/conflicting duplicate treatment, staleness, or full-window missingness. The audit itself requires later source/parser/window review (`TIER_B_SOURCE_AUDIT.md:104–110`).

Operational receipt correctness in #65 is separate. No current #65 implementation was inspected in this packet, and its correctness would not establish complete Tier-B history or features. The bundled historical CFTC/FRED lineage material is context, not readiness proof.

Required evidence: a separately authorized exact-artifact parser/source/window review with complete feature evidence, explicit source definitions and timestamp units, duplicate/conflict handling, finite-value checks, missingness, and an accepted historical availability policy. Unsupported inputs retain `UNKNOWN`. This reviewer does not grant new data-acquisition infrastructure, inference, or scoring admission.

## Finding F51-03: source authenticity and historical publication are unresolved

**P1 / BLOCKED.** The packet omits the 84 spot vendor ZIPs and Tier-B vendor ZIPs, raw catalog response bytes, and checksum-sidecar bytes. The reviewer verified the preparer's review package and the internal equality of all 84 reported canonical/Muse source digests. That does not independently authenticate vendor-origin source bytes or reproduce the full external raw-source run.

The distinction between current archives and historical availability is correctly disclosed. `MOMENTUM_EVENT_CONTRACT.md:8–15` calls historical spot availability an explicit assumed end+5m clock, and `source.py:53–59` constructs that retrospective clock. `TIER_B_SOURCE_AUDIT.md:85–102` states that corrected vintages, actual historical receipt, and per-row publication are absent. Every Tier-B source records `historical_pit=false` and `actual_historical_receipts=null`. October 2026 audit receipt proves neither original market publication nor original vintage identity.

The audit describes cached external evidence at `TIER_B_SOURCE_AUDIT.md:114–124`, but that cache was outside the allowed evidence boundary and was not inspected. Digest claims and sampled metadata remain qualified. Event times, filename coverage, bucket LastModified, or a current receipt provider fix cannot supply missing historical publication clocks. A reconstruction alternative needs an explicitly declared and independently accepted policy; the reviewer did not select that policy or relax any gate.

Required scope remains blocked pending an authorized isolated review of sufficient authentic source evidence and publication/vintage policy. No receipt is backdated, no event time is promoted to knowledge time, and no historical assumption is silently presented as authenticated PIT.

## Supported reconciliation evidence

The DOWN implementation at `rocket/momentum/core.py:354–385` selects the hourly **low** for favorable DOWN excursion and the **high** for adverse DOWN excursion. UP uses high/low. The fixed scale is the candidate's S. First touches, ambiguous both-barrier bars, full horizon completeness, hourly-end resolution, and zero-floored MFE are consistent with the supplied contract. Bundled mirrored synthetic tests cover both directions, success, adverse touch, ambiguity, timeout, future-bar exclusion, and primary overlap boundaries.

The full independent artifact probe checked all 354 event IDs, chronological timestamps, 4h cutoffs, decision-time lag, directions, label maturity clocks, spacing flags, reference prices, sigma/S values, complete compared label fields, and reported discrepancy lists. The preserved label fingerprint is:

`cea8f41de55a5b65c432120db79aa58e2da06c8df7452741a9f8dca55802fbfb`

| Spaced population | UP canonical/historical | DOWN canonical | DOWN historical |
| --- | ---: | ---: | ---: |
| Candidates | 64 | 43 | 43 |
| CONTINUES | 5 | 8 | 7 |
| FAILS | 21 | 21 | 19 |
| TIMEOUT | 34 | 12 | 15 |
| UNKNOWN | 4 | 2 | 2 |

All supplied canonical label fields match `EVENTS.json`; the fingerprint matches the frozen #49 census and reconciliation manifest. The historical 5/7 result remains preserved in #50. Across all crossings, the independent diff computation gives **13 outcome differences**, **68 normalized hourly-resolution differences**, **137 MFE differences**, and **123 MAE differences**. Orientation-only repair leaves 12 MFE/MFE-normalized differences; applying the explicitly documented zero floor removes all remaining compared differences. Reference prices agree exactly; maximum absolute sigma and S differences are `3.469446951953614e-18` and `2.7755575615628914e-17`.

All 13 supplied discrepant touch traces pass their barrier-price and log-excursion arithmetic, OHLC containment, timestamp/horizon bounds, first-touch label, and hourly-end resolution checks. The eighth DOWN success is specifically reproduced by the bundled synthetic trace test at `tests/momentum/test_reconciliation.py:36–83`. This validates the supplied narrow-touch mechanism. It does **not** independently prove that earlier raw tape bars lacked a touch: the full tape was intentionally unavailable.

Every one of the nine preserved #50 quarantined CSV rows matches the source-manifest exclusion and canonical field-list fingerprint, normalized opening/closing time, OHLC/base volume, and vendor-close delta. The quarantine/missing sets are disjoint. Expanding source gap intervals and independently deriving affected aggregation/history cutoffs yields:

- 61,309 received vendor rows; 61,300 accepted rows; 59 absent calendar slots.
- Nine excluded received rows, including one close-before-open row; 68 unusable expected hours.
- 35 incomplete 4h groups among 15,342 scheduled groups; 15,307 complete groups.
- 11,943 eligible cutoffs; 180 initial-history cutoffs; 3,219 gap-induced unknown cutoffs including absent aggregates, or 3,184 on existing aggregate rows.

The strict exclusions remain the frozen historical population; no tolerance-based parser or alternative census was run. The proposed source-contract v2 remains a proposal. The quoted source-row identities are canonical JSON field fingerprints, as implemented, rather than an unsupported claim of independent raw vendor-byte authentication.

The supplied diagnostic leg tables agree on 156 canonical completed geometries, 14 gap-censored runs, and 65 large completed legs (33 UP / 32 DOWN). Large canonical diagnostics match `EPISODES_DIAGNOSTIC.json`; historical Muse algorithms/results are separately preserved. Code at `census.py:58–199` keeps extrema-scale diagnostic segmentation separate from candidate labels/features. The existing extrema-update regression passes. No more attractive diagnostic replaces the frozen gate.

## Reproducible checks

All commands ran in `/private/tmp/rocket-foundation-51-independent-2br1p126` using the prescribed existing interpreter. No acquisition, export, fitting, historical scorer, or new market-data request was executed. The bundled census tests statically import modules containing dormant acquisition functions; those paths are not invoked by the reviewed tests. FRED HTTP calls use MockTransport or a synthetic fetcher.

```sh
/Users/jhonny/.codex/worktrees/f891/rocket/.venv/bin/python verify_packet.py
```

Output: `VERIFIED 42 pinned files; no acceptance or scoring permission`.

```sh
PYTHONPATH=/private/tmp/rocket-foundation-51-independent-2br1p126 \
  /Users/jhonny/.codex/worktrees/f891/rocket/.venv/bin/python -m pytest \
  tests/momentum/test_core.py tests/momentum/test_census.py \
  tests/momentum/test_reconciliation.py tests/momentum/test_fred_contract.py \
  -o addopts="" -q
```

Output: **25 passed in 0.18s**.

```sh
PYTHONPATH=/private/tmp/rocket-foundation-51-independent-2br1p126 \
  /Users/jhonny/.codex/worktrees/f891/rocket/.venv/bin/python independent_checks.py
```

Output: all final assertions pass; detailed results are preserved at `/private/tmp/rocket-foundation-51-independent-2br1p126/independent_checks_result.json`. The reviewer independently wrote `/private/tmp/rocket-foundation-51-independent-2br1p126/independent_checks.py`. Its results explicitly reproduce the documentation defect and mark raw-source/publication authentication false. During probe construction, discrepancy-list comparison was made order-insensitive because sorted JSON maps alter iteration order; no artifact defect was inferred from that construction issue.

Python is `3.14.1`, Clang 16 build. `rocket.momentum.core.__file__` resolves to the extracted packet. PYTHONPATH points only to the extraction; installed dependencies come from the shared existing virtual environment. No extra environment or package installation was performed.

## Preserved records and limits

The detailed machine record is `/private/tmp/rocket-independent-51-review.json`, created from the bundled `review_decision_template.json`. It includes the complete 42-file source manifest, exact packet/source/probe hashes, actual reviewer identity and contribution disclosure, timestamps, locations, distinct scope decisions, tests, and limitations. This report is `/private/tmp/rocket-independent-51-review.md`.

These records preserve the original review decision of the exact original packet. A later documentation-only erratum would need a separate addendum bound to its exact artifact; it would not retroactively erase this finding or solve Tier-B/source/publication blockers. No human economic/risk values were supplied and no gate, population, trial budget, experiment disposition, or live-execution setting was changed.
