# Threat model

The listing trader can move the funds in the hot wallet. This page uses STRIDE so each control is tied to a threat. The controls are what the code does. They are not a promise about an exchange or a signer vendor.

## Spoofing

`EXECUTOR_AUTH_TOKEN` and `RESOLVER_AUTH_TOKEN` are required at boot, must differ from each other and from every strategy token, and must be at least 16 characters. Mutating routes compare `Authorization: Bearer` with SHA-256 and `timingSafeEqual`. `GET /health` is the only open route and returns only `{"ok":true}`. The public config moved to an authenticated `GET /status`. Secrets, the router list, and the approval cache are not in either payload.

The collector holds the executor token. The executor calls the resolver with the resolver token, so one leaked token does not open both services. A strategy token from `STRATEGY_CAPS_JSON` opens only that strategy's live `/execute`, under its own caps and namespaced idempotency keys. A missing, short, or reused token refuses boot.

## Tampering

Zod parses every request and every aggregator or screening body this service acts on. A mismatch is a 400 or a null quote. Firm quotes are checked again against the slippage cap before sign.

App policy constrains the destination token account, chain, native value, and Solana instructions. The Turnkey EVM policy constrains only the router in `eth.tx.to`, the chain, the native value cap, and the selector prefix; it cannot see the swap's destination token account, so that check lives in the app policy and the pre-sign simulation. The Turnkey Solana policy constrains native transfer recipients and program ids. Each Turnkey policy is scoped to one wallet with `wallet.id`. The checked-in file is `policies/turnkey.json`, a template with placeholder ids. `ROUTER_ALLOWLIST_JSON` is a map of chain id to router addresses. A router allowed on one chain is denied on another. An empty list for that chain denies the swap. A token sell with a non-zero native value is denied. Solana program ids outside the base set plus `SOLANA_PROGRAM_ALLOWLIST` deny the signature. `SOLANA_PROGRAM_ALLOWLIST` adds program ids. It does not replace the base set.

The app decodes every top-level instruction of a base program against a default-deny table in `signing-policy.ts`. An instruction that is not in the table is denied. The table allows these:

- System Program Transfer from the hot wallet to the hot wallet, an allowlisted withdraw address, the hot wallet's wrapped SOL account, or a published Jito tip account. Assign, CreateAccount, TransferWithSeed, AdvanceNonceAccount, and every other System instruction are denied.
- Token and Token-2022 SyncNative, CloseAccount that pays the hot wallet, InitializeAccount3 owned by the hot wallet, and Transfer or TransferChecked into an associated token account of the hot wallet or an allowlisted withdraw address. Approve, ApproveChecked, SetAuthority, and the rest are denied.
- Associated Token Account CreateIdempotent funded by the hot wallet for the hot wallet or an allowlisted withdraw address.
- Compute Budget unit limit, unit price, and loaded-data limit.
- Jupiter `route`, `routeWithTokenLedger`, `sharedAccountsRoute`, `sharedAccountsRouteWithTokenLedger`, and `sharedAccountsExactOutRoute`. The transfer authority must be the hot wallet, the platform fee account must be unset, and the destination must be the hot wallet's token account for the output mint. Other Jupiter instructions, such as `exactOutRoute` and newer v2 routes, are denied until they are added to the table.

An account that comes from an address lookup table cannot be checked offline, so a rule that needs it denies the signature. Instructions of an extra program from `SOLANA_PROGRAM_ALLOWLIST` are not decoded. Only add a program you trust with the hot wallet's signature.

The Turnkey Solana policy allows native transfers only to the hot wallet, its wrapped SOL account, or a Jito tip account, and denies every top-level SPL transfer. Turnkey's policy language has no condition that derives an owner's associated token account for an arbitrary mint, so SPL recovery under Turnkey needs a root-quorum approval. The Turnkey EVM policy checks chain, router, native value, and, when `selectors` is passed, the first four bytes of calldata through `eth.tx.data[0..10]`. `eth.tx.function_name` needs an ABI uploaded to Turnkey for each router, so the policy does not use it. The app does not check router selectors.

Pre-sign simulation is viem `simulateCalls` on EVM and `simulateTransaction` on Solana. A revert is `simulation rejected the transaction` and `broadcast` is false, so the spend reservation is released.

`TOKEN_SCREENING=true` rejects a live-lookup token when GoPlus or Blockaid fails, times out, or reports a honeypot, `cannot_sell_all`, or a result other than `Benign`. That path is the unlisted fallback only.

## Repudiation

pino logs the execution report. Authorization, API keys, and OKX signature headers are redacted. `redactError` still strips a 64-hex key and a long base58 string. The spend journal records the idempotency key, the USD amount, the UTC day, and `reserved`, `committed`, or `released`.

## Information disclosure

With Turnkey, the trading keys are not in this process. The process holds the Turnkey API key, which can request a signature inside the policy. The local keystore decrypts into the process only for a dry-run. Live mode does not accept it. Live boot refuses to start when `EVM_PRIVATE_KEY`, `SOLANA_SECRET_KEY`, `HYPERLIQUID_AGENT_KEY`, `KEYSTORE_PATH`, or `KEYSTORE_PASSPHRASE` is set. A dry-run deletes those variables from `process.env` after it loads them. Every config API key, the auth and admin tokens, the notifier URL, and the Turnkey key are redacted from error text. A Hyperliquid signature from Turnkey must recover to the agent address before it is submitted. Logs do not print `Secret` values.

Do not attach a Railway public domain. Boot throws when `RAILWAY_PUBLIC_DOMAIN` is set. Use the private network URL for Postgres and for `RESOLVER_URL`.

## Denial of service

Fastify limits the body to 32 KiB. The global rate limit is 60 a minute. Buy, withdraw, rebalance, and watchlist writes are 10 a minute. Provider calls have a per-minute budget, a 350 ms timeout, and a 500 ms deadline. Three failures, or one compliance response, open that provider. A compliance skip is not retried on another host.

## Elevation of privilege

Withdrawals are native transfers to `OWNER_WITHDRAW_ADDRESSES`. Calldata on an EVM withdraw is `0x`. An empty allowlist denies every withdraw and every bridge plan. Bridge plans never broadcast.

HyperCore refuses `withdraw3`, `usdSend`, `spotSend`, `sendAsset`, `agentSendAsset`, `usdClassTransfer`, `vaultTransfer`, and `approveAgent`. Turnkey's Agent policy cannot see those names inside `connectionId`. The ban is in this process, before submit. Load the agent key, not the master key. The signature scheme follows the Python SDK and has not been checked against a mainnet vector.

`KILL_SWITCH=true`, or the `kill_switch` row in `control_flags`, skips new buys on `/listing` and `/execute`. `/withdraw` is not blocked by the database flag; it stays open as the incident escape hatch, and the env switch holds a live withdraw at `would_send`. Neither deletes a key. Revoke the Turnkey API user to stop signing. See the [runbook](runbook.md).

The daily cap is enforced inside a Postgres transaction with an advisory lock. A second executor cannot pass the boot advisory lock, and `railway.json` runs one replica, so the in-memory idempotency map is never shared.

A compromised or mispriced Hyperliquid agent could try to drain the account through IOC orders crossed far from the mark. The app bounds that path before signing: the order size comes from the per-trade USD cap, and the limit price is the mark moved by at most the slippage cap, rounded to the venue wire format. An order the venue reports as an error, or that fills nothing, releases the spend reservation.

## What this does not cover

A quoted router can still be a hostile contract the aggregator returned, inside the allowlist you configured. The caps bound the size. Screening does not run on the watchlist hot path. Research CI does not run these tests and does not fetch market data for them.
