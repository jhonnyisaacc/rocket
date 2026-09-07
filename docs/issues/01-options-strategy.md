# Options strategy not validated — do not schedule (crypto + equity)

Status: open tracking issue. Not a V1 live agent job.

## Why it is not live

- Crypto (BTC/ETH) and equity options were separate domains; neither produced a validated edge. Evaluate cannot write `VALIDATED`.
- Reported metrics are `GROSS_UNCOSTED`: no fees, spread, assignment, pin risk, or crypto-options funding in the P&L. A positive mean return is not an edge.
- No autonomous live options snapshot path comparable to shorts. Normal use required handcrafted snapshots; missing IV/RV/`defined_risk` or late `available_at` → `INSUFFICIENT_EVIDENCE`, so a PIT live series never accumulated.
- The large NAVE `options/` package (gem finder, walkforward, visualization, ticker registry, opportunities CLI) was a parallel platform, not a scientific result. Merge-readiness treated tiny samples (`trades >= 2–3`) as “approved” — overfitting, not validation.
- n=30 and mean>0 was explicitly rejected as a PROMISING gate.
- Stale volatility (>1 day), unknown availability, and out-of-scope underlyings fail closed.

## Keep in Rocket

`rocket options scan` and `rocket options evaluate` as research primitives. Unschedulable. Never auto-`VALIDATED`. Crypto and stocks stay separate.

## Do not

Enable a cron/agent job, mix stocks and crypto chains, or port gem-finder/walkforward as if they were the strategy.
