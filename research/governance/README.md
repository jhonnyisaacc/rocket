# Minimal research gate contracts

`rocket research verify --base origin/main` checks all registered manifests,
frozen contract/population/features/model/gate/runtime bytes, preregistration
Git objects, base-branch frozen-manifest immutability and append-only evidence.
`rocket research score ID` is the only official scorer path. MOM-002 is Draft,
unauthorized and has no scorer. Do not invoke it during infrastructure setup.

To register a future admitted experiment, create a new manifest after the
required independent admission/review. Use the MOM-002 draft as structural
scaffolding, but never promote it without its unlock conditions. Commit all
artifacts first, then record that full commit in `freeze_revision`; hash each
artifact using SHA-256. All six roles must have nonempty lists of `{path,
sha256}`: contract (includes data/population/metric/threshold definitions),
population, features, model, gate, runtime (runner, dependency lock/environment
identity and relevant transitive source files). List every code dependency;
undeclared code imports are an independent-review rejection. Files must be
repository-relative, tracked at the frozen revision, and not symlinks. An
ADMITTED manifest must itself be committed on canonical main with scientific approval evidence before scoring.

Set explicit family, proposer, implementer, positive trial_number, trial_budget
1, dataset `{path, sha256}`, scorer `{path, protocol: "python-json-v1",
timeout_seconds, python_version}` and approval `{reviewer, decision: "APPROVE",
reviewed_revision, artifact_fingerprint, timestamp, evidence, review_provenance}`. The approval's
artifact fingerprint is SHA-256 of the canonical JSON artifacts mapping
(sorted keys, compact separators, UTF-8). Approval identifies the exact
freeze_revision and must come from someone who neither proposed nor
implemented/designed the experiment. The approval's `review_provenance` must contain nonempty `model_family`, `role`,
`isolated_context` and `contribution_history`; `designed_experiment`,
`implemented_experiment` and `outcomes_accessed` must each be false. Optional
`github_actor` identifies the publisher and may match the implementer's actor.
Scientific contributor IDs and contributions establish review independence;
GitHub username separation is not required. Recorded claims still need genuine
independent review; hashes/strings alone cannot prove unseen outcome access. Freeze actual solver/package/interpreter versions, source/PIT
rules, metrics, thresholds and dependencies, not merely a narrative contract.

After fetching main, score only from a clean canonical checkout matching
origin/main, with dataset bytes matching the admitted fingerprint. The frozen
Python scorer is run without shell interpretation or inherited credentials:
`python -I frozen_scorer.py dataset_path`. It must emit a single JSON object
`{"experiment_id":"ID","result":"PASS|FAIL|BLOCKED", ...gate evidence...}`.
No operator supplies a result to the official scoring command. The implementer
cannot reinterpret emitted FAIL. Scorer code/thresholds receive independent
review; a wrapper cannot determine scientific adequacy by itself.

Each invocation writes an fsynced, SHA-256 chained receipt. Failed admission
preflight writes BLOCKED without outcome access. Once a START receipt is
written the trial is reserved permanently, including timeout/crash/invalid
output. The paired FINISH records commit/time, frozen hashes, dataset/scorer
identity, output fingerprint and code result. No retry flag exists. Preserve
stdout/stderr/result artifacts in the evidence PR before continuing. Publish
the journal addition through the ordinary PR workflow with scientific audit evidence; CI refuses any rewritten prefix.
Local locking serializes one checkout only: before a future official score,
appoint one scoring authority/checkout and prohibit parallel scoring in other
clones. A protected external serialized runner would be required for stronger
multi-host enforcement; it is not deployed here. Git history and remote
review are the durable audit boundary, not a tamper-proof outcome vault.

A frozen manifest/artifact cannot be edited or deleted to fix a failed trial.
Append an invalidation JSONL row containing experiment_id, timestamp, reason,
evidence, reviewer and new_trial_id (or null when killed). Preserve original
frozen files at their paths. Independently admit a new ID/trial using new
artifact paths; prior outcome access and trial consumption remain inherited.
No newly admitted packet follows from a failure automatically.

`rocket research next --snapshot FILE` selects only explicitly verified Ready
primary work at WIP <3; snapshot preparation must validate current Project
fields against committed admission/unlock/dependency evidence. It never treats
Project editing as admission. `rocket research disposition --receipt FILE
--audit FILE` derives the MOM-002 branch decision from a canonical scorer
receipt and independent provenance audit. `scripts/research/sync_gate.py`
applies an audited FAIL to the downstream Project card (Rejected) and program
outcome, or records PASS pending human acknowledgment; it never creates a
successor. See the protocol for full human and scientific gates.

The authoritative setup includes no scoring of MOM-002, new alpha trial,
trading key, order placement, execution toggle or historical dataset acquisition.

## Refinement contracts

`project.json` distinguishes Trial Budget from Trials Consumed and commits
Review Tier, Gate Source, primary-item membership, all seven PR dispositions
and individually named blockers. `rocket.research.policy.pr_action` emits a
reviewable action plan; it cannot merge, close or admit a PR. Linked evidence
rows and unrelated issues are outside dispatch. HUMAN/CAPITAL work cannot be
selected by the agent dispatcher. Maintenance requires tests/CI/separate code
review, without imposing MOM-002's isolated scientific admission burden.

MOM-002 FROZEN/ADMITTED states additionally require every entry in
`mom002_prerequisites.json` ACCEPTED, with exact Git/artifact evidence,
resolved reviewer and prior aware timestamp. Freeze hashes that acceptance
contract and the final post-power-audit proposal. Pending #51 foundation,
Tier-B/overlap, #58 power, pre-result amendments or #56 decisions block it.
An edit to a Project field cannot satisfy this verifier.

The synthetic audit is `python scripts/research/power_audit.py`, with only
draw-count options and one strict approved structural input. Its code has no
I/O or real-data loader; the runner cannot choose an outcome file. The separate
geometry export uses causal MOM-000 source primitives only, removing forward
label definitions and requiring existing frozen ZIPs without acquisition.
See [audit scope](../../docs/research/POWER_AUDIT.md). Neither command invokes
the official scorer or writes the invocation journal. Tests use synthetic
geometry/features/endpoints exclusively.

`sync_gate.py` rejects every item marked `kill_on_mom002_fail`, including the
parked human risk/capital charter, on an independently audited official FAIL.
A conditional/underpowered synthetic audit is never a predictive FAIL and
never invokes this kill. After the final official freeze, no gate changes.

## Lightweight repository workflow

No repository-wide scientific review/check ruleset is required. The human removed
ruleset 24519812; research CI is scoped and informational. Official scoring still
requires the admitted manifest, independent scientific provenance, all prerequisite
and frozen hashes, clean canonical main, exact dataset/runtime and an unconsumed
single trial. GitHub mergeability never creates admission. Ordinary PRs are outside
research dispatch/WIP; optional technical identity separation grants no authority.
