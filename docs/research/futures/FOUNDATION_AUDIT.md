# PR #38 canonical foundation audit

Status: `CANONICAL_FOUNDATION_BLOCKED`, 2026-09-30. Temporary closing blocker:
GitHub must execute and pass the new narrow offline research workflow on the
pushed branch. Local checks below pass. No strategy, FUT-014 or carry trial is
admitted; this status concerns research hygiene only.

## Reconciliation findings and changes

The PR body stopped around FUT-004; frontier and source scouts still proposed
new discovery; frozen contract/ledger rows displayed old unscored states next
to scored results. Carry remained a possible directional successor and family
failures were spread across experiment numbers. Five result-to-scorer links
were broken, several freeze/result revisions were pending, and the claimed
Ruff verification no longer held: FUT-008/009 contained two assigned lambdas
and an unused import. GitHub had no status checks or repository workflow.

[FAMILY_AUDIT.md](FAMILY_AUDIT.md) now groups all materially distinct families,
includes historical component failures, states exactly what closed, preserves
broader uncertainty and lists rescue prohibitions/reopening evidence. All
family budgets are zero. [EXPERIMENT_ADMISSION.md](EXPERIMENT_ADMISSION.md)
requires nine written criteria, a named independent reviewer, exact packet
fingerprints, one cheap trial per grant, result suspension, a two-attempt
family stop rule and reviewed exceptions. Scope denials are retained; no
independent approval was fabricated. This is a repository policy gate, not a
runtime enforcement system or a trading permission.

Frontier and pillar now direct consolidation and admission only. Frozen
contracts/data records and pre-result ledger rows are explicitly historical;
original rules, failures and source caveats are preserved. Scouts link to
subsequent results. Carry is outside the single-venue directional product;
OI remains an unsigned source without an admitted rule. The retained
preliminary explorer report is labeled unverified because its temporary raw
responses are gone; it does not establish cohort coverage.

## Merge and shared-policy audit

Main at inspection was `42983fc38d07795dc45673bd6929bded1b93719b`.
GitHub reported PR #38 `CONFLICTING` / `DIRTY`. A local merge-tree identified
**only README.md** as conflicting: research hierarchy versus main's external
research-data instructions. Main was merged in `4040fca`, retaining both
sections and all main changes. Relative to current main, this PR has no diff
under `rocket/` or `pyproject.toml`; main's production changes are inherited,
not futures research edits. The PR is not merged.

PR #37 was inspected at `d689e13eb82b5bf6580fd4340a1df1930dec429e`.
A prospective merge-tree reports an add/add conflict in
`docs/research/RESEARCH_CONSTITUTION.md`; `rocket/cli.py` merges automatically.
No memecoin files or governance runtime were imported or changed. Both
constitutions share PIT, costs, negative evidence, promotion and independent
admission principles. The futures addendum explicitly preserves stronger
other-domain gates. When both PRs land, the shared-file resolution must keep
futures' detailed seven method rules and domain admission link, plus #37's
machine-readable memecoin workflow link and controls. This is compatible
textual reconciliation, not permission to bypass #37 or to deploy its CLI
from this PR. No operator strategy-policy decision is needed for this pass;
revalidate the merge against the then-current revisions.

## Verification and practical limits

- Local command: `python -m pytest tests/research tests/workflows/test_crypto.py tests/contract/test_safety_boundary.py tests/contract/test_operational_vs_research.py -ra`: **82 passed** (48 research tests plus 34 crypto/safety tests).
- `ruff check research/futures tests/research`: passed after the three
  behavior-preserving scorer lint fixes. `git diff --check`: passed.
- FUT-001 OOS and FUT-002/003/005/006/007 replayed from retained local inputs,
  on already scored windows only, byte for byte against the recorded reports.
  FUT-004 economic JSON matched exactly after excluding its current
  `scored_at` provenance field; whole-file bytes intentionally differ.
- These replays were offline. No new strategy outcome, new source acquisition,
  conditional follow-up, 2026 outcome, scan or live execution was run.
- Later FUT-008–013 full raw-data replays were not claimed in this audit.
  Some original temporary source bundles are absent locally; existing source
  URLs/manifests/digests and published result documents remain provenance,
  not a newly reverified historical market dataset. Promotion still requires
  source and execution acceptance. FUT-008 tests cover its touched scoring
  helpers; FUT-009's removed unused import and lambda-to-function change
  preserve the arithmetic expression and call semantics.
- [.github/workflows/futures-research.yml](../../../.github/workflows/futures-research.yml)
  runs the 48 offline research tests, research Ruff and changed-file whitespace
  checks on relevant PRs and pushes. It needs no market archive, credentials or
  network data calls. Large-data replays remain separate local evidence;
  GitHub CI is not claimed to reproduce historical alpha tables.

Foundation readiness requires coherent documents, safe main reconciliation,
passing automated checks and no unreviewed successor. It does not require
resolving every strategy-source limit or validating an edge. Final status and
remote CI evidence will be recorded after the pushed workflow completes.
