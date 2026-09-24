# Integer rounding and routed-user mismatch experiment

Completed offline; zero new Helius credits. Extended the event decoder through cashback/buyback fields using the already inspected published layout. Shareholder/quote extensions remain unparsed. No simulated returns or live execution.

## Amount reconstruction

Across 102 cached curve trades, the ordinary integer curve formulas reproduce the emitted SOL amount exactly for all 35 `buy` and 54 `sell` events. The 13 exact-input buys differ consistently by one lamport when evaluated using the ordinary exact-output buy formula. This is instruction-specific, not random numerical noise. Do not patch the simulator by adding a fitted constant: implement exact-input semantics separately and verify token output before counterfactual use.

All 102 emitted base fees equal ceil(sol_amount × fee_basis_points / 10000). This validates the observed base fee rounding only. Tail fields consistently decode cashback_fee_basis_points=30 and buyback_fee_basis_points=5000. Their economic denominator and relationship to base fees are not independently verified; treating these as an additional 50% trade fee would be unjustified. They remain uninterpreted parameters pending protocol-source validation.

The reconstruction infers pre-reserves from the same event's emitted post-reserves and amounts. It checks formula consistency but is not an independent historical replay. Independent pre-state continuity and state gaps must still be checked.

## User mismatch resolved as a routed flow

Transaction `2jxvHMszMf2JEet7KVEd1bbkN1PjdiYKBBcahyiJaWKJznvgDLEvtSV6ZHwFFEgCuLaFgjQMW9EmF68XZW3NBeGC` first transfers exactly 360754552864 raw tokens into the event user's token account, then transfers exactly that amount into the reserve. The intermediate user has no net token change even though the sell event is real. Additional native/WSOL forwarding is visible. The event user is therefore not safely equated with the original economic trader. This resolves the discrepancy without falsifying the net-balance ledger or treating the intermediate account as a new independent trader.

## Next concrete checks

Validate full fee-distribution semantics from primary protocol sources; reconstruct exact-input quotes rather than fitting observed one-lamport differences; test independent adjacent-state continuity and report missing transactions. Keep routed actors distinct from verified wallet identities. Exit-window acquisition follows once those checks pass. NO_EDGE_VALIDATED remains unchanged.
