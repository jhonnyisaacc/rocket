# Cashflow reconciliation and concentration experiment

Completed offline on the 100 cached historical-wallet records. Zero new Helius calls or credits. Research only; NO_EDGE_VALIDATED.

## Results

Parsed successful system transfers and account creations, subtracting transaction fees only for the actual owner fee payer, explain the exact native balance change in 55/100 records. All 18 failed transactions reconcile to owner-paid fees alone; their listed but reverted transfer instructions must not be counted.

Of the 27 previously unassigned records, 17 reconcile exactly. Their combined native delta is -10.417207883 SOL, but this is **not a trading loss**: the group contains direct outgoing/incoming transfers, dust receipts, an ephemeral wrapped-SOL receipt/closure and unresolved direct program lamport changes. The unresolved net is 0.132202149 SOL across ten records under this parser. No automatic allocation to the twelve trade groups is justified.

Seven records overall close token accounts to the owner. Closure refunds cannot safely be inferred from opening account balances: a wrapped-SOL account can be created, funded, receive tokens and close within the same transaction. Likewise, summing all account creation amounts overstates retained rent if some accounts close immediately. The earlier audit's account_creation_lamports field is gross creation funding, not a proven recoverable-rent adjustment. The first manually inspected losing pair remains a specific case; do not generalize its rent adjustment to other groups.

## Concentration check on the twelve balanced groups

Observed native cashflow across the twelve groups: +3.015797035 SOL. Largest contribution: +2.835270528 SOL, mint `EcPhZph4VXgHW279x5bYX2VjvWBHW5TTQingCAtEpump` (Solana). Excluding it leaves +0.180526507 SOL. The second-largest contribution is +0.939069856 SOL; excluding both leaves -0.758543349 SOL.

This does not disprove a positively skewed strategy: rare winners can be the economic source of returns. It does show why the headline sum and six-positive/six-negative count are inadequate evidence of consistency. The sample is selected, partial, one wallet, and these are cashflow groups rather than a fully reconciled strategy return series. A follower could miss precisely the tail events that dominate results.

## Completed next backlog item

Added machine-readable independent Fomo fill adjudications in `data/fomo-fill-adjudications.json`, retaining canonical contracts, owner, signatures, timestamps and exact integer amounts. Extended offline regression tests to validate both adjudications and all failed-transaction fee-only accounting. Five tests pass. The generic ledger remains conservative; the explicit adjudication layer carries the verified public-fill correspondence.

## Remaining evidence gap

Pump-style sells can transfer native lamports directly from program-owned reserves without parsed system-transfer instructions. Those residuals require reserve/fee-recipient accounting, not relabeling them as unexplained profit or discarding them. All 33 positive-native single-owner-mint records inspected have one non-owner native-debited account, providing a focused next reserve-verification target. Economic purpose is not proven solely by that pattern.

Next execution: map reserve accounts to the observed swap instruction account lists, reconcile program-direct reserve debits against wallet/fee-recipient credits, and distinguish transient account rent from retained deposits. Then use the largest and a losing cycle as paired historical-price-path acquisition targets; do not pretend leader fill prices are executable delayed-follower prices.
