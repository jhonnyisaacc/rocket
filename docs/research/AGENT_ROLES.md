# Agent roles and separation

| Role | May do | May not do |
| --- | --- | --- |
| Orchestrator | Select only the highest-priority Ready item with satisfied dependencies/unlock, admission and WIP capacity; open/update its PR; synchronize audited code gates | Invent successors, change thresholds after results, approve its own work, merge an agent-authored PR, authorize live execution |
| Implementer (Codex or equivalent) | Implement, acquire required data, run admitted experiments, test and document | Approve its own experiment or access unadmitted outcomes |
| Replication/adversarial agent (Muse or equivalent) | Independently reproduce, find bugs, challenge assumptions and audit sources | Approve a design it helped create; treat an alternate attractive metric as a pass |
| Independent reviewer | Review an isolated pre-result package and exact commit; prefer a different model family | Have designed or implemented the experiment; have unrestricted historical outcome access during admission |
| Research auditor | Verify frozen contract, scorer identity, trial history, code-emitted result, dataset/outcome provenance and receipt chain | Subjectively decide a near-pass deserves continuation |

Actual MOM-002 reviewer: **UNRESOLVED**. Existing Codex/Muse collaborators on MOM-000 do not automatically qualify as independent MOM-002 admission reviewers. The human may approve identity/process in #56. Record stable agent identity, model family, human operator/GitHub actor and contribution history; names alone are not evidence of independence.

The authenticated GitHub actor is the real repository owner `@jhonnyisaacc`, with admin permission. CODEOWNERS uses this valid owner for sensitive files. GitHub cannot distinguish a human from an LLM using the same credential. Required PR/last-push review and no bypass reduce accidental pushes, but separate reviewer credentials/collaborator access are needed for meaningful platform identity separation. The owner is not invented as the scientific reviewer. Agents must never approve or merge their own research PRs. Human charter/capital approval is separate from scientific review.

Admission outcomes: APPROVE; APPROVE_WITH_PRE_RESULT_CHANGES (renewed review required); REJECT_AS_RESCUE; REJECT_AS_UNDERPOWERED. Approval must precede fitting/association access and name the exact pre-result revision, artifact hashes and single-trial budget. Audit approval after scoring validates provenance, not scientific taste.
