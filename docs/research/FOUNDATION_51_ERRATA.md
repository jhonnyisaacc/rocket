# Foundation #51 overlap documentation correction

The independent review of the exact #51 packet found a prose error in
`docs/research/momentum/REPLICATION_REPORT.md` at source revision
`7c42582168e7538cfac00393bc3ffce54beb21b1`: its comparison says both
14-day interval conventions have 47 components. The frozen
`RECONCILIATION.json` and independent timestamp-only recomputation instead agree
on the following counts.

| Interval convention | 7-day components | 14-day components |
| --- | ---: | ---: |
| Decision start: `[cutoff+5m, cutoff+horizon]` | 128 | 47 |
| Cutoff start: `[cutoff, cutoff+horizon]` | 117 | 45 |

The two 14-day exact cutoff contacts are 2024-12-05 04:00 UTC and
2025-12-15 16:00 UTC. A five-minute shift separates those contacts in the
decision-start convention. Globally spaced candidates remain 107.

This additive erratum preserves the original pinned report, source revision,
packet ZIP and hashes. It changes no population, label, outcome, gate,
synthetic surface or trial accounting. Use the decision-start convention
when interpreting the current 128/47 structural geometry; do not describe
47 as common to both interval conventions.

The review uses established MOM-000 evidence and does not qualify as isolated
MOM-002 admission review. Source-audit limitations remain: authenticated
historical publication, full OI/feature-window completeness and actual
Tier-B readiness require separate evidence. This correction alone does not
accept the foundation, close #50, merge #49 or authorize MOM-002 scoring.

Original independent [decision](../../research/governance/review_decisions/foundation-51/review.json)
and [report](../../research/governance/review_decisions/foundation-51/review.md)
remain REQUEST_CHANGES. A separate exact-artifact addendum must verify this
correction; the original decision is never rewritten.
