# What the listing trader refuses to do

The process can hold a hot-wallet key and talk to aggregators. The controls below are the ones the code enforces. They are not a promise about the exchanges.

## Keys stay in the process

Wallets are created locally. The keystore is scrypt plus AES-256-GCM. The file stores salt, iv, ciphertext, and public addresses. Logs, JSON responses, and thrown errors run through redaction that replaces the loaded secret, a 64-hex key with or without `0x`, and a long base58 string. The create-wallet command exits if the raw key would appear in the file it writes.

There is no admin route that returns a key. Withdrawals go only to `OWNER_WITHDRAW_ADDRESSES`, and only as native gas, and only when live mode is on. An empty allowlist denies every withdraw. The executor does not implement a general transfer API.

HyperCore uses a separate agent key. The official pages checked describe API wallets as signers for a master account. They do not state that an agent is unable to withdraw. This service still refuses `withdraw3`, `usdSend`, `spotSend`, `sendAsset`, `agentSendAsset`, `usdClassTransfer`, `vaultTransfer`, and `approveAgent`. Load the agent key, not the master key. The action hash follows the Python SDK's L1 scheme, and it has not been checked against a mainnet test vector. A bad signature is an exchange reject, and a reject after the request is sent still counts against the daily cap so a retry cannot double-send.

## Limits are in the request path

Every buy passes `checkLimits` before a quote is accepted. The kill switch, the per-trade cap, the daily cap, the slippage cap, the chain allowlist, and the 1x leverage cap are ordinary branches on that path. Dry-run never calls `send` and never increments spend. Live mode will not boot without `DATABASE_URL`, because the spend journal has to survive a restart. A broadcast that throws after the transaction was submitted keeps the journal row. A failure before broadcast deletes it, so a bad quote does not eat the cap.

The in-memory idempotency map is per process. Two replicas can both pass it. Run one executor replica, and rely on the journal's primary key for the live case.

## Matching prefers a miss over a lookalike

Ticker equality is exact. Name equality is exact after normalization, including a Korean alias when one was stored. A lookalike does not fall through to the live search. The live search itself has a short timeout and returns no trade when the result is late, empty, or ambiguous. Pool rows for an unknown DexScreener slug are dropped.

Quotes with no impact are dropped. A firm quote above the slippage cap is not signed. LI.FI is same-chain only. zkSync can be quoted and cannot be sent. Native balances cannot be spent down through the gas reserve.

## What this does not cover

The hot wallet can still lose the funds it holds if the host is compromised or if a quoted route is a hostile contract the aggregator returned. The caps bound the size. They do not review the contract. Aggregator API keys in the environment are not written to the health payload, and the health payload is the public config only.

Research CI does not run these tests and does not fetch market data for them. The listing-trader workflow runs `npm test` on this tree alone.
