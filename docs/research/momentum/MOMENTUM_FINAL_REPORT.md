# Momentum foundation: reconciliation and unscored MOM-002 proposal

Repository `jhonnyisaacc/rocket`; branch `feat/momentum-refactor-codex`;
existing draft [PR #49](https://github.com/jhonnyisaacc/rocket/pull/49).
Audited independent [PR #50](https://github.com/jhonnyisaacc/rocket/pull/50)
at `b8ddbd0d1f477f82f96b26298885b97b0f95e063`.

**MOM-000 remains `STOP_INSUFFICIENT_FEASIBILITY`. MOM-001 remains
`NOT_ADMITTED_SAMPLE_GATE_FAILED`. MOM-002 is `PENDING_INDEPENDENT_REVIEW`;
no predictive fitting, scoring, feature/target association or alpha search
was executed. Total new predictive trials: zero.**

The binary rare-event design has too few successful independent BTC episodes
for the planned conditional model. This is an exact research STOP, not
universal evidence against momentum anticipation. The separately requested
continuous experiment is a proposal only and cannot waive that binary gate.

## Canonical result and evidence boundaries

Plan froze at `3272afc`; event/source contract remains unchanged. Historical
BTCUSDT spot archive years are 2019–2025. The original #49 result is retained
at `c8f22be5a7f065382d01d4fa167a0b9eacdb67c3` and copied in the replication
artifacts. The full label fingerprint remains
`cea8f41de55a5b65c432120db79aa58e2da06c8df7452741a9f8dca55802fbfb`.
Original event and large-leg JSONs retain identical bytes. Census explanation
now explicitly names its 7d/14d interval components.

| Population / primary label | UP | DOWN | Total |
| --- | ---: | ---: | ---: |
| Raw crossing events | 219 | 135 | 354 |
| Global 14d-spaced candidates | 64 | 43 | 107 |
| Fully labeled spaced candidates | 60 | 41 | 101 |
| CONTINUES in spaced set | **5** | **8** | **13** |
| FAILS in spaced set | 21 | 21 | 42 |
| TIMEOUT in spaced set | 34 | 12 | 46 |
| UNKNOWN in spaced set | 4 | 2 | 6 |

All crossings have 329 complete primary horizons and 25 incomplete horizons.
No outcome filter replaces the generator or spacing. Source has 61,309
present vendor rows; nine quarantined plus 59 absent expected rows leave
61,300 accepted hours, 15,307 complete 4h aggregates and 11,943 eligible
decisions. There are 128 primary 7d and 47 maximum-horizon 14d components;
none is a proven independent sample size.

The original failed gate requires at least 120 fully labeled spaced
candidates and 40 successes per side; there are 101 and 5/8. No registered
annual fold has ten successes per side. All registered horizon/barrier
sensitivities remain far below 40. Ex-post latency diagnostics cannot repair
these sample gates. Historical data are heavily inspected development data;
2026 is not a pristine holdout because earlier Rocket research exposed it.

Mean signed 7d log return on complete spaced candidates was -0.3507% UP and
-3.2096% DOWN; extra4h delay plus40bp gave -0.5824%/-3.8258%. These census
sanity checks are unchanged, not predictive strategy PnL. The original binary
census sensitivities are retained, not chosen to improve the headline.

## Twenty answers for the next researcher

1. **Why #49 and #50 differed.** Same 84 source ZIP hashes, accepted hourly
   prices, 4h bars, 354 candidate timestamps/directions and 107 spacing
   flags. Muse has a DOWN extrema orientation defect, a negative-MFE
   convention, a bar-open resolution timestamp convention, different
   overlap intervals and an ex-post algorithm that differs from its written
   extrema-scale contract. Full per-candidate evidence is in
   [replication](REPLICATION_REPORT.md) and its deterministic JSON artifacts.

2. **Bugs versus definitions.** DOWN favorable must use LOW and adverse
   HIGH; reversing them is a bug. After orientation correction all labels
   and normalized resolution times agree. MFE floors at zero canonically;
   12 orientation-corrected Muse values remain negative until that floor.
   Open versus end timestamps are explicit reporting conventions. The
   7d/14d and cutoff/decision interval choices explain components. Muse's
   threshold-only extrema updates and stale scale do not match the frozen
   leg description. The favorable-looking Muse UP latency is not adopted.

3. **Definitive counts.** The primary spaced result is **5 UP / 8 DOWN**.
   The eighth DOWN is cutoff **2025-11-13 20:00 UTC**, reference98,682.14,
   S0.06343520457967326. On Nov20 17:00–18:00 the low86,395.47 crosses the
   favorable86,923.9474 barrier; high88,158.49 does not cross adverse105,144.8772.
   Correct resolution is CONTINUES_DOWN at18:00; Muse times out. Two other
   spaced candidates, 2022-08-04 20:00 and 2023-08-01 04:00, fail rather
   than time out. No cleaning difference causes these discrepancies.

4. **MOM-000 preservation.** Generator, UTC4h decisions, S, 7d primary,
   2S/1S barriers, global14d spacing, source vintage/exclusions, labels and
   STOP remain unchanged. Original frozen JSONs are preserved. Removing
   an ambiguous metadata field and correcting prose do not rerun an alpha
   search or consume a predictive trial.

5. **Source anomalies.** Nine quarantined rows are distinct from59 absent
   vendor hours. One close precedes its open; other early closes include a
   1,980BTC bar ending999ms early. Ideal close equality is an explicit
   frozen source rule and a vendor convention, not necessary for causal
   correctness in general. These archives do not prove completeness of
   an anomalous row. Original exclusions stay; the separately named
   [source-v2 proposal](SOURCE_CONTRACT_V2_PROPOSAL.md) is not activated.
   The old prose's June8 timestamp was also an incorrect UTC conversion:
   1559941200000 is June7 21:00. Raw data never changed.

6. **Overlap interpretation.** Canonical `[decision_time, cutoff+horizon]`
   yields128 components at7d and47 at14d. Muse117 at7d uses closed cutoff
   intervals and connects11 exact-seven-day boundary contacts. Use7d
   dependence for the primary and14d as a conservative sensitivity view;
   bootstrap whole clusters and report both with the original107-spaced
   set. Neither components nor spacing supplies a scalar effective N.

7. **Canonical front loading.** `closed-4h-extremum-scale-v1` updates
   every extremum and freezes that bar's S for reversal, anchors large-leg
   scale at the start, requires observed reversal, censors gaps/tail, and
   counts missed/delayed-past-end confirmations fully consumed. It gives
   156 completed legs, 33UP/32DOWN large; +4h median consumed36.5%/42.3%.
   [Exact steps and both arrays](REPLICATION_REPORT.md) are diagnostic only.
   The primary power STOP does not depend on choosing a latency algorithm.

8. **Tier B coverage.** [Independent audit](TIER_B_SOURCE_AUDIT.md) verifies
   all72 perp1h months and72 funding months Jan2020–Dec2025 with SHA-256,
   and catalogs all1,948 daily metrics files Sep2020–Dec2025. Three metrics
   days were inspected; full within-file OI history remains unverified.
   Monthly premiumIndexKlines exists; Muse's blanket absence is incorrect.
   Monthly OI/metrics directories are absent. Funding subsecond offsets,
   intraday OI duplicates, publication assumptions and backfills are
   explicit. No features or models were scored.

9. **CFTC/FUT-005 PIT.** [Exact lineage audit](CFTC_LINEAGE_AUDIT.md) confirms
   FUT-005 bypassed the live provider: six annual ZIPs, independently
   lagged availability, +10calendar-day floor and documented2023 release
   exceptions. All313 dates and six hashes match; no Tuesday→Friday
   lookahead was found. No replay/reopening was warranted. Annual
   current-reported revisions still limit historical PIT. Shared direct/
   OpenBB CFTC now records post-fetch receipt rather than caller decision
   time, retains as-of separately and rejects known late use.

10. **FRED PIT.** The existing correction is preserved: normal FRED CSV/
    OpenBB values are current-reported history, with observation date,
    unknown historical release availability, unknown vintage identity
    and `historical_pit=false`. Retrieval is not original publication.
    No global ALFRED migration is performed.

11. **Prospective status.** [SHADOW_STATUS.json](SHADOW_STATUS.json) records
    two original startup forecasts, zero outcomes, one verified source
    blob and no due scheduled gap at audit time. Both original identities
    and database hash remain unchanged. The separately inspected heartbeat
    is ACTIVE at UTC00/04/08/12/16/20+2m, targeting cutoff+5m. New status
    reads SQLite without mutation, checks schema/clocks/hash identities,
    verifies outcome source blobs and replays separate mature labels.
    Collector ACTIVE-after-UNKNOWN behavior now matches the frozen scan;
    retries preserve originals and missing/late data remain UNKNOWN.
    Sustained scheduling and real mature-outcome validation remain pending.

12. **Why collection cannot quickly solve power.** Historical complete
    spaced successes were roughly0.71UP and1.14DOWN per calendar year.
    At those descriptive frequencies, reaching40 per side prospectively
    would take roughly56/35years from zero, even before lost receipts or
    dependence; rates are not stationary forecasts. Months of active
    logging cannot establish rare-positive inference. It validates causal
    receipts/parity first. No short-horizon statistical success is claimed.

13. **MOM-002 hypothesis.** Given the same exact BTC breakout population,
    do the six fast market features add OOS information about direction-
    aligned magnitude of the next7days beyond Tier A and causal simple
    benchmarks? It is a separately requested continuous-information
    proposal, not an amendment admitting the failed binary classifier.

14. **Continuous outcome.** `direction * log(P_close[t+7d]/P0) / S`, with
    original direction, reference, horizon and S, complete167 future1h
    bars and maturity at least horizon+5m. No barrier-success conditioning,
    winsorization or target/horizon search. A complete intrabar-ambiguous
    binary label can still have an observed continuous target.

15. **Frozen features.** Inherited six: signed24h return/(sigma sqrt6),
    SD6/SD180, relative6-bar volume/prior174-bar volume, signed24h realized
    funding sum,24h contract-OI log change, spot/perp24h quote-volume
    ratio. [Proposal](MOM_002_PROPOSAL.md) fixes clocks, duplicates, missing
    policy and reconstructed availability; no daily-floor/notional OI
    fallback, interactions, proxy or feature search. Review can reject
    a feature only before scoring with an explicit new proposal version.

16. **Frozen model.** One ridge linear regression, common six slopes,
    separate unpenalized direction intercepts, train-only weighted
    normalization and alpha1 on a precisely stated mean-loss objective.
    No hyperparameter/model search. B0 direction means, B1RV, Tier A
    three-feature ridge and unfiltered reference share matched rows/folds.

17. **Frozen inference.** Annual causal OOS2023/2024/2025, expanding mature
    prior training, purge and14d pre-test embargo. Equal primary7d cluster
    weights; paired2,000-draw cluster bootstraps at7d and14d, fixed seed,
    both confidence bounds required. Preserve all354 identities, missing
    reasons and original107-spaced economic view. Causal training quantiles
    and a fixed annual cap prevent future-year score ranking. Report raw,
    component, spaced and scored counts rather than a fake effective N.

18. **Success/failure gates.** Proposal freezes Pearson r>=0.10,
    incremental MSE skill>=5% versus Tier A, positive lower confidence
    bounds under both bootstraps, simple/spaced/fold consistency, fixed-bin
    monotonicity, positive40bp-net selected returns, minimum alert coverage,
    MAE limits, year/component removal and concentration limits. Every
    gate is required; secondary metrics cannot rescue failure. Frequency/
    source readiness is checked before fitting; failure there is blocked
    readiness, not license to weaken inference. Exact thresholds and
    algorithms reside in the reviewable proposal, with no evaluated gates.

19. **Terminal commitment.** If an authorized MOM-002 fails its frozen
    OOS/incremental/economic gates, this candidate-based BTC momentum
    line is closed. No MOM-003, COT, macro, Cava, X/news, Pana, ETH/SOL,
    new generator/horizon, complexity or transformations rescue. This
    closes a specified line for lack of useful evidence, not all possible
    momentum anticipation.

20. **Review status.** `PENDING_INDEPENDENT_REVIEW`. The proposal has not
    been independently approved. A reviewer who did not design it must
    approve/request changes against a named commit before any MOM-002
    fitting, association inspection, forecast or gate evaluation. The
    design team's drafting/read-through is explicitly not that approval.

## Architecture, inherited failures and operational safeguards

The stdlib momentum primitives separate observations/PIT, causal snapshots,
candidates, future labels, census, immutable forecasts and later enrichment.
No execution/signing, live probability or detector trading alert is enabled.
The [evidence audit](EVIDENCE_AUDIT.md) preserves standalone trend/breakout,
COT, Pana, macro portfolio timing, options insurance and derivatives/flow
failures from PRs38/40/46/26 and their antecedents. Conditional roles are not
claimed successful merely because their data exist. Slow context, revised
macro, LLM history and IV remain outside this packet.

Earlier iteration accidentally pushed main because the new branch inherited
main's upstream and repository `push.default=upstream`. Main was immediately
restored with an exact lease and the intended branch/upstream established;
no other changes were removed. This iteration verifies branch/upstream before
push and uses the explicit refspec
`HEAD:refs/heads/feat/momentum-refactor-codex`. Main is never rewritten.

Recommended repository protections: require pull requests and passing CI on
main; prohibit force pushes/deletion; apply protections to administrators;
limit bypass/direct pushes; require review for research contracts and data-
clock changes. A read-only GitHub branch query at this audit reports main `protected=false`
and SHA09d71503906345c194778ecf951dc3a06f2b42cc. Protection settings are
not changed by this PR. Avoid
`push.default=upstream` for research branches; explicit destination remains
mandatory here. Existing draft PR49 is updated; no new PR is opened.

## Validation record

Meaningful regressions cover mirrored UP/DOWN favorable-only/adverse-only/
both/neither OHLC barriers, the exact eighth DOWN touch, all frozen candidate
identities/label hash, 7d boundary separation, extremum-scale updates, six UTC
collector cutoffs, missing slots, original v1/v2 records, retry immutability,
outcome-source replay and CFTC actual receipt clocks. Final verification: **668 offline tests passed, one integration test
excluded**; Ruff and whitespace checks passed. All six reconciliation JSONs
replayed byte-identically. Frozen event/large-leg bytes and the actual shadow
journal hash remain unchanged. Remote CI results are recorded in the PR. No
predictive test or MOM-002 scorer is part of CI.
