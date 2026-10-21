---
name: rocket-get-started
description: Understand what Rocket wallet access the user has granted and how to widen it. Use when the user asks what the wallet can do, or when a tool is blocked by a missing chain, a spend cap, or a strict approval mode. Covers the grant model and the approval modes.
license: MIT
---

# Rocket access, and what to do when it blocks you

## Invoke this skill when

- A tool returns an access block. It may be a disabled chain, a cap, or a strict approval mode.
- The user asks what the wallet can do, or wants to change it.

## Granted is not the same as configured

`wallet_status` shows the mode, the enabled chains, and the caps that the executor enforces. A chain that is configured but not in `ENABLED_CHAINS` cannot trade. A router that is not in the Turnkey policy cannot sign. Most blocks are a grant that was never made. They are not a missing feature.

## Approval modes

Each deployment carries one mode in `WALLET_APPROVAL_MODE`. The default needs a passkey.

| Mode | Behaviour |
| --- | --- |
| `autonomous` | Signs a screened live send without asking, inside its caps |
| `iframe` | Needs a confirm inside the signing window |
| `always_approve` | Needs a passkey for every live send |

A blocked send is often the mode. It is not always a permission. Under `always_approve` a live listing returns `pending_approval` until a human approves it.

## Widening access

A human widens access. The agent never does. The human enables the chain, raises the cap, or adds the router in the Turnkey console. Then the human restarts the executor. The agent can name the missing grant from `wallet_status`. It cannot grant it.

## Never

- Never ask for a private key, a seed phrase, or a passphrase. No Rocket flow needs one.
- Never print a key, a token, or a signed payload into chat.
- Never call a live listing to test whether a grant works. Use a dry-run swap.
