# Live scan confirm

NO_EDGE_VALIDATED. Human-gated. Read-only. Identification is not an entry.
A WATCH_ENTER row is not a buy. execution_enabled is false.

Liquidity is 2 × the current PumpSwap quote-vault balance in USD at the snapshot SOL price. Graduation-time `real_quote_reserves` is not used. A missing or zero vault is null and SKIP.

- workflow: memecoin.scan
- research: INSUFFICIENT_EVIDENCE
- operational: HEALTHY
- coverage_status: OBSERVED
- edge: NO_EDGE_VALIDATED
- execution_enabled: False
- notice: A WATCH_ENTER row is not a buy.
- selected: 20
- selected_cap: 20
- age_floor_seconds: 1800
- liquidity_floor_usd: 10000
- decision_time: 2026-09-23T08:38:52.533836+00:00
- WATCH_ENTER: 0
- SKIP: 1
- TOO_EARLY: 0
- AVOID: 19
- liquidity_usd range: 2.62 to 991.65 (19 priced values, 1 null)

## Provider health

- browser:fomo.family: HEALTHY coverage=fomo.family login-walled; pump.family/api/sales migrated+closed excluded=0
- browser:pump.fun: HEALTHY coverage=frontend-api-v3.pump.fun GET /coins complete=true offsets=0,26 second=ok
- x: UNAVAILABLE failure=OPTIONAL_NOT_CONSULTED coverage=optional
- helius: HEALTHY coverage=getAccountInfo+getTokenLargestAccounts+quoteVault confirmed=20 liquidity=19

## Decision rows

- AVOID $CATTY age=2154 liquidity_usd=569.97 reasons=['liquidity_below_floor'] graduation=graduated window=closed
- AVOID My age=2284 liquidity_usd=4.32 reasons=['liquidity_below_floor'] graduation=graduated window=closed
- AVOID JEANWIFHAT age=2315 liquidity_usd=811.81 reasons=['liquidity_below_floor'] graduation=graduated window=closed
- AVOID CATO age=2412 liquidity_usd=398.72 reasons=['liquidity_below_floor'] graduation=graduated window=closed
- AVOID Hermès age=2428 liquidity_usd=137.31 reasons=['liquidity_below_floor'] graduation=graduated window=closed
- AVOID LOTTO age=2480 liquidity_usd=89.72 reasons=['liquidity_below_floor'] graduation=graduated window=closed
- AVOID JEANDIESEL age=2497 liquidity_usd=991.65 reasons=['liquidity_below_floor'] graduation=graduated window=closed
- SKIP VSOF age=2509 liquidity_usd=None reasons=['liquidity_unknown'] graduation=graduated window=closed
- AVOID $CAT age=2718 liquidity_usd=190.98 reasons=['liquidity_below_floor'] graduation=graduated window=closed
- AVOID TRUMP age=2756 liquidity_usd=73.24 reasons=['liquidity_below_floor'] graduation=graduated window=closed
- AVOID ₽ age=2819 liquidity_usd=210.15 reasons=['liquidity_below_floor'] graduation=graduated window=closed
- AVOID Robinhood age=2861 liquidity_usd=73.88 reasons=['liquidity_below_floor'] graduation=graduated window=closed
- AVOID $CAT age=2908 liquidity_usd=384.31 reasons=['liquidity_below_floor'] graduation=graduated window=closed
- AVOID UNA age=2930 liquidity_usd=9.85 reasons=['liquidity_below_floor'] graduation=graduated window=closed
- AVOID AHOOD age=3162 liquidity_usd=2.62 reasons=['liquidity_below_floor'] graduation=graduated window=closed
- AVOID BFC age=3452 liquidity_usd=50.66 reasons=['liquidity_below_floor'] graduation=graduated window=closed
- AVOID ToadPepe age=3458 liquidity_usd=896.85 reasons=['liquidity_below_floor'] graduation=graduated window=closed
- AVOID FAP age=3461 liquidity_usd=682.66 reasons=['liquidity_below_floor'] graduation=graduated window=closed
- AVOID $CAT1 age=3536 liquidity_usd=61.62 reasons=['liquidity_below_floor'] graduation=graduated window=closed
- AVOID AHOOD age=3644 liquidity_usd=468.55 reasons=['liquidity_below_floor'] graduation=graduated window=closed
