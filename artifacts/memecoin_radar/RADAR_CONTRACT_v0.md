# Radar contract v0

NO_EDGE_VALIDATED. Human-gated. Read-only. Identification ≠ entry.
Browser and X are evidence sources, not execution.
Every result keeps edge=NO_EDGE_VALIDATED and execution_enabled=false.

A WATCH row is not a buy. This contract is a triage label for a human. It is not an entry, a copy rule, or a claim that any row has edge.

## Universe, in order

1. `browser:pump.fun` — graduated coins. The page board does not print mints. The page’s own client calls `GET https://frontend-api-v3.pump.fun/coins` with `complete=true`. That flag is the graduated / bonding-curve-complete bit. Snapshot bound: 20 coins, newest `created_timestamp` first.
2. `browser:fomo.family` — `https://fomo.family/` is login-walled, so the public sibling the pump.family page actually fetches is `GET https://pump.family/api/sales`. Phase `migrated` is in universe (window closed and off-curve). Phase `launched` is window-closed but still on the bonding curve: at most 8 of those are kept, and they cannot be WATCH. Phase `open` is excluded.
3. `helius` — confirm only, and only if `HELIUS_API_KEY` is already exported. Methods: `getAccountInfo` (mint, and pool when the page JSON has one) and `getTokenLargestAccounts`. No `getTransactionsForAddress`.
4. `x` — optional. Never required. Never an identity. If it is not consulted, provider health is `OPTIONAL_NOT_CONSULTED` and `social_heat` is `unknown`.

`universe_source` on every scan is `browser:pump.fun`, `browser:fomo.family`, `helius`, `x`.

## Floors and cap

| Gate | Value | Meaning |
| --- | --- | --- |
| Age floor | 1800 seconds (30 minutes) | `age_seconds = decision_time - event_time`. Slot-0 snipes and the observed ~8s buy / ~12s disposal sit inside this floor. Too new is not WATCH. |
| Liquidity floor | 10000 USD | `liquidity_usd` only. Advertised market cap is stored aside and is not liquidity. |
| Selected cap | 20 | Newest `discovered_at` first, then higher `liquidity_usd`. Further rows are `selected_cap`, not a silent drop of the whole market. |
| Intake cap | 40 observations per collect | Plus at most a few provider-cache frames. Output is never a thousand-row dump. |

SOL reserve conversion, when used: `real_quote_reserves` lamports ÷ 1e9 × the same snapshot’s pump.family `solUsd`, and only when the quote mint is wrapped SOL or the native-SOL placeholder and the reserve is **greater than zero**. A zero reserve stays `liquidity_usd: null` (unknown), not a confirmed zero.

## Clocks

The only PIT fields are `event_time`, `available_at`, and `decision_time`.

- `event_time` is the page’s creation time or, for a pump.family sale, `windowEnd` or else `firstSeen`. It is not guessed from “now”.
- `available_at` is `retrieved_at` of the response that carried the row. It is not backdated to `event_time`.
- `decision_time` is the scan clock.
- `available_at` or `event_time` after `decision_time` is rejected (`future_available_at` / `future_event_time`). The row is not selected.
- A missing clock does not become WATCH. The row is `UNKNOWN` with `clocks_incomplete` or `age_unknown`.

## State

`WATCH` only when all of these are true:

- Canonical identity is `solana:mainnet` plus a mint that passes the existing base58 32-byte check. The pump.fun chain string `solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp` normalizes to `solana:mainnet`. Any other chain is `unknown_identity`.
- `event_time`, `available_at`, and `decision_time` are present and PIT-eligible.
- `liquidity_usd` is present and ≥ 10000.
- `age_seconds` ≥ 1800.
- Graduation is `graduated` and the window state is `closed` (not still on the bonding curve).
- Helius `getAccountInfo` confirmed the mint account exists and decodes. A browser row without that confirm is `UNKNOWN` or rejected. It is not WATCH.

`AVOID` when Helius has confirmed the mint and a computed gate fails: below the age floor, liquidity present but under the floor, or still on the bonding curve.

`UNKNOWN` when a required check cannot be computed, including missing Helius confirm, missing liquidity, missing age, or missing graduation. Unknown is not rewritten into “safe”.

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

## Secrets

Helius is read from `HELIUS_API_KEY` only. The request URL that contains the key is not stored, logged, or copied into spool records. Spool frames are the normalized intake row, a small provider-health manifest, and the public page JSON. Confirm-on-chain responses keep booleans and `top1_holder_bps` only.
