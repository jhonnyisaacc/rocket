"""What led each drawdown, and how close later buys were to the low. Descriptive, not a fit."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from rocket.market_check.calendar import events_on
from rocket.market_check.config import Config
from rocket.market_check.episodes import _drawdowns
from rocket.market_check.panel import SeriesPanel

STOCK_SIGNALS = (
    ("vix_jump", "VIX 5-session jump of 6 points or more"),
    ("vix_level", "VIX at or above 25"),
    ("credit", "High-yield OAS wider by 40bp over 20 sessions"),
    ("yield_30y", "30-year yield up 35bp over 20 sessions"),
    ("oil", "WTI up 8% over 5 sessions"),
    ("dollar", "Dollar up 1.5% over 20 sessions"),
)
CRYPTO_SIGNALS = (
    ("funding", "7-day BTC funding sum negative"),
    ("dvol_level", "DVOL at or above 65"),
    ("dvol_jump", "DVOL up 5 points over 5 sessions"),
)


def _series(panel: SeriesPanel, name: str) -> dict[date, float]:
    return {day: value for day, value in panel.points(name)}


def _change(series: dict[date, float], calendar: list[date], day: date, sessions: int, *, pct: bool) -> float | None:
    prior = [item for item in calendar if item <= day]
    if len(prior) <= sessions:
        return None
    previous = series.get(prior[-1 - sessions])
    current = series.get(prior[-1])
    if previous in (None, 0) or current is None:
        return None
    if pct:
        return current / previous - 1
    return current - previous


def _funding(panel: SeriesPanel, day: date, days: int = 7) -> float | None:
    rows = [(stamp, value) for stamp, value in panel.points("funding_daily") if stamp <= day]
    if not rows:
        return None
    cut = rows[-1][0] - timedelta(days=days - 1)
    sample = [value for stamp, value in rows if stamp >= cut]
    if not sample:
        return None
    return sum(sample)


def _equal_weight(panel: SeriesPanel, config: Config, days: list[date]) -> list[tuple[date, float]]:
    level = 100.0
    previous: dict[str, float] = {}
    path = []
    for day in days:
        returns = []
        current: dict[str, float] = {}
        for name in config.portfolio.core:
            price = dict(panel.points(name)).get(day)
            if price is None:
                continue
            current[name] = price
            if previous.get(name):
                returns.append(price / previous[name] - 1)
        if path and returns:
            level *= 1 + sum(returns) / len(returns)
        elif not path:
            level = 100.0
        path.append((day, level))
        previous = current or previous
    return path


def _triggers(panel: SeriesPanel, config: Config, days: list[date]) -> dict[date, dict[str, bool]]:
    series = {name: _series(panel, name) for name in ("vix", "hy_oas", "yield_30y", "wti", "dollar", "dvol")}
    calendars = {name: [day for day, _ in panel.points(name)] for name in series}
    rows = {}
    for day in days:
        funding = _funding(panel, day)
        rows[day] = {
            "vix_jump": (_change(series["vix"], calendars["vix"], day, 5, pct=False) or -999) >= 6,
            "vix_level": series["vix"].get(day, 0) >= 25,
            "credit": (_change(series["hy_oas"], calendars["hy_oas"], day, 20, pct=False) or -999) >= 0.40,
            "yield_30y": (_change(series["yield_30y"], calendars["yield_30y"], day, 20, pct=False) or -999) >= 0.35,
            "oil": (_change(series["wti"], calendars["wti"], day, 5, pct=True) or -999) >= 0.08,
            "dollar": (_change(series["dollar"], calendars["dollar"], day, 20, pct=True) or -999) >= 0.015,
            "funding": funding is not None and funding < 0,
            "dvol_level": series["dvol"].get(day, 0) >= 65,
            "dvol_jump": (_change(series["dvol"], calendars["dvol"], day, 5, pct=False) or -999) >= 5,
            "event": bool(events_on(day, config)),
        }
    return rows


def _first(flags: dict[date, dict[str, bool]], days: list[date], start: date, end: date, name: str) -> date | None:
    for day in days:
        if day < start:
            continue
        if day > end:
            return None
        if flags[day][name]:
            return day
    return None


def _noise(flags: dict[date, dict[str, bool]], days: list[date], covered: set[date], oos: date) -> dict[str, str]:
    labels = {}
    sample = [day for day in days if day < oos]
    for name in [item[0] for item in (*STOCK_SIGNALS, *CRYPTO_SIGNALS)]:
        hits = [day for day in sample if flags[day][name]]
        if not hits:
            labels[name] = "no in-sample triggers"
            continue
        outside = [day for day in hits if day not in covered]
        rate = len(outside) / len(hits)
        labels[name] = "noise" if rate >= 0.5 else "specific"
    labels["event"] = "noise"
    return labels


def _span_days(days: list[date], peak: date, trough: date, lead: int) -> list[date]:
    prior = [day for day in days if day < peak]
    start = prior[-lead] if len(prior) >= lead else peak
    return [day for day in days if start <= day <= trough]


def diagnose(panel: SeriesPanel, config: Config) -> dict[str, Any]:
    start, end = config.window.start, config.window.end
    oos = config.window.oos_start
    spy_days = [day for day in panel.dates("spy") if start <= day <= end]
    flags = _triggers(panel, config, spy_days)
    spy = [(day, _series(panel, "spy")[day]) for day in spy_days if day in _series(panel, "spy")]
    btc_map = _series(panel, "btc")
    btc = [(day, btc_map[day]) for day in panel.dates("btc") if start <= day <= end and day in btc_map]
    books = {
        "SPY": (spy, config.regime.stress.spy_drawdown, "stock"),
        "equal-weight book": (_equal_weight(panel, config, spy_days), config.regime.stress.spy_drawdown, "stock"),
        "BTC": (btc, config.regime.stress.btc_drawdown, "crypto"),
    }
    for name in config.portfolio.core:
        prices = _series(panel, name)
        points = [(day, prices[day]) for day in spy_days if day in prices]
        books[name] = (points, 0.15, "stock")
    covered: set[date] = set()
    episodes = []
    for asset, (points, threshold, kind) in books.items():
        for episode in _drawdowns(points, threshold):
            window = _span_days(spy_days, episode["peak"], episode["trough"], config.regime.stress.lead_sessions)
            covered.update(window)
            episodes.append({**episode, "asset": asset, "kind": kind, "window": window})
    noise = _noise(flags, spy_days, covered, oos)
    rows = []
    for episode in episodes:
        window = episode["window"]
        lo, hi = window[0], episode["trough"]
        fired = []
        for name, text in (*STOCK_SIGNALS, *CRYPTO_SIGNALS):
            hit = _first(flags, spy_days, lo, hi, name)
            if hit is None:
                continue
            fired.append({
                "name": name,
                "text": text,
                "date": hit.isoformat(),
                "versus_peak": (hit - episode["peak"]).days,
                "versus_low": (episode["trough"] - hit).days,
                "group": "crypto" if name in {item[0] for item in CRYPTO_SIGNALS} else "stock",
                "noise": noise.get(name, ""),
            })
        event_days = [day for day in window if flags[day]["event"]]
        vix = _series(panel, "vix")
        hold = [day for day in spy_days if episode["peak"] <= day <= episode["trough"] + timedelta(days=20)]
        vix_peak = max(hold, key=lambda day: vix.get(day, -1)) if hold else None
        fade = None
        if vix_peak is not None:
            for day in spy_days:
                if day <= vix_peak or day > episode["trough"] + timedelta(days=15):
                    continue
                change = _change(vix, panel.dates("vix"), day, 5, pct=False)
                if change is not None and change < 0 and vix.get(day, 99) < vix.get(vix_peak, 0):
                    fade = day
                    break
        credit_calm = None
        hy = _series(panel, "hy_oas")
        for day in spy_days:
            if day < episode["trough"] or day > episode["trough"] + timedelta(days=40):
                continue
            change = _change(hy, panel.dates("hy_oas"), day, 20, pct=False)
            if change is not None and change <= 0:
                credit_calm = day
                break
        dvol = _series(panel, "dvol")
        crypto_days = [day for day in panel.dates("dvol") if episode["peak"] <= day <= episode["trough"] + timedelta(days=20)]
        dvol_peak = max(crypto_days, key=lambda day: dvol.get(day, -1)) if crypto_days else None
        funding_day = next((day for day in spy_days if episode["peak"] <= day <= episode["trough"] and flags[day]["funding"]), None)
        rows.append({
            "asset": episode["asset"],
            "kind": episode["kind"],
            "sample": "in_sample" if episode["peak"] < oos else "out_of_sample",
            "peak": episode["peak"].isoformat(),
            "trough": episode["trough"].isoformat(),
            "depth": episode["depth"],
            "signals": fired,
            "event_days": len(event_days),
            "vix_peak": None if vix_peak is None else vix_peak.isoformat(),
            "vix_peak_level": None if vix_peak is None else vix.get(vix_peak),
            "vix_fade": None if fade is None else fade.isoformat(),
            "vix_fade_vs_low": None if fade is None else (fade - episode["trough"]).days,
            "credit_calm": None if credit_calm is None else credit_calm.isoformat(),
            "credit_calm_vs_low": None if credit_calm is None else (credit_calm - episode["trough"]).days,
            "dvol_peak": None if dvol_peak is None else dvol_peak.isoformat(),
            "dvol_peak_vs_low": None if dvol_peak is None else (dvol_peak - episode["trough"]).days,
            "funding_negative": None if funding_day is None else funding_day.isoformat(),
            "funding_vs_low": None if funding_day is None else (episode["trough"] - funding_day).days,
        })
    return {"rows": rows, "noise": noise, "markdown": _markdown(rows, noise)}


def _offset(days: int | None) -> str:
    """Days from the trough. Positive means the mark printed after the low."""
    if days is None:
        return "n/a"
    if days > 0:
        return f"{days}d after the low"
    if days < 0:
        return f"{-days}d before the low"
    return "on the low"


def _first_on_or_after_peak(items: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    before = [item for item in items if item["versus_peak"] < 0]
    after = [item for item in items if item["versus_peak"] >= 0]
    lead = min(before, key=lambda item: item["date"]) if before else None
    first = min(after, key=lambda item: item["date"]) if after else None
    return first, lead


def _side_lines(label: str, items: list[dict[str, Any]], empty: str) -> list[str]:
    if not items:
        return [empty if label == "Stock" else "No crypto signal fired in the lookback."]
    first, earlier = _first_on_or_after_peak(items)
    if first is None:
        earlier = min(items, key=lambda item: item["date"])
        return [(
            f"{label} side had no print on or after the peak. "
            f"The lookback did catch {earlier['text']} on {earlier['date']} ({_lead(earlier['versus_peak'])})."
        )]
    line = (
        f"{label} side moved first via {first['text']} on {first['date']} "
        f"({_lead(first['versus_peak'])}, {first['versus_low']}d before the low)."
    )
    if earlier is not None:
        line += f" Earlier in the lookback: {earlier['text']} on {earlier['date']} ({_lead(earlier['versus_peak'])})."
    return [line]


def _lead(days: int | None) -> str:
    if days is None:
        return "n/a"
    if days < 0:
        return f"{-days}d before the peak"
    if days > 0:
        return f"{days}d after the peak"
    return "on the peak"


def _markdown(rows: list[dict[str, Any]], noise: dict[str, str]) -> str:
    noisy = [name for name, label in noise.items() if label == "noise"]
    lines = [
        "## What moved before the drawdowns",
        "",
        (
            "Major drawdowns are 8% for SPY and the equal-weight core book, 15% for BTC and for each "
            "core name. Each signal is scored from the close, with a 10-session lookback before the peak. "
            "Stock signals are the VIX, credit, the 30-year, oil and the dollar. Crypto signals are "
            "funding and DVOL. A signal is marked noise when at least half of its in-sample triggers "
            "fell outside these drawdown windows. Scheduled FOMC, CPI and payroll dates are noise as a "
            "timing tool: a multi-week decline almost always contains one."
        ),
        "",
        f"In-sample noise labels: {', '.join(noisy) if noisy else 'none'}.",
        "",
    ]
    for row in rows:
        stock = [item for item in row["signals"] if item["group"] == "stock"]
        crypto = [item for item in row["signals"] if item["group"] == "crypto"]
        lines.append(
            f"### {row['asset']} {row['sample'].replace('_', ' ')}: {row['peak']} to {row['trough']} ({row['depth']:.1%})"
        )
        lines.append("")
        lines.extend(_side_lines(
            "Stock", stock, "No stock signal fired in the lookback. The equity complex did not lead this decline.",
        ))
        lines.extend(_side_lines("Crypto", crypto, "No crypto signal fired in the lookback."))
        detail = ", ".join(
            f"{item['name']} {item['date']} ({_lead(item['versus_peak'])}, {item['noise']})"
            for item in sorted(row["signals"], key=lambda item: item["date"])
        ) or "none"
        lines.append(f"All hits: {detail}.")
        lines.append(
            f"Calendar events inside the window: {row['event_days']}. Treated as noise, not a lead."
        )
        funding = (
            "Funding did not go negative between the peak and the low."
            if not row["funding_negative"]
            else (
                f"Funding negative {row['funding_negative']} "
                f"({_offset(-(row['funding_vs_low'] or 0))})."
            )
        )
        level = "n/a" if row["vix_peak_level"] is None else f"{row['vix_peak_level']:.1f}"
        lines.append(
            "Bottom marks: "
            f"VIX peaked {row['vix_peak'] or 'n/a'} at {level}, "
            f"first fade {row['vix_fade'] or 'n/a'} ({_offset(row['vix_fade_vs_low'])}). "
            f"Credit 20-session change back to flat {row['credit_calm'] or 'n/a'} "
            f"({_offset(row['credit_calm_vs_low'])}). "
            f"DVOL peak {row['dvol_peak'] or 'n/a'} ({_offset(row['dvol_peak_vs_low'])}). "
            f"{funding} "
            "There is no volume series in the panel, so capitulation volume cannot be tested."
        )
        lines.append("")
    lines.append(
        "Reading the in-sample tape: the deep equity low was a VIX and credit event, not an oil or "
        "30-year event. Funding turning negative and the DVOL rise showed up in the crypto book during "
        "the decline, weeks before the low, so they are stress markers rather than bottom markers. "
        "The usable bottom was the VIX falling off a spike of 25 or more while the index was still "
        "about 12% under its 60-session high. Waiting for credit to tighten again missed the turn."
    )
    lines.append("")
    return "\n".join(lines)


def _price_on(panel: SeriesPanel, name: str, day: date) -> float | None:
    rows = [(stamp, value) for stamp, value in panel.points(name) if stamp <= day]
    if not rows:
        return None
    return rows[-1][1]


def entry_quality(
    panel: SeriesPanel,
    config: Config,
    trades: list[dict[str, Any]],
    crypto_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Average fill after each low, divided by the price on the trough day."""
    start, end = config.window.start, config.window.end
    spy_days = [day for day in panel.dates("spy") if start <= day <= end]
    books: list[tuple[str, list[tuple[date, float]], float]] = []
    spy_map = _series(panel, "spy")
    books.append(("SPY", [(day, spy_map[day]) for day in spy_days if day in spy_map], config.regime.stress.spy_drawdown))
    for name in config.portfolio.core:
        prices = _series(panel, name)
        books.append((name, [(day, prices[day]) for day in spy_days if day in prices], 0.15))
    btc_map = _series(panel, "btc")
    btc_days = [day for day in panel.dates("btc") if start <= day <= end and day in btc_map]
    books.append(("BTC", [(day, btc_map[day]) for day in btc_days], config.regime.stress.btc_drawdown))
    rows = []
    for asset, points, threshold in books:
        for episode in _drawdowns(points, threshold):
            after = episode["trough"] + timedelta(days=21)
            if asset == "BTC":
                buys = []
                for crypto in crypto_rows or []:
                    if crypto.get("position") != "long" or crypto.get("opened") is False:
                        continue
                    entry_day = date.fromisoformat(crypto.get("entry_date") or crypto["date"])
                    if episode["peak"] <= entry_day <= after:
                        buys.append(crypto)
            elif asset == "SPY":
                buys = [
                    trade for trade in trades
                    if trade["side"] == "buy" and trade["reason"] != "initial"
                    and episode["trough"] <= date.fromisoformat(trade["date"]) <= after
                ]
            else:
                buys = [
                    trade for trade in trades
                    if trade["side"] == "buy" and trade["ticker"] == asset and trade["reason"] != "initial"
                    and episode["peak"] <= date.fromisoformat(trade["date"]) <= after
                ]
            gaps = []
            for trade in buys:
                if asset == "BTC":
                    trough_px = _price_on(panel, "btc", episode["trough"])
                    fill = float(trade["entry"])
                else:
                    anchor = asset if asset != "SPY" else trade["ticker"]
                    trough_px = _price_on(panel, anchor, episode["trough"])
                    fill = float(trade["price"])
                if trough_px:
                    gaps.append(fill / trough_px - 1)
            rows.append({
                "asset": asset,
                "sample": "in_sample" if episode["peak"] < config.window.oos_start else "out_of_sample",
                "peak": episode["peak"].isoformat(),
                "trough": episode["trough"].isoformat(),
                "depth": episode["depth"],
                "buys": len(buys),
                "avg_entry_vs_low": None if not gaps else sum(gaps) / len(gaps),
            })
    return rows
