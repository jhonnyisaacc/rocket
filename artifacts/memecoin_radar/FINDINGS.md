# Findings — why memecoin scan cannot identify tokens today

NO_EDGE_VALIDATED. Human-gated. Read-only. Identification ≠ entry.
Browser and X are evidence sources, not execution.
Every result keeps edge=NO_EDGE_VALIDATED and execution_enabled=false.

This note is discovery and triage context. It is not an entry strategy and it is not a profitability claim.

## Why `rocket memecoin scan` cannot identify a token today

`MemecoinWorkflow.scan` only scores rows the caller already built. It does not open a board, read a spool, or call Helius. Each row must already carry a chain, a contract, `decision_time`, `available_at`, and finite `volume_acceleration` / `liquidity_usd`. An empty list is `INSUFFICIENT_EVIDENCE` / `CALLER_STATE_MISSING`. That is a missing caller fixture, not a look at the market. A failed or empty live feed must not be reported as “no memecoins exist.”

The old collector path that this repo deliberately did not revive is WebSocket → participant expansion → SQLite → outcomes. SQLite insert and page I/O overflowed `MAX_QUEUE_DEPTH`. Research automation that depended on that collector is paused. Rocket’s hot path stays the raw spool in `rocket/capture/spool.py`: append bytes, fsync, and only then rank. This trial does not put SQLite back on that path.

## What PR #27 showed, and what this branch does not take from it

[PR #27](https://github.com/jhonnyisaacc/rocket/pull/27) (`feat/cryptofutures_v3`, open, about 1 GB) is a read-only reference. It is not merged here, and its caches are not copied into this branch.

What it actually established:

- A public Fomo buy on the USELESS mint `Dz9mQ9NzkBcCsuGPFJ3r1bS4wgqKMHBPiVuniW8Mbonk` was reconciled after the fact to one signed transaction: 50,000 USDC out, about 755,233.67 USELESS in, plus 22.50 USDC of fee-like transfers. That is attribution of one historical fill, not a repeatable entry rule.
- Follower replay on the frozen fixtures was not a profitable copy. The primary losing row was a modeled loss. Other delay/size cells rejected entry on the frozen slippage bound. The winning fixture did not produce a fabricated positive return. No follower replay is run in this trial.
- One recurring wallet bought the later-sample token “34%” at about 8 seconds of age and disposed of that amount at about 12 seconds. A 5s, 15s, or 30s delayed copy would have been after that disposal. That timing is not copyable, and it is not a signal this radar emits.
- Status on that work remained `NO_EDGE_VALIDATED`. Helius history there used `getTransactionsForAddress` with cached pages. This radar does not call that method and does not spend a history crawl.

## Pages this trial actually opened

Cloud browser, 2026-09-23, read-only, no login and no wallet:

| URL | What was visible |
| --- | --- |
| `https://pump.fun/` and `https://pump.fun/explore` | Public board. Tabs included Movers, New, Charities, Market cap, Oldest, Last trade. No graduated / bonded-off-curve tab. Cards showed display name, ticker, and market cap. Mints were not on the cards. |
| `https://pump.fun/advanced` | Redirected to `https://trade.padre.gg/sign-in?utm_source=pumpweb` (login wall). Not used. |
| `https://fomo.family/` | Marketing page. “Start trading” opened a login modal (Apple / Google). No public launch board. |
| `https://fomo.family/feed` | 404. |
| `https://pump.family/` and `https://pump.family/explore` | Public. Explore filters include All, New, Closing soon, and Migrated. Cards showed name, ticker, and market cap. Mints were not on the cards. |

Two address-bar transcriptions from the visual pass were not used as identity. One coin URL 404’d (`Coin not found`). Another transcription did not match the mint string in the page payload for the same display name. Screenshots are not join keys.

Because the boards are mint-less or login-walled, intake falls back to public JSON those pages already call. Details and the mints actually returned are in `browser_pass_2026-09-23T0715Z.md`.

## Helius methods this radar will call

Only when `HELIUS_API_KEY` is already in the process environment (the name Rocket already uses for inventory RPC). No second env name. The key is not written to git, JSON, logs, or this file.

Bounded JSON-RPC on `mainnet.helius-rpc.com`, at most the mints in one snapshot cap:

1. `getAccountInfo` on the mint. The account must be owned by the SPL Token or Token-2022 program and decode as an initialized mint. This is the “mint exists” check.
2. `getAccountInfo` on a pool address when the page JSON included one (`pump_swap_pool` or pump.family `pool`). Existence is a pool fact. It is not a USD liquidity number.
3. `getTokenLargestAccounts` when the mint decodes. The top holder’s raw share of supply is stored as `top1_holder_bps`. Dev-hold stays `UNKNOWN` unless a later, separate owner match exists. No such match is invented here.

`getTransactionsForAddress` is not called. If the key is absent, Helius provider health is `UNAVAILABLE` / `HELIUS_API_KEY_ABSENT`, no RPC is sent, and a browser-only row cannot be `WATCH`.

## X

X is optional and not required for the radar to return. No tweet is an entry. If X is not consulted, `social_heat` is `unknown`. X cannot create a mint.

## What “identify” means after this change

Collect writes a bounded snapshot into the spool. Scan ranks that feed. `WATCH` is a human-review label after identity, clocks, age, liquidity, and a Helius mint confirm. A WATCH row is not a buy.
