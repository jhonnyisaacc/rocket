# FUT-007 ETH lower-tail funding result

Status: `NO_SAMPLE_2023H2_AND_GROSS_NET_FAILED_2024`, 2026-09-24.
The exact [FUT-007 contract](FUT-007.md) was frozen at `eac3c94` before
ETH funding-conditioned returns were read. The deterministic scorer was
committed at `268a354`. This is an ETH **asset transfer** of a published BTC
spot-return association, not a post-publication or intended-venue result.

## Source and timing

The [audited source](../FUNDING_DIRECTION_SOURCE_SCOUT.md) has every ETHUSDT
USD-M 1h Binance bar in 2023–2025 and every eight-hour ETH funding slot.
Official ZIP hashes, hourly continuity and the funding database fingerprint
were checked before scoring. The ignored local source manifest SHA-256 is
`263c64597d44619e45a23fe540182cc0ef2af9bf52b1216718634e79b363db1a`;
the funding database SHA-256 is
`e42cfcfc5d244293a9a3327a5009c05723c541b1d86ed3a5050a08c7f97e863b`.
The [scorer](../../../research/futures/fut007_score.py) checked all 540
prior eight-hour rates for each daily 180-day reference window, used the
00:00 settlement only after its actual timestamp, then delayed entry to
the 01:00 hourly open. Each target held to the next 01:00 open. Funding
payments, changes in target, initial entry and terminal exit were charged.
No exposed data gap was encountered. No 2025 funding-conditioned entry or
return was scored; its January 1 hourly price closes the last 2024 trade.
The ignored local result SHA-256 is
`d3ccf95dc2dc10696ae5a3c6265b64f3ab0cff83fc5fbb211619380c104cece4`.

## Frozen gate

Gross and net daily means include cash days; event gross is the mean on
triggered days only. Returns below are percentages, not basis points.

| Measure | 2023 Jul–Dec | 2024 |
| --- | ---: | ---: |
| Scheduled days | 184 | 366 |
| Lower-tail triggers | **13** | 52 |
| Mean event gross | +1.1242% | **−0.0165%** |
| Mean event gross minus all-day long gross | +1.0075% | **−0.1759%** |
| Mean scheduled-day net, 5 bp/side | +0.07374% | **−0.00949%** |
| Mean scheduled-day net, 10 bp/side | +0.06831% | **−0.01523%** |
| Compounded net, 5 bp/side | +14.02% | **−6.84%** |
| Always-long ETH compounded net, 5 bp/side | +13.28% | +28.49% |
| Target-change turnover, sides | 20 | 42 |

The 2023 half-year has **13 events, below the frozen minimum of 15**. Its
positive returns cannot count as a gate pass; events occurred in July–October,
with zero in November–December. Its five best triggered days contributed
+0.1744 in summed return units against +0.1461 across all 13, indicating
concentration. In 2024 the sample is sufficient but **the event gross,
event-versus-unconditional gross, and both net means are negative**. The
2024 lower-tail rule had no triggers in January–March or October–December;
37 of 52 triggered funding rates were actually *positive* despite being
low relative to their trailing history. This is faithful to the frozen
relative-percentile rule, not grounds for an ex-post absolute-negative filter.

The combined 10 bp-per-side scheduled-day point mean is +0.01272%, carried
by the insufficient 2023 half-year; it cannot override the required
partition gates. Calendar-month block 95% intervals for the 5 bp-per-side
scheduled-day mean were **[+0.01664%, +0.15136%]** in 2023H2 and
**[−0.08319%, +0.05022%]** in 2024. The event-minus-all-day gross intervals
were **[+0.2177%, +2.5726%]** and **[−0.7297%, +0.3418%]**, respectively.
These intervals do not repair the too-small 2023 sample or the failed 2024
point gate. Prior four-hour ETH returns were slightly negative on 2023
trigger days and slightly positive on 2024 triggers, so the result also
does not isolate funding from recent-price state.

## Interpretation

Close this **once-daily, one-hour-delayed, lower-decile long-ETH** contract
as a standalone candidate. Do not select the 2023 months, require absolute
negative funding, change the 180-day window or decile, move entry closer to
settlement, switch to BTC, or invert the upper tail using these outcomes.
The 2024 failure is visible **before fees**; quote-level execution would
only add uncertainty to a gate already failed. The positive 2023 half-year
is an insufficient and concentrated sample. The test does not refute the
source paper's BTC *spot* association, establish a universal funding
relation, or test funding as context for a later viable forecast.

The hourly open is an optimistic fill proxy, not an executable order-book
quote; account fees, spread, impact and Hyperliquid funding/price transfer
remain unmeasured. No conditional 2025 score or 2026 final holdout was used.
No `ENTER_LONG` or other production decision is validated. Execution
remains disabled.
