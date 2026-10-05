# Research direction admission v1

Experiment validity and direction validity are independent requirements. The Constitution's frozen definitions, PIT clocks, coverage, costs and untouched validation still apply. Direction control adds **permission to spend another experiment**, never authority to trade.

Canonical memecoin state is [memecoin/RESEARCH_STATE.json](memecoin/RESEARCH_STATE.json). CLI implementation extends `rocket research`; existing research primitives, data contracts and JSON presentation are reused. There was no existing experiment-admission validator. State/checkpoint/review/result schemas are versioned and fail closed in `rocket/research/governance.py`. Unknown domains/families/categories, invalid booleans/budgets, stale previous/economic evidence and missing reviewer inputs block admission.

## Required sequence

1. Prepare a frozen design and `rocket.research-checkpoint.v1`, following [ER-001's checkpoint](memecoin/experiments/ER-001-CHECKPOINT.json). Include proposer, experiment/family, previous result, economic gate, action category, kind, exact new information, decision change, mechanism difference, stop status and operator-review flag.
2. Export the bounded packet: `rocket research review --checkpoint PATH --packet-out /tmp/packet.json`. Without review this deliberately exits 2 / WORKFLOW_BLOCK. The packet contains Constitution, Pillar, Frontier, whole current state, checkpoint, frozen proposal and latest family result. No raw chain archive needed. It includes at most 100k document characters. The emitted `packet_sha256` binds all those inputs and governance implementation fingerprints.
3. Give that packet to an independent human or separately authorized reviewer. Reviewer contract: assess workflow compliance only, never decide profitability. Check stop rule; accumulated disjoint economic failures; genuinely different mechanism; decision value; whether infrastructure is justified by a still-live alpha dependency; required operator review. Return schema below. Reviewer must differ from checkpoint proposer. All checks must be boolean true for WORKFLOW_OK; otherwise WORKFLOW_BLOCK with structured reasons. Never let the proposing agent fill its own approval.
4. `rocket research start ER-001 --checkpoint PATH --independent-review /tmp/review.json`. Start rechecks the current packet, consumes one budget, persists admission and allows one active experiment. Exit 2 blocks; malformed inputs/lock conflicts also block. STARTED does not execute a command. A changed document/checkpoint/state invalidates review.
5. Resolve with `rocket research record-result --result PATH`. Every meaningful result sets REVIEW_REQUIRED, zero budget and operator review required; the emitted block refers to **further continuation**, not failure to save the result. Economic failures/nonrobustness accumulate once per cohort. Dependent results remain in that cohort without increasing independence. CALIBRATION cannot be recorded as an economic success. Inconclusive data does not clear debt. A direction review sets the next explicit budget/status in a reviewed repository state change.

Review example (replace SHA with emitted packet digest):

```json
{
  "schema": "rocket.workflow-review.v1",
  "packet_sha256": "<digest>",
  "reviewer": "independent_operator_or_reviewer",
  "decision": "WORKFLOW_OK",
  "checks": {
    "stop_rule_complies": true,
    "family_evidence_considered": true,
    "mechanism_distinct": true,
    "decision_value": true,
    "infrastructure_justified": true,
    "operator_review_satisfied": true
  },
  "reasons": []
}
```

Post-result example:

```json
{
  "schema": "rocket.direction-result.v1",
  "experiment": "ER-001",
  "economic_test": true,
  "cohort": "ER-001-frozen-temporal-corpus-v1",
  "outcome": "NEGATIVE",
  "evidence": "docs/research/memecoin/experiments/ER-001-RESULT.md"
}
```

## Reopening and failure policy

No universal numeric death threshold. Independent failure count is diagnostic, with independence explicitly scoped by cohort/regime. The reviewed decision must weigh replication, measurement corrections, quoted-only outcomes, mechanism breadth, transfer evidence and whether another test can change the strategy decision. Each result immediately suspends automatic investment so the proposer cannot decide on its own that another unresolved bottleneck deserves more work.

REJECTED and REVIEW_REQUIRED block every start, even with a friendly reviewer. To reopen, record a reviewed state change with positive budget, the allowed category (remove it from forbidden categories) and a family `reopening` object containing `condition`, exact `experiment`, nonempty `evidence` and `operator_authorization`. Conditions are new_independent_data, invalid_prior_test, different_mechanism, transfer_replication or operator_decision. Evidence reopening still requires explicit review of that record; a proposer cannot simply assert a different mechanism. The new family may alternatively be registered by reviewed state change, with inherited failures referenced and causal distinction documented. New names alone confer no permission. Reopening never removes economic history or changes execution restrictions.

These are local reviewable records, **not cryptographically authenticated operator identity**. Repository access/review is the trust boundary. No free-text CLI override exists. An operator authorization must reference an actual human decision or reviewed evidence; Codex must not fabricate it. File edits by a malicious or unrestricted actor cannot be prevented by a local JSON gate.

## Enforcement scope

The CLI start boundary is mandatory for meaningful new work. Python prospective stream/account/buyer collectors require a current STARTED admission via `ROCKET_RESEARCH_EXPERIMENT=ID`; they revalidate the packet before network work. Offline historical replay remains available. Node stream and unsigned buy/sell entrypoints use the same gate before SDK loading. Low-level importable functions remain research libraries, not secure job dispatchers; direct use must also follow admission policy. Gate coverage is not an OS sandbox against arbitrary code or direct network calls. Neither scan/evaluate primitives nor admission can enable ENTER.

Evidence summaries and a separately bounded schema-only feasibility probe are permitted preparation, not a full ER-001 result or production build. Generic family allows no further experiment categories today. Its approved next work is preservation/audit, proposing a distinct causal mechanism or operator review; an actual experiment must be admitted. ER-001 received a separate independent workflow review and consumed its single admission budget. Its admission is now SUSPENDED after the operator narrowed scope to feasibility. The historical approval is preserved and is stale for the changed current packet; it cannot authorize resumption. No economic result has been recorded.

## Internal steps within an approved experiment

An admission's frozen `allowed_steps` records its source-semantic validation, bounded dataset acquisition, historical reconstruction and deterministic analysis. `rocket research step ER-001 --action dataset_acquisition` revalidates the same admission and does not consume another budget or require another operator approval. A different experiment, unlisted step or stale reviewed definition fails closed. Outcome artifacts and acquisition logs live outside the admission state until terminal resolution, so ordinary internal progress does not invalidate the initial review. Operator authorization for ER-001 is explicitly recorded in its checkpoint. Prospective captures/trading are not ER-001 internal steps.
