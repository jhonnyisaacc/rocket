# MOM-002 pre-outcome power and gate feasibility audit

Before a terminal one-shot experiment is frozen, verify that its gate package
can detect effects large enough to matter. This is methodology, with trial
budget **0** and trials consumed **0**. It does not admit or score MOM-002.

The audit distinguishes predictive information, economic evidence and the
probability of passing every gate simultaneously. Repository contracts remain
authoritative; the audit cannot amend a threshold, declare a real PASS/FAIL,
or choose whether economic evidence should be terminal or descriptive.

## Data boundary

Allowed: candidate identities/timestamps/directions, fixed annual folds,
7d/14d component membership, original 107 spaced identities, causal training
sizes, frequency, cap arithmetic, source coverage, feature availability and
missingness, causal scale S, and feature-feature structure. Existing MOM-000
aggregate findings stay documented but never calibrate a synthetic DGP.

Forbidden: real future returns, y, binary labels, MFE/MAE, feature/outcome
associations, fitted real forecasts, and real gate results. The simulation
accepts only a strict structural JSON schema; it has no price/archive loader,
network client, scorer import or outcome-file option. Tests use synthetic
fixtures exclusively.

The separate geometry exporter loads only checksum-pinned spot ZIPs and
causal generator definitions from the frozen MOM-000 commit. It strips all
forward-label definitions before execution, disables acquisition, checks all
84 existing ZIPs/receipts, and never opens census/results/reconciliation
outcome artifacts. Each candidate uses only its causal prefix. The exported
manifest records source/code hashes; it contains no real feature values or
future prices. Horizon availability uses timestamp coverage only.

## Synthetic assumptions and interpretation

Use fixed seeds, r = 0/.05/.10/.15/.20/.25/.30/.40, independent Gaussian,
14d-cluster Gaussian, variance-normalized Student-t(3), and UP/DOWN asymmetric
scenarios. r denotes nominal oracle signal strength, not guaranteed fitted
OOS correlation. Synthetic six-feature ridge models and B0/B1/Tier-A
benchmarks use the proposal's mean-loss alpha=1, direction intercepts,
training-only standardization/weights, causal annual folds and frozen score
thresholds/caps. Cluster inference uses 2,000 paired whole-component bootstrap
draws, seed 20261002, retaining duplicate-cluster replicate weights and the
5% undefined rule. Monte Carlo probabilities include binomial uncertainty.

Synthetic economic mean/drift varies separately from r, with volatility/path
assumptions recorded explicitly; there is no unique correlation-to-tradable-return mapping. Synthetic
Brownian bridges conditional on synthetic endpoints approximate adversity;
their hourly grid omits intrahour extremes and cannot establish the real MAE
distribution. Full PASS is conditional on this proxy; the separate full-pass
probability without adversity is an upper bound under the remaining synthetic
assumptions. Costs remain the proposed
40bp; the audit never tunes scenarios using MOM-000 realized outcomes.

Actual six-feature completeness and source-readiness acceptance are pending.
Report complete-case and exogenous missingness scenarios as assumptions,
including deterministic geometry/cap ceilings. Never label assumed coverage
as verified real readiness. An idealized positive power estimate is conditional
on the DGP; weak power under these assumptions is a warning, not a real FAIL.

## Disposition

Allowed audit conclusions: GATE_PACKAGE_FEASIBLE;
GATE_PACKAGE_ONLY_DETECTS_VERY_LARGE_EFFECTS;
GATE_PACKAGE_UNDERPOWERED_FOR_STATED_QUESTION;
INDETERMINATE_ASSUMPTIONS_REQUIRED.

If underpowered, MOM-002 becomes NEEDS_PRE_RESULT_GATE_REVIEW, with no trial
consumption. Unknown minimum effect/readiness/path assumptions require
INDETERMINATE_ASSUMPTIONS_REQUIRED and pre-result review; they do not justify
a claim of full feasibility. The human decides the minimum worthwhile effect
and, after this audit, whether economics is terminal or descriptive. Finalize
and version any pre-result changes, then give #54 only that final packet.
After independent approval and official freeze, no gate changes are allowed.

MOM-002 admission/freeze requires #51 foundation acceptance, Tier-B readiness,
overlap acceptance, this completed/reviewed audit, finalized pre-result
contract changes, recorded near-term human decisions, and exact independent
review. MOM-002 FAIL still rejects the whole downstream branch; no MOM-003.
