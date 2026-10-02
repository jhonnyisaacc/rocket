# Rocket

Read-only market research engine. Bot-runtime agnostic.

```text
any bot  →  rocket <workflow> --json  →  ResearchResult  →  adapter presents
```

Safety: `READ_ONLY_RESEARCH_ONLY_HUMAN_GATED`. No orders, no signing, no automatic holdings or watch changes.

Design: [docs/ROCKET_PLAN.md](docs/ROCKET_PLAN.md)

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/rocket status
.venv/bin/pytest -q -m 'not integration'
```

Secrets come from the process environment (existing names). Rocket never deletes or rewrites them. Callers pass private state paths explicitly.

## Research data

Large research payloads (for example the ~1GB Solana memecoin follower-study
captures) live outside git in the public dataset
[jhonnyisaacc/rocket](https://huggingface.co/datasets/jhonnyisaacc/rocket),
laid out under the same `docs/research/...` paths they were captured from.
Small manifests and code stay in the repo; anything over ~1MB goes to the
dataset. Fetch what you need, for example:

```bash
hf download jhonnyisaacc/rocket --repo-type=dataset \
  --include 'docs/research/memecoin/data/*'
```

## Momentum research

The current momentum research roadmap is
[Momentum research](docs/research/momentum/MOMENTUM_RESEARCH.md).
It separates point-in-time snapshots, deterministic BTC candidates, future-only
labels and gated conditional prediction. Experiment 0 failed its independent
sample gate; no predictive model or execution is admitted. See the
[final report](docs/research/momentum/MOMENTUM_FINAL_REPORT.md),
[historical negative evidence](docs/research/momentum/EVIDENCE_AUDIT.md) and
[prospective collection](docs/research/momentum/PROSPECTIVE_OPERATIONS.md).
The staged crypto scan remains an operational research readout; its older
futures artifacts preserve evidence and do not define a competing active
momentum experiment roadmap.
