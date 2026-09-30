# Futures family experiment admission

Status: `REQUIRED_BEFORE_FUT014`, 2026-09-30. No successor is admitted in
this consolidation pass. The [family audit](FAMILY_AUDIT.md) is the current
decision and all new outcome-trial budgets are zero. This is a written,
reviewed repository gate; it is not a runtime permission or trading control.
The proposing agent cannot approve its own experiment.

## Admission packet and decision

Before registering FUT-014 or any later contract, add a proposal under
`admissions/` with all nine sections below. Record `ADMITTED`, `DENIED` or
`DEFERRED`, reasons, proposer, independent reviewer, review date and exact
reviewed commit/dataset/specification fingerprints. `DEFERRED` is a block,
not provisional approval. Retain denied proposals and their reasons in the
admission ledger. Approval applies to that exact packet; a changed mechanism,
feature, chronology, source, budget or rule requires new review.

1. **Distinct mechanism.** Name the existing family and inherited failed
   attempts. Explain the causal economic difference, not a new indicator,
   paper, label, threshold, clock or horizon. A renamed family inherits its
   parent's evidence until the independent reviewer accepts the distinction.
2. **Evidence-independent motivation.** Cite the external/structural prior
   and when it was formed. Declare every Rocket outcome already inspected.
   Favorable slices, near misses and model-generated plausibility are
   insufficient; prior-inspired exact replication may be considered only
   with explicit selection debt and reopening evidence.
3. **Point-in-time observability.** Define event, publication/receipt,
   feature-completion, decision, entry and exit clocks. Show that all feature,
   universe and wallet-class inputs were available before each decision.
   Later API history or stable full-sample classification is not proof.
4. **Source feasibility.** Provide bounded return-free source checks, hashes,
   missing/duplicate and revision policy, delisting/survivorship semantics,
   mapping and acquisition plan. Source checks must not condition on future
   returns. Expensive acquisition requires a separately reviewed cost plan.
5. **Execution compatibility.** State the current directional scan and intended
   venue assumptions; bound delay, fees, spread/impact, funding and capacity.
   Multi-leg/multi-venue products require a separate approved pillar before
   scoring. A maker fee or observed mid cannot stand in for achievable fills.
6. **Cheap falsifier.** Freeze the minimum sample, primary statistic, controls,
   economic hurdle, uncertainty/concentration checks and kill conditions.
   Explain why this small test can kill the mechanism before broad backtests.
   No result-driven secondary endpoint may override failure.
7. **Fresh evaluation chronology.** List inspected periods and feature/outcome
   combinations, related-family overlap, proposed discovery and chronological
   checks. A previously scored calendar remains program-inspected even if a
   new feature was not conditioned there. The 2026 final holdout is sealed;
   access requires constitution-authorized promotion review for a frozen
   candidate, never exploratory admission. Declare overlapping-label embargo.
8. **Family budget and stop rule.** Default grant is **one** meaningful cheap
   outcome trial, with explicit maximum data cost and allowed preparatory
   steps. Source repairs/replays share that admission and cannot extend its
   economics. Every result suspends admission and sets remaining budget zero
   pending independent review. A family with **two failed or nonrobust material
   attempts** is suspended for ordinary parameter/transfer continuation;
   any further attempt requires recorded independent new evidence or a
   demonstrated invalid prior test, reviewer-approved reopening and operator
   approval of the exception. Attempt count is not an independence claim.
   Existing trend and all-wallet voluntary-close families already exceed or
   reach this stop rule. Single failed exact rules also have no automatic retry.
9. **Independent review.** A human reviewer or separately authorized reviewer
   different from the proposer checks all eight requirements, inherited
   failures and disguised rescue risk before registration and again before
   outcome scoring. Record each check and reasons. Permission to trade remains
   outside this gate. Repository review is the trust boundary; a self-authored
   reviewer name or asserted operator approval is invalid.

Registration and scoring require an `ADMITTED` decision bound to the current
packet. Once admitted, freeze the contract before any conditioned outcome.
After a result, append it to experiment and family ledgers, record the failed
or passed gates and actual spend, and stop. A promising result does not itself
grant replication, holdout access or implementation. Reopen only through a
new documented review; never delete the prior denial or failure.

## Admission ledger

| Date / proposal | Decision | Evidence and reason | Reviewer / budget |
| --- | --- | --- | --- |
| 2026-09-30 / automatic FUT-014 continuation from FUT-013 or unresolved source scouts | `DENIED` | No distinct proposal meeting nine requirements exists. Nearby parameters, fitted-model substitution, OI direction by assertion and source availability do not qualify. No strategy is proposed or scored. | Operator's consolidation instruction; independent successor review still required; 0 trials. |
| 2026-09-30 / carry as the next directional FUT experiment | `DENIED_FOR_CURRENT_PRODUCT` | Two-venue hedged payoff requires separate product architecture; [source/product classification](CARRY_SOURCE_FEASIBILITY.md). No carry outcome scored. | Operator's scope constraint applied; 0 directional trials. |

These are recorded scope denials, not fabricated independent approvals. Future
packets must preserve them. The current pass admits only preservation,
consistency edits, offline reproduction of already inspected outputs and CI
hygiene. It does not authorize new sources, conditioned outcomes or FUT-014.
