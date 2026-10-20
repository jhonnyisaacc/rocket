# Integrate Phantom

Phantom Connect SDK and MCP access to an agent-controlled Solana wallet is blocked, as of Oct 2026. Rocket does not call Phantom.

Wait for an official client fix before you retry.

## Set up the client

Do not start a bot that depends on Phantom Connect SDK or the Phantom MCP server. Login can complete in the browser and still fail in the client.

The failure is HTTP 403 from a client filter. It is tracked in [phantom/phantom-connect-sdk#406](https://github.com/phantom/phantom-connect-sdk/issues/406).

## Approve access

Device approval in the browser is not enough. The client call after that approval can still return 403. The session never becomes usable.

Do not spoof the client. Do not spoof the User-Agent. A forged header hides a broken client and can fail again on the next release.

## Choose a chain and an amount

There is no supported chain call, as of Oct 2026. Do not send a Solana amount through this client until issue 406 is fixed in an official release.

## Confirm a transaction

There is no confirmation method. A 403 happens before a transaction exists. Do not poll for a signature you never received.

## Handle failures

If the client returns HTTP 403, stop. Do not retry with a forged client header.

If a later official release clears the 403, re-test login, a quote, and a confirmed signature on a fresh session before you trust the client.

## Follow the safety rules

Do not replace this client with another signer and still call the result a Phantom agent wallet. Read [Handle safety and fast execution](execution-lessons.md) when an official client works.
