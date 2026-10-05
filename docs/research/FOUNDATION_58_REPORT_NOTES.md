# Foundation #58 synthetic report interpretation

The current independent review distinguishes tied synthetic gate probabilities
from a unique bottleneck. Concentration has zero estimated pass probability in
all 240 rows of the pinned synthetic surface. Eighteen rows also have zero
incremental-information pass probability. The runner's `min()` chooses the
first listed gate in those ties, so their `binding_gate` label is incremental
information. That label does not establish that incremental information is
uniquely binding or that concentration ceases to constrain those rows.

This note preserves the original report, code, geometry, surface and packet
hashes. It changes no gate, DGP, simulation probability or trial accounting.
Zero full synthetic passes remain conditional on the tested assumptions,
with the recorded per-regime Monte Carlo uncertainty. They are not a real
MOM-002 FAIL or a bound on unconditional real-world power.

Actual feature readiness, authenticated source/publication evidence, human
minimum worthwhile effect and economic-gate role remain separate prerequisites.
No conditional methodology acceptance supplies those values or authorizes
MOM-002 fitting, association inspection or scoring.
