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
| Result / failure attribution | `OPEN` / `DATA_LIMITATION`: `main` has a spool but no subscribed decoded launch stream or coverage proof. |
| Allowed conclusion | Existing data contracts can reject late or unprovenanced features. The sample requirement is defined. |
| Forbidden conclusion | Any early predictive signal, graduation alpha, trade expectancy or `ENTER` decision. |
| Next implication | Build and audit a bounded read-only collection session, then freeze a feature/label experiment. |
| Git SHA | To be filled by PR commit; design created on 2026-09-24. |
