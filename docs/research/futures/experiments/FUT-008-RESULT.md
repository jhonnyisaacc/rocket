# FUT-008: frozen two-day OKX near-touch pressure result

Status: `GROSS_INCREMENTAL_AND_NET_FAILED`, 2026-09-24. The [rule and
gates](FUT-008.md) were frozen in `d77c052` before pressure-conditioned
returns were read; the deterministic scorer was committed in `aeb69b0`
before it was run. Run:
`python3 -m research.futures.fut008_score .rocket/futures_data/okx --output .rocket/futures_data/okx/fut008_result.json`.
The ignored local JSON has SHA-256
`765fc3003a8acfe43beb8be07b6a2e544b611abd9fe499d9ae60215d2df298c3`.
Source file hashes and timestamp rules are in the frozen contract.

| Fixed UTC day | Eligible / scheduled | Triggers | Trigger short mid gross | Trigger minus all-short mid gross | Trigger bid-to-ask gross | Trigger net, 5 bp/side | Trigger net, 10 bp/side |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2023-04-01 | 286 / 286 | 107 | −0.251 bp | −0.233 bp | −0.286 bp | −10.286 bp | −20.286 bp |
| 2024-09-01 | 286 / 286 | 116 | +0.708 bp | −0.318 bp | +0.690 bp | −9.310 bp | −19.310 bp |

The minimum 20-trigger gate passed on both days. All 572 scheduled
intervals were eligible with no unresolved entry or exit. The two UTC
days contained 375,360 and 1,331,285 trades, respectively, and all
1,440 trade minutes each. The combined triggered 10 bp/side touch-to-touch
net was **−19.778 bp per trade**. Both daily economic gates failed, so
`passed_all_frozen_gates=false`.

The all-interval short mid-gross controls were −0.018 bp in 2023 and
+1.026 bp in 2024; the simpler net-sell-only mid-gross controls were
+0.038 and +0.954 bp. Thus the 2024 positive triggered gross was weaker
than both controls. The always-short 5 bp/side touch net was −10.053 and
−8.992 bp, respectively, while the simpler flow-only touch net was −9.997
and −9.063 bp. Cash is zero. Triggers occurred across all 24 hours on
both days; the longest consecutive runs were five and nine decisions.
The 2024 pressure ratio was heavy-tailed (mean 495.8, maximum 48,456),
which reflects a small displayed-best-bid denominator in some snapshots;
the frozen threshold is unchanged.

This is an optimistic execution proxy: the short sells at the displayed
best bid and buys at the displayed best ask after the fixed delay. Spread
is included, but market impact, order rejection, extra latency and funding
are omitted. Adding them cannot rescue the negative scored net under this
fill model. The source L2 feed lacks sequence numbers, and cross-feed
reception order is unobserved. Two days are a cheap falsifier of the exact
rule, not an independent-regime confidence interval or a refutation of
the source paper's short-horizon regression or passive-buy toxicity.

**Decision:** close this exact five-minute taker-short contract. Do not
select the 2024 day, adjust the threshold or horizon, invert the side, or
substitute assumed maker fills. The conditional 2025-01-01
pressure-conditioned result and the 2026 holdout were not read. A future
entry-avoidance test would require an independently validated base and a
new frozen incremental contract. No live decision or production change.
