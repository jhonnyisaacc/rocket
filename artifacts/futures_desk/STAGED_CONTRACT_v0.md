# Staged contract v0 — crypto scan decision book

Status: trial contract for `rocket crypto scan --json`. Not a validated edge. Not an order. Not PR #28.

`execution_enabled` is false. The process prints research. A human decides. A runner bot may print coin, state, direction, `cot_alignment`, zone, invalidation, and reasons. It does not print an entry recommendation and it does not manage a position.

## Inherited (do not reinterpret)

These already follow `docs/ROCKET_PLAN.md`, `docs/issues/03-crypto-futures-polish.md`, and the live providers.

| Rule | Source |
|---|---|
| One crypto engine. No second scanner, no Cava import on the scan path, no Discord/Hermes, no orders or signing | Plan non-goals; issue 03 |
| Universe is the current top 100 by market cap intersected with a Hyperliquid perpetual. A name with no perp is a gap, not a candidate row. Ambiguous tickers stay unresolved | `build_live_observation` |
| Liquid means the existing gates: 24h quote volume, open interest, spread, slippage | `assess_live_liquidity` |
| COT is BTC/ETH market regime only. Scope text stays `market/regime context; no per-altcoin COT signal`. There is no per-altcoin COT | `cot_regime_passes` usage; `rocket/providers/cftc.py` |
| Unknown or stale COT does not delete a row | existing fail-open in `build_funnel` |
| Known COT against the row's direction keeps the row and sets `cot_alignment=against` | this trial's explicit rule; the old funnel may still withhold `final_candidates` |
| Completed candles only. A bar whose close is after `decision_time` is unseen. Missing warmup is `UNKNOWN`, never a guessed bias | PIT rules; `fetch_setup_candles` already drops an open 4h bar |
| Hyperliquid access stays `rocket/providers/hyperliquid.py` public `/info`. No second client, no key, no signing | provider module |
| Missed-move results are not fed back into the live scan | issue 03 |
| PR #28 primary chain is not the live detector: weekly velocity ±1.2, daily BOS lock, 75–86% of the daily impulse, BEN, confluence ≥ 3, 4h reaction, hourly flip | PR #28 `CONTRACT.md`, `engine.py` `frame` |

The legacy 6-bar monotonic setup (`STRUCTURE_BARS = 6`, `NO_CHASE_PCT = 0.02`) remains available to the old `final_candidates` funnel so existing fixtures keep their meaning. It is not the decision book. `FINDINGS.md` records why that gate prints empty live scans.

## Research interpretation (labeled, not tuned)

Not educator doctrine. Not fit to the 6,480-snapshot zero-admission result. Do not change these numbers because a book looks empty or full.

### Bias

Completed candles only.

- Weekly bias uses the close of the last completed weekly candle versus the close four completed weeks earlier (`weekly_close_change`). That comparison needs five completed weekly candles. Fewer than five → `weekly_bias=UNKNOWN`.
- Daily bias uses the close of the last completed daily candle versus the close six completed days earlier (`daily_close_change`). That comparison needs seven completed daily candles. Fewer than seven → `daily_bias=UNKNOWN`.
- Change > 0 → `long`. Change < 0 → `short`. Change = 0 → `none`.
- This is close-to-close momentum. It is not the PR #28 ±1.2 weekly velocity and not a pivot HH/HL daily structure test.

### States

Evaluated only when the coin was actually scored. No candle series at all on a liquid eligible name → `evaluated=false`, `state=NO_TRADE`, biases `UNKNOWN`. The row stays.

| State | When |
|---|---|
| `NO_TRADE` | Not an eligible liquid top-100 perpetual, or not evaluated |
| `NO_BIAS` | Evaluated and liquid-eligible, but weekly and daily do not give one direction (unknown on both, flat, or they disagree) |
| `BIAS` | Exactly one of weekly/daily is `long` or `short`, the other is `UNKNOWN` or `none`, and price is not extended on a confirmed 4h impulse in that direction |
| `IN_PLAY` | Liquid top-100 perpetual and weekly bias and daily bias are the same `long` or the same `short`, and price is not in the research band and not extended |
| `ZONE` | `IN_PLAY` conditions, plus the last confirmed 4h impulse in that direction, plus last close inside the 50–86% retracement band |
| `EXTENDED` | A directional bias exists (agreed, or the single known timeframe) and the last close has retraced less than 50% of that confirmed 4h impulse (still chasing the extreme) |

Mixed 4h structure (`structure_state` → `MIXED`) is stored on `structure_4h` and listed in `reasons`. It does not remove the coin and it does not throw.

### 4h impulse and band

`RESEARCH INTERPRETATION`. Last confirmed 4h impulse in the bias direction:

- Terminal is the highest high (long) or lowest low (short) among closed 4h bars **excluding the last bar**, so the extreme has one later close.
- Origin is the opposite extreme from the first bar through that terminal bar.
- Retrace for long: `(terminal - close) / (terminal - origin)`. For short: `(close - terminal) / (origin - terminal)`. `0` is the extreme. `1` is back at the origin.
- Research band is 50–86% retracement. Zone prices are the closes that match those two retracements, low to high, on `entry_research_zone`.
- Invalidation is the impulse origin (a research level, not a stop order).
- Deeper than 86% stays `IN_PLAY` (pulled through the band), not `EXTENDED` and not a hard fail.
- No confirmed impulse → `IN_PLAY` when biases agree, not a synthetic zone.

`reasons` includes `research_interpretation_retracement_50_86` whenever a band is computed.

### COT alignment

| Regime | Direction | `cot_alignment` |
|---|---|---|
| `unknown` (or anything outside bullish/bearish/neutral) | any | `unknown` |
| any | `none` | `n/a` |
| `neutral` | `long` or `short` | `n/a` |
| `bullish` | `long` | `aligned` |
| `bearish` | `short` | `aligned` |
| `bullish` with `short`, or `bearish` with `long` | as stated | `against` |

`against` keeps the row.

### Payload

Each book row (`payload.candidates[]`) has: `asset`, `asset_key`, `venue`, `contract_symbol`, `state`, `direction` (`long` \| `short` \| `none`), `reasons[]`, `weekly_bias`, `daily_bias`, `momentum` (a summary string of the changes, 4h structure, and retrace actually computed; missing pieces say `UNKNOWN`), `cot_regime`, `cot_alignment`, `structure_4h`, `entry_research_zone`, `invalidation`, `mark_price`, `funding`, `quote_volume_24h`, `open_interest_usd`, `evaluated`.

Scan payload also has funnel counts (including `staged_states`), `cot_scope` = `market/regime context; no per-altcoin COT signal`, `execution_enabled=false`, and `theory_note` stating this is staged momentum + COT research, not the PR #28 primary contract, and not an entry recommendation.

`payload.final_candidates` remains the legacy funnel (6-bar setup plus macro/COT pass). The decision book is `payload.candidates`.
