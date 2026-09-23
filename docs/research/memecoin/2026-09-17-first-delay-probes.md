# First market-path acquisition and latency probes

## Completed work

Advanced from wallet-only evidence to market activity around the verified losing cycle, Solana mint `435CfmvrJ4QtkVv4cZ1TbUa7rzrKKjvQJLMnvhTCpump`. Queried its observed reserve once, capped at 100 full transactions. Manifest records address, window and maximum estimated cost before the request. Estimated new Helius cost: 10 credits. No pagination, no retries after successful response.

Requested five seconds before the leader's buy through thirty seconds after its sell. The first page returned 100 records spanning timestamps 1782328092–1782328167; the requested end was 1782328188. The page is truncated, not a complete market window. It includes the buy, the sell and all three latency probe times.

31 records failed. The 69 successful records all have opposing native-SOL/token reserve changes. Failure count is a property of this selected page, not an estimated follower failure probability.

## Observed ratio changes

Using realized reserve exchange ratios (SOL exchanged / tokens exchanged), the first observed trades at or after the buy timestamp plus each delay show:

| Delay | Change relative to leader's reserve ratio |
| --- | --- |
| 5 seconds | +0.71% |
| 15 seconds | +3.11% |
| 30 seconds | +11.66% to +14.79% across three same-second trades |

These are **not executable follower prices or returns**. Trade sizes and directions differ, ratios include curve traversal, and same-second ordering is unresolved. No counterfactual liquidity state or fees have been simulated. The results do establish that subsequent exchange conditions changed substantially within the delay windows; copying the leader's fill price would erase that evidence.

The anchor is the already verified 61-second losing round trip. Its intermediate rise does not imply a profitable exit was available under a predeclared follower rule. Do not optimize an exit retrospectively from this path.

## Accounting task advanced first

Completed transaction-boundary creation-funding audit: nine owner-funded creations totaling 0.015816080 SOL are closed or zero by transaction end; twelve totaling 0.024888960 SOL survive as owner token accounts. Do not add all creation funding back to PnL as retained rent. Later refunds and full-lifetime rent remain separate questions. Added regression coverage.

## Next exact work

Obtain the missing final 21 seconds only if needed for a declared exit rule, using a bounded timestamp query rather than replaying this page. Acquire comparable market evidence around the largest positive group's curve and AMM reserves, explicitly marking venue transition and truncation. Before any follower backtest, specify follower size, observation delay versus block timestamp, transaction ordering, fee model and exit rule. Use the market cache to validate a price-path decoder, not to claim alpha.

Artifacts: `account_deposit_audit.json`, `losing_cycle_market_manifest.json`, `losing_cycle_market.json`, `losing_cycle_market_ratios.jsonl`, `losing_cycle_delay_probes.json`, under `data/helius-pilot-2026-09-16/`. NO_EDGE_VALIDATED remains unchanged.
