# Fomo fill attribution: first strong transaction match

## Evidence

Public profile: https://fomo.family/profile/unipcs?tradeId=c67d250b-df85-4244-a4ab-59a9171c86a2

Observed September 16, 2026. Selecting Min size >$1K reduced 177 displayed events to 17. The UI distinguishes Buy, Sent and Received. The relevant Buy displays $49,977.50 at $66.1M market cap, August 30 12:01 PM. A second Buy displays $17,666.60 on August 25 5:45 PM; not yet verified.

One bounded Helius query of the previously identified USELESS token account, August 29 through before September 1 UTC, returned 16 transactions. A pagination cursor exists; completeness is not asserted. No pagination was requested. Estimated new cost: 10 credits; actual billing not checked.

Matching signature:
`4yDik2r5JxQtgKn1SjVw6zhHjMMnibFhwnEPswx7PnK2qHpQA7mbJVHWsWXGTaVToR6HwphoraxM1o8vMc6K3jX1`

- Block timestamp: August 30, 2026 15:01:22 UTC, consistent with the UI minute at UTC−3. This is a match-based timezone inference, not verified browser configuration.
- Candidate owner `2heJbC32Tpfcb3nbUb5ER61K11FGZVfVGtVnDm6LDogF` is a signer.
- Owner USDC net debit: 50,000 USDC.
- Owner USELESS net credit: 755,233.667715 tokens, mint `Dz9mQ9NzkBcCsuGPFJ3r1bS4wgqKMHBPiVuniW8Mbonk`.
- Successful transaction contains swap logs and routed exchange instructions.
- Two additional top-level owner-authorized USDC transfers: 10 and 12.5 USDC. Their sum explains exactly the difference between total debit and Fomo displayed buy value: 50,000 − 22.50 = 49,977.50. Fee-like purpose inferred; recipients' economic roles not verified.
- Fee payer differs from the candidate owner. Fee-payer-only wallet tracking would miss attribution.

Conclusion: high-confidence correspondence of this public Fomo buy to this on-chain wallet transaction, supported by mint, minute, exact amount reconciliation, signer authority and prior holdings matches. This is not proof of legal identity, full portfolio attribution, profitability, or repeatable follower returns. The machine-generated ledger intentionally retains conservative unverified labels; this manual adjudication is the separate evidence layer.

## Offline ledger findings

200 previously cached records decoded without additional API calls:

- Candidate Unipcs recent page: 100 incoming-only token flows, all with parsed inbound transfers, none with parsed outbound token transfers, no owner native outflow, no owner signatures. These are not established buys; do not trigger on them. Fee/referral attribution remains unproven.
- Historical cohort sample: 22 token-in/native-out candidates, 33 token-out/native-in candidates, 18 failed transactions, 27 without owner token changes. The 55 candidates are not yet verified swaps or complete round trips. Native balance differences include rent and fees.

## Next experiment

Use the verified buy as a decoder fixture, confirm a second independent Fomo fill, then expand only to a small verified wallet set. Record buys, sells, transfers, transaction fees, unknown flows and opening inventory separately. Reconstruct matching round trips before reporting any leader PnL. Follower testing additionally needs executable price paths, delay, slippage, entry/exit rules fixed before holdout, and losing/delisted assets included.

No live signal, autonomous trade, or continuous collector enabled. Status: NO_EDGE_VALIDATED.

Artifacts: `data/helius-pilot-2026-09-16/*_ledger.jsonl`, `ledger_summary.json`, and cached `unipcs_useless_aug30.json`. Scripts are cache-first or offline. Query documentation: https://www.helius.dev/docs/rpc/gettransactionsforaddress
