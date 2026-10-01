# MC-021 frozen design — inventory-backed unsigned PumpSwap sell simulation

Frozen before simulation or outcome inspection on 2026-09-24 UTC. This is a bounded execution diagnostic, not a strategy return cohort or permission to trade.

## Selection and inputs

Use the three canonical pools already selected in MC-017/019/020. Read the latest 20 confirmed pool signatures each, then the first six signed transactions per pool, in that fixed pool order. For a non-pool token account with a positive base-token balance change, read its current account balance and owner native SOL balance. Select the first pool in lexicographic mint order containing a non-pool account with positive current balance and an owner with at least 0.01 SOL, then the first such account in newest-transaction order. This is a feasibility selection, not a performance sample. Save all candidate inputs and response clocks, including failed RPC calls.

The selected mint is `9NnvxfavSswySguwuQ4Pa2wVZxM58x24rCXMb8rKpump`, pool `7LgDUm7jmZ2TQc7GBzVuGSBPscWGtph4sQXrKZZ22ztg`, public holder `HatUYhTtyCHruT9MoYxNKqw3A3wXYP43gsQoFbgqSsFZ`, base token account `DPbw3QZfpKDba4T9n5be5nfjEjjrZT82MFVGnq4rsMeW`. A confirmed read at slot 450155771 found 13,868,885,223,737 raw base units; a later confirmed owner-balance read at slot 450155818 found 3,979,466,164 lamports. The pool's first six signed transactions and all account reads are retained as selection provenance.

Use official `@pump-fun/pump-swap-sdk` version 1.20.0, npm tarball SHA-256 `c558b4fb8ca7f5cdcd7dfaa23a9b026212380ecf2ba54efe651f264745a7a9f1`. Fetch global config, fee config, pool, both mints, both pool vaults, the holder base account and quote account in one confirmed `getMultipleAccounts` response. Price a **10,000,000,000 raw-base-unit** sell with the SDK's `sellBaseInput`, 1% slippage, and build the SDK's `sellInstructions` for the holder. Include compute limit 400,000 and compute unit price 100,000 micro-lamports. The holder is only a public address standing in for hypothetical Rocket inventory; no private key is used.

Compile an unsigned transaction with this public holder as the nominal fee payer and signer, use `simulateTransaction` with `sigVerify=false`, `replaceRecentBlockhash=true`, confirmed commitment, and capture the request, response, dispatch/receive clocks, context slot, program logs, units, and any returned token accounts. Never call `sendTransaction` or solicit a signature. Any missing account, state mismatch, SDK error or simulation error is a recorded failure. A simulation success supports program execution only at its response bank, not landing, inclusion, execution latency, or achieved Rocket cash recovery. The selected holder's later account state may change before simulation; keep that failure in the denominator rather than changing selection.

## Follow-up measurement amendment

The first simulation returned a successful program result but the temporary WSOL account was closed, so its post-state was null/zero. Before repeating the same frozen amount and holder, add the public owner's native SOL account to the one-bank input and simulation account-return list. This measures a simulated net native-balance change, including the transaction fee and any rent movement, while preserving the first attempt. The second call is a follow-up diagnostic, not a replacement for the first outcome.
