# Memecoin Data Truth Registry

Status: current research contract, 2026-09-24. Protocol semantics require versioned decoders and raw evidence. Official [Pump program documentation](https://github.com/pump-fun/pump-public-docs/blob/main/docs/PUMP_PROGRAM_README.md) and [PumpSwap documentation](https://github.com/pump-fun/pump-public-docs/blob/main/docs/PUMP_SWAP_README.md) are current references; a historical event must use its contemporary layout.

| Field or label | Authoritative evidence | Unacceptable shortcut | Availability and version rule |
| --- | --- | --- | --- |
| Identity / creation | Confirmed Pump create instruction/event, mint and transaction/slot | Symbol or page label | Record receive time, block time, program ID, instruction order and decoder version. |
| Curve state / liquidity | Bonding curve account or ordered state-changing events and current real/virtual reserves | Advertised market cap or static graduation reserve | State is usable only after it was observed/received; preserve curve layout and quote mint. |
| Completion | Bonding curve `complete` and reserve state (`real_token_reserves == 0` in current Pump docs) | Market-cap threshold | Distinguish completed curve from actual migration. |
| Migration / graduation | Successful migration instruction and canonical PumpSwap pool creation/state | “Graduated” API flag alone | Record migration slot and observed availability; historical version applies. |
| PumpSwap pricing/liquidity | Pool account plus base and quote token balances and quote mint | Doubling a stale quote vault or assuming WSOL | Current docs define **effective quote reserves = quote-vault balance + pool virtual_quote_reserves**. Record both, pool layout and slot. Quote vault alone is insufficient if virtual reserves are nonzero. |
| Wallet buy/sell | Signed transaction, instruction, owner balance changes, funding and fees | Token receipt or transfer alone | Distinguish fee payer, owner, routed input, deposits and refunds. |
| Holder concentration | Mint supply and beneficial holder accounts after identifying/excluding pool/vault accounts | Raw largest token account as developer holding | #30 found the largest account to be the pool base vault in 19/19 checked rows. |
| Forward executable return | Entry quote from state observable at decision plus size, fee, latency/failure; independently observed exit | Future candle midpoint or leader fill | Version execution formula and fee schedule. Failed entry is no position; failed exit retains inventory. |

Unknown source, missing account, unsupported layout, conflicting order or unmeasured latency stays `UNKNOWN`. Protocol documents can change; pin the source revision before decoding a new cohort. The #27 historical fee/curve replay applies to its observed regime only. Do not substitute a current IDL for historical bytes without compatibility checks.
