# Threat model

The listing trader can move the funds in the hot wallet. This page uses STRIDE so each control is tied to a threat. The controls are what the code does. They are not a promise about an exchange or a signer vendor.

## Spoofing

`AUTH_TOKEN` is required at boot and must be at least 16 characters. Mutating routes compare `Authorization: Bearer` with SHA-256 and `timingSafeEqual`. `GET /health` is the only open route, and it returns `publicConfig` only. Secrets, the router list, and the approval cache are not in that payload.

The collector and the executor share that token when the executor calls the resolver. A missing or short token refuses boot.

## Tampering

Zod parses every request and every aggregator or screening body this service acts on. A mismatch is a 400 or a null quote. Firm quotes are checked again against the slippage cap before sign.

App policy and the Turnkey policy both constrain destination, chain, native value, and Solana program ids. The checked-in file is `policies/turnkey.json`. `ROUTER_ALLOWLIST_JSON` is a map of chain id to router addresses. A router allowed on one chain is denied on another. An empty list for that chain denies the swap. A token sell with a non-zero native value is denied. Solana program ids outside the base set plus `SOLANA_PROGRAM_ALLOWLIST` deny the signature. A System Program or SPL transfer must pay the hot wallet or an allowlisted withdraw address.

Pre-sign simulation is viem `simulateCalls` on EVM and `simulateTransaction` on Solana. A revert is `simulation rejected the transaction` and `broadcast` is false, so the spend reservation is released.

`TOKEN_SCREENING=true` rejects a live-lookup token when GoPlus or Blockaid fails, times out, or reports a honeypot, `cannot_sell_all`, or a result other than `Benign`. That path is the unlisted fallback only.

## Repudiation

pino logs the execution report. Authorization, API keys, and OKX signature headers are redacted. `redactError` still strips a 64-hex key and a long base58 string. The spend journal records the idempotency key, the USD amount, the UTC day, and `reserved`, `committed`, or `released`.

## Information disclosure

With Turnkey, the trading keys are not in this process. The process holds the Turnkey API key, which can request a signature inside the policy. The local keystore decrypts into the process only when `ALLOW_LOCAL_SIGNER=true` or when live mode is off and a keystore is configured for a dry run that never signs. Logs do not print `Secret` values.

Do not attach a Railway public domain. Boot throws when `RAILWAY_PUBLIC_DOMAIN` is set. Use the private network URL for Postgres and for `RESOLVER_URL`.

## Denial of service

Fastify limits the body to 32 KiB. The global rate limit is 60 a minute. Buy, withdraw, rebalance, and watchlist writes are 10 a minute. Provider calls have a per-minute budget, a 350 ms timeout, and a 500 ms deadline. Three failures, or one compliance response, open that provider. A compliance skip is not retried on another host.

## Elevation of privilege

Withdrawals are native transfers to `OWNER_WITHDRAW_ADDRESSES`. Calldata on an EVM withdraw is `0x`. An empty allowlist denies every withdraw and every bridge plan. Bridge plans never broadcast.

HyperCore refuses `withdraw3`, `usdSend`, `spotSend`, `sendAsset`, `agentSendAsset`, `usdClassTransfer`, `vaultTransfer`, and `approveAgent`. Turnkey's Agent policy cannot see those names inside `connectionId`. The ban is in this process, before submit. Load the agent key, not the master key. The signature scheme follows the Python SDK and has not been checked against a mainnet vector.

`KILL_SWITCH=true` skips new buys and live withdraws. It does not delete a key. Revoke the Turnkey API user to stop signing. See the [runbook](runbook.md).

The daily cap is enforced inside a Postgres transaction with an advisory lock. Two replicas can still both pass the in-memory idempotency map. Run one executor.

## What this does not cover

A quoted router can still be a hostile contract the aggregator returned, inside the allowlist you configured. The caps bound the size. Screening does not run on the watchlist hot path. Research CI does not run these tests and does not fetch market data for them.
