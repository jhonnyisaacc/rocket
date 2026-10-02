"""Risk episodes and how early they sat relative to large drawdowns."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from rocket.market_check.config import Config
from rocket.market_check.panel import SeriesPanel


def _day(value: date | str) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def session_counts(nav: list[dict[str, Any]], oos: date) -> dict[str, dict[str, int]]:
    buckets = {"in_sample": {}, "out_of_sample": {}}
    for row in nav:
        key = "in_sample" if _day(row["date"]) < oos else "out_of_sample"
        regime = str(row["regime"])
        bucket = buckets[key]
        bucket[regime] = bucket.get(regime, 0) + 1
    return buckets


def regime_episodes(nav: list[dict[str, Any]], oos: date) -> list[dict[str, Any]]:
    """Compress consecutive caution and risk-off sessions inside the backtest window."""
    episodes: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for row in nav:
        regime = str(row["regime"])
        day = _day(row["date"])
        if regime not in {"caution", "risk-off"}:
            if current is not None:
                episodes.append(current)
                current = None
            continue
        if current is not None and current["regime"] == regime:
            current["end"] = day.isoformat()
            current["sessions"] += 1
            continue
        if current is not None:
            episodes.append(current)
        current = {
            "regime": regime,
            "start": day.isoformat(),
            "end": day.isoformat(),
            "sessions": 1,
            "sample": "in_sample" if day < oos else "out_of_sample",
        }
    if current is not None:
        episodes.append(current)
    return episodes


def _drawdowns(points: list[tuple[date, float]], threshold: float) -> list[dict[str, Any]]:
    """Peak-to-trough declines of at least `threshold` that end when price reclaims the peak."""
    if len(points) < 2:
        return []
    episodes = []
    peak_at = 0
    index = 1
    while index < len(points):
        if points[index][1] >= points[peak_at][1]:
            peak_at = index
            index += 1
            continue
        if points[peak_at][1] <= 0 or points[index][1] / points[peak_at][1] - 1 > -threshold:
            index += 1
            continue
        trough_at = index
        cursor = index + 1
        while cursor < len(points) and points[cursor][1] < points[peak_at][1]:
            if points[cursor][1] < points[trough_at][1]:
                trough_at = cursor
            cursor += 1
        peak_day, peak_px = points[peak_at]
        trough_day, trough_px = points[trough_at]
        episodes.append({
            "peak": peak_day,
            "trough": trough_day,
            "depth": trough_px / peak_px - 1,
        })
        if cursor >= len(points):
            break
        peak_at = cursor
        index = cursor + 1
    return episodes


def _first(path: list[dict[str, Any]], start: date, end: date, regimes: set[str]) -> date | None:
    for row in path:
        day = _day(row["date"])
        if day < start:
            continue
        if day > end:
            return None
        if row["regime"] in regimes:
            return day
    return None


def _lead(warning: date | None, anchor: date) -> int | None:
    if warning is None:
        return None
    return (warning - anchor).days


def drawdown_warnings(
    panel: SeriesPanel,
    config: Config,
    path: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """For each large SPY or BTC drawdown, the first caution and risk-off inside the lead window."""
    rules = config.regime.stress
    start, end = config.window.start, config.window.end
    spy_days = [day for day in panel.dates("spy") if start <= day <= end]
    spy_px = {day: value for day, value in panel.points("spy")}
    btc_px = {day: value for day, value in panel.points("btc")}
    series = {
        "SPY": ([(day, spy_px[day]) for day in spy_days if day in spy_px], rules.spy_drawdown),
        "BTC": (
            [(day, btc_px[day]) for day in panel.dates("btc") if start <= day <= end and day in btc_px],
            rules.btc_drawdown,
        ),
    }
    rows = []
    for asset, (points, threshold) in series.items():
        for episode in _drawdowns(points, threshold):
            peak = episode["peak"]
            prior = [day for day in spy_days if day < peak]
            if len(prior) >= rules.lead_sessions:
                lookback = prior[-rules.lead_sessions]
            else:
                lookback = peak - timedelta(days=14)
            caution = _first(path, lookback, episode["trough"], {"caution", "risk-off"})
            risk_off = _first(path, lookback, episode["trough"], {"risk-off"})
            rows.append({
                "asset": asset,
                "sample": "in_sample" if peak < config.window.oos_start else "out_of_sample",
                "peak": peak.isoformat(),
                "trough": episode["trough"].isoformat(),
                "depth": episode["depth"],
                "first_caution": caution.isoformat() if caution else None,
                "first_risk_off": risk_off.isoformat() if risk_off else None,
                "caution_vs_peak_days": _lead(caution, peak),
                "risk_off_vs_peak_days": _lead(risk_off, peak),
                "caution_vs_trough_days": None if caution is None else (episode["trough"] - caution).days,
                "risk_off_vs_trough_days": None if risk_off is None else (episode["trough"] - risk_off).days,
            })
    return rows
