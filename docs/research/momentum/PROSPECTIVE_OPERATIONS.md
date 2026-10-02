# Prospective collection and replay

A real startup capture was saved 2026-10-02 at 20:09:26.580 UTC (17:09:26.580
Buenos Aires), decision_time equal to actual receipt, data_cutoff 20:00 UTC.
Source OK, NO_CANDIDATE, model UNTRAINED/output null. Code c6458e3, feature
schema v1. The subsequent volume-alignment correction advances v2 and never
rewrites that record. See SHADOW_STATUS.json for evidence of current journal
integrity, source hashes, scheduled coverage and enrichment counts.

Runtime files are ignored: `.rocket/momentum/shadow/shadow.sqlite` and
`sources/<sha256>.json`. Explicit output root; no wallet/environment state read.
Raw receipt bytes are content-addressed with exclusive creation. Forecasts
are canonical JSON with SHA-256; DB identity constraints and UPDATE/DELETE
triggers enforce application immutability. Duplicate scheduled calls return
the original record without fetching a different vintage. Conflicting direct
appends fail. Outcomes have separate immutable identities/tables and maturity
checks. This is application-level integrity, not a remote tamper-proof archive.
Keep this checkout and root available for the scheduled collector.

The app heartbeat **BTC momentum prospective shadow**
(`btc-momentum-prospective-shadow`) is ACTIVE: daily at **01:02, 05:02, 09:02,
13:02, 17:02, 21:02 America/Argentina/Buenos_Aires**. Those are 00:02/04:02/
08:02/12:02/16:02/20:02 UTC. Each snapshot targets cutoff+5m and accepts only
actual source receipts before that decision. Records may be written earlier,
after all inputs have arrived; future outcomes are absent. Late invocations
or failed sources persist UNKNOWN rather than reconstructing what was not
recorded. Missed slots during app downtime are coverage gaps, not invented
forecasts. The earlier Crypto futures research loop is PAUSED and was left
unchanged. The new heartbeat does not reopen its experiments.

The snapshot contains candidate state, a causal crossing object when present,
full six-key feature vector, null/missing names, schema/generator/label/model
versions, decision/cutoff/written clocks, commit and module-tree digest, raw
source fingerprint and source status. The startup's snapshot/receipt semantics
are distinct from scheduled decisions. It is not a probabilistic forecast.
No Tier B value is backfilled from a current source. Historical replay never
reads this journal.

From the checkout, with Python 3.12+ and the project dependencies:

```bash
python -m rocket.momentum.collect .rocket/momentum/shadow --startup
python -m rocket.momentum.collect .rocket/momentum/shadow
python -m rocket.momentum.enrich .rocket/momentum/shadow
```

The scheduled command should start cutoff+2m. Only use --startup for a
separately timestamped real current observation. Enrichment waits until the
whole primary 7d horizon matures; it separately saves actual outcome-source
receipt bytes, then appends the label. No-candidate snapshots have no
candidate outcome. No mature candidate exists yet at startup; real later
outcome validation remains pending. Tests exercise mature enrichment and
original forecast preservation with controlled inputs.

The heartbeat stays quiet on healthy unchanged collection and calls attention
to persistent failures/integrity conflicts. It runs deterministic commands;
an LLM supplies neither the candidate nor a probability. Desktop/scheduler
uptime and public network access are operational dependencies. No live market
alert or trade authorization is implied by this collection.

Final committed v2 collector was also executed against a real receipt at 2026-10-02T20:19:06.108000+00:00. Both startup records retain distinct identities; the v1 original is unchanged. The current journal contains two startup snapshots and no mature candidate outcomes; scheduled continuity is still pending.
