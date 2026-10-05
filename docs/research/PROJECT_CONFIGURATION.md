# Live Project configuration and remaining UI steps

Project: [Rocket — Derivatives Strategy Research](https://github.com/users/jhonnyisaacc/projects/4), user-owned Projects v2 #4, linked to jhonnyisaacc/rocket. It remains private; authenticated agents need Projects read/write scope. All seven Status options and fourteen custom fields exist. GitHub rejects the reserved custom name `Reviewer`; the equivalent text field is **Research Reviewer**. Native `Reviewers` is GitHub PR review requests, not the scientific identity field.

Status: Backlog, Ready, In Progress, Review / Gate, Done, Rejected, Parked. Program Outcome: Active, Strategy Validated, Research Line Rejected, Ready for Capital Review. Priority/Family/Type/State/Phase options match the request. Trials Consumed is numeric; unknown historical totals stay blank with evidence annotations. Program outcome is synchronized across linked items by audited code-gate disposition; it is not an LLM's subjective decision.

API-created views have these persisted layouts/filters:

| View | Layout | Filter |
| --- | --- | --- |
| Research Board | Board | all items |
| Active Research | Table | `status:Ready,"In Progress","Review / Gate" -"Research State":Historical` |
| Research Gates | Table | `"Research State":"Admission Review",Admitted,Running` |
| Rejected / Historical | Table | `"Research State":Historical,Failed` |
| Data / PIT | Table | `"Research Family":"Data / PIT"` |
| Program Roadmap | Table | all items; Phase visible |

All six display Status, Priority, Family, Research State, Phase, Research Reviewer, Trials Consumed, Unlock/Kill, Evidence, Depends On and Program Outcome. Rejected items must be Research State Failed; this makes the archive view a union of historical/failed evidence without unsupported cross-field OR. Research Gates includes admitted/running review work; after a future scored gate, also inspect Active Research for Passed/Blocked items waiting in Review / Gate. The extra GitHub default View 1 is an unfiltered table, not a research admission.

## Exact UI follow-up

The live GraphQL schema supports create/update views, layout, filter and visibleFieldIds. Its ProjectV2ViewConfigurationInput has only visibleFieldIds; group-by, sorting, tab order and WIP limits have no mutation fields. Live reads confirmed empty groupByFields even for the new Board. Do not claim Kanban grouping is already configured.

1. Open Research Board. In the view menu beside its name select **Group by → Status**, show all seven groups, and save the view. Drag its tab to the first position if desired; delete the empty default View 1 through its tab menu.
2. Open Program Roadmap. Choose **Group by → Phase** and save. Keep Table layout until actual dates are independently admitted; phase grouping must not imply every phase will be reached.
3. In Research Gates use Fields to place **Research Reviewer, Trials Consumed, Unlock Condition, Kill Condition** near the title, then save. Their visibility is already configured through the API. Add Status Review / Gate items to this view using the UI's supported filter builder if its filter capabilities permit the union; otherwise Active Research is the companion review queue.
4. Sort active/gate tables by Priority ascending, then Phase; save. This does not override the committed Ready/unlock/WIP policy.
5. Optional view-level WIP affordance: if the current UI offers a board limit, set 3 for program research. The authoritative limit is three unique primary work items across In Progress/Review / Gate, not three per column. The `research next` dispatch check enforces the program count from a verified snapshot.

[GitHub Projects GraphQL reference](https://docs.github.com/en/graphql/reference/projects) documents view mutation/configuration. The schema inspected in this account is authoritative for the recorded UI limitations.

## Main protection and review rollout

Active repository ruleset **24519812**, [settings](https://github.com/jhonnyisaacc/rocket/settings/rules/24519812): required PR, one approving review, dismissal of stale reviews, approval by someone other than the last pusher, resolved review threads, strict **Governance checks** from GitHub Actions app 15368, no force push/deletion and no bypass actors. Direct main pushes cannot satisfy the PR rule. No destructive main push was used to test it.

Only `jhonnyisaacc` was returned by the collaborators API. GitHub cannot accept the author's self-review. Before merge, the human owner must open **Settings → Collaborators → Add people**, invite the real selected reviewer with sufficient repository access, and have that person independently review/approve the PR after the last push. The scientific reviewer identity/model family/contribution history also needs human approval in #56. Do not invent another account or disable protections to merge.

CODEOWNERS names the valid owner for sensitive files. Mandatory code-owner review is intentionally not enabled while the sole owner is also the PR author; the independent/last-push approval rule is enabled. When a real second governance owner is approved, add it through reviewed CODEOWNERS changes before enabling mandatory code-owner review. Agents never merge their own PRs.

The governance workflow arrives on main only through the dedicated PR. It runs on this branch/PR now and on every future PR after merge, with no path filters that could skip a required check. Existing PRs must receive/rebase onto the governance commit before they can produce the required check. Do not lower the required check to merge old research branches.
