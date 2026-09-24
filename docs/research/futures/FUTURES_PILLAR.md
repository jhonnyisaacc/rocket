# Futures pillar

Status: authoritative current doctrine, 2026-09-24. Read the [constitution](../RESEARCH_CONSTITUTION.md), then this pillar, then the [frontier](FUTURES_FRONTIER.md). The [historical evidence](HISTORICAL_EVIDENCE.md) and old PRs support conclusions but do not set the next task.

## Goal and boundary

Discover, validate, and eventually integrate a crypto-perpetual strategy whose deterministic `rocket crypto scan --json` decision can express `ENTER_LONG`, `ENTER_SHORT`, `WAIT`, or `NO_TRADE`, with asset, forecast, regime, setup, trigger, invalidation, objectives, risk and portfolio context, reasons, unresolved conditions, and evidence. Execution stays disabled until separately authorized. Current production code is a legacy top-100/Hyperliquid funnel and conservative direction summary; it is not a validated strategy and is not silently replaced by research output.

## Architecture and prior

Forecast → opportunity ranking → derivatives/regime context → entry timing → risk/portfolio → decision. The first continuous multi-horizon time-series trend baseline used simple EWMA volatility normalization, a point-in-time tradable universe, and explicit portfolio construction; it did not survive cost robustness. A separately frozen spot/perpetual basis factor then failed its gross-information gate. Forecast strength and position size remain separate. Seek an independently motivated causal directional mechanism with an early gross falsifier before adding relative strength, funding/OI, COT, or Pana timing as incremental ablations. A distinct funding or positioning mechanism requires its own source and trial; COT can remain context. No ML directional engine or broad parameter search at this stage.

Research may use deeper Binance USD-M perpetual history; Hyperliquid is the intended execution venue and later overlap/forward-shadow validation target. Venue transfer is an empirical question. Data coverage, funding, delistings, and costs must be verified rather than assumed.

The 2022–2025 Binance archive is now acquired and checksum verified for the first trend experiment. Its raw daily files retain flat, zero-volume rows after some contracts cease trading. Historical membership therefore requires observed tradability and funding, while exposed positions around delisting require a dated settlement outcome rather than a flat-bar exit or silent exclusion. This is a data-methodology fact, not an edge result.

The first [FUT-001 2025 OOS cheap gate](experiments/FUT-001-OOS.md) used the frozen multi-horizon forecast and predeclared bounds for 70 historical settlement events. Its arithmetic mean at 20bps was slightly positive but uncertain; compounding was negative, and the mean turned negative at 40bps throughout the settlement sensitivity range. This exact portfolio is `COST_SENSITIVE_NOT_PROMOTED`. The 60-day control had a higher one-year point estimate but a wide uncertainty interval and negative discovery history; it is not a selected successor. The intended Hyperliquid venue and 2026 holdout remain untested.

The selected 60-day control then failed its [frozen earlier-year replication](experiments/FUT-002-RESULT.md): 2021 was positive, but 2022 net was negative at 20bps across the full settlement stress. Its combined two-year gain cannot satisfy the predeclared requirement for both years. It is `REPLICATION_FAILED_2022` and remains unpromoted.

The old multi-horizon baseline's [Bybit 2022 venue-transfer diagnostic](experiments/FUT-003-RESULT.md) found a weak positive gross statistic and tiny positive 20bps arithmetic mean, but negative compounding and a negative 40bps mean across settlement stress. This is another cost-sensitive result, with no stable directional or executable edge established. Bybit's 2022 sample is a different venue in a calendar year already inspected on Binance, not a new untouched regime.

The distinct [FUT-004 spot/perpetual basis factor](experiments/FUT-004-RESULT.md) had a negative 2022 daily gross mean across predeclared settlement bounds and an approximately flat 2023 mean. It failed the frozen two-year gross-information gate before costs, so its conditional 2024/2025 tests were not run. This closes the tested one-day high-basis-long/low-basis-short perpetual factor, not every dated-futures basis or funding-carry idea.

The [FUT-005 CME BTC positioning-change trial](experiments/FUT-005.md) is frozen before COT-conditioned outcomes. Its signed prior comes from a published pre-2023 study, while the [source audit](COT_SOURCE_FEASIBILITY.md) establishes report release lags, including exceptional 2023/2025 delays. It remains an unscored BTC-only hypothesis, not a proven COT regime feature or a validated strategy.

## Established boundaries

The full Pana stack admitted no primary sample in PR #28 and PR #31. This rejects it as the starting baseline, not each pullback, reaction, or confirmation component. Staged `ZONE` is a useful state representation, but scoring it as an entry lost after costs. The tested `TheoryV2` implementation also lost. The frozen `daily-trb-50d-v1` combined event mean was negative after 20bps and 40bps plus funding; that exact rule is rejected, not trend, momentum, or all breakouts. The standalone cross-sectional quintile implementation did not validate; relative strength remains an untested ranker. Details, limits, and reopening rules are in [historical evidence](HISTORICAL_EVIDENCE.md).

## Promotion

Every new experiment receives an ID and frozen question, mechanism, falsifier, data/universe and cost rules before outcome inspection. A cheap gate needs causal data, realistic costs, chronological OOS, asset/period breakdown, concentration, simple baseline, ablation, and broad parameter stability. Strong survivors earn walk-forward and uncertainty work; only promotion candidates receive an untouched final holdout and frozen prospective shadow. Never use a portfolio throttle or an ex-post side/coin slice as signal validation. Preserve all failures and trial count.

Current strategy state: `RESEARCH`. There is no validated `ENTER_*` contract. The only active question is in [FUTURES_FRONTIER.md](FUTURES_FRONTIER.md).
