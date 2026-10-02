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

## Research

The current crypto futures research hierarchy begins with the [research constitution](docs/research/RESEARCH_CONSTITUTION.md), [futures pillar](docs/research/futures/FUTURES_PILLAR.md), and [single frontier](docs/research/futures/FUTURES_FRONTIER.md). Historical PRs remain evidence; no research result enables execution.

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
