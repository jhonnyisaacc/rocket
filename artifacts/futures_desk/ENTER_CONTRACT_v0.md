# ENTER contract v0 — add-on on top of `ZONE`

**Status: NOT YET FROZEN.** `execution_enabled` stays `false`. No row may print `ENTER_LONG` or `ENTER_SHORT` until a human accepts this file with every clause below marked closed.

Citation keys are the same as `artifacts/futures_desk/STRATEGY_GAP.md` (`T:N` = PR #28 `inputs/technical.yaml`, `V:N` = PR #28 `inputs/elcriptopanavideos.md`, `PR28 C:N` / `PR28 E:N` = PR #28 `CONTRACT.md` / `engine.py`, `RR:N` = PR #28 `inputs/RECOVERED_RULES.md`, `crypto.py:N` = this branch).

## Why it is not frozen

The documented reaction and trigger sentences exist, and PR #28 already froze a mechanical reading of them before outcomes (`PR28 C:3-5`, `:23-25`). They are the only source for this add-on. What stops the contract from freezing is that each sentence is conditioned on an object that PR #29's `ZONE` does not produce, and several clauses have no sourced value at all.

Documented reaction (4h):

> "Price has reached a valid 4H confluence zone (see confluence_zones)." / "A structural element (block rejection, BOS, PFQ fractálico, mitigation) formed within that zone in the direction of the daily bias." / "Retracement has reached at least the 75% zone of the impulse, not the 50% alert." / "The 4H candle shows the expected shape for the phase (see candle_shape_to_phase)." — `T:694-699`

> "Implement it instead as "4H is inside a confluence zone AND a structural element has printed"" — `T:748-749`

Documented trigger (1h):

> "A valid 4H setup is active and its invalidation has not been touched." / "A 1H entry pattern has printed inside the 4H entry zone" / "Liquidity has been taken (sweep of a 1H swing) before the trigger fires" — `T:754-757`

> "A 1H candle closes above a prior 1H resistance that has flipped into support (for longs), or closes below a prior 1H support that has flipped into resistance (for shorts), inside the 4H entry zone. entry: on the close of the flip candle. sl: beyond the last 1H swing that formed before the flip." — `T:887-892`

Documented objective:

> "TP1 = first confluence zone, TP2 = second confluence zone" — `T:760-761`; "siempre busca que primera zona de confluencia por lo menos de que a una r de distancia" — `V:7500`

What is missing, quoted:

1. **The "4H entry zone" the trigger fires inside.** Sources require "a valid 4H confluence zone" (`T:695`) at "at least the 75% zone of the impulse, not the 50% alert" (`T:698`). PR #29 `ZONE` is 50–86% of a rolling 4h swing with no confluence count (`crypto.py:42-43`, `:603-650`). PR #28 built the entry zone as BEN clipped to 75–86% of the locked daily leg with confluence ≥ 3 (`PR28 E:87-107`, `:149-150`). No source says which anchor is correct: the YAML says both "the leg between the most recent confirmed daily swing low and daily swing high" (`T:1136-1138`) and "After a confirmed 4H impulse" (`T:786`). PR #28 left this open (PR #28 body: "resolve the daily-versus-four-hour impulse anchor").
2. **The phase shape of the reaction candle.** `T:699` defers to `candle_shape_to_phase`, whose only entries are qualitative (`T:1263-1274`). PR #28's "adverse wick >= body" (`PR28 C:23`) is its own reading, and `T:1263-1266` maps small-body/long-wick to "Do not chase — wait for the next momentum candle".
3. **The retest.** `T:887-890` says "closes above a prior 1H resistance that has flipped into support". PR #28 adds "a later candle retests that flip level and closes beyond it" (`PR28 C:24`). No source sentence requires or forbids the retest.
4. **Entry timing.** `T:891` "on the close of the flip candle" vs `PR28 C:25` "market entry at NEXT hourly open".
5. **Stop precedence.** `T:892` hourly swing vs "a later 1.5× daily ATR floor ... introduced after reviewing historical losses" (`RR:28`; PR #28 excludes it, `PR28 C:26`).
6. **COT action.** The only sourced COT sentences are "weekly reference (not driver)", deferring to `cot_integration.yaml` "for the full usage contract and weekly_decision_order precedence" (`T:431`), and "If rates direction and COT direction disagree, the resolution is neutral" (`T:650-652`). `cot_integration.yaml` is not in PR #28 or this repo. No source says what `cot_alignment=against` or `unknown` does to an entry.
7. **The base bias.** `ZONE` requires agreed weekly and daily signs from close-to-close changes (`crypto.py:683-691`). The documented gates are weekly velocity (`T:661-664`) and daily swing structure (`T:681`, `T:689-691`). See `STRATEGY_GAP.md` rows 1–2.

## Draft definition

`ENTER_LONG` (mirror every inequality for `ENTER_SHORT`) = every clause true on the same completed-bar snapshot. Each clause is a named boolean on the row, so a bot branches on fields, not on prose.

| Clause | Draft rule | Source | Status |
|---|---|---|---|
| `C0_zone` | `state == "ZONE"` and `direction == "long"` exactly as PR #29 computes it. Not loosened, not re-fit. | `crypto.py:718-721` | Live. Base is interpretation (missing item 7). |
| `C1_entry_zone` | Last close inside the documented 4h entry zone: 75–86% of the chosen impulse anchor, intersected with a BEN zone that has ≥ 3 confluence factors, as `PR28 E:87-107`. | `T:695`, `T:698`, `T:786-788`, `T:1156-1162`; `PR28 C:19-22` | **OPEN** (missing item 1). |
| `C2_reaction_4h` | Last closed 4h bar intersects the `C1` zone, closes in the bias direction, adverse wick ≥ body, closes beyond the zone midpoint. | `T:694-699`, `T:748-749`; `PR28 C:23`, `PR28 E:109-112` | Inherited from PR #28; **OPEN** on missing item 2 and on `C1`. |
| `C3_invalidation_untouched` | No 4h close beyond the impulse origin and no opposite daily BOS since the zone was reached. | `T:754`, `T:789`; `PR28 C:29` | Inherited; binds only once `C1` fixes the anchor. |
| `C4_sweep_1h` | After `C2`, a closed 1h bar trades beyond an already-confirmed adverse 1h pivot (two bars each side) and closes back across it, intersecting the zone. | `T:756-757`; `PR28 E:176-179` | Inherited from PR #28. Needs closed 1h bars, not fetched today (`crypto.py:1295-1307`). |
| `C5_flip_1h` | After `C4`, a closed 1h bar closes through a previously confirmed opposing 1h pivot whose price is inside the zone, close inside the zone. | `T:887-890`; `PR28 E:173-175` | Inherited from PR #28. |
| `C6_retest_1h` | After `C5`, a later 1h bar touches the flip level and closes beyond it inside the zone. | `PR28 C:24`, `PR28 E:168-172` only | **OPEN** (missing item 3). |
| `C7_stop` | Stop = last confirmed adverse 1h pivot at the trigger, buffered 1bp. | `T:892`; `PR28 C:26`, `PR28 E:120-122` | Inherited; **OPEN** on missing item 5. |
| `C8_first_objective` | First objective = nearest already-confirmed opposing daily/4h pivot beyond the favorable zone edge; `(first_objective − entry) / (entry − stop) ≥ 1`. Never skip a nearer objective to reach 1R. | `T:760-761`, `V:7500-7502`; `PR28 C:25`, `:27`, `PR28 E:114-118` | Inherited. Entry price depends on missing item 4. |
| `C9_cot` | — | `T:431`, `T:650-652` | **OPEN** (missing item 6). No rule is proposed here. |

Numbers in the draft (75–86%, wick ≥ body, pivot widths 2 and 3, 1bp, 1R, confluence ≥ 3) are the ones already frozen in `PR28 C:16-27` / `PR28 E`. None is new. None was chosen against the 1,284 PR #29 `ZONE` rows, and no parameter search against them is allowed.

## Action mapping a bot may use today

Deterministic, no LLM text. This is an interpretation of the four-word vocabulary against `T:689-691` ("stand down ... wait for the daily to either flip or align"), `T:726-728` ("Stand aside and wait — this is also NOT an entry") and `T:1161-1162` ("NO fresh entry is allowed regardless of any other signal").

| PR #29 state | Action while this contract is NOT YET FROZEN | Action after acceptance |
|---|---|---|
| `NO_TRADE` | `NO_TRADE` | `NO_TRADE` |
| `NO_BIAS`, `BIAS`, `IN_PLAY`, `EXTENDED` | `WAIT` | `WAIT` |
| `ZONE` | `WAIT`, reasons include `enter_contract_not_frozen` | `ENTER_LONG` / `ENTER_SHORT` only if `C0`–`C9` are all true; otherwise `WAIT` with one `enter_blocked:<clause>` reason per false clause |

An `ENTER_*` row must carry `entry_zone`, `invalidation`, `stop`, `first_objective`, `r_to_first_objective`, every clause boolean and `reasons`. A row missing any of them is `WAIT`. `payload.final_candidates` (legacy 6-bar funnel, `crypto.py:227-278`) is not an input to this mapping.

## Acceptance

A human closes items 1–7 above by picking among existing sourced readings, not by looking at PR #29 counts. Then the chosen clause set is frozen, run once over outcome-hidden data under the PR #28 protocol (`PR28 C:33-47`, `:79-84`), and only then may `execution_enabled` be reconsidered. Loosening `ZONE` or any clause to make `ENTER` rows appear is not acceptance.

## Honesty

Inherited, with source text: the pullback → 4h reaction → 1h flip sequence (`T:694-764`, `T:886-892`), 75–86% as the entry band and 50% as an alert (`T:698`, `T:786-788`), the locked-leg warning (`T:1149-1151`), TP1 at the first confluence zone at least 1R away (`T:760`, `V:7500`), and the rule that a 1h trigger without a 4h setup is noise (`T:763`). Inherited only as PR #28's frozen research reading, not doctrine: every number in `C1`–`C8` and the pivot, BEN, confluence and wick definitions. Still interpretation with no source sentence: PR #29's close-to-close biases, its rolling 4h anchor and 50–86% band (so `C0` itself), the retest step, entry timing, stop precedence, the COT action, and the state-to-action mapping above. The YAML is a project refinement, partly outcome-informed (`RR:22`), not authenticated educator text, and the backtest universe and liquidity are today's projected backward. A bot may print state, direction, `cot_alignment`, zone, invalidation, clause booleans and `WAIT` / `NO_TRADE`. It may not print `ENTER_LONG` or `ENTER_SHORT`, recommend or size an entry, place or sign an order, or treat `ZONE` or `final_candidates` as an entry. `execution_enabled` stays `false` until a human accepts ENTER_CONTRACT_v0.
