# Live Project configuration and remaining UI steps

Project: [Rocket — Derivatives Strategy Research](https://github.com/users/jhonnyisaacc/projects/4), user-owned Projects v2 #4, linked to jhonnyisaacc/rocket. The live readback on 2026-10-05 reports **public**; mutations require authenticated Projects write access. All seven Status options and nineteen custom fields exist (32 total including native fields). GitHub rejects the reserved custom name `Reviewer`; the equivalent text field is **Research Reviewer**. Native `Reviewers` is GitHub PR review requests, not the scientific identity field.

Status: Backlog, Ready, In Progress, Review / Gate, Done, Rejected, Parked. Program Outcome: Active, Strategy Validated, Research Line Rejected, Ready for Capital Review. Priority/Family/Type/State/Phase options match the request. Trials Consumed is numeric; unknown historical totals stay blank with evidence annotations. Program outcome is synchronized across linked items by audited code-gate disposition; it is not an LLM's subjective decision.

API-created views have these persisted layouts/filters/grouping:

| View | Layout / grouping | Filter |
| --- | --- | --- |
| Research Board | Board, Status columns; Priority ascending | all items |
| Active Research | Table, Priority/Phase ascending | `status:Ready,"In Progress","Review / Gate" -research-state:Historical` |
| Research Gates | Table, Research State groups; Priority/Phase ascending | `research-state:"Admission Review",Admitted,Running,Passed,Blocked` |
| Rejected / Historical | Table, Research Family groups | `research-state:Historical,Failed` |
| Data / PIT | Table | `research-family:"Data / PIT"` |
| Program Roadmap | Table, Phase groups | all items; phases are conditional, no invented dates |
| PR Dispositions | Table, explicit disposition/blocker columns | `is:pr` |
| Review Tiers | Table, review/budget/gate columns | `is:issue` |
| Human Decisions | Table, near-term/deferred scope | `is:issue gate-source:HUMAN` |

The five added fields are Trial Budget (Number), Gate Source (CODE/HUMAN/DATA/
REVIEW/NONE), Review Tier (MAINTENANCE/FOUNDATION/SCIENTIFIC_ADMISSION/
PROSPECTIVE_VALIDATION/CAPITAL), PR Disposition (CONTINUE_ACTIVE/
MERGE_WHEN_ACCEPTED/CLOSE_EVIDENCE_ARCHIVE/SUPERSEDED/BLOCKED), and Disposition
Blocker (Text). #53 budget 1 differs from consumed 0; #58 and other new
non-predictive issues have both 0. Exact semantics are in AGENT_ROLES.md,
POWER_AUDIT.md and committed policy. PR dispositions remain fixed while their
preservation/review blockers are outstanding, rather than being relabeled
BLOCKED and losing the intended action.

All nine views show the new fields. Existing Status/Phase grouping and sorting
were preserved. GraphQL permits the three new views' filters and visible fields
but offers no grouping/sorting input; those new tables have no claimed grouped
layout. Current REST list attempts returned 404; this is a view-read limitation,
not a failure to create fields or views. Live GraphQL readbacks verify them.

All six display Title, Priority, Research Reviewer, Trials Consumed, Unlock/Kill, Status, Family, Research State, Phase, Evidence, Depends On and Program Outcome, with gate fields early in the visible-field order. Rejected items must have Research State Failed; the archive view thus includes historical/failed evidence without unsupported cross-field OR. Review / Gate items use Admission Review, Admitted, Running, Passed or Blocked states, all included by Research Gates. BLOCKED must always retain its kill condition.

GitHub's [REST view creation API](https://docs.github.com/en/rest/projects/views) supports sort_by/group_by/vertical_group_by. These controls were configured programmatically and read back through GraphQL. Views were recreated through REST because the GraphQL configuration input exposes visible fields only; the initial redundant views were deleted without deleting items. Research Board is the first retained view. Actual REST view item lists were checked, including Data / PIT selecting only #52 and the archive excluding active/draft work. Custom filter field names use lowercase hyphenated slugs; quoting a field name is not a valid substitute. [Filter semantics](https://docs.github.com/en/issues/planning-and-tracking-with-projects/customizing-views-in-your-project/filtering-projects) support OR within one field and AND across fields.

## Remaining optional UI affordance

No mandatory view grouping/sorting action remains. If the current UI offers a WIP display, set the program research limit to 3; no available view API parameter exposes that limit. The authoritative limit is three unique primary work items across In Progress/Review / Gate, not three per column. The `research next` dispatch check enforces the count from a verified current snapshot. Do not mistake linked PR evidence rows for separate admissions. Optional tab/layout preferences do not affect authority.

## Repository workflow and scientific authority

**Repository workflow: LIGHTWEIGHT. Scientific research: STRICT / MACHINE-GATED.**
The human's 2026-10-05 correction removes newly introduced ruleset **24519812**.
Live GitHub readback returned no remaining rulesets and no classic main branch
protection. No replacement, bypass exception or unrelated setting was changed.
Ordinary PRs need no second GitHub account/App, scientific review, admission,
research WIP slot or mandatory Governance checks. #63/#64 became CLEAN/MERGEABLE
immediately after removal; inspect their current normal tests before merging.

Scientific approval records reviewer role/model family, isolated pre-result
context, contribution history, exact commit/artifact hashes and decision. The
reviewer must not have designed or implemented the experiment. Evidence can be
committed/pushed by `jhonnyisaacc`; GitHub username is not proof of scientific
independence. #56 still resolves the scientific reviewer/process and human
values. #60's mandatory separate-account rollout is retired; technical identity
separation is optional infrastructure with no admission or repository blocker.

CODEOWNERS provides optional ownership hints. Research-governance CI runs only
for research/governance paths and shared CLI/dependency/contract files. It is
informational repository CI, with no globally required status check. The actual
changed paths in #63/#64 match none of its filters. A relevant research change
still needs tests and protocol-level acceptance; a green merge or skipped
workflow never grants experiment scoring permission.

The research dispatcher intersects Project membership with the committed primary
registry. WIP=3 applies to primary derivatives research only. Disclosures,
Cursor/provider fixes, refactors and unrelated ordinary engineering are outside
that registry. Their GitHub mergeability never calls `rocket research next`.
