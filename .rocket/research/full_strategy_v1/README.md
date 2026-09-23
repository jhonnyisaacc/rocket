# Local primary-strategy research

Start with [REPORT.md](REPORT.md), [CHART_REVIEW.md](CHART_REVIEW.md), and
[CONTRACT.md](CONTRACT.md). This is a conditional price-only research interpretation,
not the entire theory or a trading recommendation. No production module is imported.

## Reproduce

Working directory: `/Users/jhonny/rocket/.rocket/research/full_strategy_v1/`.
Existing Python runtime: `/Users/jhonny/nave/.venv/bin/python` (Python 3.12,
matplotlib already installed). No package installation is needed.

```sh
/Users/jhonny/nave/.venv/bin/python research.py capture
/Users/jhonny/nave/.venv/bin/python research.py verify
/Users/jhonny/nave/.venv/bin/python research.py replay
MPLCONFIGDIR=/private/tmp/mpl-cache /Users/jhonny/nave/.venv/bin/python research.py report
/Users/jhonny/nave/.venv/bin/python audit.py
```

`capture` snapshots original inputs and provenance once. `verify` seals the contract
after tests. `replay` reproduces the old baseline, caches deterministic features,
and refuses to overwrite differing immutable results. `audit.py` independently
recomputes all 6,480 features without caches and changes future candles at 18 real
cutoffs to test leakage. It also verifies input/source hashes and paused automation.

The original and retry `capture --probe` outputs preserve two public Hyperliquid
requests per attempt: metadata and BTC hourly coverage. The initial restricted
attempt recorded ConnectError; the authorized network-enabled retry succeeded.
No API key, wallet or paid credits were involved. The returned 4,321 rows include
one outside the completed frozen window; exactly 4,320 in-window bars equal the
original normalized data. This is a new cross-check, not retroactive raw provenance.

API reference: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint

## Freeze boundaries

`contract_seal.json` fixes specification and strategy/execution code before the
new historical replay. `test_audit.py` adds tests afterwards without changing
those sealed files. A future strategy change must use a NEW version/directory,
not edit the sealed v1 or delete its results.

The baseline reproduction intentionally retains the prior simulator's known
funding and boundary limitations. Its ledger is an exact reproduction check,
not the corrected primary simulator's return estimate.

All outputs stay here. Input source paths are verified read-only; changes to
production, orders, commits, PRs, automations or paid providers are out of scope.
