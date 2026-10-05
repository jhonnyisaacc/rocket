# Agent roles and separation

| Role | May do | May not do |
| --- | --- | --- |
| Orchestrator | Select only the highest-priority Ready research item with satisfied dependencies/unlock, admission and WIP capacity; update its evidence; synchronize audited code gates; follow normal engineering PR workflow | Invent successors, change thresholds after results, independently approve its own research acceptance, authorize live execution |
| Implementer (Codex or equivalent) | Implement, acquire required data, run admitted experiments, test and document | Approve its own experiment or access unadmitted outcomes |
| Replication/adversarial agent (Muse or equivalent) | Independently reproduce, find bugs, challenge assumptions and audit sources | Approve a design it helped create; treat an alternate attractive metric as a pass |
| Independent reviewer | Review an isolated pre-result package and exact commit; prefer a different model family | Have designed or implemented the experiment; have unrestricted historical outcome access during admission |
| Research auditor | Verify frozen contract, scorer identity, trial history, code-emitted result, dataset/outcome provenance and receipt chain | Subjectively decide a near-pass deserves continuation |

Actual MOM-002 reviewer: **UNRESOLVED**. Existing Codex/Muse collaborators on MOM-000 do not automatically qualify as independent MOM-002 admission reviewers. The human may approve identity/process in #56. Record stable agent identity, model family, human operator/GitHub actor and contribution history; names alone are not evidence of independence.

GitHub operations may all use the real owner `@jhonnyisaacc`. GitHub actor
identity alone proves no scientific independence. Repository operations remain
LIGHTWEIGHT; separate GitHub accounts, Apps or collaborators are optional and
are not required for merges or research admission. CODEOWNERS is informational.
The owner can publish a genuine independent review record without becoming its
scientific author. Human charter/capital approval remains separate from review.

For scientific admission, record reviewer role/model family, isolated pre-result
context, contribution history, exact commit/artifact hashes and decision. Stable
scientific contributor identifiers differ from the proposer/implementer; the
publishing GitHub username may be shared. The approval's `review_provenance`
contains nonempty `model_family`, `role`, `isolated_context` and
`contribution_history`, plus `designed_experiment=false`,
`implemented_experiment=false` and `outcomes_accessed=false`. Optional
`github_actor` describes publication only. The verifier rejects missing or
conflicting scientific provenance regardless of GitHub mergeability.

Admission outcomes: APPROVE; APPROVE_WITH_PRE_RESULT_CHANGES (renewed review required); REJECT_AS_RESCUE; REJECT_AS_UNDERPOWERED. Approval must precede fitting/association access and name the exact pre-result revision, artifact hashes and single-trial budget. Audit approval after scoring validates provenance, not scientific taste.

## Review tiers

| Tier | Required acceptance |
| --- | --- |
| MAINTENANCE | Normal technical discipline: tests, relevant CI and code/evidence review when available; no isolated scientific packet or mandatory scientific reviewer. Includes #52 PIT correctness and #55 evidence indexing. Completion grants no FOUNDATION or scientific admission. Ordinary engineering outside the Project needs no research review or WIP slot. |
| FOUNDATION | Strong independent technical/adversarial review of exact artifacts; zero-alpha reconciliation #51 and synthetic methodology #58 are not predictive trials. |
| SCIENTIFIC_ADMISSION | Isolated pre-result package; no result access; reviewer did not design/implement; preferably distinct model family; exact commit/artifact approval. #53/#54 receive only the finalized post-power-audit contract. |
| PROSPECTIVE_VALIDATION | Separately admitted frozen forward forecasts, stopping rule, isolated mature outcomes and independent exact-artifact review; historical PASS alone does not admit it. |
| CAPITAL | Human-only risk/value/capital authorization; agents stop at READY_FOR_CAPITAL_REVIEW. |

[#60](https://github.com/jhonnyisaacc/rocket/issues/60) retires mandatory GitHub
identity separation after the human's workflow correction. Scientific independence
is documented by process and artifacts; a second technical identity is optional,
not a prerequisite of #54 or ordinary repository operation. #56's accepted
scientific review process remains required. No agent independently approves its
own experiment or foundation acceptance.
