# Futures pillar

Status: authoritative current doctrine, 2026-09-24. Read the [constitution](../RESEARCH_CONSTITUTION.md), then this pillar, then the [frontier](FUTURES_FRONTIER.md). The [historical evidence](HISTORICAL_EVIDENCE.md) and old PRs support conclusions but do not set the next task.

## Goal and boundary

Discover, validate, and eventually integrate a crypto-perpetual strategy whose deterministic `rocket crypto scan --json` decision can express `ENTER_LONG`, `ENTER_SHORT`, `WAIT`, or `NO_TRADE`, with asset, forecast, regime, setup, trigger, invalidation, objectives, risk and portfolio context, reasons, unresolved conditions, and evidence. Execution stays disabled until separately authorized. Current production code is a legacy top-100/Hyperliquid funnel and conservative direction summary; it is not a validated strategy and is not silently replaced by research output.

## Architecture and prior

Forecast → opportunity ranking → derivatives/regime context → entry timing → risk/portfolio → decision. Start with a continuous multi-horizon time-series trend forecast, simple realized/EWMA volatility normalization, point-in-time tradable universe, and explicit portfolio construction. Forecast strength and position size are separate. Test relative strength, funding/OI, COT, and individual Pana timing components only as incremental ablations after the base signal is measurable. COT can remain context. No ML directional engine or broad parameter search at this stage.

Research may use deeper Binance USD-M perpetual history; Hyperliquid is the intended execution venue and later overlap/forward-shadow validation target. Venue transfer is an empirical question. Data coverage, funding, delistings, and costs must be verified rather than assumed.

## Established boundaries

The full Pana stack admitted no primary sample in PR #28 and PR #31. This rejects it as the starting baseline, not each pullback, reaction, or confirmation component. Staged `ZONE` is a useful state representation, but scoring it as an entry lost after costs. The tested `TheoryV2` implementation also lost. The frozen `daily-trb-50d-v1` combined event mean was negative after 20bps and 40bps plus funding; that exact rule is rejected, not trend, momentum, or all breakouts. The standalone cross-sectional quintile implementation did not validate; relative strength remains an untested ranker. Details, limits, and reopening rules are in [historical evidence](HISTORICAL_EVIDENCE.md).

## Promotion

Every new experiment receives an ID and frozen question, mechanism, falsifier, data/universe and cost rules before outcome inspection. A cheap gate needs causal data, realistic costs, chronological OOS, asset/period breakdown, concentration, simple baseline, ablation, and broad parameter stability. Strong survivors earn walk-forward and uncertainty work; only promotion candidates receive an untouched final holdout and frozen prospective shadow. Never use a portfolio throttle or an ex-post side/coin slice as signal validation. Preserve all failures and trial count.

Current strategy state: `RESEARCH`. There is no validated `ENTER_*` contract. The only active question is in [FUTURES_FRONTIER.md](FUTURES_FRONTIER.md).
