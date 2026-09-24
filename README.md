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
