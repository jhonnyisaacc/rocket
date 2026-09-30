# PR #30 audit — baseline freeze

NO_EDGE_VALIDATED. Human-gated. Read-only. Identification is not an entry.
A WATCH_ENTER row is not a buy. `execution_enabled` is false.
`edge` stays `NO_EDGE_VALIDATED`.

This file freezes what the radar on this branch observes. It does not retune floors, age window, gates, ranking, features, commands, exit codes, or JSON shape. Phase A stops here. See `ROADMAP.md`.

## What the radar observes

Commands: `rocket memecoin collect`, `rocket memecoin scan`, and `rocket memecoin radar`.

`collect` writes one bounded spool snapshot. `scan` ranks the latest snapshot only. `radar` collects and then scans, and prints one JSON object. None of them trade. `rocket/workflows/memecoin.py` still scores caller-supplied rows when `scan` is given the old fixture shape (`features`, `contract_address`). That path does not open a board.

The live universe, in the order in `RADAR_CONTRACT_v0.md` and `rocket/workflows/memecoin_radar.py`:

- Graduated pump.fun coins. The explore board does not print mints. Intake uses the page’s own client call, `GET https://frontend-api-v3.pump.fun/coins` with `complete=true`. Two pages, 20 coins each. Page one is `offset=0`. Page two is `offset=20` when page one already reaches the 30-minute floor; otherwise one offset aimed at that floor, capped at 400.
- pump.family `GET https://pump.family/api/sales`. `https://fomo.family/` is login-walled, so that public sibling is the feed. Phase `migrated` is in universe (window closed, off the bonding curve). Phase `launched` is window-closed and still on the curve: at most 8 of those rows, and they cannot be `WATCH_ENTER`. Phase `open` is excluded. The provider name on the result stays `browser:fomo.family`.
- Helius mint confirm and quote-vault balances, only when `HELIUS_API_KEY` is already in the process environment. Methods are `getAccountInfo` on the mint, `getAccountInfo` on a pool when the page JSON included one (`pump_swap_pool` or pump.family `pool`), `getTokenAccountBalance` on the PumpSwap quote vault, `getTokenAccountsByOwner` when the pool account is not that layout, and `getTokenLargestAccounts`. `getTransactionsForAddress` is not called. The key is not written into the repo, the spool, or this file.

X is on `universe_source` and stays optional. The live confirm left it `UNAVAILABLE` with `OPTIONAL_NOT_CONSULTED`. X does not create a mint.

## What is measured

On a ranked row, the scan computes only these:

- Mint existence. Helius `getAccountInfo` must show an account owned by the SPL Token or Token-2022 program that decodes as an initialized mint.
- Clocks. `event_time` is the page creation time, or for a pump.family sale `windowEnd` else `firstSeen`. `available_at` is the `retrieved_at` of the response that carried the row. `decision_time` is the scan clock.
- Age. `age_seconds = decision_time - event_time`.
- Liquidity as 2 × the current quote-vault token balance × the snapshot SOL price (`solUsd` from the pump.family sales payload), rounded to cents.
- Top-holder share when Helius returns largest accounts, stored as `top1_holder_bps`. `dev_hold` on that object stays `UNKNOWN`.

A missing pool, a zero vault, an unreadable account, or a missing SOL price leaves `liquidity_usd` null. That row is `SKIP`.

## What is only a proxy

- Vault balance is the quote side, doubled because a constant-product pool prices both sides the same at the pool’s own price. That figure is not measured full-pool depth.
- Advertised market cap (`usd_market_cap` on pump.fun, `marketCap` on pump.family) is stored aside. Advertised market cap is not liquidity.
- Graduation `real_quote_reserves` is the bonding-curve quote at graduation, about 85 SOL, the same print on coin after coin. It is not read into `liquidity_usd`. It was a bad proxy for current pool liquidity.
- `decision_summary` counts `WATCH_ENTER`, `SKIP`, `TOO_EARLY`, and `AVOID`, and carries coverage, Helius health, and the `WATCH_ENTER` identities. It is a label over the current gates, not evidence of an edge. The function comment in `memecoin_radar.py` still says a cron bot can branch on it. That comment is unchanged. Acting on it is quarantined in `HOW_TO_RUN.md` under `LATER_NOT_NOW`.

## Assumptions added during implementation

These are the triage choices already in the code and in `RADAR_CONTRACT_v0.md`. This audit records them. It does not change them.

| Assumption | Value in this branch |
| --- | --- |
| Liquidity floor | $10,000 (`LIQUIDITY_FLOOR_USD = 10000`) |
| Age floor | 30 minutes (`AGE_FLOOR_SECONDS = 1800`) |
| Universe that can reach `WATCH_ENTER` | graduation `graduated` and window `closed` |
| Selected cap | 20 |
| Intake trim | at most 40 observations, preferring ages 30 minutes–24 hours. The 24-hour mark is a ranking window. Coins older than 24 hours can still be `WATCH_ENTER`. |
| Selected states | `WATCH_ENTER`, `SKIP`, `TOO_EARLY`, `AVOID` |

`WATCH_ENTER` requires identity, PIT-legal clocks, liquidity at or above the floor, age at or above the floor, a closed graduated window, and a Helius mint confirm. The reason stays `floors_met_not_an_entry`. A WATCH_ENTER row is not a buy.

`TOO_EARLY` wins when Helius confirmed the mint and age is under 30 minutes. `AVOID` is a confirmed mint that fails a hard gate other than age, including liquidity present and under the floor. `SKIP` is a check that cannot be computed, including a missing Helius confirm or unknown liquidity. `SKIP` is not a safe state.

## What is unvalidated

- Any forward outcome. No later price, fill, or survival is attached to a point-in-time row.
- Any claim that a label survives a later window.
- DexScreener, or any second liquidity source. Nothing here cross-checks the vault figure.
- Holder or developer attribution beyond `dev_hold=UNKNOWN`. Top-holder share is not a dev-wallet match.

The live confirm’s research status is `INSUFFICIENT_EVIDENCE`. That status stands.

## Live snapshot

Quoted from `LIVE_CONFIRM.md`. Decision time `2026-09-23T08:38:52.533836+00:00` (2026-09-23T08:38:52Z). Workflow `memecoin.scan`.

- selected 20, selected cap 20
- WATCH_ENTER 0
- SKIP 1 (`liquidity_unknown`; the row is VSOF, vault null)
- TOO_EARLY 0
- AVOID 19, each with reason `liquidity_below_floor`
- vault liquidity about $2.62–$991.65 (19 priced values, 1 null) against the $10,000 floor
- Helius HEALTHY: `getAccountInfo+getTokenLargestAccounts+quoteVault confirmed=20 liquidity=19`
- `coverage_status` OBSERVED
- pump.fun HEALTHY, pump.family sales HEALTHY (`browser:fomo.family`), X not consulted
- `edge` NO_EDGE_VALIDATED
- `execution_enabled` false
- notice: A WATCH_ENTER row is not a buy.

The feed was not empty. `coverage_status` is `OBSERVED`, with 20 selected rows. It is not `EMPTY_INTAKE` and it is not `DATA_UNAVAILABLE`.

That snapshot is baseline evidence. It is not a reason to retune the floor.

## Real gaps, and gaps invented by chat

Real gaps, left open on purpose:

- No forward outcome is stored, so a label cannot be checked against what the coin did later.
- Nothing shows that a label survives a later window.
- Liquidity is one vault proxy. No second source has been compared to it.
- `dev_hold` is `UNKNOWN` on confirmed rows. There is no developer attribution.
- `fomo.family` itself contributes no public mint. Intake uses pump.family `/api/sales`.
- The live pass did not consult X.

`RADAR_CONTRACT_v0.md` still notes that a run every few minutes does not grow the spool. That sentence describes the spool bound (`collect` and `radar` keep the newest snapshot segment). It is not authorization to schedule.

Gaps invented by chat. This phase does not treat them as missing research and does not implement them:

- Cron, or any other scheduler.
- Grok bot wiring, Discord, or a bot that branches on `decision_summary`.
- A new scorer.
- Lowering the $10,000 floor before a distribution of the observable universe exists.

`edge` remains `NO_EDGE_VALIDATED`. `execution_enabled` remains false. A WATCH_ENTER row is not a buy.
