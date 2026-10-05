# Live Project configuration and remaining UI steps

Project: [Rocket — Derivatives Strategy Research](https://github.com/users/jhonnyisaacc/projects/4), user-owned Projects v2 #4, linked to jhonnyisaacc/rocket. It remains private; authenticated agents need Projects read/write scope. All seven Status options and fourteen custom fields exist. GitHub rejects the reserved custom name `Reviewer`; the equivalent text field is **Research Reviewer**. Native `Reviewers` is GitHub PR review requests, not the scientific identity field.

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

All six display Title, Priority, Research Reviewer, Trials Consumed, Unlock/Kill, Status, Family, Research State, Phase, Evidence, Depends On and Program Outcome, with gate fields early in the visible-field order. Rejected items must have Research State Failed; the archive view thus includes historical/failed evidence without unsupported cross-field OR. Review / Gate items use Admission Review, Admitted, Running, Passed or Blocked states, all included by Research Gates. BLOCKED must always retain its kill condition.

GitHub's [REST view creation API](https://docs.github.com/en/rest/projects/views) supports sort_by/group_by/vertical_group_by. These controls were configured programmatically and read back through GraphQL. Views were recreated through REST because the GraphQL configuration input exposes visible fields only; the initial redundant views were deleted without deleting items. Research Board is the first retained view. Actual REST view item lists were checked, including Data / PIT selecting only #52 and the archive excluding active/draft work. Custom filter field names use lowercase hyphenated slugs; quoting a field name is not a valid substitute. [Filter semantics](https://docs.github.com/en/issues/planning-and-tracking-with-projects/customizing-views-in-your-project/filtering-projects) support OR within one field and AND across fields.

## Remaining optional UI affordance

No mandatory view grouping/sorting action remains. If the current UI offers a WIP display, set the program research limit to 3; no available view API parameter exposes that limit. The authoritative limit is three unique primary work items across In Progress/Review / Gate, not three per column. The `research next` dispatch check enforces the count from a verified current snapshot. Do not mistake linked PR evidence rows for separate admissions. Optional tab/layout preferences do not affect authority.

## Main protection and review rollout

Active repository ruleset **24519812**, [settings](https://github.com/jhonnyisaacc/rocket/settings/rules/24519812): required PR, one approving review, dismissal of stale reviews, approval by someone other than the last pusher, resolved review threads, strict **Governance checks** from GitHub Actions app 15368, no force push/deletion and no bypass actors. Direct main pushes cannot satisfy the PR rule. No destructive main push was used to test it.

Only `jhonnyisaacc` was returned by the collaborators API. GitHub cannot accept the author's self-review. Before merge, the human owner must open **Settings → Collaborators → Add people**, invite the real selected reviewer with sufficient repository access, and have that person independently review/approve the PR after the last push. The scientific reviewer identity/model family/contribution history also needs human approval in #56. Do not invent another account or disable protections to merge.

CODEOWNERS names the valid owner for sensitive files. Mandatory code-owner review is intentionally not enabled while the sole owner is also the PR author; the independent/last-push approval rule is enabled. When a real second governance owner is approved, add it through reviewed CODEOWNERS changes before enabling mandatory code-owner review. Agents never merge their own PRs.

The governance workflow arrives on main only through the dedicated PR. It runs on this branch/PR now and on every future PR after merge, with no path filters that could skip a required check. Existing PRs must receive/rebase onto the governance commit before they can produce the required check. Do not lower the required check to merge old research branches.
