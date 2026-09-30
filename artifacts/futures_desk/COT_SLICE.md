# COT slice — regime is labeled, missing is WAIT

`ENTER_CONTRACT_v0.md` is still **NOT YET FROZEN**. Clause `C9_cot` stays **OPEN**. This slice does not print `ENTER_LONG` or `ENTER_SHORT`, does not set `execution_enabled` true, and does not change weekly, daily, band, or impulse thresholds. It does not implement the price theory in `STRATEGY_GAP.md`.

COT stays the existing CFTC report (`rocket/providers/cftc.py`) with the optional OpenBB fallback already registered in `config/providers.toml`. No new vendor. No second Hyperliquid client.

## What a bot reads

`payload.candidates` is still the book. `payload.bot_decision` is the COT decision. `payload.trade_decision` is still the legacy 6-bar funnel.

| Report | `cot_regime` | Directional row (`long` or `short`, state not `NO_TRADE`) | `bot_decision.action` |
|---|---|---|---|
| Fresh BTC and ETH, status `OK` | `bullish`, `bearish`, or `neutral` | Kept. `cot_alignment` is `aligned`, `against`, or `n/a`. Against does not drop the row and does not add a block reason. | `null`, reason `cot_alignment_labeled` |
| Missing, partial, or stale | `unknown` | Kept. Reason `cot_regime_unknown`. State is not rewritten to `NO_TRADE`. Row `action` is `WAIT`. | `WAIT`, reason `cot_regime_unknown` |
| No directional row | whatever the report resolved | `NO_TRADE` rows stay `NO_TRADE` because they were not a regime decision | `NO_TRADE`, reason `no_directional_row` |

Staleness rule, also on `payload.cot_context.staleness_rule`: `cot_regime` is unknown unless BTC and ETH both parse and the older as-of date is 0 to 14 days before the decision date (`STALE_AFTER_DAYS` in `rocket/providers/cftc.py`). The positions `All` row is used. The later percent-of-open-interest `All` row is not.

A replay that passes `cot_regime` of `bullish`, `bearish`, or `neutral`, or whose book rows already carry one shared regime, stamps that regime on `payload.cot_regime`, `payload.funnel.cot_regime`, and every book row. A stale or failed report clears a baked-in regime to `unknown` and WAITs. If the official report is stale and the OpenBB fallback also fails, the context stays `STALE` with that endpoint and rule. It is not replaced by `SourcesExhausted`.

## Live scan (2026-09-23)

`CryptoWorkflow.scan_live()` against public CoinGecko, Hyperliquid `/info`, and the CFTC futures report. Operational `HEALTHY`. Research `NO_SETUP` (legacy 6-bar funnel). `execution_enabled` false. 57 book rows, all `cot_regime` `bearish`. None `unknown`.

Provider: `https://www.cftc.gov/dea/futures/deacmelf.htm`. Status `OK`. Source `CFTC futures-only report`. As-of `2026-09-15`. Freshness 8 days (inside 0–14). `failure_kind` null. OpenBB was not required.

```json
{
  "asset": "BTC",
  "state": "EXTENDED",
  "direction": "long",
  "cot_regime": "bearish",
  "cot_alignment": "against",
  "weekly_bias": "long",
  "daily_bias": "long"
}
```

`bot_decision`: `{"action": null, "reason": "cot_alignment_labeled", "regime_required": true, "cot_regime": "bearish", "cot_status": "OK"}`. The long BTC row stayed. Against did not delete it.

## Pytest

`python3 -m pytest -q -m 'not integration'` exited 0. `pyproject.toml` already sets `-q`, so that command printed the progress bar only. The same suite with a single quiet flag printed:

```text
402 passed, 1 deselected in 1.58s
```
