# Read-only early-event research workflow

Status: research tooling for PR #37. Requires Node 22+ and the Rocket Python environment. No signer, wallet, order endpoint, scheduler or live strategy decision is involved. The bounded collector supports up to 900 seconds and 512 MiB; choose limits from a design frozen before each cohort.

1. Freeze the experiment design in `experiments/` before collecting its cohort. Choose a new output directory that does not exist. Run a bounded subscription, for example:

   ```sh
   node scripts/research/memecoin_capture.mjs --out /private/tmp/rocket-mc-session --seconds 300 --max-bytes 268435456
   ```

   The defaults use Solana's public mainnet websocket and HTTP RPC. `SOLANA_WS_URL` and `SOLANA_RPC_URL` may select a different read-only endpoint; do not embed credentials in a checked-in command. The capture stores raw notifications and fetched create transactions in Rocket's hashed JSONL spool format, fsyncs frames, and writes a manifest with clocks, bounds and an index anchor. `coverage_status` remains `UNVERIFIED` until the separate audit.

2. Reconcile a completed session against the independent signature index. Public RPC may rate limit large captures; `--resume` reuses already saved index pages and `--pace-seconds` bounds the request rate.

   ```sh
   python scripts/research/memecoin_audit.py /private/tmp/rocket-mc-session --max-pages 100 --resume --pace-seconds 1.2
   ```

   Require `SIGNATURES_MATCH_INNER_SLOTS`, zero event decode errors, zero native non-Mayhem continuity and quote failures before economic evaluation. The audit excludes the first/last observed slot; it cannot certify 24/7 coverage. It writes all decoded observations, source hashes and measured receive clocks. Offline reproduction uses `--offline` with the saved pages; pass the original index provider through `--rpc-url` so the audit records accurate provenance without sending a request.

3. Run the predeclared five-second quote baseline only after the gate passes, then the separate exit-risk stress where applicable:

   ```sh
   python scripts/research/memecoin_baseline.py /private/tmp/rocket-mc-session
   python scripts/research/memecoin_risk_baseline.py /private/tmp/rocket-mc-session
   ```

   Preserve all universe rows, including exclusions and unknowns. `QUOTED` is a modeled static-state quote, never an achieved fill. The stress file does not replace the original outcome file. A changed policy needs a new experiment/version, not an overwrite of the old conclusion.

The pinned IDL is `protocol/pump-81091419.json`; its source revision and hash are in the Data Truth Registry and MC-001 report. A new protocol layout or fee regime must be validated against raw transactions before reuse. Compressed evidence archives in `data/` contain the raw segment and index responses needed for offline replay.

MC-004 calibrates actual whole-transaction network fees and token-account movements on a fixed hash-selected set of MC-003 signatures. Extract both archives, then run `python scripts/research/memecoin_tx_accounting.py MC003_DIRECTORY MC004_DIRECTORY --report-only` to reproduce the saved report without network access. Its RPC reads are retrospective validation, never early features.

MC-005's new order-flow rank is frozen in `experiments/MC-005-FROZEN.md`. On its fresh covered session, first run the audit and base quote script, then `python scripts/research/memecoin_flow_baseline.py DIRECTORY`. The new script reads the same point-in-time snapshots but ranks by five-second net buy count and reports both fee scenarios plus zero-recovery exit stress. Do not use a previous cohort as its evaluation result.

The MC-005 archive contains 153 saved signature-index pages; offline audit replay needs `--max-pages 250`. It also contains the first failed protocol audit and the corrected one. Retain the first as evidence of why boundary cases were classified, and use the final audit for the frozen economic result. The archive reproduces audit, base quote and flow result hashes byte for byte.

MC-006 uses the same base quote and flow scripts, then `python scripts/research/memecoin_flow_diagnostics.py DIRECTORY` after the coverage and protocol gate. The diagnostic reports CreateEvent receipt age by minute, top-versus-rest exit risk with exact binomial intervals, and distinct event-user addresses among early buys. Event-user counts are not verified beneficial-buyer counts. The v2 collector batches disk syncs and records its sync policy/count in the manifest; every raw frame still has a receipt clock and SHA-256 provenance.

The MC-006 `.tar.xz` archive can be extracted with `tar -xJf ARCHIVE -C DIRECTORY`. Its offline audit requires 200 saved second-provider pages, so pass `--max-pages 250 --rpc-url https://solana-rpc.publicnode.com --offline`. Audit, base quote, flow and diagnostic result hashes were checked after extraction. The separate alternate-websocket smoke archive records an endpoint that failed coverage and must not be used as an economic cohort.

The MC-007 paired websocket archive extracts with `tar -xzf ARCHIVE -C DIRECTORY`. Its two session folders include all raw frames, manifest, second-provider pages and audit. Replay each audit with `--max-pages 30 --rpc-url https://solana-rpc.publicnode.com --offline`, then run `python scripts/research/memecoin_ws_compare.py BETA_DIRECTORY MAINNET_DIRECTORY --out COMPARISON.json`. Both feeds failed exact independent coverage because of the same uncorroborated all-ones signature. Preserve that failure when replaying; do not use either capture as an economic cohort.

MC-008 tested a bounded full-transaction block subscription. Install the research extra (`pip install -e '.[research]'`) for the Python `websockets` client. Its frozen 60-second capture used `python scripts/research/memecoin_block_capture.py --out DIRECTORY --seconds 60 --max-bytes 402653184`; the separate adapter used `python scripts/research/memecoin_block_derive.py RAW_DIRECTORY DERIVED_DIRECTORY`. The source is a publicnode `blockSubscribe`, and the independent index is the official Solana RPC. Reproduce the archive by extracting it, deriving to a fresh directory, and running `python scripts/research/memecoin_audit.py DERIVED_DIRECTORY --rpc-url https://api.mainnet-beta.solana.com --max-pages 25 --offline`; the saved signature-index pages are in the archived derived directory, so copy those pages to the fresh derived directory first. The derived frames keep the original block receipt clocks and identify their source; they are not direct log subscriptions. Require zero `successful_transactions_with_truncated_logs` as well as state continuity before any flow or economic evaluation. MC-008 failed those and the five-second receipt-age gate.

The separate MC-008 truncation archive holds the 29 independent official RPC `getTransaction` responses and a deterministic report. Run `python scripts/research/memecoin_truncated_log_audit.py DERIVED_DIRECTORY --responses RESPONSE_DIRECTORY --out REPORT.json` after extraction to reproduce the 14 additional TradeEvents. Those later responses repair retrospective truth, not feature availability at the original block receipt.

MC-009 used `python scripts/research/memecoin_pumpportal_capture.py --out PORTAL_DIRECTORY --seconds 180 --max-bytes 33554432` alongside the Solana collector with a 192 MiB bound. No key or paid trade subscription was used. After independent audit of the Solana session, run `python scripts/research/memecoin_create_compare.py PORTAL_DIRECTORY SOLANA_DIRECTORY --responses SAVED_RESPONSE_DIRECTORY --out COMPARISON.json` on the extracted archive. The saved 52 transaction responses make replay offline. The PumpPortal stream failed full Pump creation coverage and mixed in Bonk launches, so its matched subset is not a strategy cohort.

MC-010 freezes a new 600-second Solana capture and a signed-transaction quarantine rule. Run the usual independent audit with `--quarantine-invalid-signatures` and preserve its reported quarantined raw frames; the rule excludes only invalid base58, non-64-byte or 64-zero-byte signatures from observations. It still requires every admitted interior signature to match the independent index and every indexed signature to appear in the stream. Only after the protocol gate passes, run the unchanged base quote and MC-005 flow scripts, then `python scripts/research/memecoin_create_identity_recheck.py DIRECTORY --responses RESPONSE_DIRECTORY --fetch --out IDENTITY.json` for fast scored launches and `python scripts/research/memecoin_fast_flow.py DIRECTORY --identities IDENTITY.json`. The identity responses are later truth checks and cannot backdate a feature. The fast result preserves delayed/unknown counts and must meet every frozen gate before it can be called even a candidate entry rule.

The completed MC-010 archive is `data/mc010-fast-flow-20260924.tar.xz` (SHA-256 `704a48905b3dd0fb993f7dd44775d5642faa5da4a6cdf647f8e5199c59c924e7`). Extract it and use its `rocket-mc010-solana-20260924` directory for offline replay. The audit command is `python scripts/research/memecoin_audit.py DIRECTORY --rpc-url https://solana-rpc.publicnode.com --max-pages 250 --offline --quarantine-invalid-signatures`; then run the base quote, flow, identity recheck **without** `--fetch` using `DIRECTORY/identity-responses`, and fast-flow commands above. Ten derived output hashes matched an offline replay. MC-010 passed its data gate and failed its economic entry gates; do not change the original result when exploring later buyer or exit-route hypotheses.

Exact historical JSON hashes depend on the implementation revision: MC-002's v1 snapshot hashes require `53509ce`, and MC-005's recorded replay hashes require `40a3996`. Later audit versions added lifecycle/user fields and index provenance, so they can change audit/result hashes while preserving the original raw archive and substantive counts. Use the experiment ledger's commit and saved result files when reproducing an historical trial exactly.
