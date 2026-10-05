# Implementation plan — 2026-10-02, before GitHub mutation

Baseline main: 09d71503906345c194778ecf951dc3a06f2b42cc. Clean detached worktree.
Authentication: jhonnyisaacc ADMIN, repo/workflow scopes; project scope pending device authorization.
No main protection/rulesets; no templates/workflows committed on main. Registered Futures and Momentum workflows originate on open PRs.
Read open PRs and pinned heads of #49/#50/#38/#40/#46/#26. #49 already implements reconciliation and CFTC fixes; independent acceptance is still absent. MOM-002 PENDING_INDEPENDENT_REVIEW and unscored.

1. Use dedicated chore/autonomous-research-project branch from origin/main. Never push main; never merge agent-authored PRs.
2. Create/reuse user-owned Projects v2 Rocket — Derivatives Strategy Research with statuses, 14 custom fields, research decision tree and WIP 3. Inspect API schema for view support; document precise UI gaps.
3. Normalize 13 labels; create issues for reconciliation acceptance, CFTC correctness acceptance, draft MOM-002, independent review, historical consolidation and human charter. Add MOM-000 and a single parked downstream draft; connect all six research PRs as evidence without automatically merging/closing them.
4. Add charter (unresolved human economic/risk values), protocol, roles, trial ledger, pinned evidence index, collector operations and final operational report. Historical FUT trials 13; macro 43; derivatives reported A18/B10/C6; equity A0–A6 variants with count uncertainty. MOM census zero predictive trials. Do not reset counts.
5. Minimal Python governance primitives: manifest, five frozen artifact roles plus scorer identity, independent approval, one trial, append-only hash-chain invocation journal, controlled subprocess scorer, dataset fingerprint, immutable git-baseline CI comparison. Ship no MOM-002 scorer; its registration remains Draft. Test gate integrity with synthetic data only.
6. Add governance issue template, CODEOWNERS with actual owner, offline required CI and main protection/ruleset (PR, reviews, no force/deletion/direct push, required CI), no bypass. Record shared credential/reviewer and governance rollout limits.
7. Run offline tests/lint, push branch explicitly, create draft governance PR and attach it. Verify CI, Project fields/items/views, issues, ruleset and unchanged main; commit final operational report. Leave scientific gates/human charter unresolved honestly.

No alpha experiment, MOM-002 fitting/scoring/result inspection, market data acquisition, live execution, historical blind closure, macro/options data warehouse or automatic successor admission.
