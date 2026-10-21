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

The file mode is `0600`. `*.keystore.json` is gitignored. That file is the export. Decrypt it with the same passphrase. The command does not print the keys, and a terminal prompt does not echo them. On a laptop this is the dry-run signer. Live mode does not use it. The production signer is Turnkey. See [the ceremony](#key-ceremony) below.

A HyperCore agent key is separate. Approving that agent is a manual step on the master account. This service does not sign `approveAgent`.

## Start the two processes

```bash
export PORT=8080
export AUTH_TOKEN='a token of at least 16 characters'
export DATABASE_URL=postgres://listing:listing@127.0.0.1:5432/listing
export REFRESH_ENABLED=true
npm run start:resolver
```

In a second shell, point the executor at the resolver and describe the balances the hot wallet actually holds. Decimals are required. A native row keeps the gas reserve.

```bash
export PORT=8081
export AUTH_TOKEN='a token of at least 16 characters'
export RESOLVER_URL=http://127.0.0.1:8080
export WALLET_HOLDINGS_JSON='[{"symbol":"USDC","address":"<mint>","amount":20,"usd":20,"native":false,"decimals":6}]'
export NOTIFIER_WEBHOOK_URL=http://127.0.0.1:9/hook
npm run start:executor
```

Leave `LISTING_TRADER_LIVE` unset. `GET /health` on each port returns `live: false`.

Omit `chainKey` when that balance may fund a buy on any chain. Live mode then reads it on the chain of the buy. Set `chainKey` to a known chain key when the address belongs to one chain. An unknown key stops boot.

## Send a fake alert

The collector, or a curl stand-in, posts the alert to the executor.

```bash
curl -s -X POST http://127.0.0.1:8081/listing \
  -H 'content-type: application/json' \
  -H "authorization: Bearer $AUTH_TOKEN" \
  -d '{"id":"alert-1","ticker":"MPLX","projectName":"Metaplex","source":"upbit","publishedAt":"2026-10-21T00:00:00Z","receivedAt":"2026-10-21T00:00:00.300Z"}'
```

A hit responds with `decision: would_send`, the route, and latency stamps measured from `receivedAt`. The same `id` returns the stored report and does not quote again. A lookalike, a thin pool with no Hyperliquid market, or a missed live lookup responds with `skipped`.

`POST /execute` accepts a `SwapIntent` and always returns a dry-run report, including when the process is live. Live broadcast is only `POST /listing`, which rebuilds the intent from the resolver.

## Turn the knobs

| Variable | Default | Effect |
| --- | --- | --- |
| `MAX_USD_PER_TRADE` | 5 | Reject a larger notional |
| `DAILY_USD_CAP` | 25 | Counted only after a live broadcast. Day boundary is `SPEND_TIMEZONE`, default `UTC` |
| `MAX_SLIPPAGE_BPS` | 100 | Cap for route selection. Cannot exceed `SLIPPAGE_HARD_MAX_BPS` (300) |
| `MIN_LIQUIDITY_USD` | 75000 | Floor for the top pool |
| `KILL_SWITCH` | off | `1` or `true` skips every trade. A `control_flags` row named `kill_switch` does the same without a restart |
| `MAX_LEVERAGE` | 1 | HyperCore orders above this are rejected |
| `DISABLED_CHAINS` | empty | Comma-separated chain keys to remove from the default set |
| `ENABLED_CHAINS` | empty | Comma-separated chain keys to add. Monad stays off until this list includes `monad` |
| `QUOTE_DECIMALS_JSON` | `{}` | Quote-asset decimals for an explicit two-hop |
| `OWNER_WITHDRAW_ADDRESSES` | empty | Allowlist. Empty denies every withdraw and every bridge plan |
| `AUTH_TOKEN` | unset | Required. At least 16 characters. Boot refuses a shorter value |
| `ROUTER_ALLOWLIST_JSON` | empty | Per-chain EVM routers, for example `{"8453":["0x..."]}`. Empty denies every swap |
| `SOLANA_PROGRAM_ALLOWLIST` | empty | Extra Solana program ids added to the base set. The base programs stay allowed |
| `TOKEN_SCREENING` | on in live, off in dry-run | `false` turns screening off. `true` turns it on. Refresh and a live buy both use it |
| `MAX_TOKEN_TAX` | 0.1 | GoPlus buy or sell tax above this fraction is a deny. This is a service safety floor, not a research price |
| `JITO_ENABLED` | off | `true` sends Solana through the Jito block engine |
| `QUOTE_DEADLINE_MS` | 500 | Stop waiting for aggregator quotes |
| `MAX_BRIDGE_USD` | 25 | Largest inventory move `planRebalance` will accept |

`POST /withdraw` uses the same bearer hook as the other mutating routes, then checks `x-admin-token` against `ADMIN_TOKEN`. It stays disabled until `WITHDRAW_ENABLED=true`. The body is `{ "to", "chainKey", "amount" }` for native gas, or the same fields plus `mint` and `decimals` for an allowlisted ERC-20 or SPL recovery. `MAX_WITHDRAW_AMOUNT` defaults to 1 human unit. Dry-run returns `would_send`. Live mode sends only when the destination is allowlisted and a native send leaves the gas reserve. An SPL recovery creates the destination owner's associated token account when it is missing and transfers the tokens there. `POST /rebalance` plans a bridge and does not broadcast. This service has no bridge send.

To run live, set `LISTING_TRADER_LIVE` to the exact string `true`, set `DATABASE_URL`, and load Turnkey. Live mode refuses to boot without the database and without a Turnkey signer. The local keystore cannot override that. The daily cap is a reservation in `spend_journal`. A restart does not zero committed or reserved rows. Dry-run does not write that table.

## Key ceremony

Do this once, with two people if you can, and do not paste keys into chat.

1. In Turnkey, create an organization and a wallet with an Ethereum account, a Solana account, and a third Ethereum account for the Hyperliquid agent.
2. Create an API user that can sign and nothing else. Download the API key pair. Store the private key in the Railway secret `TURNKEY_API_PRIVATE_KEY`. Set `TURNKEY_API_PUBLIC_KEY` and `TURNKEY_ORGANIZATION_ID`.
3. Copy the three addresses into `TURNKEY_EVM_ADDRESS`, `TURNKEY_SOLANA_ADDRESS`, and `TURNKEY_HYPERLIQUID_ADDRESS`.
4. Build the three Turnkey policies with `turnkeyPolicyDocument({ userId, routers })`, using the API user id and the same map as `ROUTER_ALLOWLIST_JSON`. The file in git is that function with user id `api-user` and an empty router map, so its EVM condition matches no chain. Do not hand-edit a placeholder. The test checks that the file matches the function.
5. Fund the hot wallet with a small USDC balance and the native gas reserve. Approve each router once with the root quorum, not with the API user. Then set `APPROVAL_CACHE_JSON` to those allowances.
6. On Hyperliquid, approve the agent from the master account in the UI. Do not import the master key here.
7. Boot with live mode off. `GET /health` must show `live: false`. Send a dry-run alert. Then set `LISTING_TRADER_LIVE=true`.

## Rotation

Create a new API key pair, add it to the same API user, set the new Railway variables, restart the executor, then delete the old API key in Turnkey. Rotation of the trading key is a new wallet: move funds with `POST /withdraw` to an allowlisted address you control, create the wallet, update the address variables, and repeat the router approval. Do not reuse a keystore passphrase you have already typed into a shell you do not trust.

## Revocation

In Turnkey, delete the API key or set the API user to a policy with no allows. Signing stops on the next request even if this process is still up. Then set `KILL_SWITCH=true` and restart. If a laptop still has a keystore, delete `EVM_PRIVATE_KEY`, `SOLANA_SECRET_KEY`, and `HYPERLIQUID_AGENT_KEY`, and move the funds. Live mode will not sign with those keys.

## Kill switch

`KILL_SWITCH=true` or `KILL_SWITCH=1` makes `checkLimits` skip every buy. Live withdraw also returns `would_send`. The key is not deleted. Leave the switch on until the incident note says to clear it.

## Incident

1. Set `KILL_SWITCH=true` on the executor and restart it.
2. Revoke the Turnkey API key.
3. If a transaction was broadcast, record the idempotency key and the journal row. Do not delete a `committed` row to retry. A retry of the same id stays `exists`.
4. If funds moved to an unexpected contract, the router allowlist was too wide or the host was compromised. Withdraw any remainder to the allowlist, then rotate the wallet.
5. Write down the UTC time, the report reason, and whether `broadcast` was true. A pre-sign failure releases the reservation. A failure after send keeps it so a retry cannot double-send.

`npm test` does not call an exchange. Do not point research CI at this tree.
