# Full-strategy research v1: primary branch checkpoint

**Verdict: INCONCLUSIVE. No production remedy justified.**

Replayed 6,480 completed four-hour decisions across six assets. Admitted 0 primary-workflow hypotheses; produced 0 policy/path fills.
Do not call zero admissions zero profitability. Net expectancy, economic uncertainty, trade drawdown and mean holding time are unavailable without trades. Price-only hypothetical exposure is zero if there are no admissions; full-context eligibility is UNKNOWN.

## What this establishes

- Theory fidelity improved: locked multi-timeframe premise, explicit zone/reaction and hourly flip replace the old six-candle proxy. However institutional scaling, swing-target confluence and conservative re-entry remain research assumptions—not a certified implementation of the whole theory.
- Executability infrastructure has fixture evidence; no admitted historical primary trades exercise it in this sample. Do not confuse passing unit tests with validated fills or market edge.
- Economic evidence remains the old exploratory baseline. The new interpretation cannot yet be compared economically because it produces no sample. No parameter was relaxed after observing that result.

## Admission funnel (snapshots, not independent opportunities)

| Asset | Decisions | Confirmed impulse | Zone available | Reaction present | Eligible | Sole reaction blocker |
|---|---:|---:|---:|---:|---:|---:|
| BTC | 1080 | 156 | 156 | 0 | 0 | 0 |
| ETH | 1080 | 96 | 96 | 0 | 0 | 0 |
| HYPE | 1080 | 160 | 160 | 0 | 0 | 40 |
| SOL | 1080 | 96 | 96 | 0 | 0 | 0 |
| XRP | 1080 | 180 | 180 | 3 | 0 | 0 |
| ZEC | 1080 | 228 | 228 | 0 | 0 | 18 |

Omitting only the reaction blocker would expose 58 decision snapshots across 2 distinct coin/origin/zone combinations. These are NOT 58 trades. No relaxed PnL test was run.
Reaction-component failures: {"directional_body": 36, "intersects": 58, "wick_ge_body": 35}. Components overlap.

## Reproduced baseline — unchanged known limitations

| Policy, pessimistic hourly ordering | Fills | Mean net R, 20bps | Mean net R, 40bps |
|---|---:|---:|---:|
| immediate | 53 | 0.03747 | -0.00718 |
| retest | 29 | 0.06907 | -0.03544 |

These numbers reproduce the old results exactly, including documented funding timestamp/count and admission-boundary limitations. They are not corrected new estimates or evidence that the full workflow works.

## Coverage and limitations

- 180-day shared frozen sample, 4,320 hours and 1,080 four-hour candles per asset; exact hourly aggregation. Original six-asset acquisition retained normalized data, not full exchange responses. This provenance gap is disclosed, not repaired by pretending today’s download was the original response.
- Nine complete weekly candles consume the first 392 four-hour decision cutoffs per asset. Missing warmup is unavailable, not a failed momentum prediction.
- Archived macro data are sparse: 24 asset-decision joins within recorded availability/expiry. COT snapshots have observation times but incomplete publication metadata. No complete historical context strategy is asserted.
- Present-day instrument metadata is not historical tick/quantity precision. Fee, spread and slippage are explicit scenarios, not measurements. Funding uses entry-notional and timing sensitivity, not historical mark-notional reconstruction.
- Available saved BTC five-minute candles can refine exactly matching hours. Other hours retain two monotone-path sensitivities. Those are NOT exhaustive mathematical bounds over all possible intrabar paths.
- No leveraged account or mark-to-market portfolio is modeled. Closed-trade drawdown would not be account drawdown. No run-frequency profitability claim is made from a setup-visibility check.
- No full economic acceptance test is possible with zero primary trades. Six assets and previously inspected history introduce selection/reuse bias. No prospective collector has been started.

## Next action

Resolve the **daily-impulse versus local-four-hour impulse anchor conflict**, using outcome-hidden daily/4h/hourly overlays and the existing source examples. Audit the overly sparse provisional-terminal confirmation and BEN geometry as interpretation questions—not permission to relax the weekly gate or remove the reaction rule. Freeze a separately versioned contract only if source evidence warrants changing it; do not tune this v1 until it trades.

## Reproduction

Run with `/Users/jhonny/nave/.venv/bin/python research.py capture`, then `verify`, `replay`, `report` from this directory. For charts set `MPLCONFIGDIR=/private/tmp/mpl-cache`. `audit.py` reruns the extended verification suite. All sources and input hashes are local; no network is required for replay.

## Artifact guide

- `CONTRACT.md`, `contract_seal.json`: frozen specification, provenance and timestamp.
- `capture.json`, `inputs/`, `provider_probe*.json`: frozen input provenance and actual API probe responses/errors.
- `decisions.json/.csv`: every decision, all recorded blockers and candidate anchors.
- `ledger.json`, `outcomes.csv`, `summary.json`: complete primary outcome ledger (empty when zero admitted), explicit null performance by asset, period and exclusion.
- `reaction_diagnostic.json`: one-rule eligibility attribution without outcome selection.
- `CHART_REVIEW.md`: six initial primary charts plus legacy success/failure/untriggered illustrations. No invented primary success example.
- `baseline_parity.json`, `test_results.txt`, `verification.json`, `audit.json`: executed verification.

Production, prior experiments, PRs and automation remain unchanged.
