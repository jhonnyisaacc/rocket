# Independent #51 source-cache integrity addendum

**Decision: QUALIFIED_OFFLINE_SOURCE_CACHE_INTEGRITY_VERIFIED.** The existing cache bytes and recorded catalog inventory match the previously reviewed manifest identities. This resolves the avoidable lack-of-cache-access limitation for these bounded checks. It does not authenticate vendor origin, original historical vintages/receipts/publication, reproduce the raw-tape computations, or accept complete Tier-B feature readiness. Overall #51 remains unaccepted.

Reviewer: `/root/foundation_51_review`, independent FOUNDATION technical/adversarial reviewer. Timestamp: `2026-10-05T21:34:28Z`. Known model family: GPT-6 from runtime instructions; exact variant unavailable and distinct family from the preparer not established.

The initial `REQUEST_CHANGES` review and the separate accepted documentation erratum remain unchanged. This record describes a newly authorized evidence boundary; it does not retroactively claim that the original isolated packet contained cache bytes.

## Exact inspected cache scope

The only newly inspected source paths were:

- `/Users/jhonny/.codex/worktrees/9f31/rocket/.rocket/momentum/tier-b-audit/`: the pinned `FULL_CATALOG_MANIFEST.json`, 11 named XML pages, and the exact 149 ZIP/CHECKSUM pairs named by the reviewed Tier-B source manifest.
- `/Users/jhonny/.codex/worktrees/9f31/rocket/.rocket/momentum/raw/`: only the 84 ZIP/CHECKSUM pairs named by the already-reviewed spot source manifest.

No other spot-cache file, receipt JSON, research data, private database, or checkout Git revision was inspected. The path was provided as the pinned historical checkout, but this review binds cache bytes to the reviewed source manifests rather than asserting a separately verified checkout revision. Ignored mutable cache files are not claimed Git-frozen.

Every inspected logical path, resolved path, actual SHA-256, byte count, expected digest and comparison outcome is preserved in `/private/tmp/rocket-independent-51-source-cache-review.json`. It contains the complete **478-file** inspected-cache ledger.

## Byte and sidecar results

| Source/cache type | ZIP files hashed | Matching checksum sidecars |
| --- | ---: | ---: |
| BTCUSDT spot, 2019–2025 | 84 | 84 |
| BTCUSDT perpetual 1h, 2020–2025 | 72 | 72 |
| Realized funding, 2020–2025 | 72 | 72 |
| Daily metrics/OI, original sampled days | 3 | 3 |
| Premium-index 1h, original boundary samples | 2 | 2 |
| Total | **233** | **233** |

All 233 compressed ZIP byte digests match the already-reviewed source-manifest SHA-256 values. Tier-B ZIP byte sizes additionally match both the verified-file metadata and recorded catalog sizes. All 233 plaintext checksum sidecars declare the same digest and correct ZIP basename. Actual sidecar byte hashes are recorded in the ledger; those sidecar raw hashes were not previously pinned by the short source manifest.

ZIP files were streamed as **opaque bytes**. No ZIP parser was imported, member was opened, or spot/perp OHLC array was decoded. No funding/OI feature, target, association, geometry export, forecast, fit, scorer or new real MOM-002 outcome was computed or inspected.

The check hashed **9,663,562 cached bytes** across 478 files: 233 ZIPs, 233 sidecars, 11 catalog XML pages and one full catalog manifest. The Tier-B cache's 310 file names match exactly this expected Tier-B inventory; no additional cache file contents were read.

## Catalog and inventory results

The cached `FULL_CATALOG_MANIFEST.json` raw-byte SHA-256 is:

`f185102753e6134d4231a1b248250a3575e0e0f193e07a96a3632b2804313fb9`

It matches the hash in the previously reviewed Tier-B source manifest. All 11 XML page byte hashes and sizes match their recorded pins. Parsed XML entries and categories reproduce the full manifest, including complete page markers, final `IsTruncated=false`, and the short manifest's summary counts, first/last ZIP keys and LastModified extrema. These checks validate recorded local catalog contents and pagination, without requesting any catalog or source file from the network.

| Recorded catalog source | XML pages | Object entries in complete snapshot | Requested ZIP names verified | Requested sidecar names verified |
| --- | ---: | ---: | ---: | ---: |
| Perpetual 1h | 1 | 162 | 72 | 72 |
| Funding | 1 | 162 | 72 | 72 |
| Daily metrics | 5 | 4,444 | 1,948 | 1,948 |
| Premium-index 1h | 1 | 162 | 72 | 72 |
| Monthly category directory | 1 | 0 objects / 8 category prefixes | — | — |
| Monthly metrics directory | 1 | 0 | — | — |
| Monthly open-interest directory | 1 | 0 | — | — |
| Total | **11** | **4,930** | **2,164** | **2,164** |

Requested names were regenerated from the original declared ranges and checked individually against the parsed recorded catalog. No requested ZIP or CHECKSUM name is missing from that snapshot. Catalog metadata includes later names beyond 2025; they were parsed only for snapshot/pagination consistency. No later ZIP content was read.

The recorded monthly category list includes `premiumIndexKlines`. Empty monthly metrics/openInterest listings remain facts about those recorded catalogs, rather than universal claims about every possible source.

The short reviewed manifest and full catalog agree on all verified ZIP URL, checksum URL, SHA-256, byte size and member identities. The short manifest additionally includes `sample_timestamp_audit` metadata on the three metrics samples. A strict whole-entry comparison initially detected those added metadata keys; the byte/inventory comparison was correctly restricted to source identity fields. Those diagnostics, and the funding exact-grid/nominal-slot row diagnostics, were not revalidated by this hash-only review.

## Distinct scope decisions and remaining blockers

**Verified:** named cache presence, exact pinned ZIP byte identity, local ZIP/sidecar consistency, exact cached XML/full-manifest byte identity, consistent complete recorded pagination, and presence of all requested catalog filenames.

**Not established:** independently authenticated vendor origin or acquisition transport/receipt provenance. A local file, matching local sidecar, and matching pinned catalog digest establish reproducible byte identity relative to the recorded claims. This review inspected no authenticated live retrieval, vendor signature, independent transport receipt or source receipt JSON.

**Blocked:** original historical vintages, actual historical receipt and per-row publication evidence. Current corrected archive identity, catalog LastModified and October 2026 audit metadata do not supply original publication clocks or original-vintage identity. No receipt was backdated, and no event time was promoted to knowledge time.

**Not performed:** full raw-tape computational replication. Opaque ZIP hashes do not independently reproduce the parser/quarantine, accepted/aggregated arrays, candidate generator or barrier labels from those bytes. The bounded instruction explicitly excluded those computations. Original mathematical artifact reconciliation retains its disclosed limits.

**Blocked:** full Tier-B/OI feature-window completeness and readiness. The cache holds the originally sampled three metrics days and two premium months, while all requested names are represented in the catalog. Presence of 1,948 filenames does not validate all 1,948 days' rows. No complete parser/window, finite-value, duplicate/conflict, timestamp-unit, staleness or causal availability review was performed. A current provider receipt correction remains separate from historical feature readiness.

No overall foundation, source/PIT, original-publication, Tier-B readiness, #50 closure, #49 merge, MOM-002 admission/scoring or live-execution authorization is granted.

## Provenance, reproducibility and preserved records

The reviewer did not design or implement the original experiment, acquire/cache these sources, or implement the documentation correction. Prior feedback identifying an overlap prose error was reviewer feedback. This addendum authored only temporary reviewer checks and reports. No repository mutation, GitHub comment, gate change, new data acquisition or network operation occurred.

The checker uses only standard-library hashes, file reads, JSON, XML, date and URL-metadata parsing. It imports no acquisition, fitting, experiment or scorer module. It checks that resolved paths remain under the named cache roots. Its reproducible command is:

```sh
/Users/jhonny/.codex/worktrees/f891/rocket/.venv/bin/python \
  /private/tmp/rocket-independent-51-source-cache-check.py
```

The output is created exclusively. For a repeat, copy the checker into a fresh reviewer temporary location and change only its `OUT` path, preserving the original checker/result. It performs no cache writes.

- Checker: `/private/tmp/rocket-independent-51-source-cache-check.py`, SHA-256 `6d5eb5f89f2ed849be968a7d24bef2a02697b74dd1d24713f675d342f2da119d`.
- Detailed check result: `/private/tmp/rocket-independent-51-source-cache-check-result.json`, SHA-256 `f9a6f4bc723d4005f9f9dc9df315da6907a86d745a021e8f72f5081c888d735d`.
- Reviewed spot source manifest: SHA-256 `7ee9bfb53c30de97e5ed4fd6faf495c9ab14723a833a8465020cd1a3943e068f`.
- Reviewed Tier-B source manifest: SHA-256 `da303d3fd57ad41c84ade21118cbc3f766f11d7cc5d6710d745236a643afa989`.

Before writing this addendum, all four earlier review/erratum files were rehashed and found unchanged:

- Initial JSON: `9116cbf01e5486ab803f2be287edcae5796db2a316cb441413db2f62194c2fd3`.
- Initial Markdown: `90167661448df8d3520db597e5f83534c1ad94fafdbd64867055a2461012e1c3`.
- Erratum JSON: `08adf58d6b8bca9a4e0a24ed4b162a4fa70a610e1ffc5393dc2dc51626a166fe`.
- Erratum Markdown: `24023b0ee256d3a24363bee2b6914fbbcc94d21db45b7c148c9a789ee132b3a6`.

The same fresh reviewer and same-family uncertainty continue. Shared filesystem and installed runtime are instruction-scoped access limits rather than hermetic isolation or cryptographic outcome secrecy. Nothing about the conduct of another actor is proved.

Machine record: `/private/tmp/rocket-independent-51-source-cache-review.json`. Detailed report: `/private/tmp/rocket-independent-51-source-cache-review.md`. `foundation_51_accepted=false`, `source_pit_accepted=false`, `tier_b_readiness_accepted=false`, `scoring_authorized=false`, `new_real_mom002_outcomes_accessed=false`.
