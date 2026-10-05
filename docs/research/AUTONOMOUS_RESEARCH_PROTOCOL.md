# Autonomous research protocol

Authority: committed charter/contracts and machine gates; Project fields summarize that authority. Safety: `READ_ONLY_RESEARCH_ONLY_HUMAN_GATED`.

```text
IDEA
↓
ADMISSION REVIEW
↓
PREREGISTRATION COMMIT
↓
IMPLEMENTATION
↓
INDEPENDENT REVIEW
↓
SCORING
↓
AUDIT
↓
PASS / FAIL
```

A review-package freeze may precede admission, as in the existing MOM-002 proposal. It is not authorization to fit, inspect feature/outcome associations or score. Independent admission must approve the exact proposal commit. Implementation of the scorer is then independently reviewed and its contract/population/features/model/gate/runtime identities frozen before official scoring. Pre-result changes require a new version, rationale and renewed approval. Nothing silently amends a contract.

Every primary work item names Question, Why now, Scope, Inherited evidence, Unlock, Success, Failure, Kill, Dependencies, Trial impact, Proposer, Implementer, Reviewer and Evidence. Proposer != reviewer; implementer != reviewer; nobody approves work they helped design. Prefer a reviewer from a different model family and an isolated package containing only the pre-result contract, source audits, clocks, model/scorer specification, trial history and hashes. No unrestricted outcome access during admission.

All experiments explicitly reserve a trial count and inherit cross-family history. A new PR, checkout, directory or model does not reset trials. A failed result remains visible and cannot be reinterpreted by an LLM. No successor after FAIL without new, evidence-independent admission. The candidate BTC line specifically admits no MOM-003 rescue after MOM-002 FAIL. No historical outcome inspection before preregistration, no live execution authorization and no discretionary LLM trade override.

## Operating loop

```text
1. Read Project.
2. Find highest-priority Ready item.
3. Check dependencies and unlock conditions.
4. Verify admission.
5. Execute implementation/data work.
6. Open/update PR.
7. Move to Review / Gate.
8. Independent reviewer checks preregistration.
9. Official scorer runs.
10. Gate code emits PASS / FAIL / BLOCKED.
11. Research auditor verifies provenance.
12. PASS unlocks next permitted item.
13. FAIL applies kill conditions.
14. Update trial ledger and evidence.
15. Repeat.
```

Scoring steps apply only to admitted predictive/strategy/prospective trials, not documentation, bug repairs or admission reviews. Code at step 10 is authoritative. BLOCKED must preserve its reason and consume the reserved trial if outcomes may have been accessed. No retries after a scorer starts under the same trial identity. A crash leaves a START record and consumes that trial; an invalidation/new admission is required.

Research WIP = 3 unique primary research items in In Progress or Review / Gate. Ready is not WIP. Linked PRs are evidence for primary items, not extra research admissions; healthy operational services do not consume WIP. `rocket research next` checks a current Project snapshot and refuses dispatch at capacity or when evidence/roles/unlocks are absent. Fields are not proof of scientific approval. No agent may promote Draft to Admitted merely by editing the board.

On a verified audited MOM-002 FAIL, `rocket research disposition` emits rejection of the whole downstream item and RESEARCH_LINE_REJECTED. The auditable Project synchronizer applies that receipt; nobody chooses a near-pass exception. On PASS it records Review / Gate pending human acknowledgment; only the next permitted phase can be separately admitted. On irrecoverable data/foundation failure, explicitly invalidate, preserve the evidence and apply the affected kill condition. BLOCKED never automatically becomes a rescue trial.

After a future acknowledged PASS, default to simple entry, deterministic risk management, conservative futures expression, early freeze and increasingly prospective validation. Pana gets at most one separately admitted incremental trial; options at most one separately admitted trial with defensible historical quote/surface data. Neither family is admitted now.

## Outcome access and implementation limits

Official path: `rocket research score <experiment-id>`. The manifest must be admitted, frozen, independently approved and committed on reviewed main. It pins dataset bytes and all artifact hashes. Each invocation records experiment/trial identity, current commit, timestamp, dataset fingerprint, frozen hashes, scorer identity, result fingerprint and PASS/FAIL/BLOCKED in a hash-chain journal. See [technical contract](../../research/governance/README.md). CI checks frozen files against both their preregistration Git revision and the base branch, as well as append-only journals/ledger. Frozen manifests cannot be edited or deleted; invalidate through an appended record and re-admit a new ID/trial.

Public market data cannot be perfectly cryptographically hidden from an agent with network access. The goal is auditable admissibility. Git review, protected main, distinct credentials and durable receipt publication are part of the trust boundary; hashes cannot prove that a human/agent did not inspect data elsewhere. Local file locks serialize one checkout only. There is no deployed scoring service, secret outcome vault, independent reviewer, or live-trading authority. MOM-002 remains Draft and has no scorer in this PR.

Historical failures: [trial ledger](TRIAL_LEDGER.md). Collector: [operations](PROSPECTIVE_OPERATIONS.md). [Roles](AGENT_ROLES.md). [Project](https://github.com/users/jhonnyisaacc/projects/4).
