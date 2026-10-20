# Agentic wallet integration

This index is the lookup for external agent-wallet CLIs. Read one provider page for setup, approval, amounts, confirmation, and failures. Facts in this directory are as of Oct 2026.

Rocket stays read-only. Nothing in this directory places an order or signs a transaction.

## Compare providers

| Provider | Chains | Auth and approval | Limits | Confirmation | Status |
| --- | --- | --- | --- | --- | --- |
| [MetaMask Agent Wallet](metamask-agent-wallet.md) | EVM chain ids on the MetaMask page. No Solana in the CLI. | Guard mode inside policy. MFA when a check fails. | Rolling 24 hour outflow. Beast mode removes it. | `mm transfer --wait`, then the request list and `mm tx history`. | Usable on EVM when a human can approve MFA. |
| [Paybox](paybox-moonpay.md) | Solana, Ethereum, Base, and Robinhood Chain. | OAuth device login, a local signing key, and grants in the Paybox app. | No spend cap in the product. Cap size in the calling code. | Poll `paybox request`. Pass `--wait` on EVM. | CLI works for same-chain swaps. MCP load is blocked. Swaps from Base to Robinhood Chain are blocked. |
| [Phantom](phantom.md) | Solana agent wallet. Not reachable. | Browser approval, then the client returns HTTP 403. | No limit applies. The client never starts. | None. No transaction is created. | Blocked. Do not spoof the client. |

## Pages

- [Integrate MetaMask Agent Wallet](metamask-agent-wallet.md)
- [Integrate Paybox](paybox-moonpay.md)
- [Integrate Phantom](phantom.md)
- [Handle safety and fast execution](execution-lessons.md)
