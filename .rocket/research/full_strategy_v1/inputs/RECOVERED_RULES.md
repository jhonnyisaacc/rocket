# Recovered execution contract — corrected source diagnosis

## Important correction to the early source pass

The later sections of `nave/docs/technical.yaml` contain substantially more operational guidance than the early sections initially inspected. **Do not interpret the sealed first-pass matrix or initial review comments as saying that the project has no entry, confluence or exit definitions.** The definitions below already exist. The unresolved issue is their provenance, internal consistency, precise numerical interpretation, and implementation fidelity.

The six initial chart judgments remain sealed and unchanged. This deeper source audit occurred AFTER the follow-up reveal and is explicitly not backdated into those labels. The full theory file's SHA256 matches the one captured before review: these rules were already present, not added during this session. Excerpts and hashes are in `recovered_sources/` and `recovered_sources_manifest.json`.

## What the existing refinement actually says

| Layer | Existing documented interpretation | Current Rocket / legacy gap |
|---|---|---|
| Direction | Weekly macro/COT reference and daily confirmation establish direction. Technical YAML 637–692. | Rocket's six-bar function assigns direction from the local 4h sequence. Its complete production funnel has other contextual gates, which must be audited separately. |
| Four-hour role | A counter-daily move can be the expected pullback, NOT automatic invalidation. Wait for a structural reaction at a valid confluence zone. YAML 693–750. | Current Rocket recognizes consecutive directional highs/lows, not a confluence-zone reaction. Nave's current `four_h_setup_valid` still checks close-versus-SMA alignment, despite the documentation explicitly warning against that substitution. |
| Setup families | Block rejection + structure break; false-break/sweep pattern; retracement of an identified impulse; support/resistance flip within a block-between-levels. YAML 766–792. | Neither strict six-bar direction nor a passive midpoint touch by itself certifies one of these patterns. They must not be relabeled as the entire theory. |
| One-hour execution | A valid 4h setup must already exist. Require a flip, sweep/reversal, or micro false-break trigger within that zone. Without a trigger, pass. YAML 879–915. | Nave's `one_h_entry` constructs geometry from recent OHLC; the pure helper accepts flat candles without establishing any named trigger. Rocket's structure function does not claim to be this execution layer. |
| Zone anchors | True swing plus nearby institutional level, with at least three named confluence factors; first target usually nearest opposing structure. YAML 1214–1261. | More guidance exists than the initial pass captured, but factor tolerances, price-digit scaling across BTC/XRP, and precise swing/block recognition remain underspecified. A midpoint of six bars is a different construction. |
| Impulse state | Anchor to confirmed daily swings bracketing a structure break, lock until extension/invalidation. YAML 1127 onward. | A fresh rolling window is not equivalent to locked impulse state. Current legacy chase helper can explicitly pass when no impulse is identified. |
| Exit | ZC1/ZC2 with partials in project notes; transcript recommends first confluence at least 1R away. YAML 1230–1240, transcript 7496–7518. | Research fixed 1R/full exit/48h is a controlled simplification, not a full-theory replay. Nave already contains dynamic swing targets, so we should inspect/reuse that research knowledge rather than build an identical feature from scratch. |
| Re-entry | One active entry per 4h zone touch; a new attempt requires a qualifying counter-move and a new structural element/zone. YAML 916–943. | Candidate snapshots are not lifecycle state. This session's four MIXED updates do not establish that earlier hypotheses expired or were invalidated. |

These are **documented project refinements**, not automatically authenticated statements from the original educator. Phase-1 changelog dated 2026-04-08 attributes additions to transcripts. `analysis/iterations/iter_2.md` dated 2026-04-09 explicitly says the counter-move clarification was added after examining backtest rejection counts. Therefore it is a previously outcome-informed interpretation, not a new independent discovery or proven remedy.

## Conflicts still requiring an explicit choice before implementation

- Weekly prose says 1.5 ATR while its formula/code default says 1.2, with a recorded prior parameter sweep. Use neither as unquestioned doctrine.
- Project retracement notes call 50% an alert and 75% minimum entry; current legacy `chase_gate` defaults to 50–95%. Rocket's midpoint is based on a different anchor entirely. Changing its 50% to 75% would not reconcile the strategies.
- Stop guidance mixes thesis boundaries, hourly swing buffers, and a later 1.5× daily ATR floor. The latter was introduced after reviewing historical losses. Exact geometry and precedence need a frozen specification before testing.
- Descriptions say 20 daily / 12 four-hour closes and fixed 2R; current helper bodies use 10 / 8 and fallback targets at 1.5R / 2.5R. Documentation drift is directly checkable and is not a theory-performance result.
- “At least three confluences”, 75–86% preference, institutional percentages, and fractional exits are not established here as universally predictive rules. In particular, claimed institutional market-share percentages do not mathematically prove a retracement percentage.
- Current legacy target logic skips closer swing objectives below 1R and can create fixed-R fallback targets. That is different from independently finding the first confluence, then deciding whether the trade has room. Whether a given swing is a real confluence remains unresolved.

## Executed evidence, not just another plan

`contract_probe.py` snapshots and runs ONLY named pure legacy helpers with synthetic OHLC fixtures, without importing provider/execution services. It demonstrates close-only four-hour acceptance, geometry from flat hourly bars, a one-bar hourly return, permissive missing-impulse handling, and filtering of a nearer swing target. See `contract_probe_results.json`.

These probes isolate semantics; they do not run the full legacy engine, imply all upstream gates pass, or measure the effect on historical returns. No production defect has been repaired or profitability improvement claimed.

## Next research decision

Use the **already documented pullback → four-hour structural reaction → one-hour trigger** as the candidate contract to reconcile, instead of inventing another generic momentum threshold. Do not implement all setup families at once.

The narrow next step is to confirm the intended **flip-confirmation** interpretation on the INITIAL BTC/SOL chart packet: identify the governing daily premise, anchor one 4h zone and invalidation, and locate the first opposing objective. Then inspect only the hourly data available at each corresponding decision for the documented flip trigger. Keep zone touch, reaction observed and order eligible distinct. These labels must be frozen before any new outcome evaluation; these already reviewed six cases remain exploratory.

Three remaining user decisions are in the updated review packet. They concern choosing among conflicting existing interpretations—not asking the user to recreate the documented theory. No broad refactor, strategy parameter sweep, orders or JEV calls are needed to reach this checkpoint.
