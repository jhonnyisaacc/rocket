# How to run the 24-hour radar trial

NO_EDGE_VALIDATED. Human-gated. Read-only. Identification ≠ entry.
Browser and X are evidence sources, not execution.
Every result keeps edge=NO_EDGE_VALIDATED and execution_enabled=false.

A WATCH_ENTER row is not a buy. Identification is not an entry. See `DECISION_CONTRACT_v0.md`.

The Helius key is already on the operator’s computer (or the VPS where that environment is already exported). It must not be copied into this repo, into JSON artifacts, into screenshots, or into the pull request. Rocket reads the existing name `HELIUS_API_KEY`. Do not invent a second variable and do not paste the key into a shell history you plan to commit. This cloud agent cannot see that key; live confirm has to run on the machine where it is already exported. Do not SSH it across.

## What a pass does

`collect` writes a bounded spool snapshot: up to 20 graduated pump.fun coins from the page’s public `GET /coins?complete=true`, pump.family migrated sales (fomo.family itself is login-walled), and at most 8 closed-window names that are still on the bonding curve. If `HELIUS_API_KEY` is present, collect then calls `getAccountInfo` and `getTokenLargestAccounts` for those mints. If it is absent, Helius health is `UNAVAILABLE` and nothing is sent.

`scan` reads that spool and prints at most 20 rows, newest first, then liquidity. It does not trade.

Install once, from this repo:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

Use a state directory you control. The default spool is `$ROCKET_HOME/memecoin/spool`, or `~/.rocket/memecoin/spool` when `ROCKET_HOME` is unset.

## Commands

```bash
.venv/bin/rocket memecoin status --json --state-dir "$HOME/.rocket"
.venv/bin/rocket memecoin collect --json --state-dir "$HOME/.rocket"
.venv/bin/rocket memecoin scan --json --state-dir "$HOME/.rocket"
```

Repeat `collect` then `scan` through the day. Each collect is bounded. Scan does not dump the spool. Optional flags: `--spool PATH` and, for a file of intake rows instead of a live fetch, `collect --input observations.json` / `scan --input observations.json`. A file of the old caller PIT fixtures (`features`, `contract_address`) still hits the legacy scorer.

Check the JSON before reading any row as a candidate:

- `payload.edge` is `NO_EDGE_VALIDATED`
- `payload.execution_enabled` is `false`
- `payload.notice` is `A WATCH_ENTER row is not a buy.`
- `payload.coverage_status` is `DATA_UNAVAILABLE` when the feed could not be read. That is a provider failure, not an empty market.
- `payload.coverage_status` is `EMPTY_INTAKE` when a snapshot was written and the bounded universe was empty. `selected` is `[]`. That is also not “no memecoins exist.”
- `operational.providers` names `browser:pump.fun`, `browser:fomo.family`, `helius`, and `x`. `x` stays optional. A Helius row with `failure_kind` `HELIUS_API_KEY_ABSENT` means this process does not have the key. Move the command to the machine where it is already exported. Do not copy the key into the repo.

## Example WATCH_ENTER row

This object is an example of the shape. It is not a live scan and it is not a buy. A real WATCH_ENTER row appears only after the floors in `RADAR_CONTRACT_v0.md` and a Helius mint confirm. On a machine without the key, the same discovery row is `SKIP`.

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
  "liquidity_usd": 17001.07,
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

`reasons` contains `floors_met_not_an_entry` on purpose. Meeting the floors identifies a row for a human to look at. It does not authorize an order.

## Do not

- Do not treat WATCH_ENTER as a buy, a copy of an 8-second wallet, or a slot-0 snipe.
- Do not merge or vendor PR #27’s cache.
- Do not point X, Discord, or a trading key at this command. X is optional heat after a mint is already known.
