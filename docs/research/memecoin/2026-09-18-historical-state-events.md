# Historical state recovery from cached logs

Advanced the missing-state prerequisite without another Helius request. Inspected the publisher's current TradeEvent layout at https://raw.githubusercontent.com/pump-fun/pump-public-docs/main/idl/pump.json on September 18, 2026. Implemented a fixed-prefix decoder through creator_fee, requiring the event discriminator and active Pump program invocation. Failed transactions are excluded. Remaining event bytes are explicitly unparsed; current layout compatibility with historical records is checked, not presumed wholesale.

Recovered 69 curve events from the losing-case market cache and 33 from the winning-case curve entry cache. All 102 event timestamps match block timestamps; 101 user token deltas match the event quantity. Virtual SOL/token reserves and observed fee fields are now available for each recovered event. Both samples report fee_basis_points=95 and creator_fee_basis_points=0 in this prefix; additional tail fees may exist and must be decoded before treating these as total fees.

## Validation discrepancy retained

None of the event real-token-reserve fields directly equal the reserve token-account balance. However, every one of the 102 differences is exactly 206,900,000,000,000 raw units. This is consistent with a fixed excluded token allocation, but its protocol meaning is not yet verified and must not be silently labeled spendable liquidity. The decoder records this offset separately instead of forcing equality.

One user net-token delta does not equal the event amount: `2jxvHMszMf2JEet7KVEd1bbkN1PjdiYKBBcahyiJaWKJznvgDLEvtSV6ZHwFFEgCuLaFgjQMW9EmF68XZW3NBeGC`. Additional transfers or routing may explain it; exclude this record from fill validation until inspected.

## Consequence and next work

Historical virtual reserves are not wholly unavailable: they are present in our cached event logs. This removes a data-access obstacle but does not yet produce an executable replay. Next: decode and validate version-dependent fee tails, reconcile the single user-delta mismatch and verify the fixed reserve offset from primary protocol documentation. Reproduce known trade amounts using recovered pre/post virtual reserves and exact integer rounding before simulating new order sizes. Then acquire only missing fixed-exit state windows. No follower returns calculated; NO_EDGE_VALIDATED unchanged. New Helius credits: zero.
