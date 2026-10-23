# Frozen momentum event contract v1

Freeze: 2026-10-02, before census scoring. One generator, BTCUSDT Binance
spot, independent of perp execution assumptions. Price representation is log.

## Clocks and candidate

Source 1h bars cover [open_time, open_time+1h). Vendor close_time must equal
end minus one timestamp unit. 2025+ spot archive units are microseconds;
earlier units milliseconds. Normalize explicitly. A decision has data_cutoff
at a UTC 4h boundary and decision_time=cutoff+5m. Its last complete aggregate
bar ends at cutoff. Every feature input must have event_time and available_at
at or before decision_time; retrospective availability is an explicit assumed
end+5m, not a claim of recorded historical receipt. Full 30d contiguous history
is required; incomplete/stale history produces UNKNOWN, not NO_CANDIDATE.

Let sigma be sample SD of the last 180 4h log-close returns including the
newly completed decision bar. Candidate is UP when the close exceeds the
highest high of the preceding 42 bars by at least 0.5 sigma in log price;
DOWN when it falls below the lowest low by 0.5 sigma. New event only on an
inactive→active crossing for that side. Flat/zero sigma is UNKNOWN. No
arbitrary efficiency/persistence/candle-count rules. All crossing events are
reported. For the independent inference set accept the first crossing then
apply a **global 14d cooldown** (maximum sensitivity horizon), regardless of
side or outcome. This is deterministic and causal, never winner-dependent.

## Forward label

Reference price is the last completed 4h close. Set S=sigma*sqrt(42), fixed
at candidate time, representing 7d diffusion scale. Primary horizon is 7d;
predeclared 3d and 14d vary only timeout, not volatility/barrier scale.
Favorable barrier is direction*log(P/P0) >= 2 S. Adverse barrier is
<= -1 S. First future 1h OHLC barrier wins: favorable produces CONTINUES_UP
or CONTINUES_DOWN according to candidate direction; adverse produces FAILS;
neither by cutoff+horizon produces TIMEOUT. Decision-bar extrema are excluded.
Bars starting before decision_time (the first 5 minutes) are excluded entirely,
so the first label bar starts cutoff+1h. This conservatively loses an hour;
there is no invented intrahour entry. A both-barrier bar produces UNKNOWN
(ambiguous order), and missing future bars or incomplete horizon produce
UNKNOWN, never a censored timeout. Entire horizon required for full-horizon
excursions even when an earlier barrier resolves. Labels are distinct from
features and can become available only after the full horizon+5m.

Sensitivity: all 3 horizons at (upper,lower)=(2,1),(1.6,1),(2.4,1),
(2,0.8),(2,1.2). No cell may replace primary after viewing outcomes.

## Census and diagnostics

Report direction separately: raw rows, eligible decisions, crossings, globally
spaced candidates, successful independent opportunities; frequency/year,
label duration, full-window MAE/MFE (log and normalized S), signed end return,
cost hurdles 20/40/80bp round trip and one additional 4h close delay.
Overlapping-label interval components on all crossings expose clustering;
the spaced population supplies a conservative independent-sample upper bound,
not proof of stochastic independence. Report Kish N of year counts and
positive-MFE contribution weights, top-1/top-5 contributions, and removal of
the five largest opportunities. No raw-row t-statistic is permitted.

Ex-post legs are diagnostic only: a directional-change segmentation on 4h
closes, reversal threshold 1 S frozen at each extremum, requires completed
reversal to finish a leg. Only legs with peak-to-trough magnitude >=2 S
(anchored at leg start) are called large. The unfinished last leg is censored.
For each large leg report fraction of eventual log move completed at first
mechanical 1 S advance observed on a **closed 4h bar**, then 4h/8h/12h later;
missed/late legs count as fully consumed. Also locate the first causal
candidate in its direction. These are optimistic *ex-post conditional*
latency bounds, not signals or model labels. Segment endpoints and realized
remaining momentum never enter forecasting; quantities only defined on
realized successful legs can look artificially attractive. Report all-signal
forward outcomes independently.
