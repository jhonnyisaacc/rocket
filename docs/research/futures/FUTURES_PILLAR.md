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

The [FUT-005 CME BTC positioning-change trial](experiments/FUT-005.md) was frozen before COT-conditioned outcomes. Its signed prior came from a published pre-2023 study, while the [source audit](COT_SOURCE_FEASIBILITY.md) established report release lags, including exceptional 2023/2025 delays.

Its subsequently frozen [2023–2024 result](experiments/FUT-005-RESULT.md) failed the 2023 gross and net gate: 2023 gross mean daily return was −0.07429% and 20bps net was −0.09036%. The 2024 net arithmetic mean was positive but compounded return was negative and gains were Q1 concentrated. This closes the exact standalone paper-signed COT-change trade after conservative release delay; COT as context or a separately tested incremental feature remains open. Conditional 2025 COT outcomes were not read.

The [quarter-hour order-flow paper](https://arxiv.org/html/2607.09426v2)
supplied a distinct intraday prior. Its first-ten-second *opening forecast*
averaged less than one basis point gross, below ordinary taker fees; its
post-bin four-to-twelve-hour imbalance regression was not a trading result.
The [FUT-006 contract](experiments/FUT-006.md) therefore froze a bounded
post-study, delayed-entry twelve-hour BTC/ETH test before reading conditioned
outcomes. Its [result](experiments/FUT-006-RESULT.md) found a pooled mean
**−2.5332 bp gross** and **−7.4381 bp after 5 bp-per-side turnover and
funding** across 122 November–December 2024 intervals. BTC and ETH diverged
strongly; the pooled gross and net cheap gates failed. Close this exact
always-signed order-flow contract, with no asset, month, sign, clock or
threshold rescue. No conditional 2025 order-flow result was read.

The [funding product/source check](FUNDING_DIRECTION_SOURCE_SCOUT.md) found
that the published high-return carry trade requires a spot hedge, so it is
not evidence for a standalone short-perpetual decision. A separate 2026
study reports a BTC one-day spot-return association after funding in the
lower historical decile but does not model execution. The
[FUT-007 contract](experiments/FUT-007.md) froze an ETH perpetual
asset-transfer test with a full-hour delay, prior 180-day funding rank,
actual funding and target-change costs. Its [result](experiments/FUT-007-RESULT.md)
found only 13 triggered 2023H2 days against a frozen minimum of 15; its
2024 sample had 52 triggers but negative mean event gross, negative
event-minus-unconditional gross, and negative net after costs. The exact
once-daily lower-tail ETH trade is closed. Conditional 2025 outcomes and
the 2026 holdout remain unread.

The [FUT-008 near-touch pressure pilot](experiments/FUT-008-RESULT.md)
tested a frozen five-minute OKX BTC perpetual taker short after recent net
selling exceeded displayed best-bid quantity. On the fixed 2023 and 2024
days it had 107 and 116 eligible triggers, but mid-price gross performance
was −0.233 and −0.318 bp below the always-short control, respectively.
The optimistic bid-entry/ask-exit proxy lost −10.286 and −9.310 bp per
trigger after 5 bp per side. The exact directional rule is closed. This
small pilot does not test the paper's passive-buy toxicity finding, and
conditional 2025 pressure outcomes remain unread.

The next [daily dollar-index source screen](MACRO_DOLLAR_SOURCE_SCOUT.md)
identified a potentially material spot-BTC forecast prior, but its paper's
stated trading fee and net-return table differ by roughly a factor of ten.
An ICE-labeled Yahoo index proxy is now acquired, but its bar timestamps
are session labels, and its holiday gaps exceed ICE's stated index
calendar. Its exact relation to the paper's series and release clock
remain unresolved. The source screen did not inspect macro-conditioned
Rocket returns. The [FUT-009 sparse delayed rule](experiments/FUT-009.md)
was frozen before those returns and made post-study 2024 its first gate,
with 2025 conditional on a pass.

The [frozen post-study FUT-009 result](experiments/FUT-009-RESULT.md) then
tested that distinct delayed proxy on BTC perpetuals. Its 209 active
2024 positions averaged −8.229 bp price gross, 16.406 bp below the
same-date always-long control; scheduled net was −6.403/−8.574 bp at
5/10 bp per side with actual funding. The sample gate passed but the
gross, incremental and cost gates failed. Close this exact rule; the
conditional 2025 score was not run. The paper's spot VAR and disputed fee
table remain separate.

The [Hyperliquid loss-close source audit](HYPERLIQUID_CLOSE_FLOW_SOURCE_SCOUT.md)
found wallet-level taker, realized-P&L and liquidation fields in two free
2025 block-fill mirror shards, but also a large internal October gap. The
[frozen FUT-010 gross pilot](experiments/FUT-010-RESULT.md) tested only
contiguous hours with an optimistic delayed trade-price proxy. All 222
scheduled BTC/ETH events were active, but July/October mean gross was
+3.873/+3.431 bp, below the 9 bp base taker fee floor on both dates;
July also lagged its always-short control. Close this exact all-wallet
five-minute-flow, thirty-minute-hold rule. The paper's classified wallet
cohort, forced liquidations, actual bid/ask and 2026 final holdout remain
separate and untested.

The [author slide and HYPE source follow-up](HYPERLIQUID_CLOSE_FLOW_SOURCE_SCOUT.md)
identified `FrontendMarket` orders as part of the paper's front-end wallet
fingerprint and a longer close-loser markout horizon. Six fixed 2025 fill
order IDs all returned `unknownOid` from today's public order-status API,
so the free fill mirror cannot establish that wallet cohort. A distinct
[frozen FUT-011 HYPE 120-minute trial](experiments/FUT-011-RESULT.md)
used two new, source-audited seven-hour Sunday windows. All 118 events
were active, but August's mean optimistic gross was +4.973 bp, below the
9 bp base taker fee floor and its always-short control; September's
+13.649 bp exceeded 9 bp but lagged its +43.340 bp always-short control.
The exact longer-horizon all-wallet rule failed its two-date gross and
incremental gate. Neither result validates a front-end cohort edge or a
live decision.

The distinct [market-liquidation source audit](HYPERLIQUID_LIQUIDATION_SOURCE_SCOUT.md)
first found just 21 separated market-wide episodes in twelve fragmented
2025 shards. Four complete SHA-pinned days subsequently yielded
4,308,938 consecutive blocks and 54 separated HYPE episodes with both
entry and exit trade-proxy timestamps present. Backstop rows were shown
to have different semantics and are excluded. The [FUT-012 contract](experiments/FUT-012.md)
freezes a delayed HYPE trial across these four dates and chronological
halves before any conditioned return is inspected. No liquidation
strategy result or production change exists.

## Established boundaries

The full Pana stack admitted no primary sample in PR #28 and PR #31. This rejects it as the starting baseline, not each pullback, reaction, or confirmation component. Staged `ZONE` is a useful state representation, but scoring it as an entry lost after costs. The tested `TheoryV2` implementation also lost. The frozen `daily-trb-50d-v1` combined event mean was negative after 20bps and 40bps plus funding; that exact rule is rejected, not trend, momentum, or all breakouts. The standalone cross-sectional quintile implementation did not validate; relative strength remains an untested ranker. Details, limits, and reopening rules are in [historical evidence](HISTORICAL_EVIDENCE.md).

## Promotion

Every new experiment receives an ID and frozen question, mechanism, falsifier, data/universe and cost rules before outcome inspection. A cheap gate needs causal data, realistic costs, chronological OOS, asset/period breakdown, concentration, simple baseline, ablation, and broad parameter stability. Strong survivors earn walk-forward and uncertainty work; only promotion candidates receive an untouched final holdout and frozen prospective shadow. Never use a portfolio throttle or an ex-post side/coin slice as signal validation. Preserve all failures and trial count.

Current strategy state: `RESEARCH`. There is no validated `ENTER_*` contract. The only active question is in [FUTURES_FRONTIER.md](FUTURES_FRONTIER.md).
