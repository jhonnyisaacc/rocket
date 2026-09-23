# Reserve-pair experiment completed

Read-only offline analysis of all 55 successful single-mint owner flows in the historical-wallet cache. No new API calls. Six regression tests pass.

## What changed

Every flow has a unique opposing token-account authority: its token change is exactly the negative of the owner's change. Forty-nine flows reference that authority in the observed bonding-curve program instruction and show an opposing native-SOL change. Six reference it in the observed AMM program instruction: those authorities have **zero native-SOL change**, but their wrapped-SOL token balance changes in the expected opposite economic direction. All 55 transactions conserve lamports after network fees and have the owner as signer.

This resolves the false-negative condition in a native-SOL-only reserve check. It matters for following tokens across venues: the largest positive cashflow group, `EcPhZph4VXgHW279x5bYX2VjvWBHW5TTQingCAtEpump`, contains both curve-program and AMM-program events. A follower parser restricted to the curve program would miss some of that group's trades. Program transitions are observed here; the migration transaction itself has not been captured.

The twelve balanced groups each begin with zero owner tokens in the first observed transaction and end with zero in the last observed transaction. This strengthens the observed-account inventory evidence beyond just summing deltas. The thirteenth mint begins with 15,849,512,476,909 raw tokens, confirming its missing opening acquisition; exclude it from cost-basis returns.

## Limits

These are transaction-level reserve/owner matches and accounting checks, not independently derived reserve PDAs or audited economic fee labels. Lamport conservation is an internal consistency check, not independent proof of fair execution. Same-slot transaction order, closed historical accounts, gross versus retained rent, unknown program receipts and complete history remain unresolved. Do not change NO_EDGE_VALIDATED or report follower returns from leader fill prices.

## Reproducibility

Run `python3 docs/research/memecoin/verify_reserve_pairs.py` for per-signature evidence and per-mint summary. Run the existing unittest discovery command; six tests pass including a regression case requiring WSOL reserve accounting for all six AMM flows.

## Next executable experiment

Historical price-path acquisition should query the actual reserve addresses recorded in `reserve_pair_evidence.jsonl`, not ticker search. Start with the largest positive group and the already adjudicated losing pair. Bound each query around its first buy through final sell plus 30 seconds, cache responses, and cap at 100 full transactions per request. Record truncated coverage explicitly. Historical observed swap prices remain proxies; executable follower outcomes require liquidity/curve state, ordering, fee parameters and latency. Before expanding the cohort, complete retained-rent accounting so small margins are not mislabeled.
