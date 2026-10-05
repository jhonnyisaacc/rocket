# Prospective shadow collector service

Purpose: point-in-time/live-replay validation. Healthy collection is an operational service and consumes no research WIP; do not maintain a permanent In Progress research card for it.

> Prospective collection does not solve MOM-000's rare-positive statistical-power problem on a useful short timescale.

Implementation/receipt evidence lives in PR #49, pinned by [evidence index](EVIDENCE_INDEX.md). Initial audit recorded two startup snapshots, no scheduled continuity and no mature real candidate outcomes. That snapshot is historical, not current service health. This governance PR does not start, deploy or change a collector. Use the canonical collector's current read-only status command at its actual journal root after #49 acceptance; do not reconstruct missing forecasts.

Each status receipt must include:

| Field | Required interpretation |
| --- | --- |
| health | HEALTHY / DEGRADED / UNHEALTHY / UNKNOWN with reasons |
| last_expected_cutoff | Latest scheduled closed 4h UTC cutoff due at actual audit clock |
| last_successful_cutoff | Latest actual scheduled receipt meeting source/decision timing; startup captures are separate |
| missing_receipts | Every expected missing cutoff; do not backfill a historical decision |
| unknown_rate | UNKNOWN scheduled records / scheduled records, with numerator/denominator/window; empty window is UNKNOWN |
| source_fingerprint_status | Verify each receipt's content hash, source provenance and parity; distinguish forecast and outcome receipts |
| collector_version | Commit, module-tree digest and schema/generator/model version |
| audited_at / schedule_verified | Actual UTC audit clock and independently read scheduler state |

Expected UTC cutoffs: 00/04/08/12/16/20; scheduled call cutoff+2m, decision cutoff+5m. Prospective forecast records contain causal features/clocks/source hashes and no future label. Mature outcomes live separately with their own timestamps/source receipt and maturity gate. An UNKNOWN stays UNKNOWN; no synthetic historical receipt, vintage or forecast rewrite.

Operational response: on persistent missing receipts, UNKNOWN spikes or fingerprint conflicts, create/reuse a focused Operations issue with the affected cutoffs and source evidence. Deduplicate an existing incident, link it to the Project, record unlock/success/failure/kill conditions, repair only the collector bug, then close after recovered service evidence. Report meaningful changes/failures, stay quiet on healthy unchanged state. Automatic incident creation is optional; this PR supplies the documented status mechanism, not an unverified monitoring deployment.

Source status receipt schema: research/governance/collector_status.schema.json. No historical options/Cava/X warehouse is authorized by this service.
