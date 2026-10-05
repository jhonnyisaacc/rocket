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
# Autonomous derivatives research governance

The [Research Project](https://github.com/users/jhonnyisaacc/projects/4) is a gated
decision tree with WIP 3. Start with the [charter](docs/research/RESEARCH_CHARTER.md),
[protocol](docs/research/AUTONOMOUS_RESEARCH_PROTOCOL.md), and
[trial ledger](docs/research/TRIAL_LEDGER.md). Minimal machine gates and the
official scoring contract live in [research/governance](research/governance/README.md).
MOM-002 remains Draft/unapproved/unscored. Rocket remains
`READ_ONLY_RESEARCH_ONLY_HUMAN_GATED`; these controls authorize no execution.
