# MC-004 result — transaction accounting calibration

Status: `ACCEPTED` as bounded execution-cost and token-transfer evidence, 2026-09-24; no entry strategy promotion. The [sample rule](MC-004-FROZEN.md) was fixed before fetching this subset of the MC-003 prospective stream. These later transaction reads are validation evidence, never point-in-time early features. Solana's [`getTransaction` response](https://solana.com/docs/rpc/http/gettransaction) and [shared transaction metadata](https://solana.com/docs/rpc/json-structures) define the `meta.fee`, pre/post lamport and token balances used here.

## Sample and retrieval

Of MC-003's supported single-event native, non-Mayhem trade signatures, the deterministic hash selection frame contained 4,172 buys and 3,507 sells. The multi-trade stratum contained 106 signatures. We selected 24 buys, 24 sells and eight multi-trade signatures without substitution. All **56/56** responses were retrieved from `solana-rpc.publicnode.com` and matched the streamed signature and slot; all had successful transaction metadata. A version-0 request failed for one selected transaction with RPC error `-32015`; the same fixed sample was retried with version-1 support before analysis, preserving the failed attempts. The retrieved set includes 28 version-0, 18 version-1 and ten legacy transactions.

Evidence: [`mc004-transactions-20260924.tar.gz`](../data/mc004-transactions-20260924.tar.gz), SHA-256 `683ba852d07be8aa987beed9179f4ec6190daf41983b69b583b48d39b7e59d95`. It contains the fixed selection, each raw RPC response and request/retrieval time, the initial report, and the corrected attribution report. Selection SHA-256: `70d0359719367c70d71fb354604d21f0dc8fa85890642ea0e621a37b8ddcbf1c`; final report SHA-256: `ddffe8c05f06a865cdce745027b57ea06193f835fe15194a4eb0fe12eeec51fe`. With the MC-003 archive extracted, run `python scripts/research/memecoin_tx_accounting.py MC003_DIRECTORY MC004_DIRECTORY --report-only`; the reproduced report matched byte for byte.

## Measured accounting

| Stratum | Verified | Top-level Pump | Whole-tx fee median | Fee range | Fee above 155k |
| --- | ---: | ---: | ---: | ---: | ---: |
| Single buy | 24/24 | 7 | 117,500 lamports | 9,001–3,404,152 | 9/24 |
| Single sell | 24/24 | 11 | 100,000 lamports | 5,000–1,005,000 | 6/24 |
| Multi-trade | 8/8 | 7 | 60,000 lamports | 60,000–80,001 | 0/8 |

For 47/48 single-event transactions, the two nonzero token-account changes were exactly the signed event token amount. One remaining buy created the mint and traded in the same transaction: the buyer gained the event amount, while the newly created curve token account had no pre-balance to compare. An initial strict check also flagged a sell because a third, unchanged zero-balance token account was present; ignoring zero deltas gives the exact two-account match. Eight multi-trade transactions remain aggregate-accounting cases, so individual event deltas are not assigned to a single transfer without instruction-order reconstruction. There is no observed contradictory token delta in this bounded sample.

Every sampled fee payer's whole-transaction lamport change included amounts besides `meta.fee`. Routed transfers, account rent and trade cash explain why a fee-payer net delta cannot be treated as the event's economic cash flow. The fixed 155,000-lamport per-leg MC-002/MC-003 scenario is neither a universal fee nor uniformly conservative; fifteen of 48 sampled single-event transaction fees exceeded it. This is a hash-selected sample of observed transactions, not the fee distribution a hypothetical Rocket transaction would face. It does not measure our order inclusion, failure rate, priority-fee choice, market impact or achieved exits.

## Decision

Retain the MC-002/MC-003 frozen outcomes unchanged. Use transaction metadata, token account movements and route classification in the next simulator calibration. A fresh strategy test should predeclare fee scenarios informed by this distribution and collect transaction-level exit-route and inclusion evidence on new covered windows. The failed five-second curve-progress rank remains rejected as an entry basis.
