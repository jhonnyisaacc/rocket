"""Walk-forward for crypto derivative families: 12-month train, 3-month test.

Every engine is causal (next-bar fills, trailing signals), so each window is
evaluated by running the engine on history from day zero through the window
end and measuring only the window slice. The headline is the stitched
out-of-sample test segments. Holdout (from 2026-01-01) is evaluated once,
via `evaluate_holdout`, at the very end.
"""

from __future__ import annotations

from datetime import date

from rocket.crypto import data as datamod
from rocket.crypto.carry import CarryRule, run_carry
from rocket.crypto.data import Bar
from rocket.crypto.longs import LongRule, run_longs
from rocket.crypto.puts import PutRule, max_dd, run_insurance

HOLDOUT_START = date(2026, 1, 1)
YEAR = 365.25


def add_months(day: date, n: int) -> date:
    month = day.month - 1 + n
    year = day.year + month // 12
    month = month % 12 + 1
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    last = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return date(year, month, min(day.day, last))


def windows(
    first_test: date = date(2020, 1, 1),
    last_test_end: date = HOLDOUT_START,
) -> list[tuple[date, date, date, date]]:
    """(train_start, train_end, test_start, test_end) stepped quarterly."""
    out = []
    test_start = first_test
    while add_months(test_start, 3) <= last_test_end:
        test_end = add_months(test_start, 3)
        out.append((add_months(test_start, -12), test_start, test_start, test_end))
        test_start = test_end
    return out


def _index(bars: list[Bar], day: date) -> int:
    days = [b.day for b in bars]
    lo, hi = 0, len(days)
    while lo < hi:
        mid = (lo + hi) // 2
        if days[mid] < day:
            lo = mid + 1
        else:
            hi = mid
    return lo


def causal_stress_sets(bars: list[Bar], thresholds: list[float]) -> dict[float, set[date]]:
    """Days where the close is `dd` below the trailing 90-day high.

    Each day uses only its own past, so slicing these sets per window is safe.
    """
    closes = [b.close for b in bars]
    out: dict[float, set[date]] = {dd: set() for dd in thresholds}
    for i, bar in enumerate(bars):
        high = max(closes[max(0, i - 89) : i + 1])
        dd = closes[i] / high - 1
        for threshold in thresholds:
            if dd <= -threshold:
                out[threshold].add(bar.day)
    return out


def _window_years(start: date, end: date) -> float:
    return max((end - start).days, 1) / YEAR


def puts_window_metrics(
    bars: list[Bar],
    combined: list[float],
    naked: list[float],
    legs: list[dict],
    byday: dict[date, Bar],
    start: date,
    end: date,
) -> dict:
    """Cost/yr and drawdown reduction measured strictly inside [start, end)."""
    i, j = _index(bars, start), _index(bars, end)
    years = _window_years(start, end)
    spend = sum(
        leg["premium"] / byday[date.fromisoformat(leg["entry"])].close
        for leg in legs
        if start <= date.fromisoformat(leg["entry"]) < end
    )
    cost = spend / years * 100
    dd_win = (max_dd(combined[i:j]) - max_dd(naked[i:j])) * 100 if j > i + 1 else 0.0
    return {"cost_pct_per_year": cost, "dd_win_pp": dd_win,
            "score": dd_win - cost}


def longs_window_metrics(legs: list[dict], start: date, end: date) -> dict:
    inwin = [leg for leg in legs
             if start <= date.fromisoformat(leg["entry"]) < end]
    rets = [leg["return"] for leg in inwin]  # percent units
    if len(rets) < 2:
        return {"n": len(rets), "score": float("-inf")}
    return {"n": len(rets), "score": sum(rets) / len(rets),
            "win_rate": sum(1 for r in rets if r > 0) / len(rets)}


def carry_window_metrics(equity: list[float], bars: list[Bar],
                         start: date, end: date) -> dict:
    i, j = _index(bars, start), _index(bars, end)
    if j <= i + 1 or equity[i] <= 0:
        return {"score": float("-inf"), "total": 0.0}
    total = (equity[j - 1] / equity[i] - 1) * 100
    return {"score": total, "total": total}


def run_family_wf(family: str, candidates: list[dict], bars: list[Bar],
                  vols: dict, funding: dict, events: dict | None,
                  stress: dict[float, set[date]] | None) -> dict:
    """Select argmax train score per window, stitch test segments to a headline."""
    byday = {b.day: b for b in bars}
    event_list = (events or {}).get("fomc", []) + (events or {}).get("elections", [])
    picks: list[dict] = []
    for train_start, train_end, test_start, test_end in windows():
        scored = []
        for cand in candidates:
            result = _run_candidate(family, cand, bars, vols, funding,
                                    event_list, stress, test_end)
            metric = _window_metric(family, cand, result, bars, byday,
                                    train_start, train_end)
            scored.append((metric["score"], cand["name"], result, metric))
        scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
        best_score, best_name, best_result, best_train = scored[0]
        test_metric = _window_metric(family, candidates_by_name(candidates, best_name),
                                     best_result, bars, byday, test_start, test_end)
        picks.append({"test_start": test_start.isoformat(),
                      "test_end": test_end.isoformat(),
                      "pick": best_name, "train_score": best_score,
                      "train": best_train, "test": test_metric,
                      "test_end_index": _index(bars, test_end)})
        # keep full-window results for stitching
        picks[-1]["_result"] = _strip_result(family, best_result)
    headline = _stitch(family, picks, bars)
    freq: dict[str, int] = {}
    for pick in picks:
        freq[pick["pick"]] = freq.get(pick["pick"], 0) + 1
    return {"family": family, "n_windows": len(picks), "picks": picks,
            "selection_frequency": freq, "headline": headline}


def candidates_by_name(candidates: list[dict], name: str) -> dict:
    for cand in candidates:
        if cand["name"] == name:
            return cand
    raise KeyError(name)


def _run_candidate(family: str, cand: dict, bars: list[Bar], vols: dict,
                   funding: dict, event_list: list,
                   stress: dict | None, end: date) -> dict:
    sub = [b for b in bars if b.day < end]
    sub_vols = {day: v for day, v in vols.items() if day < end}
    if family == "puts":
        rule = cand["rule"]
        stress_days = stress.get(cand.get("stress_dd")) if cand.get("stress_dd") else None
        return run_insurance(sub, sub_vols, rule,
                             events=event_list if rule.trigger == "pre_event" else None,
                             stress_days=stress_days)
    if family == "longs":
        sub_funding = {day: v for day, v in funding.items() if day < end}
        return run_longs(sub, sub_vols, sub_funding, cand["rule"])
    sub_funding = {day: v for day, v in funding.items() if day < end}
    return run_carry(sub, sub_funding, cand["rule"])


def _window_metric(family: str, cand: dict, result: dict, bars: list[Bar],
                   byday: dict, start: date, end: date) -> dict:
    # result paths align with bars[:end_index]; map window to that frame.
    end_idx = next((k for k, b in enumerate(bars) if b.day >= end), len(bars))
    frame = bars[:end_idx]
    if family == "puts":
        return puts_window_metrics(frame, result["combined"], result["naked"],
                                   result["legs"], byday, start, end)
    if family == "longs":
        return longs_window_metrics(result["legs"], start, end)
    return carry_window_metrics(result["equity"], frame, start, end)


def _strip_result(family: str, result: dict) -> dict:
    if family == "puts":
        return {"combined": result["combined"], "naked": result["naked"],
                "legs": result["legs"], "n_bars": len(result["combined"])}
    if family == "longs":
        return {"legs": result["legs"]}
    return {"equity": result["equity"]}


def _stitch(family: str, picks: list[dict], bars: list[Bar]) -> dict:
    if family == "puts":
        combined_ret, naked_ret = 1.0, 1.0
        spend_pp, test_years = 0.0, 0.0
        for pick in picks:
            res = pick["_result"]
            i = _index(bars, date.fromisoformat(pick["test_start"]))
            j = pick["test_end_index"]
            legs = res["legs"]
            # attribute spend by entry day inside the test window
            t0, t1 = date.fromisoformat(pick["test_start"]), date.fromisoformat(pick["test_end"])
            spend_pp += sum(leg["premium"] for leg in legs if t0 <= date.fromisoformat(leg["entry"]) < t1)
            test_years += _window_years(t0, t1)
            c, n = res["combined"], res["naked"]
            if j > i + 1 and c[i] > 0 and n[i] > 0:
                combined_ret *= c[j - 1] / c[i]
                naked_ret *= n[j - 1] / n[i]
        # cost in pp of starting capital: normalize spend by first naked level
        first_spot = bars[0].close
        return {"stitched_combined_x": round(combined_ret, 3),
                "stitched_naked_x": round(naked_ret, 3),
                "oos_cost_pct_per_year": round(spend_pp / first_spot / test_years * 100, 2)}
    if family == "longs":
        rets: list[float] = []
        for pick in picks:
            t0 = date.fromisoformat(pick["test_start"])
            t1 = date.fromisoformat(pick["test_end"])
            for leg in pick["_result"]["legs"]:
                if t0 <= date.fromisoformat(leg["entry"]) < t1:
                    rets.append(leg["return"])
        equity = 1.0
        for r in rets:
            equity *= 1 + r / 100
        return {"oos_n_legs": len(rets),
                "oos_win_rate": round(sum(1 for r in rets if r > 0) / len(rets), 3) if rets else None,
                "oos_mean_leg_pct": round(sum(rets) / len(rets), 2) if rets else None,
                "oos_equity_x": round(equity, 3)}
    rets_chain = 1.0
    dds: list[float] = []
    for pick in picks:
        eq = pick["_result"]["equity"]
        i = _index(bars, date.fromisoformat(pick["test_start"]))
        j = pick["test_end_index"]
        if j > i + 1 and eq[i] > 0:
            rets_chain *= eq[j - 1] / eq[i]
            peak = eq[i]
            for level in eq[i:j]:
                peak = max(peak, level)
                dds.append(level / peak - 1)
    years = sum(_window_years(date.fromisoformat(p["test_start"]),
                              date.fromisoformat(p["test_end"])) for p in picks)
    return {"oos_total_pct": round((rets_chain - 1) * 100, 2),
            "oos_ann_pct": round((rets_chain ** (1 / years) - 1) * 100, 2),
            "oos_max_dd_pct": round(min(dds) * 100, 2) if dds else 0.0}
