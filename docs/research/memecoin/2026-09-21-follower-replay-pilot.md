# Follower replay pilot — September 21, 2026

Status: **NO_EDGE_VALIDATED**. Research only, on `feat/cryptofutures_v3`. No orders, signals, production changes, persistent collector, or automation restart.

## Outcome

A reproducible, explicitly conditional follower simulation is now runnable for the losing calibration fixture. Six size/delay variants produce modeled losses. The other twelve variants reject entry under the frozen 2% slippage rule. **These are eighteen settings on two already-known outcomes, not eighteen independent strategy observations.**

The winning fixture also has a genuine unresolved state-path gap. Its entries can be rejected from the earlier, supported entry segment; its follower exit returns cannot be computed under the strict decoder. No winning-case return is fabricated.

The session was bounded by 18:10:53–19:10:53 UTC. The independent profile-discovery block was moved earlier because the first execution implementation completed ahead of the minute-by-minute allocation. No background continuation is promised.

## Frozen experiment

See `session_20260921_manifest.json`, created before new outcome-window acquisition:

- Losing fixture: `435CfmvrJ4QtkVv4cZ1TbUa7rzrKKjvQJLMnvhTCpump`; source buy at Unix time `1782328096`.
- Winning fixture: `EcPhZph4VXgHW279x5bYX2VjvWBHW5TTQingCAtEpump`; source buy at `1782326648`.
- Anonymous historical cohort wallet: `789sBYAGntSyAPoS4ZH3zo3SUFuv1jeAjPeaq7muVany`. This is **not** asserted to be Unipcs or any newly inspected social profile.
- Sizes: 0.01 / **0.1** / 0.5 SOL, inclusive of curve trade fees, exclusive of transaction costs and deposits.
- Entry delays: 5 / **15** / 30 seconds from the source block timestamp.
- Exit decision: 60 seconds after hypothetical entry; execution after the same additional delay. Thus target exits are +70 / +90 / +120 seconds from the source buy.
- Fixed 2% output slippage tolerance at both legs; no retries, optimized targets, fallback exits, or peak selection.

These remain development fixtures. The rule tested is delayed entry plus fixed holding-period exit, **not copying the leader's later sell**.

## Results

Numbers below are SOL cash outcomes after modeled protocol fees and median observed transaction costs, excluding the separately locked token-account deposit. Cashback is charged but not credited back without a claim. Full integer amounts and all eighteen rows are in `data/session-2026-09-21/pilot_results.json` and `.csv`.

| Losing fixture size | Allocated cash, median-cost scenario | +5s entry / +70s exit | +15s entry / +90s exit | +30s entry / +120s exit |
| --- | ---: | ---: | ---: | --- |
| 0.01 SOL | 0.012384080 | −0.004477366 | −0.004819584 | Entry rejected |
| **0.1 SOL** | **0.102384080** | **−0.042191795** | **−0.045596413** | Entry rejected |
| 0.5 SOL | 0.502384080 | −0.214256233 | −0.230898802 | Entry rejected |

For the winning fixture, **all three delays at all three sizes reject entry**. The market has moved beyond the allowed output deterioration relative to the quote calculated immediately after the source transaction. This is a non-execution result, not a zero-return winning trade.

### Primary losing-case accounting

- Buy cash: 100,000,000 lamports; 1,591,385,691,004 raw tokens received.
- Buy curve input: 98,765,431 lamports. Protocol fee: 938,272; cashback accrual: 296,297; creator payment: zero.
- Sell gross: 55,406,165 lamports. Protocol fee: 526,359; cashback accrual: 166,219. Cash received: 54,713,587.
- Median observed network-cost scenario: 155,000 lamports per leg; recognized Jito tip in that selected observation: zero. Combined modeled transaction cost: 310,000 lamports.
- Modeled outcome: **−45,596,413 lamports**, or −45.60% of the 0.1 SOL trade budget. This is a conditional calibration loss, not a general expected return.
- Surviving token-account deposit: 2,074,080 lamports, accounted for as cash locked, not an economic fee. Wallet cash change including the deposit: −47,670,493 lamports. No refund assumed.
- Cashback accumulated but not realized: 462,516 lamports. No automatic claim or asset-value credit included.
- If a new 137-byte user accumulator is required, add the independently observed 1,844,400-lamport deposit to allocated cash. Base results assume that accumulator already exists; the JSON includes this additional-cash scenario separately.

Low / median / high observed transaction-cost scenarios give −0.045296413 / −0.045596413 / −0.051296413 SOL for this row. The high scenario uses the observed 95th-percentile combined network/recognized-tip cost. These costs are **not quotes for our hypothetical transaction and do not guarantee inclusion within the chosen delay**.

The entry's immediate marginal-price impact is approximately 44.29 bps; the sell's is 33.05 bps. The much larger loss comes from the historical price path over the frozen holding period, not solely transaction overhead. The original leader exited after 61 seconds; this experiment's primary exit is after 90 seconds. The difference is intentional and must not be described as a replication of the leader's exit rule.

### Leader-fill shortcut comparison

At 0.1 SOL, scaling the leader's average all-in fill price gives 1,655,399,144,425 raw tokens, versus 1,591,385,691,004 under the +15s size-aware quote. Valuing that shortcut inventory at the same fixed exit gives −0.043399345 SOL rather than −0.045596413 SOL. The shortcut is an explicitly non-executable comparator; it does not justify using leader prices in a follower backtest.

## Execution validation

Primary sources were saved as inert, hashed content under `data/session-2026-09-21/sources/`; no downloaded package code was executed.

- Pre-trade Pump docs revision: [`1b822158844a60ca577df6ca122211b595a1a578`](https://github.com/pump-fun/pump-public-docs/tree/1b822158844a60ca577df6ca122211b595a1a578), published May 18, 2026. Historical IDL SHA-256: `b90bc471327f671449271d5d1d42354d1fae6f5a06502f5834459a3108138e49`.
- The historical TradeEvent structure exactly describes the observed extension: zero shareholders, native quote marker, and matching quote/native reserves. Current September IDL has additional fields; it was **not blindly substituted for the historical layout**.
- Current docs commit `81091419e4457566469d4e2a27f64ed84d42419c`, and official npm `@pump-fun/pump-sdk` 2.0.0, were also inspected. The npm archive's SHA-512 integrity was verified. Source manifest records every content hash.
- Exact-input arithmetic comes from the pre-trade IDL documentation: fee-adjusted integer input, bounded ceiling-rounded fees, then token output computed with `net_sol - 1`. The one-lamport term is therefore documented, not a fitted constant.
- Ordinary exact-output buys and sells use separate integer formulas. All **192 admitted fills** reproduce from instruction arguments and event-implied reserves: 74 ordinary buys, 92 sells, 22 exact-quote-input buys, and 4 exact-SOL-input buys. This single-event check alone is not called independent replay validation.
- The stronger check uses the next transaction's **actual pre-account balances**, plus reserve/account offsets from the **previous** event, to quote the next instruction without using its own fill amount as input. **189/190 adjacent transitions pass**. Losing window: 81/81; winning window: 108/109.
- Ordering comes from 31 archived block-signature lists where multiple successful transactions share a slot. Ordering is not guessed from signature sorting. Mint, reserve, program, instruction position, and timestamps are checked. Duplicate or incomplete block-order evidence fails closed.

These establish compatibility for the observed regime, not cryptographic attestation of the historical deployed program binary or universal support for all Pump versions/venues.

### Fees and destinations

All admitted events use 95 bps protocol allocation, zero creator payment, 30 bps cashback, and 5,000 bps buyback share. The [historical cashback documentation](https://github.com/pump-fun/pump-public-docs/blob/1b822158844a60ca577df6ca122211b595a1a578/docs/PUMP_CASHBACK_README.md) describes redirecting the creator fee to the user's accumulator. It is still charged on the trade; a claim or account closure is a separate action.

Observed fee arithmetic and recipient balance changes establish:

1. Protocol amount = ceiling of trade quote amount × 95 / 10,000.
2. Cashback = ceiling of trade quote amount × 30 / 10,000.
3. Buyback = floor of the **protocol amount** × 5,000 / 10,000. The remainder goes to the ordinary protocol recipient. **Do not add a 50% trade fee or charge the buyback a second time.**

Protocol-retained and buyback destination deltas match in 192/192 admitted transactions. The eight resolved buyback destinations agree with the [published recipient list](https://github.com/pump-fun/pump-public-docs/blob/main/docs/FEE_RECIPIENTS.md).

Cashback accounting: 180 exact retained-balance matches; five include a separately identified accumulator-creation deposit; seven explicitly claim or close the accumulator in the same transaction. The latter are not treated as absent fees merely because the final balance is zero. Full destination-level cashflow reconstruction of every closure is not asserted, and no such refund is credited to the hypothetical follower.

## Coverage, exclusions, and limits

The calibration evidence contains 249 unique transactions: 192 admitted events, 56 failed transactions retained as fee-only records, and one excluded successful transaction. The new acquisition added **115 unique market records**; seven additional returned records were duplicates removed by chain/signature identity. Earlier raw caches were preserved.

Short responses still had cursors. Explicit bounded continuation requests established provider-reported exhaustion for all ten calibration intervals; an empty page alone was not treated as proof of no activity. These remain archival-provider responses, not an independently rebuilt blockchain index.

The unresolved winning-case signature is `335cgm4nVceZ7h34CtcL9ZbAK1zB16pBSkeqq6mLhkGj8d7Fg4ThgZZGs7fU3z51apyaUcz31owmjP85ni4UrEQ8`, slot `428647196`, block time `1782326703`. Its logs are truncated. One targeted `getTransaction` request confirms the archive also contains truncated logs. The strict decoder excludes it and prevents exit replay across the resulting gap. No repeated retrieval loop was used.

The primary losing-case exit target is `1782328186`; the last state-changing admitted transaction is at `1782328176`. The 10-second state age is reported. Cursor-verified interval coverage supports carrying that unchanged state; this is not interpolation between future prices or an assumption based on a failed query.

Additional approximation boundaries:

- A historical-state execution approximation includes each hypothetical order's immediate curve impact but resets later quotes to recorded historical states. It does not propagate our trade through other traders' responses, slippage checks, liquidity changes, or arbitrage. It is **not an exact counterfactual replay**.
- Timestamp convention: after all ordered transactions in the last slot whose block time is at or before the target second. Subsecond timing, receipt latency, finality latency and real bot availability are unmeasured. Actual `available_at` remains null; modeled availability is labeled separately as a scenario assumption.
- Direct-program execution scenario: platform service charge zero, not a claim that trading through Fomo is free. Non-Jito routing/service transfers in observed transactions are not silently called network fees. The observed network/Jito sample, unknown MEV/inclusion costs, and off-chain infrastructure costs are separately disclosed in the JSON. Jito's [execution documentation](https://docs.jito.wtf/lowlatencytxnsend/) does not promise that a particular bid lands.
- Native-SOL curve state and wrapped-SOL AMM state remain separate. Migrations, other fee regimes, unsupported layouts, missing ordering, truncated logs, insufficient liquidity and missing exit coverage fail closed.
- Failed historical instructions do not change reserves; network fees remain. A simulated entry slippage failure has no trade return; if submitted and failed on-chain it can still cost the stated network fee. An exit rejection retains inventory rather than fabricating a completed round trip.

## Public-profile discovery

The frozen convenience sample was the first three distinct non-Unipcs names in the default Fomo Feed after its pinned recap. Fomo initially restored a leaderboard, but no candidate was selected from that ranking. Feed cards inherently exposed some position/PnL data; selection followed display order, not those amounts. No rejected candidate was replaced with a winner.

| Profile | Evidence checked | Wallet admission |
| --- | --- | --- |
| [Rochaboyyyy](https://fomo.family/profile/Rochaboyyyy) | Explicit Fomo bio names [X account](https://x.com/Rochaboyyyy); matching display name. Inspected CATE posts are promotional, not signed transaction evidence. Public profile exposes historical buys but insufficient identifiers. | Unavailable; zero matches |
| [therear66](https://fomo.family/profile/therear66) | Public Nautilo buys, $2,999.75 and $1,999.24; selected activity is Robinhood Chain. No explicit X link observed. | Unavailable; cross-chain reconstruction deferred |
| [GMannnnn](https://fomo.family/profile/GMannnnn) | Public CATE buys at displayed Sep 21 15:23/15:24, including $5,530.03, $5,530.57 and $9,956.03. No explicit X link observed. | Unavailable; partial chain windows, no exact reconciliation |

For GMannnnn, two initial version-0 capture attempts failed; the second safely retained RPC error code −32015. [Current Helius documentation](https://www.helius.dev/docs/rpc/gettransactionsforaddress) specifies version-1 support. A single corrected pass returned 200 records, including 67 failed transactions, but each response hit its 100-record cap and covered only approximately the first ten seconds of its minute. The remaining intervals were not declared empty.

Four buy-like signer/token/USDC net flows are saved separately as **unattributed**, not as verified trades or GMannnnn's wallets. Two 5,000-USDC debits do not reconcile to the displayed amounts. Similar timing or repeated buying is insufficient attribution. **Zero new wallet mappings admitted.** No “insider” inference, skill claim, or historical identity-availability claim is made.

Candidate selection, unsuccessful checks, public URLs and next evidence requirements are in `session_20260921_candidates.json`; reproducible chain diagnostics are in `data/session-2026-09-21/discovery_evidence.json`.

## Credit accounting

| Allocation | Conservatively reserved | Session cap |
| --- | ---: | ---: |
| State/ordering/exit windows | 221 | 400 |
| Fresh-wallet evidence | 40 | 200 |
| Diagnosed gaps | 1 | 200 |
| Contingency | 0 | 200 |
| **Total** | **262** | **1,000** |

There were 55 dispatch reservations: 53 successful responses and two failed captures. Successful-response cost estimate: **242 credits**. Local budget usage remains **262**, retaining the full reservations for the failed attempts. **Actual provider billing was not inspected.** The [published credit schedule](https://www.helius.dev/docs/billing/credits) prices full history at 10 credits per 100 returned records rounded up, minimum 10; archived block/transaction requests at 1; failed API responses at zero. That schedule is not an invoice.

No upgrade or funding occurred. The first failed capture predates safe error-code persistence: its original provider message/code cannot be recovered from the local cache. Its failure sidecar explicitly records that limitation rather than inventing a raw response. Later diagnostics preserve only safe error codes/categories, never provider messages that could echo secrets.

## Reproduce and inspect

From the repository root, with Python 3.11+ and no third-party packages:

```sh
python3 docs/research/memecoin/pilot_decode.py
python3 docs/research/memecoin/pilot_replay.py
python3 docs/research/memecoin/pilot_discovery.py
python3 -m unittest discover -s docs/research/memecoin -p 'test_*.py'
```

These commands perform **zero network requests**. Capture is a separate, explicit interface with an allowlist, immutable response hashes, a locked pre-dispatch credit ledger, bounded windows, no automatic retries, and an expiry guard. Derived reports reference raw captures, decoder/model versions and implementation hashes. No private key, signing operation or trade endpoint exists in this interface.

For one combined offline integrity audit and regression run, use `python3 docs/research/memecoin/pilot_validate.py`. It verifies all source hashes and ledger request identities, regenerates derived evidence, and runs the full suite. The session completion marker also blocks new capture dispatches; cached reproduction remains available after closeout.

The suite includes the original nine regressions plus new quote, rounding, fee-split, independent-state, ordering, failed-CPI, migration rejection, deposits, slippage, missing-liquidity, cache-integrity, cap-enforcement, expiry and deterministic-reproduction checks. Final test count/result is recorded in the session completion artifact.

## Conclusions and next executable experiment

Completed: instruction-specific integer quoting, observed historical fee semantics, independent state continuity, bounded fixed-exit coverage for the losing fixture, costed size/delay sensitivity, explicit rejection results, and a three-profile evidence panel.

Not established: follower profitability, wallet consistency, a general entry/exit rule, new social wallet identities, winning-case exit returns, executable live latency, or a tradable edge. The two calibration outcomes cannot support statistical significance. The result specifically rejects treating a leader's winning fill as automatically copyable at that price under the frozen tolerance.

**Next executable prerequisite:** validate an independent recovery path for the single truncated winning-case transaction using its already-cached instruction-embedded event and actual reserve balances, with a dedicated regression that does not globally relax truncated-log rejection. No additional Helius history is needed for that attempt. If that evidence is insufficient, keep the gap unavailable.

After that, freeze a new chronological sample and its inactive/no-eligible outcome before retrieving prices. Include every failure/rejection and matched momentum/independent-wallet controls; hold back untouched observations. Do not tune this pilot's horizon or slippage to rescue its losses. This broader sampling remains deferred, as requested, rather than silently starting another experiment in today's session.

Automation `memecoin-alpha-research-loop` was read and confirmed **PAUSED**. Execution remains disabled. PONS, SCRIBE, cross-chain reconstruction, broad paper survey, deployment and notifications remain outside this pilot.
