# How to run the 24-hour futures desk

Rocket prints staged research. It does not place orders, sign, or recommend an entry. You decide. A runner bot may print coin, state, direction, `cot_alignment`, zone, invalidation, and reasons. It should not add "I recommend entering."

JSON is the contract:

```bash
rocket crypto scan --json
rocket status --json
```

No private key, seed, or API secret. Hyperliquid is the public `/info` endpoint already used by `rocket/providers/hyperliquid.py`. `payload.execution_enabled` is false.

## VPS

From the rocket checkout, with the same environment the box already uses for CoinGecko, CFTC, and FRED:

```bash
cd /path/to/rocket
python -m rocket.cli crypto scan --json --state-dir "${ROCKET_HOME:-$HOME/.rocket}"
python -m rocket.cli status --json --state-dir "${ROCKET_HOME:-$HOME/.rocket}"
```

`rocket` on `PATH` is the same command. Stdout is the result. Stderr is logs.

Read `payload.candidates`. The book is the top 100 by market cap intersected with a Hyperliquid perp. `payload.perp_gap` lists top-100 names with no perp. Those are not rows. Do not decide from `status` or `trade_decision` alone. Those still follow the legacy 6-bar funnel. A healthy scan can be research `NO_SETUP` with `trade_decision.direction` `NO_TRADE` while `candidates` holds the book. That is not a failed theory. `payload.theory_note` says this is staged momentum and COT research, not the PR #28 primary contract.

`payload.cot_scope` is `market/regime context; no per-altcoin COT signal`. `payload.funnel.staged_states` counts the book.

## Healthy empty book

Operational `HEALTHY`. Every evaluated row is `NO_BIAS` or `NO_TRADE`. `staged_states` for `IN_PLAY`, `ZONE`, and `EXTENDED` are 0. Candles that arrived have `evaluated: true`. Missing candles stay on the row with `evaluated: false`, `state: NO_TRADE`, biases `UNKNOWN`. Nothing was dropped for mixed 4h structure or for unknown COT.

```json
{
  "status": "NO_SETUP",
  "payload": {
    "execution_enabled": false,
    "cot_scope": "market/regime context; no per-altcoin COT signal",
    "funnel": {"staged_states": {"NO_BIAS": 4, "BIAS": 0, "IN_PLAY": 0, "ZONE": 0, "EXTENDED": 0, "NO_TRADE": 6}},
    "candidates": [
      {
        "asset": "SOL",
        "state": "NO_BIAS",
        "direction": "none",
        "cot_alignment": "n/a",
        "weekly_bias": "short",
        "daily_bias": "long",
        "entry_research_zone": null,
        "invalidation": null,
        "evaluated": true,
        "reasons": ["mixed_4h_structure", "weekly_daily_disagree"]
      }
    ]
  }
}
```

## A real IN_PLAY or ZONE row

`IN_PLAY`: liquid top-100 perp, weekly and daily bias the same direction, price not in the research band and not chasing. `ZONE`: that, plus the last close inside the 50–86% retracement of the last confirmed 4h impulse. The band is labeled in `reasons` as `research_interpretation_retracement_50_86`. `invalidation` is the impulse origin, not an order.

Fixture (tests, not live): BTC `ZONE` long, ETH `EXTENDED` long, XRP `IN_PLAY` long, SOL `NO_BIAS`. Bearish COT keeps the long BTC row at `cot_alignment` `against`.

Live public scan on 2026-09-23 (operational `HEALTHY`, legacy funnel `final_candidates` 0): PUMP and LIT were `ZONE` long with COT `against`. BTC was `EXTENDED` long, `structure_4h` `MIXED`, retrace about 0.06. The 6-bar gate on those BTC bars was `valid: false` / `mixed_or_insufficient_structure`.

```json
{
  "asset": "PUMP",
  "state": "ZONE",
  "direction": "long",
  "cot_alignment": "against",
  "weekly_bias": "long",
  "daily_bias": "long",
  "structure_4h": "MIXED",
  "entry_research_zone": [0.00439884, 0.004599],
  "invalidation": 0.004321,
  "evaluated": true,
  "reasons": ["mixed_4h_structure", "research_interpretation_retracement_50_86", "inside_research_band"]
}
```

Print that row. Do not turn it into an entry.

## Tests

```bash
pytest -q -m 'not integration'
```

The staged cases live in `tests/workflows/test_crypto.py`. Integration tests hit the network and stay opt-in.
