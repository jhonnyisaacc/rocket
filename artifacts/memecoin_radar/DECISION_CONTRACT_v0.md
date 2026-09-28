# Decision contract v0

NO_EDGE_VALIDATED. Human-gated. Read-only. Identification ≠ entry.
Browser and X are evidence sources, not execution.
Every result keeps edge=NO_EDGE_VALIDATED and execution_enabled=false.

A WATCH_ENTER row is not a buy. WATCH_ENTER is not an order, a copy rule, or a follower replay. No edge is claimed. `execution_enabled` stays false. `edge` stays `NO_EDGE_VALIDATED`.

Floors, clocks, and the universe are the ones in `RADAR_CONTRACT_v0.md`. This file only names the bot label on each selected scan row.

## Enum

Each selected row has `state` set to exactly one of:

`TOO_EARLY` | `SKIP` | `WATCH_ENTER` | `AVOID`

There is no selected `UNKNOWN`. `SKIP` is not a safe state. Selected length stays ≤ 20. Graduated rows inside the 30-minute to 24-hour window rank first, then older graduated rows, then unknown age, then rows below the age floor. Within a band, newer `event_time`, then higher `liquidity_usd`. The 24-hour mark is a ranking window, not a hard gate.

## Mapping

Apply the first match that fits.

`WATCH_ENTER` only when every existing WATCH gate passes:

- chain normalizes to `solana:mainnet` and the mint passes the existing base58 32-byte check
- `event_time`, `available_at`, and `decision_time` are present and point-in-time legal (neither event nor available time is after the decision clock)
- `liquidity_usd` is present and ≥ 10000. The number is current pool liquidity from `RADAR_CONTRACT_v0.md` (2 × the quote vault in USD). It is not pump.fun `real_quote_reserves` and not advertised market cap. Null does not pass this gate.
- `age_seconds` ≥ 1800 (30 minutes), with `age_seconds = decision_time - event_time`
- graduation is `graduated` and `window_state` is `closed`
- Helius `getAccountInfo` confirmed the mint

Reason stays `floors_met_not_an_entry`. The payload notice is `A WATCH_ENTER row is not a buy.`

`TOO_EARLY` when the mint is real and Helius confirmed it, and age is below 1800. This is checked before other hard fails. Liquidity under the floor or a still-open bonding curve stays in `reasons` and does not turn the row into `WATCH_ENTER`.

`AVOID` when identity is invalid, the mint fails decode or is not found, timestamps are in the future, or Helius confirmed the mint and a hard gate other than age fails. Those hard gates are: liquidity is present but under 10000, or the coin is still on the bonding curve (`still_on_curve` or `window_open`). Invalid identity, failed decode, mint not found, and future timestamps are rejected. They are not selected. A bad mint may show up as `AVOID` or as a rejected row; a future `available_at` is ineligible and is not selected.

`SKIP` when a required check cannot be computed. That includes no Helius confirm, liquidity unknown, and clocks incomplete. Liquidity is unknown when the pool address is missing, the quote vault is zero or unreadable, or the snapshot SOL price is missing. Those rows are `SKIP`, never `WATCH_ENTER`. A browser-only row is `SKIP`, not `WATCH_ENTER`. A young row without a Helius confirm is `SKIP`, not `TOO_EARLY`. `SKIP` means the check is missing. It does not mean the row is safe, ranked, or cleared.

## What this is not

No follower replay. No second pass that turns a label into an entry. No asset-specific rule. Meeting the floors identifies a row for a human to look at.
