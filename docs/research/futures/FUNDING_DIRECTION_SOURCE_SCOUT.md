# Funding direction: product fit and ETH source scout

Status: `SOURCE_READY_NO_CONDITIONED_OUTCOME`, 2026-09-24.

[He et al., *Fundamentals of Perpetual Futures*](https://arxiv.org/html/2212.06888)
derive and backtest an arbitrage trade that **shorts the perpetual and buys
spot** (or reverses both legs for the opposite dislocation). Their funding
return is conditional on the spot hedge and requires both legs, collateral,
spread and liquidation accounting. It cannot validate a standalone
`ENTER_SHORT` perpetual decision. The current
[`trade_decision`](../../../rocket/workflows/crypto.py) emits one direction
summary for candidates and has no paired-leg/venue contract. The already
audited Binance/Hyperliquid carry source remains useful for separate future
product work, but a two-venue carry strategy is not adopted as the next
one-direction Rocket rule.

A [different primary study by Memon et al. (2026)](https://www.aijmr.com/papers/2026/4/1493.pdf)
reports that BTC funding observations in the **lower decile of their own
preceding 180-day distribution** preceded an average +0.506% 24-hour BTC
*spot* return in its September 2019–August 2026 Binance sample. The paper
uses a mid-rank percentile to handle ties and at least 300 prior observations.
It finds no symmetric positive-tail result. The authors explicitly caution
that the association does not establish a costed standalone trading strategy.
Their BTC sample includes Rocket's full 2023–2025 history; a BTC backtest
there would not be independent chronology. ETH is an **asset-transfer**
question, not a post-publication time holdout. The sign, 180-day reference,
lower-decile threshold and 24-hour horizon come from the paper; an ETH
perpetual trade with a one-hour post-settlement delay is a separate Rocket
contract and must pay funding and turnover.

For that transfer, the [source audit](../../../research/futures/funding_tail_source_audit.py)
downloaded all **36 official Binance USD-M ETHUSDT 1h monthly ZIPs and
matching `.CHECKSUM` files** for 2023–2025. Official hashes, fixed 12-column
schema, all **26,304** expected hourly bars, one-hour spacing, exact close
times and positive internally consistent OHLC passed. ZIP bytes total
**1,381,752**. The ignored local source report SHA-256 is
`263c64597d44619e45a23fe540182cc0ef2af9bf52b1216718634e79b363db1a`.
The checksum-repaired Binance funding database SHA-256 is
`e42cfcfc5d244293a9a3327a5009c05723c541b1d86ed3a5050a08c7f97e863b`.
It has every ETH eight-hour slot: 1,095 in 2023, 1,098 in leap-year 2024,
and 1,095 in 2025. Actual record stamps were at most **29 ms** after the
nominal slot in 2023, 15 ms in 2024 and 16 ms in 2025. This is an archive
timestamp audit, not a proof of real-time publication latency; a full
one-hour decision delay is retained.

No funding-tail-conditioned ETH return, selected date or direction was
computed in this scout. The official first January 2024 candle was read
solely to establish the source schema. The 2026 final holdout remains
untouched. A result on Binance ETH still needs venue transfer, executable
quotes and prospective shadow before any Rocket decision promotion.
