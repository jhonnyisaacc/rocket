# MOM-000: PR #49 / #50 reconciliation

Status: **MOM-000 `STOP_INSUFFICIENT_FEASIBILITY` unchanged; MOM-001 not
admitted; predictive trials 0.** MOM-002 is a separate unscored proposal,
`PENDING_INDEPENDENT_REVIEW`. This audit resolves differences against the
frozen contract, without changing generators, source exclusions, primary
7d horizon, 2S/1S barriers, or global 14d spacing.

## Evidence and replay

Compare #49 at `c8f22be5a7f065382d01d4fa167a0b9eacdb67c3` with #50 at
`b8ddbd0d1f477f82f96b26298885b97b0f95e063`. Both frozen census JSONs are
preserved under [reconciliation](reconciliation/RECONCILIATION.json).
`rocket.momentum.reconcile` reads only the pinned descriptive Muse modules
from Git into an isolated namespace. It hashes their original bytes; it
imports no feature/model/experiment scorer. Its separately named orientation
variant changes only DOWN high/low selection for labels and excursions.
Neither upstream PR nor its original result is edited.

```bash
# Required Git objects: the two commits above. Fetch #50 if absent.
git fetch origin feat/momentum-refactor-muse
python -m rocket.momentum.reconcile .rocket/momentum/raw docs/research/momentum/reconciliation
# Optional comparison against Muse's separately acquired ZIPs:
python -m rocket.momentum.reconcile .rocket/momentum/raw docs/research/momentum/reconciliation --muse-raw /private/tmp/momdata/spot_klines_1h
```

Artifacts:

- [RECONCILIATION.json](reconciliation/RECONCILIATION.json): aggregate checks,
  source taxonomy, per-archive SHA-256, module identities and frozen gate.
- [CANDIDATE_DIFF.json](reconciliation/CANDIDATE_DIFF.json): every one of 354
  timestamps, directions, clocks, spacing flags, sigma, reference, S, primary
  label, normalized resolution time, MFE/MAE and end return, before/after
  orientation repair. Numeric tolerance is absolute/relative 1e-12.
- [DISCREPANT_BARRIER_TRACES.json](reconciliation/DISCREPANT_BARRIER_TRACES.json):
  exact barriers and every touching future hour for all 13 outcome differences.
- [LEG_DIFF.json](reconciliation/LEG_DIFF.json): all156 canonical completed geometries,14 gap-censored states,
  both large-leg sets and Muse's front-loading outputs. These remain descriptive, never features.

All 84 independently acquired Muse ZIPs match the canonical ZIP SHA-256
exactly. Both raw parsers and both 4h aggregators produce identical accepted
OHLC/base-volume arrays. All candidate timestamps, directions, decision
clocks and global spacing flags agree. References agree exactly; maximum
absolute sigma/S differences are 3.47e-18/2.78e-17, floating arithmetic only.
Both have 11,943 eligible decisions. The unchanged Muse descriptive census
reproduces its committed counts, summary metrics, legs and overlap output.

Muse's manifest describes its source fingerprint as normalized closes. Its
script actually hashes sorted first/last 64 CSV characters and truncates the
SHA-256 to 32 hex characters. This audit uses all 84 full ZIP hashes instead.

## Definitive binary labels and the DOWN bug

| Globally spaced population | UP, canonical and Muse | DOWN canonical | DOWN Muse original |
| --- | ---: | ---: | ---: |
| Candidates | 64 | 43 | 43 |
| CONTINUES | 5 | **8** | 7 |
| FAILS | 21 | **21** | 19 |
| TIMEOUT | 34 | **12** | 15 |
| UNKNOWN | 4 | 2 | 2 |

Correct UP favorable/adverse prices are high/low. Correct DOWN prices are
low/high. Muse multiplies log(high/reference) by -1 and treats it as the
DOWN favorable maximum, while log(low/reference) becomes its adverse minimum.
That selects the opposite extrema, missing narrow favorable/adverse touches
and delaying other resolutions. On all 354 crossings this changes **13
outcomes and 68 resolution timestamps**. It also changes excursions; the
original differences are 137 MFE and 123 MAE values (and their normalized
counterparts). Signed terminal returns agree at comparison tolerance.

After orientation repair, every label and resolution time agrees. Twelve
MFE values still differ (nine UP, three DOWN): Muse permits negative MFE when
the entire future window is adverse. Canonical MFE includes the zero initial
excursion, `max(0, max(favorable))`. With that explicit floor, all compared
fields agree within tolerance. This convention affects excursion summaries,
not barrier outcomes or STOP. Muse records resolution at the hour's **open**;
canonical records its **end**. The diff adds one hour to Muse's timestamp
before comparing, while retaining the original open separately. Neither
claims to know an exact intrahour touch time.

Only three outcome disagreements occur in the original spaced set:

| Candidate cutoff UTC (decision is +5m) | Reference | S | Favorable price | Adverse price | First touching hour UTC | Canonical / Muse |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| 2022-08-04 20:00 | 22,451.24 | 0.09578746344891544 | 18,537.040501 | 24,708.153984 | Aug 11 07:00–08:00, high 24,745, low 24,355.78 | FAILS / TIMEOUT |
| 2023-08-01 04:00 | 28,835 | 0.038696675234963916 | 26,687.534310 | 29,972.689058 | Aug 2 01:00–02:00, high 30,047.50, low 29,791.46 | FAILS / TIMEOUT |
| **2025-11-13 20:00** | **98,682.14** | **0.06343520457967326** | **86,923.947400** | **105,144.877229** | **Nov 20 17:00–18:00**, high **88,158.49**, low **86,395.47** | **CONTINUES_DOWN / TIMEOUT** |

The last row is the eighth DOWN success. Its low is below the favorable
barrier while its high remains above that favorable level and well below the
adverse barrier. Correct favorable excursion is 0.13296873380470142 >=
2S=0.12687040915934652; adverse excursion is +0.11276776037589006, far from
-S. No earlier hour hits either canonical barrier. Resolution is therefore
CONTINUES_DOWN at the Nov 20 18:00 hourly end. Muse requires the whole hourly
high to fall through the favorable threshold and misses this narrow touch.
No cleaning difference explains any of these candidates.

The label fingerprint stays
`cea8f41de55a5b65c432120db79aa58e2da06c8df7452741a9f8dca55802fbfb`.
`EVENTS.json` and `EPISODES_DIAGNOSTIC.json` remain byte-identical to frozen
#49. Only explanatory census metadata gains explicit interval horizons.

## Source taxonomy and actual anomalies

| Concept | Exact meaning / count |
| --- | --- |
| Received vendor row | CSV row actually present: **61,309** |
| Expected hour | Calendar slot Jan 2019–Dec 2025: **61,368** |
| Missing vendor hour | No row in any received ZIP: **59** |
| Quarantined row | Present row excluded by frozen close-time rule: **9** |
| Unusable expected hour | Missing or quarantined, disjoint categories: **68** |
| Malformed columns/numerics/OHLC | No such rows in these accepted/rejected raw arrays: **0** |
| Invalid timestamp | One close precedes its own open; all opens have correct units/alignment |
| Duplicate | Repeated spot hourly open: **0** |
| Incomplete 4h aggregation | At least one unusable constituent hour: **35** of 15,342 expected groups |
| UNKNOWN decision due to a gap | **3,219** scheduled cutoffs including 35 absent aggregates; **3,184** on existing 4h bars |
| Initial insufficient history | First **180** cutoffs; separate from gap-induced UNKNOWN |
| Eligible decision | Complete contiguous 181 closes and finite positive sigma: **11,943** |

The previous prose singled out one anomaly and called the broader 68 hours
missing/rejected; the manifest already recorded **all nine**. Neither code
silently rejected 68 vendor rows. Also, the old prose UTC conversion for
1559941200000 was wrong: it is **2019-06-07 21:00 UTC**, not June 8 05:00.
That documentation correction changes no source timestamp or outcome.

| Open UTC | Base volume | Vendor close minus ideal end-1ms |
| --- | ---: | ---: |
| 2019-06-07 21:00 | 0 | -2,806,475ms |
| 2020-02-19 11:00 | 405.969511 | -1,467,713ms |
| 2020-03-04 09:00 | 254.392569 | -2,293,305ms |
| 2020-12-21 14:00 | 0 | -4,359,478ms; close precedes open |
| 2021-02-11 03:00 | 0 | -1,145,226ms |
| 2021-04-25 04:00 | 5.887034 | -3,541,853ms |
| 2021-08-13 01:00 | 1,980.126619 | **-999ms** |
| 2021-12-24 04:00 | 560.592590 | **-5,637ms** |
| 2023-03-24 12:00 | 0 | -1,218,353ms |

[Binance's archive documentation](https://github.com/binance/binance-public-data/blob/master/README.md)
shows the end-minus-one-unit convention and explicitly permits later archive
corrections. Exact equality is a **frozen source-contract requirement**, not
a necessary theorem of causal availability. In particular, a high-volume
row ending 999ms early is not automatically a price-invalid or future-leaking
row. Open/interval identity and actual receipt can establish causality without
that equality. These ZIPs alone do not establish whether early closes reflect
formatting, a last-trade timestamp, interrupted trading, or incomplete prices.
The close-before-open row is a stronger metadata defect. We make no unproven
outage/maintenance attribution.

The parser remains strict for MOM-000 and the inherited MOM-002 population.
[Separate source-contract v2 proposal](SOURCE_CONTRACT_V2_PROPOSAL.md) explains
an interval-based future correction. It is not activated or replayed here;
no relaxed census replaces the observed result.

## Interval dependence: 128, 117 and 47

Canonical closed intervals are `[decision_time=cutoff+5m, cutoff+horizon]`;
endpoints that actually touch connect transitively. Primary 7d intervals have
**128 components**; maximum-sensitivity 14d intervals have **47**. Muse's
closed `[cutoff, cutoff+7d]` convention has **117**: it additionally connects
11 exact-seven-day boundary contacts. Merely saying "different horizons"
would miss this five-minute convention. At 14d both conventions have 47.
The updated census removes the ambiguous `overlap_components` key in favor
of `overlap_components_7d`, `overlap_components_14d` and its interval convention.
Frozen original JSONs retain their old field names as historical evidence.

Use 7d clusters for primary dependence and 14d clusters for conservative
maximum-horizon inference. The causal global 14d cooldown remains **107**;
it is different from connected components and is an upper bound on distinct
nonoverlapping opportunities, not proof of stochastic independence. Bootstrap
whole components/blocks, keep paired outcomes and temporal/regime dependence
visible, report both geometries and spaced views. None is a true scalar N.

## Canonical front-loading algorithm

The frozen text requires reversal scale frozen **at each extremum**. #49
matches this requirement; #50 does not. Name the canonical diagnostic
`closed-4h-extremum-scale-v1`. Its exact steps are:

1. At each closed 4h bar compute S from its trailing contiguous 180 returns.
   Start at the first valid scale; invalid/gapped windows reset the segment
   and censor the unfinished run rather than bridging a gap. Each invalid
   bar sets both tracked extrema to itself. Recovery retains the last invalid
   extremum until a new low/high replaces it; direction establishment requires
   a valid scale at the establishing extremum, rather than automatic reseeding.
2. While direction is undecided, track running low/high closes. Establish UP
   after a >=1S rise from a valid low, or DOWN after a >=1S fall from a valid
   high. Freeze that extremum as the leg anchor. UP takes precedence only in
   the degenerate dual-condition case; no such conflict is used as a forecast.
3. Every equal/new high in UP or equal/new low in DOWN updates the extremum
   index. Use **that bar's** S as the frozen subsequent reversal threshold,
   including advances smaller than 1S. Never keep a stale peak simply because
   its advance is small.
4. A >=1S opposite close from the extremum completes the leg, ending at the
   extremum's closed-bar time; retain the later reversal-observed time. The
   next leg anchors at the old extremum. Incomplete runs at gaps/final source
   end are censored and not included as completed legs.
5. A completed leg is large only if its signed anchor-to-extremum log move
   is >=2S **at its anchor**. Reversal scale and large-leg scale have different
   identities; neither is recomputed from a later attractive move.
6. First confirmation is the first closed bar after the anchor with >=1
   anchor-S directional advance. Fraction consumed is directional log move
   to that detection close divided by the eventual leg move, clipped [0,1].
   Confirmation +4/8/12h uses the respective following closed bar; beyond
   the endpoint or absent confirmation counts 1 (fully consumed). First
   matching causal candidate is measured separately; missed legs count 1.

There are **156 completed legs**, of which **33 UP / 32 DOWN** meet the
large-leg criterion. The final directional tail and **14 gap-interrupted directional runs** are
censored. Gap-censored runs are excluded without being promoted to large episodes. Median consumed
at first1S/+4h is 35.9%/36.5% UP and 41.3%/42.3% DOWN. These are optimistic
ex-post conditional diagnostics; many legs exceed 7d. They are not evidence
of candidate prediction, and they do not solve the rare-positive gate.

Muse reports 122 legs including a censored tail, 30 UP / 28 DOWN large
completed legs, and +4h consumed medians 28.0%/45.7%. Its implementation seeds
bar zero with sigma from the first 181 closes, compresses history across gaps,
updates extrema only after another entire 1S advance, and updates its scale
only on a completed reversal. It can evaluate delayed fractions after the
endpoint without automatically marking them consumed, and names close prices
with bar-open timestamps. These answer a different algorithm than the frozen
written contract. Preserve their exact arrays in LEG_DIFF as a replication
finding; do not adopt the more attractive UP fraction. No primary binary
labels, success counts or STOP depended on selecting a leg algorithm.

Muse's gate also differs in bookkeeping: it checks spaced count instead of
fully labeled spaced count, year concentration of all candidates instead of
successes, omits a usable-history gate, and does not enforce the canonical
24-month training prefix in its annual success check. Both still stop by a
wide margin; the canonical frozen gate remains authoritative.

## Infrastructure and research boundary

[Tier B audit](TIER_B_SOURCE_AUDIT.md) confirms perp/funding 72/72 months,
metrics 1,948/1,948 file names, and monthly premium-index existence. It records
funding subsecond event offsets and intraday OI duplicates; publication and
revision limitations persist. No Tier B association or prediction was scored.
[CFTC lineage audit](CFTC_LINEAGE_AUDIT.md) confirms FUT-005 used separate
annual ZIPs with conservative release timing. Future live-provider records
now retain actual response receipts and distinguish as-of from availability.
FRED current-reported/PIT metadata is preserved; ALFRED is not rebuilt.

Shadow audits now open SQLite read-only, verify identities/clocks/schema and
source-backed outcome hashes/replay. Six UTC cutoff regressions pass. The
collector's suppression of ACTIVE after an UNKNOWN previous window differed
from the historical reset rule; it now follows the frozen generator. New
records use their new code-tree identity; old forecasts are never rewritten.
The real journal still has two startup forecasts, no mature outcomes, and
its original file hash. ACTIVE automation is verified from its own config,
separately from the journal audit. [Operations](PROSPECTIVE_OPERATIONS.md)
states the coverage and statistical limits.

[MOM-002](MOM_002_PROPOSAL.md) is a frozen reviewable proposal only. Its
continuous target, six features, fixed ridge, matched benchmarks, causal
annual folds/budgets, two cluster bootstraps and all terminal gates await a
reviewer who did not design it. A design-team read-through is not independent
approval. No scorer or fitting was introduced. A failed later authorized
MOM-002 closes this candidate-based BTC line; no rescue successor is admitted.
