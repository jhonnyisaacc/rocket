# Memecoin experiment ledger

Append entries; do not overwrite a frozen design or result. Fields for every future entry: ID, parent, question, mechanism, falsifier, lifecycle timestamp/window, feature schema, label, protocol/fee versions, dataset fingerprint, execution model, metrics, temporal split, result, failure attribution, status, allowed/forbidden conclusion, next implication, git SHA.

## MC-001 — point-in-time early panel gate

| Field | Frozen value |
| --- | --- |
| Parent | Historical #27/#30 audit; no inherited threshold |
| Question | Can Rocket observe a covered early-launch universe with features actually available at decision time? |
| Mechanism | Raw create/trade receipts plus ordered on-chain state provide early features without future leakage. |
| Cheap falsifier | Missing creation coverage, unknown receive delay, unsupported account versions or unavailable source provenance. |
| Lifecycle window | To be frozen before a prospective collection session; creation through pre-graduation. No retrospective fixture is silently treated as live. |
| Feature/label | `rocket.memecoin.pit-snapshot.v1`; no outcome label joined yet. Later label: size-aware realizable return and separate protocol survival/risk. |
| Protocol / fee | Record per event; unknown remains unknown. |
| Dataset fingerprint | None: the prospective cohort has not been captured. Individual rows will be hashed by the snapshot builder. |
| Execution | Disabled. Later simulator must pin protocol fee, size, latency, slippage, failure and exit rules. |
| Baseline / metrics / split | Age/curve-only baseline; coverage and latency first, then temporal OOS ranking and net expectancy. Split cannot be frozen until a collection window exists. |
| Result / failure attribution | `KNOWN` for the bounded MC-001 window: 2,458/2,458 inner-slot signatures matched; six creates/437 trades decoded; 113/113 native non-Mayhem state transitions and 208/208 observed quotes reconciled. Initial 8 MiB capture failed its disk bound; the completed session used 32 MiB. See [result](experiments/MC-001-RESULT.md). |
| Allowed conclusion | A read-only prospective early-event stream can be captured and audited for a short window; the data contract rejects late or unprovenanced features. |
| Forbidden conclusion | Any early predictive signal, graduation alpha, trade expectancy or `ENTER` decision. |
| Next implication | Run the predeclared longer MC-002 collection and quote baseline; test regime coverage and execution beyond the short calibration. |
| Git SHA | To be filled by PR commit; design created on 2026-09-24. |

## MC-002 — five-second curve-progress / costed quote proxy

Parent MC-001. Status `OPEN` / no promotion. [Frozen question, mechanism, falsifier, population, five-second features, 60-second label approximation, 70/30 temporal split, costs and forbidden conclusion](experiments/MC-002-FROZEN.md). [Result and evidence](experiments/MC-002-RESULT.md): capture-manifest SHA-256 `eecafe4a98590184e8d88963cd195532480bfd80c394f9fc3a26658923e429da`; 104 creates, 41 scored, 19 quoted, 22 censored. Evaluation had three numeric quote outcomes. Failure attribution: `DATA_LIMITATION` (small numeric and temporally held-out sample), `EXECUTION_UNREPRODUCIBLE` (static-state proxy and unavailable exits), not `NO_SIGNAL`. Allowed conclusion: the current simple curve-progress rank is not promoted. Forbidden conclusion: a validated profitable strategy or proof that all early features lack signal. The original misclassified-exit result and corrected result are both in the archive. No frozen clock, size, cost or rank was retuned.

## MC-003 — exit feasibility and replication

Parent MC-002. Status `REJECTED` as an entry basis. [Frozen design](experiments/MC-003-FROZEN.md) and [result](experiments/MC-003-RESULT.md). A new 300-second cohort yielded 102 creates, 52 scored names, 40 quoted exits and 12 exit-unavailable names. The unchanged rank's held-out all-quoted mean was −8.99% (11); top-quartile mean −8.05% (3). The zero-recovery stress mean was −33.67% for all 15 and −31.42% for the top four. Failure attribution: `NO_SIGNAL` for this simple rank under the frozen quote proxy; `EXECUTION_UNREPRODUCIBLE` for actual fills and zero-recovery valuation; `DATA_LIMITATION` for cohort duration and held-out size. No model is promoted. Raw and second-provider index evidence are archived; implementation commit `0f81aae`.

## MC-004 — transaction accounting calibration

Parent MC-003. Status `ACCEPTED` for bounded protocol/cost calibration, not for strategy entry. [Frozen selection](experiments/MC-004-FROZEN.md) and [result](experiments/MC-004-RESULT.md). All 56 selected transactions were retrieved and matched stream signature/slot. One transport version amendment was recorded before analysis without changing the sample. Forty-seven of 48 single-event token transfers reconciled to the event amount; the remaining create-and-buy lacked a pre-balance. Fifteen of 48 single-event network fees exceeded the older 155,000-lamport scenario. Failure attribution: `EXECUTION_UNREPRODUCIBLE` remains for hypothetical Rocket inclusion and exit fills; not a signal test. Raw responses and deterministic replay are archived.

## MC-005 — early net flow on an independent covered panel

Parent MC-003/MC-004. Status `FROZEN` before acquisition. [Design](experiments/MC-005-FROZEN.md): a 600-second bounded prospective capture, one early net buy-minus-sell score, the inherited clocks and population, a 70/30 chronological split, explicit exit-unavailability risk, zero-recovery stress and 155,000/1,000,000-lamport per-leg fee scenarios. No result exists until the new capture passes the protocol and coverage gate.
