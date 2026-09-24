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
