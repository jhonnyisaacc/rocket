# How to run the memecoin radar

NO_EDGE_VALIDATED. Human-gated. Read-only. Identification ≠ entry.
Browser and X are evidence sources, not execution.
Every result keeps edge=NO_EDGE_VALIDATED and execution_enabled=false.

A WATCH_ENTER row is not a buy. Identification is not an entry. See `DECISION_CONTRACT_v0.md`.

The Helius key must already be exported on the machine that runs the command, under the name `HELIUS_API_KEY`. Rocket does not take a second variable. Do not copy the key into this repo, into JSON artifacts, into a crontab, into screenshots, or into the pull request.

## What a pass does

`radar` is the cron entry. It collects one bounded snapshot and then scans it, and it prints exactly one JSON object. `collect` and `scan` still work on their own.

`collect` writes a bounded spool snapshot: two pages of graduated pump.fun coins (`GET /coins?complete=true`, 20 per page), pump.family migrated sales (fomo.family itself is login-walled), and at most 8 closed-window names that are still on the bonding curve. Intake is trimmed to 40 observations, preferring coins aged 30 minutes to 24 hours. If `HELIUS_API_KEY` is present, collect then confirms those mints and reads pool quote vaults. If it is absent, Helius health is `UNAVAILABLE` and nothing is sent.

`scan` reads the latest snapshot only and prints at most 20 rows. It does not trade. Liquidity is 2 × the current quote-vault balance in USD, using the snapshot SOL price. Graduation-time `real_quote_reserves` is not liquidity. A missing or zero pool leaves `liquidity_usd` null and the row `SKIP`.

Repeated collects keep the newest spool segment and delete older ones.

Install once, from this repo:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

Use a state directory you control. The default spool is `$ROCKET_HOME/memecoin/spool`, or `~/.rocket/memecoin/spool` when `ROCKET_HOME` is unset.

## Commands

```bash
.venv/bin/rocket memecoin status --json --state-dir "$HOME/.rocket"
.venv/bin/rocket memecoin radar --json --state-dir "$HOME/.rocket"
.venv/bin/rocket memecoin collect --json --state-dir "$HOME/.rocket"
.venv/bin/rocket memecoin scan --json --state-dir "$HOME/.rocket"
```

The bot should run `radar`, not a shell loop. Optional flags: `--spool PATH` and, for a file of intake rows instead of a live fetch, `--input observations.json`. A file of the old caller PIT fixtures (`features`, `contract_address`) still hits the legacy scorer when passed to `scan`.

## Cron

`HELIUS_API_KEY` must already be exported in the environment this crontab uses. The line does not contain the key. Change `$HOME/rocket` if the checkout lives somewhere else. Every few minutes is safe; the command is bounded.

```cron
*/5 * * * * cd "$HOME/rocket" && "$HOME/rocket/.venv/bin/rocket" memecoin radar --json --state-dir "$HOME/.rocket"
```

Stdout is one JSON object. Branch on `decision_summary`. Do not treat exit 0 as “there is a buy.”

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Ran fine. Healthy or partial scan, including zero `WATCH_ENTER`. Not a crash. |
| 2 | Provider down. Operational `UNAVAILABLE`, including `coverage_status` `DATA_UNAVAILABLE`. |
| 1 | Bad config or `ERROR`. Invalid `radar --input` JSON exits 1. |

A partial scan (one board down, rows still ranked) is exit 0. Read `decision_summary.helius` and `coverage_status` for that. Exit 0 with `counts.WATCH_ENTER` of 0 is a normal cron result.

## decision_summary

Top-level and inside `payload`. Counts, coverage, Helius health, and the `WATCH_ENTER` rows only (`identity`, `mint`, `liquidity_usd`, `age_seconds`). The full `selected` list is still there if a human wants it. The bot does not need it to branch.

`edge` is `NO_EDGE_VALIDATED`. `execution_enabled` is false. `notice` is `A WATCH_ENTER row is not a buy.`

Check the JSON before reading any row as a candidate:

- `payload.edge` is `NO_EDGE_VALIDATED`
- `payload.execution_enabled` is `false`
- `payload.notice` is `A WATCH_ENTER row is not a buy.`
- `payload.coverage_status` is `DATA_UNAVAILABLE` when the feed could not be read. That is a provider failure, not an empty market. The process exits 2.
- `payload.coverage_status` is `EMPTY_INTAKE` when a snapshot was written and the bounded universe was empty. `selected` is `[]`. That is also not “no memecoins exist.” Exit code is 0.
- `operational.providers` names `browser:pump.fun`, `browser:fomo.family`, `helius`, and `x`. `x` stays optional. A Helius row with `failure_kind` `HELIUS_API_KEY_ABSENT` means this process does not have the key. Do not copy the key into the repo.

## Example decision_summary

Real scan, 2026-09-23T08:38:52Z, redacted to the summary block. It is not a buy. Exit code was 0. Priced `liquidity_usd` on the 20 selected rows ran from 2.62 to 991.65, under the 10000 floor, so `WATCH_ENTER` is 0. One pool could not be priced and is the `SKIP`.

```json
{
  "counts": {"WATCH_ENTER": 0, "SKIP": 1, "TOO_EARLY": 0, "AVOID": 19},
  "coverage_status": "OBSERVED",
  "helius": {"status": "HEALTHY", "failure_kind": null},
  "watch_enter": []
}
```

## Example WATCH_ENTER row

This object is an example of the shape. It is not a live scan and it is not a buy. A real WATCH_ENTER row appears only after the floors in `RADAR_CONTRACT_v0.md` and a Helius mint confirm, with liquidity from the pool quote vault. On a machine without the key, the same discovery row is `SKIP`.

```json
{
  "example_only": true,
  "edge": "NO_EDGE_VALIDATED",
  "execution_enabled": false,
  "notice": "A WATCH_ENTER row is not a buy.",
  "identity": "solana:mainnet:EXAMPLE_MINT_NOT_A_SIGNAL",
  "asset": "LABEL",
  "mint": "EXAMPLE_MINT_NOT_A_SIGNAL",
  "state": "WATCH_ENTER",
  "liquidity_usd": 12000.0,
  "age_seconds": 7200,
  "volume_acceleration": null,
  "sources": ["browser:pump.fun", "helius"],
  "social_heat": "unknown",
  "reasons": ["floors_met_not_an_entry"],
  "discovered_at": "2026-09-23T05:15:00+00:00",
  "available_at": "2026-09-23T07:15:00+00:00",
  "source_urls": ["https://pump.fun/explore"],
  "bundle_or_dev_hold": {"top1_holder_bps": 250, "dev_hold": "UNKNOWN"}
}
```

`liquidity_usd` 12000 here means 30 SOL in the quote vault × a $200 snapshot SOL price × 2. It is not the graduation print. `reasons` contains `floors_met_not_an_entry` on purpose. Meeting the floors identifies a row for a human to look at. It does not authorize an order.

## Do not

- Do not treat WATCH_ENTER as a buy, a copy of an 8-second wallet, or a slot-0 snipe.
- Do not merge or vendor PR #27’s cache.
- Do not point X, Discord, or a trading key at this command. X is optional heat after a mint is already known.
- Do not put `HELIUS_API_KEY` in the crontab, the shell command, or the log line.
