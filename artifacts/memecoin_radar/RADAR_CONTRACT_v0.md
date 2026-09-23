# Radar contract v0

NO_EDGE_VALIDATED. Human-gated. Read-only. Identification ≠ entry.
Browser and X are evidence sources, not execution.
Every result keeps edge=NO_EDGE_VALIDATED and execution_enabled=false.

A WATCH_ENTER row is not a buy. This contract is a triage label for a human. It is not an entry, a copy rule, or a claim that any row has edge. Selected-row bot labels are in `DECISION_CONTRACT_v0.md`.

## Universe, in order

1. `browser:pump.fun` — graduated coins. The page board does not print mints. The page’s own client calls `GET https://frontend-api-v3.pump.fun/coins` with `complete=true`. That flag is the graduated / bonding-curve-complete bit. Two bounded pages, 20 coins each. Page one is `offset=0`. Page two is `offset=20` when page one already reaches the 30-minute floor; otherwise one offset aimed at that floor, capped at 400. Intake then keeps at most 40 observations and prefers graduated coins aged 30 minutes to 24 hours, so the newest page does not fill the list by itself.
2. `browser:fomo.family` — `https://fomo.family/` is login-walled, so the public sibling the pump.family page actually fetches is `GET https://pump.family/api/sales`. Phase `migrated` is in universe (window closed and off-curve). Phase `launched` is window-closed but still on the bonding curve: at most 8 of those are kept, and they cannot be WATCH_ENTER. Phase `open` is excluded.
3. `helius` — confirm only, and only if `HELIUS_API_KEY` is already exported. Methods: `getAccountInfo` (mint, and pool when the page JSON has one), `getTokenLargestAccounts`, and `getTokenAccountBalance` on the pool quote vault. `getTokenAccountsByOwner` is the fallback when the pool account is not a PumpSwap `Pool`. No `getTransactionsForAddress`. Calls stay inside the selected cap of 20, spent on age-window rows first.
4. `x` — optional. Never required. Never an identity. If it is not consulted, provider health is `OPTIONAL_NOT_CONSULTED` and `social_heat` is `unknown`.

`universe_source` on every scan is `browser:pump.fun`, `browser:fomo.family`, `helius`, `x`.

## Floors and cap

| Gate | Value | Meaning |
| --- | --- | --- |
| Age floor | 1800 seconds (30 minutes) | `age_seconds = decision_time - event_time`. Slot-0 snipes and the observed ~8s buy / ~12s disposal sit inside this floor. Too new is not WATCH_ENTER. |
| Liquidity floor | 10000 USD | `liquidity_usd` only. Advertised market cap is stored aside and is not liquidity. |
| Selected cap | 20 | Age-window rows first (30 minutes to 24 hours), then older graduated rows, then unknown age, then rows under the age floor. Within a band, newer `event_time`, then higher `liquidity_usd`. Further rows are `selected_cap`, not a silent drop of the whole market. |
| Intake cap | 40 observations per collect | Two pump pages plus the bounded pump.family rows, then trimmed to 40. Plus at most a few provider-cache frames. Output is never a thousand-row dump. |

## Liquidity

`liquidity_usd` is current pool liquidity. Advertised market cap is stored aside and is not liquidity. pump.fun `real_quote_reserves` is the bonding-curve quote at graduation (about 85 SOL, the same print on coin after coin). It is not current pool liquidity and it is not read into `liquidity_usd`.

For a row with `pump_swap_pool` or a pump.family `pool`:

1. `getAccountInfo` on the pool.
2. PumpSwap pools are owned by `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA`. The account starts with the Anchor `Pool` discriminator `[241, 154, 109, 4, 17, 177, 109, 188]`. The quote mint is the 32 bytes at offset 75. The quote-vault token account is the 32 bytes at offset 171.
3. `getTokenAccountBalance` on that vault. If the account is not this layout, one `getTokenAccountsByOwner` for wrapped SOL is the fallback.
4. The quote mint must be wrapped SOL or the native-SOL placeholder. Liquidity = 2 × (raw vault amount ÷ 10^decimals) × the same snapshot’s pump.family `solUsd`. The ×2 is the constant-product pool: both sides are the same value at the pool’s own price. The result is rounded to cents.

A missing pool, a zero vault, an unreadable account, or a missing `solUsd` leaves `liquidity_usd` null. That row is `SKIP`, never `WATCH_ENTER`. Null is not a confirmed zero and is not `liquidity_below_floor`.

## Clocks

The only PIT fields are `event_time`, `available_at`, and `decision_time`.

- `event_time` is the page’s creation time or, for a pump.family sale, `windowEnd` or else `firstSeen`. It is not guessed from “now”.
- `available_at` is `retrieved_at` of the response that carried the row. It is not backdated to `event_time`.
- `decision_time` is the scan clock.
- `available_at` or `event_time` after `decision_time` is rejected (`future_available_at` / `future_event_time`). The row is not selected.
- A missing clock does not become WATCH_ENTER. The row is `SKIP` with `clocks_incomplete` or `age_unknown`.

## State

Selected `state` is the bot enum in `DECISION_CONTRACT_v0.md`: `TOO_EARLY`, `SKIP`, `WATCH_ENTER`, `AVOID`. There is no selected `UNKNOWN` state. `SKIP` is not safe.

`WATCH_ENTER` only when all of these are true. Reason stays `floors_met_not_an_entry`.

- Canonical identity is `solana:mainnet` plus a mint that passes the existing base58 32-byte check. The pump.fun chain string `solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp` normalizes to `solana:mainnet`. Any other chain is `unknown_identity`.
- `event_time`, `available_at`, and `decision_time` are present and PIT-eligible.
- `liquidity_usd` is present and ≥ 10000.
- `age_seconds` ≥ 1800.
- Graduation is `graduated` and the window state is `closed` (not still on the bonding curve).
- Helius `getAccountInfo` confirmed the mint account exists and decodes. A browser row without that confirm is `SKIP` or rejected. It is not WATCH_ENTER.

`TOO_EARLY` when Helius confirmed the mint and `age_seconds` is below 1800. That label wins over other hard fails. Those fails stay in `reasons`.

`AVOID` when identity is invalid, the mint fails decode or is not found, timestamps are in the future, or Helius confirmed the mint and a hard gate other than age fails (liquidity present but under the floor, or still on the bonding curve). Invalid identity, failed decode, mint not found, and future timestamps are rejected and are not selected.

`SKIP` when a required check cannot be computed: no Helius confirm, liquidity unknown, or clocks incomplete. `SKIP` is not a safe state.

Rejected, not selected: unknown identity, bad mint, future timestamps, Helius account missing (`mint_not_found`), failed decode, duplicate identity.

`bundle_or_dev_hold` is `{"top1_holder_bps": N, "dev_hold": "UNKNOWN"}` when largest-account evidence exists. Otherwise the field is `UNKNOWN`. Top-holder share is not a dev-wallet attribution.

`social_heat` is `none`, `low`, `high`, or `unknown`. Default `unknown`. X does not create the row.

## Live failure

| Situation | Operational | Research | `coverage_status` |
| --- | --- | --- | --- |
| Spool directory missing, or collect could not read either public source | `UNAVAILABLE` | `INSUFFICIENT_EVIDENCE` | `DATA_UNAVAILABLE` |
| Feed read succeeded and the bounded universe was empty | `HEALTHY` | `INSUFFICIENT_EVIDENCE` on scan | `EMPTY_INTAKE` |
| Rows exist and Helius or one board is down | `PARTIAL` | `INSUFFICIENT_EVIDENCE` | `PARTIAL` |

`selected: []` with `DATA_UNAVAILABLE` or `EMPTY_INTAKE` is not a finding that no memecoins exist. The payload warning says that explicitly. Caller-supplied legacy fixtures still use the old `scan()` path, including `CALLER_STATE_MISSING` on an empty fixture list. That path is not the live feed.

## Spool window

Scan ranks the latest complete snapshot only. Older snapshots do not leak into the new ranking. `collect` and `radar` keep the newest spool segment that contains a snapshot and delete the older segments, so a run every few minutes does not grow the spool without a bound.

## Bot summary

`rocket memecoin radar --json` collects and then scans, and prints one JSON object. `collect` and `scan` stay available. Scan and radar payloads include `decision_summary`:

- `counts` for `WATCH_ENTER`, `SKIP`, `TOO_EARLY`, and `AVOID`
- `coverage_status`
- `helius.status` and `helius.failure_kind`
- `watch_enter`: `identity`, `mint`, `liquidity_usd`, `age_seconds` for each `WATCH_ENTER` row

`edge` stays `NO_EDGE_VALIDATED`. `execution_enabled` stays false. The notice stays `A WATCH_ENTER row is not a buy.` Exit codes are in `HOW_TO_RUN.md`. Exit 0 includes a healthy scan with zero `WATCH_ENTER`.

## Secrets

Helius is read from `HELIUS_API_KEY` only. The request URL that contains the key is not stored, logged, or copied into spool records. Spool frames are the normalized intake row, a small provider-health manifest, and the public page JSON. Confirm-on-chain responses keep booleans and `top1_holder_bps` only.
