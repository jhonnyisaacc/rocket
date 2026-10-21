# Deploy the listing trader on Railway

Deploy two services from this directory. Do not point them at the Rocket research app. Leave live mode off until you have read [the threat model](threat-model.md) and loaded a key on purpose.

## Build

Railway's root directory is `listing-trader`. The Dockerfile builds TypeScript in one stage and runs `node dist/src/resolver-server.js` as the default command. `railway.json` checks `GET /health`.

Create a second service from the same root and set its start command to:

```bash
node dist/src/executor-server.js
```

Give the resolver and the executor different `PORT` values if the platform does not inject one. Railway injects `PORT`.

## Data

Attach Postgres to the resolver. Copy `DATABASE_URL` to the executor as well when you later enable live mode. Use the private network URL. Both services read that variable. The resolver writes the watchlist. The executor writes the spend journal only in live mode.

Set `REFRESH_ENABLED=true` on the resolver. Leave it unset on a laptop if you do not want the coin-list fetch.

## Secrets

Set these on the executor only, as Railway variables, not in the repo.

- `KEYSTORE_PATH` and `KEYSTORE_PASSPHRASE`, or `EVM_PRIVATE_KEY` and `SOLANA_SECRET_KEY`
- `HYPERLIQUID_AGENT_KEY` if you want the perp fallback to be able to send later
- `ZEROX_API_KEY`, `JUPITER_API_KEY`, `LIFI_API_KEY`, `COINGECKO_API_KEY` as the vendors require
- `RPC_URL_<chainId>` for each EVM chain you enable, and `SOLANA_RPC_URL`
- `RESOLVER_URL` on the executor, using the resolver's private URL
- `WALLET_HOLDINGS_JSON` with decimals
- `OWNER_WITHDRAW_ADDRESSES` if you want a withdraw destination
- `NOTIFIER_WEBHOOK_URL` for the public report

Do not set `LISTING_TRADER_LIVE`. Health should show `live: false`. The collector posts alerts to the executor `/listing` route. The notifier receives the report JSON and nothing else.

## Live mode

Set `LISTING_TRADER_LIVE` to the exact string `true` only after the signer and `DATABASE_URL` are present. The process exits on boot if either is missing. `KILL_SWITCH=true` stops new buys without deleting the key.
