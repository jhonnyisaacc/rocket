# Outputs implementation and PR #17 follow-up review

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
Generate them with `.venv/bin/python -m scripts.output_examples`; these are
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
| Disclosures | Official House/OGE metadata; FMP Pelosi history; free Open Cabinet Trump history | Official metadata worked; FMP history previously returned 402. Follow-up live Trump acquisition returned 8,940 transaction rows, all joined to OGE posting dates. |
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

- Trump structured acquisition now uses Open Cabinet's public JSON export. Of
  8,940 live rows, 6,410 have checked common-stock/T1 identities eligible for
  independent equity research. Other instruments remain review items. This is
  secondary extraction, not an assertion of complete holdings or personal trade
  decisions. OGE posting dates are labelled separately from filing signature dates.
- Pelosi historical opportunity logic is fixture-tested; live FMP history requires
  entitlement. Do not claim complete historical coverage.
- Actual wallet reconciliation and a populated caller portfolio still require live
  validation with caller configuration. RPC reachability is not holdings validation.
- Cava parsing is intentionally bounded. Ambiguous indicators/windows remain
  unverified. With no supported exact measure, the full transcript is now handed
  to the caller bot for a key-claims summary. Saving that handoff advances the
  delivery cursor without creating a validated market overlay. A failed named
  measure provider still cannot advance the cursor. Rocket does not host an LLM;
  the caller bot renders the summary using the supplied transcript and instructions.
- ISM industry mappings are curated and incomplete; unmapped industries remain explicit.
  Live company fundamentals were partial. Live Shorts could not establish required
  factors for the supplied candidates, so it returned diagnostic IE.
- A full fresh adversarial review of the feature, all issue acceptance audits and
  post-integration validation have not been completed. Passing tests do not replace them.

Issues #5–#11 and #13–#15 remain open for acceptance review. The required eventual
integration order remains `feat/outputs -> fix/insufficient_evidence -> main`.
Neither merge has been performed. Issues #1–#3 are outside this work.

## Follow-up validation (2026-09-08)

- Fresh full suite: 347 passed, 1 integration test deselected; Ruff, compilation
  and whitespace checks passed, including the final examples and regression checks.
- The free Trump CLI path ran end-to-end with isolated `/tmp` research state and
  no API credentials: 21 official filing records plus 8,940 secondary transactions.
  Every transaction joined to an exact OGE document. Independent research was
  bounded to 30 listed assets, plus 10 unresolved-instrument examples. Missing
  fundamentals produced NEEDS_REVIEW; old sales did not seed new shorts.
- The live probe exposed timezone-free OGE index timestamps. The adapter now
  uses their calendar date only, without inventing a PIT timestamp. It also
  exposed misleading per-provider NO_NEW_RECORDS coverage; coverage now matches
  the secondary provider's rows.
- Regression checks cover stale/future exports, wrong people, bad PDF sources,
  incomplete exports, duplicate same-day rows, unresolved instruments, future
  transcripts, complete transcript delivery, repeat silence and named-provider
  failures. The Cava example documents a bot handoff, not generated summary prose.
- Focused source review covered dispatcher bounds, provider clocks, candidate
  promotion, inventory zero confirmation, and Cava cursor/overlay separation.
  This is not a claim that every linked issue's full acceptance audit is complete.

The user confirmed that credentials and caller state are on the VPS and will
perform the live review there. Fresh paid-provider entitlement, latest-video bot
rendering, actual wallet and populated caller-portfolio acceptance are therefore
reserved for that review. Earlier live observations above remain historical
observations. PR #17 is conflict-free against `fix/insufficient_evidence`; leave
the merge and issue closures pending the user's VPS review.

### VPS review

Use the existing credential launcher and a separate research state directory.
Run `rocket disclosures --person 'Donald Trump' --state-dir <review-dir> --json`:
check secondary attribution, original amount ranges, posted-date basis and
independent opportunity decisions. Repeat it to check new-record deduplication.
Run the same command with `--person 'Nancy Pelosi'` to check FMP entitlement.

Run `rocket cava --state-dir <review-dir> --json`. For commentary-only output,
the bot consumes `payload.summary_request`, summarizes the full transcript's key
claims and attributes them to Cava. Confirm it does not claim verification or
create a macro overlay. For a named-measure video, review `claims_checked` and
provider failures. A failed required provider must not advance the cursor.

Run the usual populated `rocket portfolio review --state <caller-file>` with
the review state directory; repeat with `--refresh-inventory` for the real wallet.
Check caller theses are preserved, stable HOLD is silent, unknown mints stay
pending review, and an empty wallet requires independent confirmation. Then
review ISM/Shorts with the VPS provider entitlements. This work does not modify
the VPS bot adapter or claim that its summary rendering has already been tested.

Source notes: [Open Cabinet export](https://open-cabinet.org/download),
[methodology](https://open-cabinet.org/methodology), and
[deterministic ticker rules](https://github.com/tbrown034/open-cabinet/blob/main/lib/asset-resolution.ts).
OpenBB's [government trades reference](https://docs.openbb.co/odp/python/reference/equity/ownership/government_trades)
documents Senate/House coverage; that does not establish presidential OGE coverage.

## VPS review findings addressed

The pasted Grok review was checked against each PR's own base. Parent fixes are
in commit `372a5ff` on PR #16 and integrated into PR #17. No GitHub PR was merged,
no pending review was submitted, and issue checklists remain intact.

| PR / finding | Resolution |
| --- | --- |
| #16 Cava freshness | Shared stale-days map and inclusive calendar-date eligibility, tested at and beyond the 7/14/62-day boundaries through the real corroborator. |
| #16 candle outages | Failed `hyperliquid.candles:*` providers yield REQUIRED_PROVIDER_UNAVAILABLE with the provider name. |
| #16 NAPM | Matching-month mapping and numeric-value tests, publisher precedence, and explicit documentation that CLI does not acquire NAPM. |
| #17 ISM presentation | Valid headlines or industry rankings remain visible, including replay, unmapped and contraction-only reports. |
| #17 portfolio diagnostics | Per-ticker missing dimensions and provider reasons; usable action transitions remain visible beside diagnostics. Missing-data reviews do not replace action baselines. |
| #17 caller references | Unknown/invalid portfolio or watch coverage forces NEEDS_REVIEW and suppresses proposals; explicit empty lists are distinguished. |
| #17 inventory approval | Only literal boolean true removes pending review; truthy strings and numbers cannot update caller quantities. |
| #17 Shorts run order | CLI help and workflow documentation name the upstream ISM/disclosures requirement and explicit snapshot input. |
| #17 Cava delivery | Completed contradictory reports are delivered once without overlay validation; failed acquisition remains retryable. |

Validation: PR #16 separately **220 passed, 1 integration test deselected**;
PR #17 combined **384 passed, 1 integration test deselected**. Ruff, compilation,
example regeneration and diff whitespace checks passed. These are deterministic
regression checks; VPS credentials and caller-state live acceptance remain with
the reviewer as requested.
