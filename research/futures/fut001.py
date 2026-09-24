"""Causal signal and preflight for the frozen FUT-001 contract."""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from research.futures.download_archives import tasks_from_coverage
from research.futures.normalize_archives import DAY_MS, HOUR_MS

HORIZONS = (20, 60, 120)
VOL_DECAY = 0.94
VOL_FLOOR = 0.05
MIN_QUOTE_VOLUME = 5_000_000.0
MAX_WEIGHT = 0.05
START_MS = int(datetime(2023, 1, 1, tzinfo=UTC).timestamp() * 1000)
END_MS = int(datetime(2026, 1, 1, tzinfo=UTC).timestamp() * 1000)


def ewma_annual_vol(closes: list[float]) -> float:
    if len(closes) != 121 or any(price <= 0 for price in closes):
        raise ValueError("EWMA requires 121 positive consecutive closes")
    returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    variance = sum(value * value for value in returns[:30]) / 30
    for value in returns[30:]:
        variance = VOL_DECAY * variance + (1 - VOL_DECAY) * value * value
    return max(math.sqrt(365 * variance), VOL_FLOOR)


def forecast(closes: list[float], annual_vol: float) -> tuple[float, float]:
    sigma_day = annual_vol / math.sqrt(365)
    scores = [max(-2.0, min(2.0,
              math.log(closes[-1] / closes[-1 - horizon]) / (sigma_day * math.sqrt(horizon)))) / 2
              for horizon in HORIZONS]
    return sum(scores) / 3, scores[1]


def funding_window(records: list[tuple], slots: list[int], start: int,
                   end: int) -> tuple[bool, float]:
    """Check settlement cadence and sum payments in (start, end]."""
    index = bisect.bisect_right(slots, start) - 1
    if index < 0:
        return False, 0.0
    previous = records[index]
    if previous[0] + previous[2] * HOUR_MS < start:
        return False, 0.0
    total = previous[3] if start < previous[1] <= end else 0.0
    while index + 1 < len(records) and records[index + 1][0] < end:
        current = records[index + 1]
        if current[0] - previous[0] > max(previous[2], current[2]) * HOUR_MS:
            return False, 0.0
        if start < current[1] <= end:
            total += current[3]
        previous = current
        index += 1
    if previous[0] + previous[2] * HOUR_MS < end:
        return False, 0.0
    return True, total


def generate_signals(db: sqlite3.Connection) -> tuple[dict[int, dict[str, dict]], dict, dict[int, dict[str, bool]]]:
    """Use only completed bars and settlements known at each decision close."""
    signals: dict[int, dict[str, dict]] = defaultdict(dict)
    fills: dict[int, dict[str, bool]] = defaultdict(dict)
    counts = defaultdict(int)
    symbols = [row[0] for row in db.execute("SELECT DISTINCT symbol FROM prices ORDER BY symbol")]
    for symbol in symbols:
        bars = list(db.execute(
            "SELECT open_ms,open,high,low,close,base_volume,quote_volume,tradable "
            "FROM prices WHERE symbol=? ORDER BY open_ms", (symbol,)))
        by_time = {bar[0]: bar for bar in bars}
        for bar in bars:
            fills[bar[0]][symbol] = bool(bar[7])
        funding = list(db.execute(
            "SELECT slot_ms,stamp_ms,interval_hours,rate FROM funding "
            "WHERE symbol=? ORDER BY slot_ms", (symbol,)))
        slots = [row[0] for row in funding]
        for index in range(120, len(bars)):
            day = bars[index][0]
            entry = day + DAY_MS
            if not START_MS <= entry < END_MS:
                continue
            counts["candidate_symbol_days"] += 1
            history = bars[index - 120:index + 1]
            if any(history[j][0] != history[0][0] + j * DAY_MS or not history[j][7]
                   for j in range(121)):
                counts["invalid_or_gap_history"] += 1
                continue
            if sum(bar[6] for bar in history[-30:]) / 30 < MIN_QUOTE_VOLUME:
                counts["below_liquidity_floor"] += 1
                continue
            prior_funding_ok, _ = funding_window(funding, slots, day - 29 * DAY_MS, entry)
            if not prior_funding_ok:
                counts["incomplete_prior_funding"] += 1
                continue
            closes = [bar[4] for bar in history]
            volatility = ewma_annual_vol(closes)
            multi, single = forecast(closes, volatility)
            fill = by_time.get(entry)
            exit_bar = by_time.get(entry + DAY_MS)
            hold_funding_ok, funding_sum = funding_window(funding, slots, entry,
                                                           entry + DAY_MS)
            unresolved = []
            if fill is None or not fill[7]:
                unresolved.append("missing_or_inactive_fill")
            if exit_bar is None or not exit_bar[7]:
                unresolved.append("missing_or_inactive_exit")
            if not hold_funding_ok:
                unresolved.append("incomplete_hold_funding")
            signals[entry][symbol] = {
                "multi": multi, "single": single, "vol": volatility,
                "return": exit_bar[1] / fill[1] - 1 if fill and exit_bar and fill[7] and exit_bar[7] else None,
                "funding": funding_sum if hold_funding_ok else None,
                "unresolved": unresolved,
            }
            counts["eligible_symbol_days"] += 1
    counts["symbols_with_any_eligibility"] = len({s for day in signals.values() for s in day})
    return dict(signals), dict(counts), dict(fills)


def partition(day: int) -> str | None:
    year = datetime.fromtimestamp(day / 1000, UTC).year
    if year not in (2023, 2024, 2025):
        return None
    if datetime.fromtimestamp((day + DAY_MS) / 1000, UTC).year != year:
        return None
    return "oos" if year == 2025 else "discovery"


def desired_weights(current: dict[str, dict], component: str) -> dict[str, float]:
    if component not in ("multi", "single"):
        raise ValueError("unfrozen component")
    denominator = sum(1 / item["vol"] for item in current.values())
    if not denominator:
        return {}
    return {symbol: max(-MAX_WEIGHT, min(MAX_WEIGHT,
            item[component] / item["vol"] / denominator))
            for symbol, item in current.items()}


def preflight(signals: dict[int, dict[str, dict]], fills: dict[int, dict[str, bool]],
              *, component: str) -> list[dict]:
    """Identify every missing exposed price/funding interval before scoring."""
    unresolved = []
    previous: dict[str, float] = {}
    previous_year = None
    for day in range(START_MS, END_MS, DAY_MS):
        if partition(day) is None:
            continue
        year = datetime.fromtimestamp(day / 1000, UTC).year
        if year != previous_year:
            previous = {}
        previous_year = year
        current = signals.get(day, {})
        weights = desired_weights(current, component)
        for symbol, weight in weights.items():
            if weight and current[symbol]["unresolved"]:
                unresolved.append({"entry_ms": day, "symbol": symbol, "weight": weight,
                                   "reasons": current[symbol]["unresolved"]})
        for symbol in previous.keys() - weights.keys():
            if previous[symbol] and not fills.get(day, {}).get(symbol, False):
                unresolved.append({"entry_ms": day, "symbol": symbol,
                                   "weight": previous[symbol],
                                   "reasons": ["missing_or_inactive_exit_fill"]})
        previous = weights
    return unresolved


def score(signals: dict[int, dict[str, dict]], fills: dict[int, dict[str, bool]],
          *, component: str, bps: int) -> dict:
    if bps not in (20, 40):
        raise ValueError("unfrozen cost scenario")
    days = []
    unresolved = []
    previous: dict[str, float] = {}
    previous_year = None
    asset_gross = defaultdict(float)
    side_gross = defaultdict(float)
    for day in range(START_MS, END_MS, DAY_MS):
        group = partition(day)
        if group is None:
            continue
        year = datetime.fromtimestamp(day / 1000, UTC).year
        if year != previous_year:
            previous = {}
        previous_year = year
        current = signals.get(day, {})
        weights = desired_weights(current, component)
        turnover = sum(abs(weights.get(s, 0) - previous.get(s, 0))
                       for s in weights.keys() | previous.keys())
        gross = funding_drag = 0.0
        for symbol, weight in weights.items():
            if weight == 0:
                continue
            item = current[symbol]
            if item["unresolved"]:
                unresolved.append({"entry_ms": day, "symbol": symbol, "weight": weight,
                                   "reasons": item["unresolved"]})
                continue
            contribution = weight * item["return"]
            gross += contribution
            asset_gross[symbol] += contribution
            side_gross["long" if weight > 0 else "short"] += contribution
            funding_drag += weight * item["funding"]
        for symbol in previous.keys() - weights.keys():
            if previous[symbol] and not fills.get(day, {}).get(symbol, False):
                unresolved.append({"entry_ms": day, "symbol": symbol,
                                   "weight": previous[symbol],
                                   "reasons": ["missing_or_inactive_exit_fill"]})
        cost = turnover * bps / 20_000
        days.append({"partition": group, "entry_ms": day, "gross": gross,
                     "funding_drag": funding_drag, "transaction_drag": cost,
                     "net": gross - funding_drag - cost,
                     "gross_exposure": sum(abs(w) for w in weights.values()),
                     "active_names": sum(w != 0 for w in weights.values())})
        previous = weights
    return {"component": component, "round_trip_bps": bps,
            "daily": days, "unresolved_exposures": unresolved,
            "asset_gross": dict(sorted(asset_gross.items())),
            "side_gross": dict(side_gross)}


def signal_statistic(signals: dict[int, dict[str, dict]], component: str) -> dict:
    by_group: dict[str, list[float]] = defaultdict(list)
    for day, candidates in signals.items():
        group = partition(day)
        if group is None:
            continue
        for item in candidates.values():
            if item["unresolved"]:
                continue
            by_group[group].append(item[component] * item["return"])
    return {group: {"symbol_days": len(values), "mean_forecast_times_return":
                    sum(values) / len(values) if values else None}
            for group, values in by_group.items()}


def summarize(days: list[dict], group: str) -> dict:
    rows = [row for row in days if row["partition"] == group]
    values = [row["net"] for row in rows]
    count = len(rows)
    mean = sum(values) / count if count else None
    variance = sum((value - mean) ** 2 for value in values) / (count - 1) if count > 1 else None
    volatility = math.sqrt(365 * variance) if variance is not None else None
    equity = peak = 1.0
    drawdown = 0.0
    for value in values:
        equity *= 1 + value
        peak = max(peak, equity)
        drawdown = min(drawdown, equity / peak - 1)
    months: dict[str, list[float]] = defaultdict(list)
    quarters: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        stamp = datetime.fromtimestamp(row["entry_ms"] / 1000, UTC)
        month = stamp.strftime("%Y-%m")
        months[month].append(row["net"])
        quarters[f"{stamp.year}-Q{(stamp.month - 1) // 3 + 1}"].append(row["net"])
    return {"days": count, "mean_daily_net": mean,
            "compounded_return": equity - 1, "annualized_volatility": volatility,
            "annualized_sharpe": mean * 365 / volatility if volatility else None,
            "max_drawdown": drawdown,
            "mean_daily_gross": sum(row["gross"] for row in rows) / count if count else None,
            "total_funding_drag": sum(row["funding_drag"] for row in rows),
            "total_transaction_drag": sum(row["transaction_drag"] for row in rows),
            "mean_gross_exposure": sum(row["gross_exposure"] for row in rows) / count if count else None,
            "mean_active_names": sum(row["active_names"] for row in rows) / count if count else None,
            "month_means": {month: sum(v) / len(v) for month, v in sorted(months.items())},
            "quarter_means": {quarter: sum(v) / len(v) for quarter, v in sorted(quarters.items())}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("coverage", type=Path)
    parser.add_argument("database", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    coverage = json.loads(args.coverage.read_text())
    expected = len(tasks_from_coverage(coverage, 2022, 2025))
    with sqlite3.connect(args.database) as db:
        actual = db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        if actual != expected:
            raise ValueError(f"incomplete normalized dataset: {actual}/{expected} files")
        signals, eligibility, fills = generate_signals(db)
    unresolved = []
    for component in ("multi", "single"):
        unresolved.extend({"component": component, **item}
                          for item in preflight(signals, fills, component=component))
    report = {"contract": "FUT-001", "contract_status": "FROZEN_FOR_DATA_ACQUISITION",
              "generated_at": datetime.now(UTC).isoformat(),
              "database_sha256": hashlib.sha256(args.database.read_bytes()).hexdigest(),
              "expected_files": expected, "normalized_files": actual,
              "eligibility": eligibility, "unresolved_exposures": unresolved}
    if unresolved:
        report["result_status"] = "INCOMPLETE_DATA"
    else:
        scored = [score(signals, fills, component=component, bps=bps)
                  for component in ("multi", "single") for bps in (20, 40)]
        report["results"] = [{"component": result["component"],
                              "round_trip_bps": result["round_trip_bps"],
                              "discovery": summarize(result["daily"], "discovery"),
                              "oos": summarize(result["daily"], "oos"),
                              "asset_gross": result["asset_gross"],
                              "side_gross": result["side_gross"],
                              "signal_statistic": signal_statistic(signals, result["component"])}
                             for result in scored]
        primary = report["results"][0]["oos"]["mean_daily_net"]
        stressed = report["results"][1]["oos"]["mean_daily_net"]
        report["result_status"] = ("REJECTED" if primary is None or primary <= 0 else
                                   "COST_SENSITIVE" if stressed is None or stressed <= 0 else
                                   "SURVIVED_CHEAP_GATE")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps({"result_status": report["result_status"],
                      "eligible_symbol_days": eligibility.get("eligible_symbol_days", 0),
                      "unresolved_exposures": len(unresolved),
                      "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
