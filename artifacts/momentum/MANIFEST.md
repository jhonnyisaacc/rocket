# artifacts/momentum — MOM-000 provenance

`mom000_census.json` is the frozen output of Experiment 0 (mom000-v1),
produced 2026-10-02 by `scripts/research/momentum_census.py`.

- candidate_generator: candgen-v1; label_contract: label-v1
- source_fingerprint (sha256 over normalized 1h closes): `0573411bcc6b700f584ce5f13d65e928`
- gate verdict: STOP (`permit_experiment_1: false`)
- n_1h_bars 61300, n_4h_bars 15307, n_crossings 354, n_spaced 107
- quarantined_rows 9 (vendor anomalies, detail inside)

## Reproduction

Data directory is outside the repo (gitignored raw archives):

```bash
# 1. acquire checksum-verified Binance archives (spot 2019-01..2025-12,
#    perp + funding 2020-01..2025-12, daily metrics 2020-09-01..2025-12-31)
./.venv/bin/python scripts/research/momentum_acquire.py /tmp/momdata

# 2. re-run the census
./.venv/bin/python scripts/research/momentum_census.py /tmp/momdata artifacts/momentum/mom000_census.json

# 3. verify the gate verdict and fingerprint match this file
```

Live-data shadow collection (prospective, append-only):

```bash
./.venv/bin/python scripts/research/momentum_shadow.py /tmp/momdata/shadow --once
```

Unit tests for all primitives:

```bash
./.venv/bin/python -m pytest tests/test_momentum.py tests/test_momentum_pit.py -q -p no:cacheprovider
```
