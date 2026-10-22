## Why

## What changed

## Scope

Name what this change covers and what it deliberately leaves out. One pull request carries one send path, one caller surface, or one gate. A larger change names the stack order and the slice it leaves to the next pull request.

## Verification

## Wallet value-moving changes

Complete this section for any change under wallet that can quote, sign, send, withdraw, or spend. Write n/a with a reason when a line does not apply.

- [ ] I listed every caller that can reach the send. The list covers HTTP routes, the MCP tools, and service to service calls.
- [ ] I tested the reachability matrix. Each caller by live and dry mode by token role by approval mode asserts zero sends or one named allowed decision.
- [ ] The final route gets rechecked at the send point. Enabled chains, liveSend, support tier, screening, and the flagged buy token all run against the picked route, not only the primary.
- [ ] Every value-out path joins a cumulative ledger with an idempotency key, and one kill switch stops all of them.
- [ ] Each gate has a paired live test with a fake signer. A would_send result alone does not prove a gate.
- [ ] Vendor traffic goes through the shared fetch wrapper. Redirects stay on the vendor host and bodies stay under the byte cap.
