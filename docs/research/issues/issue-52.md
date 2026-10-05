## Question

Can CFTC positions be used only after defensible publication/receipt availability?

## Why now

Existing CFTC availability semantics are a correctness bug that could contaminate future PIT research.

## Scope

Accept the fix already in #49 and get it to main through independent PR review. Audit rocket/providers/cftc.py, OpenBB actual receipts, as-of versus publication, UNKNOWN/LATE behavior, source hashes and regressions; trace FUT-005 lineage.

## Inherited evidence

https://github.com/jhonnyisaacc/rocket/pull/49; https://github.com/jhonnyisaacc/rocket/pull/38; https://github.com/jhonnyisaacc/rocket/blob/7c42582168e7538cfac00393bc3ffce54beb21b1/docs/research/momentum/CFTC_LINEAGE_AUDIT.md

## Unlock condition

Existing correctness bug; data work permitted independently of new alpha admission.

## Success condition

Tests prove no future receipt is eligible at a past decision. FUT-005 independent ZIP/+10d/special-release lineage accepted; annual vintage limitations preserved.

## Failure condition

Future availability leaks through, or provenance remains UNKNOWN but treated as historical PIT.

## Kill condition

Disable affected CFTC historical eligibility until fixed; preserve FUT-005 failure. Do not reopen COT or score a conditional successor.

## Dependencies

#49 provider correction and pinned #38 FUT-005 lineage. No #54 or full scientific admission package dependency. Separate identities are tracked in #60; implementation/testing may proceed meanwhile.

## Trial impact

0 new trials; FUT-005 remains historical failed trial.

## Proposer

Human research mandate; existing authors credited in linked PRs.

## Implementer

Codex or equivalent; implementation already present in #49 where specified.

## Reviewer

Different agent/person reviews the provider fix, tests and CI. MAINTENANCE does not require MOM-002 isolated scientific admission review or #54 completion. Protected GitHub merge still requires a real distinct approving actor.

## Evidence links

https://github.com/jhonnyisaacc/rocket/pull/49; https://github.com/jhonnyisaacc/rocket/pull/38; https://github.com/jhonnyisaacc/rocket/blob/7c42582168e7538cfac00393bc3ffce54beb21b1/docs/research/momentum/CFTC_LINEAGE_AUDIT.md

Safety: `READ_ONLY_RESEARCH_ONLY_HUMAN_GATED`. No scoring, trading or live execution is authorized by this issue. WIP limit: 3.

## Review Tier

MAINTENANCE; Trial Budget 0, Trials Consumed 0; Gate Source REVIEW. One implementer, meaningful regressions, CI and a different agent/person code review. No isolated scientific packet.

