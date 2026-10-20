# Integrate MetaMask Agent Wallet

Use the `mm` CLI 7.x to create an EVM wallet, set a policy, and send a transfer or a swap. Facts on this page are as of Oct 2026.

Rocket does not call `mm`. Run the CLI from the separate process that is allowed to sign.

## Set up the CLI

Install Node 22 before you install the CLI.

Create the wallet in guard mode. There is no rename command, so choose the name first.

```bash
mm wallet create --chain-namespace evm --name <name> --trading-mode guard
```

The active wallet is global to the CLI session. If several bots share one session, select your wallet again after any `mm wallet select`. Do not select another wallet while a position manager is running.

## Approve a transaction or a policy

Guard mode sends a transaction with no extra prompt only when every check below passes.

- The transaction matches the allowlists.
- Blockaid screening passes.
- Rolling 24 hour outflow stays under the policy limit.

If any check fails, the request stays in `AWAITING_MFA`.

Every swap counts toward outflow. A round trip spends about twice the trade size against the limit. Set the limit for the trades that can be in flight together.

Read or replace the policy for the selected wallet.

```bash
mm wallet policy get
mm wallet policy set --policy <policy.yaml>
```

Loosening a policy needs MFA. Tightening a policy confirms at once. Only one policy request can be pending on a wallet. A second change returns `WALLET_POLICY_APPROVAL_IN_PROGRESS` until the first request expires. `mm wallet policy set --no-wait` still starts that approval.

Beast mode removes the limits. Turning it on needs two-factor authentication. Turning it off takes effect at once.

With social or browser login, MFA arrives as a link to the account email. With QR login, MFA arrives as a MetaMask Mobile notification. The CLI does not print the approval URL. Links expire in about 10 minutes. Login codes expire in about 3 minutes. Mail delay can expire a forwarded link. Have the human approve the request directly.

The MetaMask developer dashboard has no controls for this wallet. Approval happens only through that link or notification.

Each transfer over the limit needs its own approval. Send one transfer and wait for it to finish before you send the next. Do not queue several transfers in one script. A denied transfer can be followed by later transfers that still run.

## Choose a chain and an amount

The CLI is EVM only, as of Oct 2026. It does not send Solana transactions.

Pass a numeric chain id on every transfer and swap. The CLI also accepts testnets. Mainnet ids it accepts, with public network names as of Oct 2026, are below.

| Chain id | Network |
| --- | --- |
| 1 | Ethereum |
| 10 | Optimism |
| 56 | BNB Smart Chain |
| 137 | Polygon |
| 143 | Monad |
| 999 | HyperEVM |
| 1329 | Sei |
| 4326 | MegaETH |
| 4663 | Robinhood Chain |
| 8453 | Base |
| 42161 | Arbitrum One |
| 43114 | Avalanche C-Chain |
| 46630 | Listed by the CLI. This guide does not assign a network name. |
| 59144 | Linea |

Native gas is charged on top of the token amount. Keep a small native reserve on the chain you use.

## Confirm a transaction

Send one transfer and wait for the CLI result.

```bash
mm transfer --to <destination> --amount <amount> --chain-id <chain-id> --token <token> --wait --json
```

Read open approvals and past transactions before you treat the send as finished.

```bash
mm wallet requests list
mm tx history
```

Request a swap quote before you execute. Default slippage is 0.5 percent. For an illiquid token, set slippage from 2 percent to 5 percent.

```bash
mm swap quote --slippage <percent>
```

`--to-chain-id` bridges and swaps through Relay. Pass `--strategy` or `--refuel` only when you have checked what this CLI version does with that flag.

## Handle failures

If the status is `AWAITING_MFA`, stop. Ask the human to approve that request. Do not send another transfer until it finishes.

If policy set returns `WALLET_POLICY_APPROVAL_IN_PROGRESS`, wait until the pending request finishes or expires. Do not start a second policy change.

If the approval link expires, create a new request. Have the human approve it from the original channel.

If the active wallet is not the one this bot owns, run `mm wallet select` for that wallet and retry. Do not change the selection while a position manager is running.

If the chain rejects the transaction for lack of native gas, add a small gas reserve and retry that same transfer once.

## Follow the safety rules

Leave guard mode on unless a human has enabled beast mode on purpose. Do not loosen a policy from a bot. Loosening needs a human MFA step.

Do not share one CLI session across bots unless you re-select the wallet before each action.

Read [Handle safety and fast execution](execution-lessons.md) before you automate quotes or copy a trade.
