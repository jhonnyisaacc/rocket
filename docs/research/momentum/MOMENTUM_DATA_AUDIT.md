# Momentum data audit

Frozen 2026-10-02 alongside the event contract, before census scoring.
Covers sources, clocks, historical coverage, gaps, PIT risks and known
contamination. Safety: `READ_ONLY_RESEARCH_ONLY_HUMAN_GATED`.

## Primary source: Binance BTCUSDT spot 1h archives (2019-01 → 2025-12)

- Monthly zips from the public Binance data archive, verified against
  published checksums before use. Calendar window fixed by long liquid
  coverage, not by results.
- 1h bars aggregate to complete UTC 4h bars. A 4h decision bar is only
  complete at the 4h boundary; `decision_time = cutoff + 5m`.
- Timestamp units changed historically (milliseconds, then microseconds
  in 2025+ spot archives). Normalize explicitly; reject rows whose
  `close_time != open_time + 1h - 1 unit`.
- Retrospective availability is an **assumed** `bar_end + 5m`, not a claim
  of recorded historical receipt. Actual receipt is known only
  prospectively via the shadow log. Ingest time is never backdated.
- 2026 is excluded from historical scoring: heavily inspected elsewhere
  (PR #46 and others), neither clean nor needed here.
- Revisions: spot klines are append-mostly but late corrections exist;
  the archive is a single vintage, so historical reconstruction cannot
  detect what changed. Recorded as a limitation, not assumed away.

## Why not Hyperliquid history for 2019–2025

`rocket/providers/hyperliquid.py` is live-only (`/info` candleSnapshot,
fundingHistory capped at 500 rows/call, perp history starts ~2023).
It cannot supply 2019–2025 history and its funding/OI depth is shallow.
It remains the prospective Tier B collector, not the historical source.

## Tier B historical coverage (MOM-DATA-001, executed 2026-10-02)

Tier B needs point-in-time OI level/change, funding level/change and
spot-vs-perp participation over the same window. Hyperliquid cannot
supply it. Binance futures archives were probed and fetched:

- Perp 1h klines (`futures/um/monthly/klines/BTCUSDT/1h`):
  2020-01→2025-12 complete, 72/72 zips checksum-verified.
- Funding rate (`futures/um/monthly/fundingRate/BTCUSDT`):
  2020-01→2025-12 complete, 72/72 zips checksum-verified.
- Daily metrics incl. open interest
  (`futures/um/daily/metrics/BTCUSDT`): available 2020-09-01→2025-12-31,
  absent before (bounds established by HEAD bisection; full backfill not
  executed — unnecessary under the MOM-000 STOP).
- No monthly openInterest/premiumIndex archives exist upstream (404);
  daily metrics is the only OI history.

Tier B historical scoring would have been feasible on a gated 2020-09+
sub-window with per-feature availability gating (UNKNOWN outside
coverage, no imputation, no live backfill). Moot under the MOM-000
STOP; recorded for any future separately-justified program.

## Vendor anomalies found in-spot (quarantine log)

9 of 61,368 hourly rows quarantined (recorded in the census report's
`quarantine_detail`, skipped, gaps → local UNKNOWN):

- Zero-volume flat rows with truncated close times (e.g. file005 line
  166: close only ~13min after open; file023/025 similar).
- Rows with mid-bar close times and real volume (file013 line 443:
  close ~35min after open; file014, file027 similar).

These are isolated single-hour gaps, not regime changes. The strict-abort
parser was replaced by quarantine-and-skip (amendment A1) at first crash,
before any outcome was viewed.

## Existing Rocket data layer: PIT gaps found

- `rocket/pit.py` (`PointInTime`) is the only PIT implementation and is
  reused, not replaced. It has no vintage/revision identity; the momentum
  package adds explicit `vintage` + `ingested_at` fields on observations.
- FRED (`rocket/providers/fred.py`) serves revised CSV history as if it
  were point-in-time (`as_of` = latest observation, no vintage). A normal
  historical FRED CSV is **not** automatically point-in-time. No ALFRED
  rebuild in this PR; Experiment 1 uses market/crypto data that does not
  depend on revisions. Future Tier C slow-context features would require
  ALFRED or equivalent vintage reconstruction.
- COT (`rocket/providers/cftc.py`) parses `as_of_date` (Tuesday position
  date) with `release_date: None`. Publication is Friday: using `as_of`
  as availability is ~3 days of lookahead. COT stays out of Experiment 1.
- `closed_bars` in `rocket/workflows/crypto.py` already enforces
  completed-bar-only filtering (`open + interval <= decision`). The
  momentum 4h aggregation follows the same rule; bar timestamp semantics
  (`[open, open+4h)`, complete at boundary) are tested, not assumed.
- US cross-asset data does not update during crypto weekends; slow data
  stays constant across 4h decisions. 4h crypto decisions never wait for
  equity sessions.
- Live/replay separation: historical reconstruction must never silently
  use live context (current mappings, current universe, current
  parameters). Anti-lookahead tests mutate post-decision information and
  require features/outcomes at `t` to be unchanged.

## Known contamination

BTC history already heavily inspected by Rocket is research-development
data, not a pristine holdout. PR #46 exposed substantial parts of the
2026 path; the tuning universe (2024-10 → 2026-05) and holdout months in
PR #40 were inspected during selection. Walk-forward here is honest
development; final validation is prospective. No protected prospective
holdout is inspected and then used for tuning.

## Preserved negative evidence (summary; detail in FRONTIER)

- PR #38/FAMILY_AUDIT: FUT-001/002/003 trend, FUT-004 basis, FUT-005
  COT, FUT-006 order flow, FUT-007 funding tails, FUT-008 order book,
  FUT-009 macro/dollar, FUT-010/011 wallet closes, FUT-012 liquidations,
  FUT-013 lead/lag — all `CLOSED_EXACT_RULE`. OI participation and
  portfolio context remain `OPEN_MECHANISM` with PIT/source limits.
- PR #46: systematic BTC puts uneconomic (11–18%/yr, lost to naked
  hold); dip-buying luck-indistinguishable (DSR P=0.00); funding carry
  statistically real but regime-concentrated (2/3 from 2021), thin since
  2023. Hedge recommendation: SKIP.
- PR #40: v6 market-check lost the clean holdout (Sharpe 0.44 vs 0.49
  equal-weight); return edge indistinguishable from mining luck
  (deflated Sharpe ~0.00 over 43 trials).
- PR #26: ISM shorts v2 `EDGE_NOT_VALIDATED` vs sparse A0 baseline.
