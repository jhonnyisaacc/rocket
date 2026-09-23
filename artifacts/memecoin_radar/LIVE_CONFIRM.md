# Live scan confirm

NO_EDGE_VALIDATED. Human-gated. Read-only. Identification is not an entry.
A WATCH_ENTER row is not a buy. execution_enabled is false.

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
- WATCH_ENTER: 3
- SKIP: 1
- TOO_EARLY: 16
- AVOID: 0

## Provider health

- browser:fomo.family: HEALTHY coverage=fomo.family login-walled; pump.family/api/sales migrated+closed excluded=0
- browser:pump.fun: HEALTHY coverage=frontend-api-v3.pump.fun GET /coins complete=true
- x: UNAVAILABLE failure=OPTIONAL_NOT_CONSULTED coverage=optional
- helius: HEALTHY coverage=getAccountInfo+getTokenLargestAccounts confirmed=20

## Decision rows

- SKIP FAMILY age=None liquidity_usd=None reasons=['helius_confirm_missing', 'clocks_incomplete', 'age_unknown', 'liquidity_unknown'] graduation=graduated window=closed
- TOO_EARLY BFC age=787 liquidity_usd=10022.81 reasons=['below_age_floor'] graduation=graduated window=closed
- TOO_EARLY ToadPepe age=793 liquidity_usd=None reasons=['below_age_floor', 'liquidity_unknown'] graduation=graduated window=closed
- TOO_EARLY FAP age=796 liquidity_usd=10022.81 reasons=['below_age_floor'] graduation=graduated window=closed
- TOO_EARLY $CAT1 age=871 liquidity_usd=None reasons=['below_age_floor', 'liquidity_unknown'] graduation=graduated window=closed
- TOO_EARLY AHOOD age=979 liquidity_usd=10022.81 reasons=['below_age_floor'] graduation=graduated window=closed
- TOO_EARLY $CCOW age=1048 liquidity_usd=None reasons=['below_age_floor', 'liquidity_unknown'] graduation=graduated window=closed
- TOO_EARLY McDonald's age=1062 liquidity_usd=10022.81 reasons=['below_age_floor'] graduation=graduated window=closed
- TOO_EARLY Agritrump age=1068 liquidity_usd=10022.81 reasons=['below_age_floor'] graduation=graduated window=closed
- TOO_EARLY cancer age=1097 liquidity_usd=None reasons=['below_age_floor', 'liquidity_unknown'] graduation=graduated window=closed
- TOO_EARLY ₽ age=1106 liquidity_usd=10022.81 reasons=['below_age_floor'] graduation=graduated window=closed
- TOO_EARLY $CAT1 age=1166 liquidity_usd=None reasons=['below_age_floor', 'liquidity_unknown'] graduation=graduated window=closed
- TOO_EARLY $BITFOOTS age=1244 liquidity_usd=None reasons=['below_age_floor', 'liquidity_unknown'] graduation=graduated window=closed
- TOO_EARLY YouTube age=1329 liquidity_usd=10022.81 reasons=['below_age_floor'] graduation=graduated window=closed
- TOO_EARLY SOLAZY age=1558 liquidity_usd=10022.81 reasons=['below_age_floor'] graduation=graduated window=closed
- TOO_EARLY Robinhood age=1607 liquidity_usd=10022.81 reasons=['below_age_floor'] graduation=graduated window=closed
- TOO_EARLY LOONGPHIL age=1774 liquidity_usd=10022.81 reasons=['below_age_floor'] graduation=graduated window=closed
- WATCH_ENTER Muse AI age=1855 liquidity_usd=10022.81 reasons=['floors_met_not_an_entry'] graduation=graduated window=closed
- WATCH_ENTER TRUMP2 age=2042 liquidity_usd=10022.81 reasons=['floors_met_not_an_entry'] graduation=graduated window=closed
- WATCH_ENTER STARBUCKS age=2057 liquidity_usd=10022.81 reasons=['floors_met_not_an_entry'] graduation=graduated window=closed
