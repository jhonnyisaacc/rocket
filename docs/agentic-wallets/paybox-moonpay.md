# Integrate Paybox

Use the Paybox CLI, package `@paybox-sh/sdk` 2.2.0, for same-chain swaps on Solana and on a short list of EVM chains. Facts on this page are as of Oct 2026.

Rocket does not call `paybox`. Run the CLI from the separate process that is allowed to sign.

The native MCP connector fails to load with Cloudflare error 1010. That failure is tracked in [moonpay/paybox-plugin#6](https://github.com/moonpay/paybox-plugin/issues/6). Use the CLI.

## Set up the CLI

Have a human complete the OAuth device approval. Then link a local signing key.

```bash
paybox connect
paybox whoami
```

Continue only when `whoami` reports `canSign: true`.

The paired key is stored unencrypted in the local Paybox config. Restrict that file to the user who runs the CLI. Treat the host as sensitive.

Grants are set per wallet in the Paybox app. The fields that matter are `approval_mode`, `max_slippage_bps`, and the spend limit. As of Oct 2026 the app does not offer a spend limit. Cap size in the calling code, and fund the wallet with only what that code may spend. Set `approval_mode` to autonomous for unattended same-chain swaps. The CLI cannot edit grants. `paybox account-change` prints a link to the manage page.

## Approve a transaction

Autonomous mode signs a same-chain swap that stays inside the grant. Slippage you pass must be less than or equal to `max_slippage_bps`.

The Jupiter plugin is not an unattended path. `paybox plugins use jupiter` still returns `await_human` or `signing_ui_required` for a swap, even when the grant is autonomous. Use it for discovery, limit orders, or DCA orders only when a human is present to sign.

## Choose a chain and an amount

Supported networks, as of Oct 2026, are Solana, Ethereum chain id 1, Base chain id 8453, and Robinhood Chain chain id 4663.

On Solana, pass `solana:mainnet` for both the source chain and the destination chain. The standard CAIP Solana id is rejected.

```bash
paybox swap --src-chain solana:mainnet --dst-chain solana:mainnet --src-token <mint> --dst-token <mint> --amount <smallest-unit> --slippage <bps>
```

`--amount` is the smallest unit. USDC uses 6 decimals. SOL uses lamports. The native token id is `native`. `--slippage` is in basis points.

On Base, pass `eip155:8453`. The USDC contract is `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`.

```bash
paybox swap --src-chain eip155:8453 --dst-chain eip155:8453 --src-token 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 --dst-token native --amount <smallest-unit> --slippage <bps> --wait
```

Issue 7 passes `--credential` on the swap command. Supply the selector the CLI already stored. Do not supply a key.

Always pass `--wait` on an EVM swap. Without it, the swap stalls at `pending_signature` after the token approval.

A same-chain round trip costs about 0.7 percent to 1.2 percent, plus a 0.3 percent router fee on some routes, as of Oct 2026. The first buy of a new SPL token also pays about 0.0015 SOL to create the token account.

Do not swap from Base to Robinhood Chain. That route hung, and nothing bridged. The hang is tracked in [moonpay/paybox-plugin#7](https://github.com/moonpay/paybox-plugin/issues/7).

## Confirm a transaction

A swap that you do not wait on returns `pending_confirmation`. Poll the top-level request id until the status is terminal.

```bash
paybox request <request-id>
```

Treat the trade as done only when the status is `success`. A success payload includes `output.value.tx_hash` and `confirmed_at`. On Solana that round trip is about 5 seconds to 6 seconds. On Base, a swap passed with `--wait` finishes in about 2 seconds.

If the status is anything else, treat the trade as failed. Price moving past the slippage cap is a common cause. Do not place a dependent order on an unconfirmed swap.

## Handle failures

If `whoami` does not report `canSign: true`, stop. Repeat `paybox connect` and have the human approve the device login again.

If an EVM swap sits at `pending_signature`, you omitted `--wait`. Do not send a second swap for the same trade. Inspect the request, and retry only after you know the first one failed.

If a request sticks, the CLI cannot list it and cannot cancel it. That gap is tracked in [moonpay/paybox-plugin#7](https://github.com/moonpay/paybox-plugin/issues/7). Do not send another swap on that wallet until you know the stuck request is finished.

If the public Solana RPC returns HTTP 429, you are over about 1 request per second. If the public Base RPC rejects the call, send a normal User-Agent header. Use a paid RPC for monitoring either way.

If a Jupiter swap asks for `await_human` or `signing_ui_required`, stop the bot path. A human has to sign that plugin swap.

## Follow the safety rules

Keep the signing key file private. Do not print it, and do not copy it into chat.

Cap each trade in code. The grant will not do that for you, as of Oct 2026.

Stay on one chain per swap. Get a quote, check price impact, and only then execute. Read [Handle safety and fast execution](execution-lessons.md) for the shared checks.
