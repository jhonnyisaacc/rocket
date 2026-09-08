# Outputs implementation: draft review

This branch starts at PR #16 head d0ec688771dc3dd9847e259c29f1afac4bbc9891.
It preserves the parent's typed reasons, missing dimensions, retryability,
presentation semantics, CROSS warm-up, partial evidence and cursor safety.
Execution remains disabled. This is a draft, not completion of every issue's
acceptance criteria. No issue should close based on this draft.

## Implemented behavior

- Bounded capability acquisition with ordered fallbacks, attempt health and provenance.
- Watch entry output preserves caller thesis; healthy no-entry remains silent.
- Cava exact named measures, windows, levels, negation, unresolved forecasts,
  unestablished causality, partial reports and local structured forecast records.
- Macro current state persists every run; deterministic materiality controls silence.
- Broad Solana token inventory, independent zero confirmation, movement checks,
  pending unknown assets and preservation of portfolio thesis records.
- Portfolio transition outputs, optional news and disclosure context.
- Shared candidate state connects ISM, disclosures and the canonical Shorts evaluator.
- Exact person/source-family filtering and structured historical opportunity evaluation.
- Shorts consumes upstream candidates; successful empty scans have compact output.

Synthetic REPLAY examples are in [examples/outputs.json](examples/outputs.json).
Generate them with `.venv/bin/python scripts/output_examples.py`; these are
contract illustrations, not live investment recommendations.

## Provider order and live observations

Read-only probes on 2026-09-08 used isolated research state. Credentials were
loaded only into child processes; no secrets or user portfolio files are included.

| Capability | Order | Observed result |
| --- | --- | --- |
| Fundamentals | FMP then Massive | FMP worked for some tickers/endpoints; others returned 402. Massive CAT returned 403 entitlement limitation. Fixture fallback succeeds. |
| COT | Official CFTC then OpenBB CFTC | Both independently returned current BTC/ETH reports. Primary success does not call fallback. |
| Prices/history | Yahoo; exact supported Massive asset routes | Yahoo worked; Massive gold spot worked. |
| News | FMP then OpenBB company news | FMP entitlement failure; OpenBB returned company headlines. Reporting is context, not factual proof. |
| Video discovery | YouTube RSS then Supadata metadata | RSS 404; Supadata exact-channel discovery and transcript succeeded. |
| Exact macro indicators | FRED and exact market identifiers | CPI YoY, 10Y, date-aligned liquidity, DXY and BTC obtained. |
| ISM | Official publisher then its PRNewswire releases | Official access challenge; exact current manufacturing/services releases acquired through issuer archive. |
| Disclosures | Official House/OGE metadata; FMP structured Pelosi history | Official metadata worked; FMP history returned 402. Trump structured transaction history is not implemented. |
| Wallet RPC | Explicit RPC, Helius, public Solana, publicnode | Mainnet RPC reachability checked; actual caller wallet inventory unavailable for live validation. |

OpenBB can use the configured `OPENBB_PYTHON` interpreter when installed outside
Rocket's environment. No new mandatory dependencies are introduced. Grok/X and
browser scraping are not used to manufacture corroboration. The experimental
PDF/OCR transaction parser was removed: structured APIs are the preferred route.

## Validation

- Feature suite: 328 passed; Ruff, bytecode compilation and diff whitespace checks passed.
- Parent PR #16 separately checked: 208 passed, Ruff and compilation passed.
- No type checker or CI workflow is configured in this repository.
- Synthetic JSON examples have contract tests, including presentation and execution disabled.

## Remaining acceptance gaps

- Trump historical opportunity acquisition needs a reliable structured transaction
  source and exact instrument resolution. Official filing metadata is insufficient.
- Pelosi historical opportunity logic is fixture-tested; live FMP history requires
  entitlement. Do not claim complete historical coverage.
- Actual wallet reconciliation and a populated caller portfolio still require live
  validation with caller configuration. RPC reachability is not holdings validation.
- Cava parsing is intentionally bounded. Ambiguous indicators/windows remain
  unverified. The latest acquired video was technical education without sufficient
  named macro claims to form a macro review; it correctly did not advance the cursor.
- ISM industry mappings are curated and incomplete; unmapped industries remain explicit.
  Live company fundamentals were partial. Live Shorts could not establish required
  factors for the supplied candidates, so it returned diagnostic IE.
- A full fresh adversarial review of the feature, all issue acceptance audits and
  post-integration validation have not been completed. Passing tests do not replace them.

Issues #5–#11 and #13–#15 remain open for acceptance review. The required eventual
integration order remains `feat/outputs -> fix/insufficient_evidence -> main`.
Neither merge has been performed. Issues #1–#3 are outside this work.
