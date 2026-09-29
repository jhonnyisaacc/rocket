# Audit/pivot iteration verification — 2026-09-29

Delivered recommendation: PIVOT_TO_EXTREME_RUNNER_RESEARCH. Generic entry family REJECTED, zero budget, operator review required. Actor confluence remains UNTESTED with zero economic failures. ER-001's independently reviewed admission was subsequently SUSPENDED by the latest operator instruction restricting this iteration to audit/design/feasibility. Canonical direction status is REVIEW_REQUIRED, active_experiment is null, remaining budget zero. Historical authorization/review are preserved, not current resumption authority. Bounded public archive probes did not satisfy primary data requirements. No full experiment labels or effect tables evaluated. The separate closing [independent review](experiments/er001/REVIEW-ITERATION.json) is WORKFLOW_OK for these deliverables and explicitly grants no admission authority.

Checks:

- `.venv/bin/python -m pytest -m 'not integration'`: 474 passed, 1 integration test deselected (28 governance tests and 7 archive boundary tests included).
- `.venv/bin/ruff check rocket tests scripts/research --output-format concise`: passed.
- Ruff formatting of new governance/CLI/acquisition/test modules: passed.
- Whole-file formatting check of nine touched legacy Python files: failed; independently checked `git show HEAD:<file>` copies and all nine already fail formatting on HEAD. Avoided unrelated format rewrite; new integration blocks follow formatting style.
- `node --check` on admission helper, stream collector, unsigned buy and unsigned sell: passed. Tests additionally execute all three Node entrypoints without admission and verify failure before SDK/network work.
- `git diff --check`: passed.
- Real `rocket research review` exports the bounded packet and exits 2 with INDEPENDENT_REVIEW_MISSING. It does not create a synthetic approval or consume another budget. The archived historical review also blocks against the changed current state; all four internal-step categories reject the suspended admission.

## Files changed in this iteration

Authority/evidence:

- `docs/research/RESEARCH_CONSTITUTION.md`
- `docs/research/WORKFLOW_GOVERNANCE.md` (new)
- `docs/research/memecoin/MEMECOIN_PILLAR.md`
- `docs/research/memecoin/MEMECOIN_FRONTIER.md`
- `docs/research/memecoin/KNOWLEDGE_LEDGER.md`
- `docs/research/memecoin/DATA_TRUTH_REGISTRY.md`
- `docs/research/memecoin/WORKFLOW_AUDIT.md` (new)
- `docs/research/memecoin/RESEARCH_STATE.json` (new)
- `docs/research/memecoin/experiments/ER-001-FROZEN.md` (new)
- `docs/research/memecoin/experiments/ER-001-CHECKPOINT.json` (new)
- `docs/research/memecoin/ER-001-FEASIBILITY.md` (new)
- `docs/research/memecoin/ITERATION_VALIDATION.md` (new)

Bounded source probe (all new, source copies retained as text, not executed):

- `docs/research/memecoin/probes/ER-001/manifest.json`
- `docs/research/memecoin/probes/ER-001/README.md`
- `docs/research/memecoin/probes/ER-001/collect.py.txt`
- `docs/research/memecoin/probes/ER-001/gmgn_client.py.txt`
- `docs/research/memecoin/probes/ER-001/LICENSE`

Implementation/tests:

- `rocket/research/governance.py` (new)
- `rocket/research/cli.py` (new)
- `rocket/cli.py` (register research commands)
- `tests/test_research_governance.py` (new)
- `scripts/research/research_admission.cjs` (new)
- `scripts/research/memecoin_capture.mjs`
- `scripts/research/memecoin_capture_py.py`
- `scripts/research/memecoin_block_capture.py`
- `scripts/research/memecoin_pumpportal_capture.py`
- `scripts/research/memecoin_curve_snapshot_capture.py`
- `scripts/research/memecoin_live_actor_capture.py`
- `scripts/research/memecoin_route_snapshot_capture.py`
- `scripts/research/memecoin_pump_buy_companion.py`
- `scripts/research/memecoin_pump_buy_stratified.py`
- `scripts/research/memecoin_pump_unsigned_buy.cjs`
- `scripts/research/memecoin_amm_unsigned_simulation.cjs`

## Existing local work preserved

Did not modify the preexisting changes in `scripts/research/memecoin_pump_entry_route_audit.py`, untracked `scripts/research/memecoin_pump_paired_size_quote.cjs`, MC-023 archive or `artifacts/`. No prospective replacement capture, full ER-001 corpus acquisition/outcome evaluation, threshold search, model, wallet graph/subscription system, browser/X automation, live strategy, signing, order broadcast or ENTER enablement. Public archive footers/row groups and capped compressed prefixes were acquired as separate feasibility evidence. Changes are committed and pushed on `research/memecoin-strategy`, updating existing PR #37; no new PR created.

Operator approval is required for reopening the generic family and before expensive acquisition/ER-002. Source adequacy and renewed scope/admission review are required before resuming ER-001. The latest instruction deliberately restricts the completed iteration to feasibility. These gates are local repository records, not authentication against unrestricted file edits or arbitrary direct code execution.

## Follow-up files and validation

Additional source-semantic tooling: `rocket/research/extreme_runner_acquisition.py`, `scripts/research/extreme_runner_acquire.py`, `tests/test_extreme_runner_acquisition.py`, and optional research `pyarrow` dependency. Strict HTTP range validation rejects whole-file fallback; cumulative transfer caps stop oversized projection, including failed/truncated bodies. Tests exercise cache reuse, pre-request cap rejection, unsupported/mismatched/truncated/overflow responses and small-body download bounds.

Durable probe evidence: `probes/ER-001/bounded_archive_manifest.json`, both pinned acquisition plans under `experiments/er001/`, historical `WORKFLOW_REVIEW.json`, closing `REVIEW-ITERATION.json`, `ER-001-FROZEN-v1.md` and superseded authorization evidence. Raw byte/sample artifacts stay in ignored `.rocket/er001/`, separate from primary data. Six sample files had independently verified hashes. The total successful manifest transfer is 47,037,255 bytes; no conditional tail rates are reported.

Governance tests additionally verify approved internal steps reuse one budget, stale binding fails, and a suspended admission cannot execute an internal step. Test pre-admission fixtures explicitly isolate their scenario from current live research progress. Closing review is bounded to workflow validity; it does not judge profitability or reopen either family.
