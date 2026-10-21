# Run the listing trader

Use this when you want a dry-run resolver and executor on one machine. For Railway, use [the deploy guide](deploy.md).

## Create a wallet

The command prints the keystore path and the two public addresses. It does not print the keys.

```bash
cd listing-trader
export KEYSTORE_PASSPHRASE='a passphrase of at least 12 characters'
export KEYSTORE_PATH=wallet.keystore.json
npm run create-wallet
```

The file mode is `0600`. `*.keystore.json` is gitignored. On a VPS, run the same command as the user that will own the process. To load it, set `KEYSTORE_PATH` and `KEYSTORE_PASSPHRASE` on the executor. You can instead set `EVM_PRIVATE_KEY` and `SOLANA_SECRET_KEY` as environment secrets. A HyperCore agent key is separate, in `HYPERLIQUID_AGENT_KEY`. Approving that agent is a manual step on the master account. This service does not sign `approveAgent`.

## Start the two processes

```bash
export PORT=8080
export DATABASE_URL=postgres://listing:listing@127.0.0.1:5432/listing
export REFRESH_ENABLED=true
npm run start:resolver
```

In a second shell, point the executor at the resolver and describe the balances the hot wallet actually holds. Decimals are required. A native row keeps the gas reserve.

```bash
export PORT=8081
export RESOLVER_URL=http://127.0.0.1:8080
export WALLET_HOLDINGS_JSON='[{"symbol":"USDC","address":"<mint>","amount":20,"usd":20,"native":false,"decimals":6}]'
export NOTIFIER_WEBHOOK_URL=http://127.0.0.1:9/hook
npm run start:executor
```

Leave `LISTING_TRADER_LIVE` unset. `GET /health` on each port returns `live: false`.

## Send a fake alert

The collector, or a curl stand-in, posts the alert to the executor.

```bash
curl -s -X POST http://127.0.0.1:8081/listing \
  -H 'content-type: application/json' \
  -d '{"id":"alert-1","ticker":"MPLX","projectName":"Metaplex","source":"upbit","publishedAt":"2026-10-21T00:00:00Z","receivedAt":"2026-10-21T00:00:00.300Z"}'
```

A hit responds with `decision: would_send`, the route, and latency stamps measured from `receivedAt`. The same `id` returns the stored report and does not quote again. A lookalike, a thin pool with no Hyperliquid market, or a missed live lookup responds with `skipped`.

`POST /execute` accepts a `SwapIntent` directly. That is the entry a copy-trading process uses.

## Turn the knobs

| Variable | Default | Effect |
| --- | --- | --- |
| `MAX_USD_PER_TRADE` | 5 | Reject a larger notional |
| `DAILY_USD_CAP` | 25 | UTC day, counted only after a live broadcast |
| `MAX_SLIPPAGE_BPS` | 100 | Cap for route selection. Cannot exceed `SLIPPAGE_HARD_MAX_BPS` (300) |
| `MIN_LIQUIDITY_USD` | 75000 | Floor for the top pool |
| `KILL_SWITCH` | off | `1` or `true` skips every trade |
| `MAX_LEVERAGE` | 1 | HyperCore orders above this are rejected |
| `DISABLED_CHAINS` | empty | Comma-separated chain keys |
| `QUOTE_DECIMALS_JSON` | `{}` | Quote-asset decimals for an explicit two-hop |
| `OWNER_WITHDRAW_ADDRESSES` | empty | Allowlist. Empty denies every withdraw |

`POST /withdraw` with `{ "to", "chainKey", "amount" }` returns `would_send` while dry-run or the kill switch is on. Live mode sends native gas only when the destination is allowlisted and the leftover balance stays above the reserve.

To run live, set `LISTING_TRADER_LIVE=true`, set `DATABASE_URL`, and load a signer. Live mode refuses to boot without both. The daily cap is stored in `spend_journal`, so a restart does not zero it. Dry-run does not write that table.
