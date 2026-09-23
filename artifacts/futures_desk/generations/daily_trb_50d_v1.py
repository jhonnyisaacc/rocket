"""One validation run of the frozen daily-trb-50d-v1 contract.

The contract page is daily-trb-50d-v1.md. This file implements that page.
It does not search 50, 10, a band, or the cost levels. It does not import
the live scan and it does not set execution_enabled.

Candles go through rocket.providers.hyperliquid.fetch_candles. One httpx
client is shared with fetch_perp_markets. Funding history uses that same
client because the provider on this branch has no funding helper.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rocket.models import OperationalStatus  # noqa: E402
from rocket.providers.hyperliquid import (  # noqa: E402
    MAINNET_INFO_URL,
    fetch_candles,
    fetch_perp_markets,
)

CHANNEL = 50
HOLD_SESSIONS = 10
COST_BPS = (20, 40)
QUOTE_VOLUME_FLOOR = 5_000_000.0
LOOKBACK_DAYS = 365
DAY_MS = 86_400_000
HOUR_MS = 3_600_000

JUNE_START = datetime(2026, 6, 25, tzinfo=UTC)
JUNE_END = datetime(2026, 8, 31, 23, 59, 59, tzinfo=UTC)
HYPE_START = datetime(2026, 9, 15, tzinfo=UTC)
HYPE_END = datetime(2026, 9, 29, 23, 59, 59, tzinfo=UTC)
HYPE_COIN = "HYPE"

CACHE = Path("/tmp/daily-trb-50d-v1")
HERE = Path(__file__).resolve().parent
RESULTS_PATH = HERE / "daily-trb-50d-v1-RESULTS.md"


def ms(stamp: datetime) -> int:
    return int(stamp.timestamp() * 1000)


def iso(millis: int) -> str:
    return datetime.fromtimestamp(millis / 1000, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def day_key(millis: int) -> str:
    return datetime.fromtimestamp(millis / 1000, UTC).strftime("%Y-%m-%d")


def month_key(millis: int) -> str:
    return datetime.fromtimestamp(millis / 1000, UTC).strftime("%Y-%m")


def load_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def as_bars(rows) -> list[dict]:
    if isinstance(rows, dict):
        return []
    out = []
    seen: set[int] = set()
    for raw in rows:
        t, o, h, l, c, v = raw
        t = int(t)
        if t in seen:
            continue
        seen.add(t)
        try:
            o, h, l, c, v = float(o), float(h), float(l), float(c), float(v)
        except (TypeError, ValueError):
            continue
        if h <= 0 or l <= 0 or c <= 0 or o <= 0 or h < l:
            continue
        out.append({"t": t, "o": o, "h": h, "l": l, "c": c, "v": v})
    out.sort(key=lambda bar: bar["t"])
    return out


def completed_bars(bars: list[dict], now_ms: int) -> list[dict]:
    return [bar for bar in bars if bar["t"] + DAY_MS <= now_ms and bar["t"] <= now_ms]


def find_breaks(completed: list[dict]) -> list[dict]:
    """New 50-close extremes. The signal bar is not inside the 50."""
    breaks = []
    for index in range(CHANNEL, len(completed)):
        window = completed[index - CHANNEL : index]
        hi = max(bar["c"] for bar in window)
        lo = min(bar["c"] for bar in window)
        close = completed[index]["c"]
        if close > hi:
            side, level = 1, hi
        elif close < lo:
            side, level = -1, lo
        else:
            continue
        notional = completed[index]["v"] * close
        breaks.append(
            {
                "signal_t": completed[index]["t"],
                "direction": side,
                "level": level,
                "notional": notional,
                "eligible": notional >= QUOTE_VOLUME_FLOOR,
            }
        )
    return breaks


def bar_exactly_after(bars: list[dict], stamp: int, sessions: int) -> dict | None | str:
    """Walk `sessions` exact one-day steps. None if the bar has not printed. 'gap' if a day is missing."""
    current = stamp
    found = None
    by_t = {bar["t"]: bar for bar in bars}
    for _ in range(sessions):
        nxt = current + DAY_MS
        found = by_t.get(nxt)
        if found is None:
            later = [bar for bar in bars if bar["t"] > current]
            if later and later[0]["t"] != nxt:
                return "gap"
            return None
        current = nxt
    return found


def attach_prices(breaks: list[dict], bars: list[dict]) -> list[dict]:
    events = []
    for item in breaks:
        if not item["eligible"]:
            continue
        fill = bar_exactly_after(bars, item["signal_t"], 1)
        event = dict(item)
        if fill is None or fill == "gap" or not isinstance(fill, dict):
            event["fill_t"] = None
            event["fill"] = None
            event["exit_t"] = None
            event["exit"] = None
            event["unresolved"] = "gap" if fill == "gap" else "no_fill"
            events.append(event)
            continue
        event["fill_t"] = fill["t"]
        event["fill"] = fill["o"]
        exit_bar = bar_exactly_after(bars, fill["t"], HOLD_SESSIONS)
        if exit_bar is None or exit_bar == "gap" or not isinstance(exit_bar, dict):
            event["exit_t"] = None
            event["exit"] = None
            event["unresolved"] = "gap" if exit_bar == "gap" else "open"
        else:
            event["exit_t"] = exit_bar["t"]
            event["exit"] = exit_bar["o"]
            event["unresolved"] = None
        events.append(event)
    return events


def select_book(events: list[dict]) -> list[dict]:
    """Skip a new fill while this name's prior 10-session window is still open."""
    ordered = sorted(
        (event for event in events if event.get("fill_t") is not None),
        key=lambda event: (event["fill_t"], event["direction"]),
    )
    taken = []
    busy_until = None
    for event in ordered:
        if busy_until == "open":
            event["book"] = "skipped"
            continue
        if busy_until is not None and event["fill_t"] < busy_until:
            event["book"] = "skipped"
            continue
        event["book"] = "taken"
        taken.append(event)
        busy_until = "open" if event.get("exit_t") is None else event["exit_t"]
    return taken


def net_return(direction: int, entry: float, exit_px: float, bps: float, rate_sum: float) -> float:
    gross = direction * (exit_px - entry) / entry
    return gross - (bps / 10_000.0) - direction * rate_sum


def funding_rate_sum(buckets: dict[int, float], start_ms: int, end_ms: int) -> float | None:
    """Hourly prints whose timestamp falls in (start, end].

    The venue stamps each print about 50ms after the hour. The print on the
    exit hour is therefore after the exit open and is outside the hold. A
    missing hour inside the hold drops the trade. Missing hours are not zero.
    """
    if end_ms <= start_ms:
        return 0.0
    total = 0.0
    stamp = (start_ms // HOUR_MS) * HOUR_MS + HOUR_MS
    while stamp < end_ms:
        if stamp not in buckets:
            return None
        total += buckets[stamp]
        stamp += HOUR_MS
    return total


def max_drawdown(values: list[float]) -> float | None:
    if not values:
        return None
    equity = 0.0
    peak = 0.0
    worst = 0.0
    for value in values:
        equity += value
        if equity > peak:
            peak = equity
        drop = equity - peak
        if drop < worst:
            worst = drop
    return worst


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def pstdev(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    avg = sum(values) / len(values)
    return (sum((value - avg) ** 2 for value in values) / len(values)) ** 0.5


def in_window(stamp: int, start: datetime, end: datetime) -> bool:
    return ms(start) <= stamp <= ms(end)


def position_fraction(events: list[dict], bars: list[dict]) -> float:
    if not bars:
        return 0.0
    occupied: set[int] = set()
    for event in events:
        fill_t = event.get("fill_t")
        if fill_t is None:
            continue
        exit_t = event.get("exit_t")
        for bar in bars:
            if bar["t"] < fill_t:
                continue
            if exit_t is None or bar["t"] < exit_t:
                occupied.add(bar["t"])
    return len(occupied) / len(bars)


def score_one(event: dict, buckets: dict[int, float]) -> dict:
    row = dict(event)
    if event.get("fill") is None or event.get("exit") is None:
        return row
    rate_sum = funding_rate_sum(buckets, event["fill_t"], event["exit_t"])
    row["funding_incomplete"] = rate_sum is None
    if rate_sum is None:
        return row
    row["rate_sum"] = rate_sum
    row["gross"] = event["direction"] * (event["exit"] - event["fill"]) / event["fill"]
    row["ret20"] = net_return(event["direction"], event["fill"], event["exit"], 20, rate_sum)
    row["ret40"] = net_return(event["direction"], event["fill"], event["exit"], 40, rate_sum)
    return row


def closed_funded(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row.get("ret20") is not None]


def share_of(total: float, part: float) -> float | None:
    if total == 0:
        return None
    return part / total


def concentration(rows: list[dict], key: str) -> dict:
    if not rows:
        return {
            "sum": 0.0,
            "n": 0,
            "share": None,
            "complement_n": 0,
            "complement_mean": None,
            "fires": False,
        }
    total = sum(row[key] for row in rows)
    part = sum(row[key] for row in rows if row.get("_in"))
    inside = [row[key] for row in rows if row.get("_in")]
    outside = [row[key] for row in rows if not row.get("_in")]
    complement = mean(outside)
    share = share_of(total, part)
    book_mean = mean([row[key] for row in rows])
    fires = bool(
        book_mean is not None
        and book_mean > 0
        and (
            not outside
            or (complement is not None and complement <= 0)
            or (share is not None and share > 0.5)
        )
    )
    return {
        "sum": part,
        "n": len(inside),
        "share": share,
        "complement_n": len(outside),
        "complement_mean": complement,
        "fires": fires,
    }


def summarize(rows: list[dict], bars_by_coin: dict[str, list[dict]], universe: list[str]) -> dict:
    funded = closed_funded(rows)
    by_exit = sorted(funded, key=lambda row: (row["exit_t"], row["coin"], row["fill_t"]))
    ret20 = [row["ret20"] for row in funded]
    ret40 = [row["ret40"] for row in funded]
    longs = [row for row in funded if row["direction"] > 0]
    shorts = [row for row in funded if row["direction"] < 0]

    by_coin: dict[str, list[dict]] = {}
    for row in funded:
        by_coin.setdefault(row["coin"], []).append(row)
    coin_rows = []
    for coin, group in by_coin.items():
        coin_rows.append(
            {
                "coin": coin,
                "n": len(group),
                "n_long": sum(1 for row in group if row["direction"] > 0),
                "n_short": sum(1 for row in group if row["direction"] < 0),
                "mean20": mean([row["ret20"] for row in group]),
                "mean40": mean([row["ret40"] for row in group]),
                "sum20": sum(row["ret20"] for row in group),
                "sum40": sum(row["ret40"] for row in group),
            }
        )
    coin_rows.sort(key=lambda item: (-item["sum20"], item["coin"]))
    largest = coin_rows[0] if coin_rows else None

    def marked(predicate) -> list[dict]:
        marked_rows = []
        for row in funded:
            item = dict(row)
            item["_in"] = predicate(row)
            marked_rows.append(item)
        return marked_rows

    if largest is None:
        largest_block = {
            "coin": None,
            "n": 0,
            "sum20": None,
            "share20": None,
            "complement_n": 0,
            "complement_mean20": None,
            "fires": False,
            "sum40": None,
            "share40": None,
            "complement_mean40": None,
        }
    else:
        marked_coin = marked(lambda row: row["coin"] == largest["coin"])
        conc20 = concentration(marked_coin, "ret20")
        conc40 = concentration(marked_coin, "ret40")
        largest_block = {
            "coin": largest["coin"],
            "n": largest["n"],
            "sum20": largest["sum20"],
            "share20": conc20["share"],
            "complement_n": conc20["complement_n"],
            "complement_mean20": conc20["complement_mean"],
            "fires": conc20["fires"],
            "sum40": largest["sum40"],
            "share40": conc40["share"],
            "complement_mean40": conc40["complement_mean"],
        }

    june20 = concentration(marked(lambda row: in_window(row["fill_t"], JUNE_START, JUNE_END)), "ret20")
    june40 = concentration(marked(lambda row: in_window(row["fill_t"], JUNE_START, JUNE_END)), "ret40")
    hype20 = concentration(
        marked(lambda row: row["coin"] == HYPE_COIN and in_window(row["fill_t"], HYPE_START, HYPE_END)),
        "ret20",
    )
    hype40 = concentration(
        marked(lambda row: row["coin"] == HYPE_COIN and in_window(row["fill_t"], HYPE_START, HYPE_END)),
        "ret40",
    )

    months: dict[str, list[dict]] = {}
    for row in funded:
        months.setdefault(month_key(row["fill_t"]), []).append(row)
    month_rows = []
    for name, group in sorted(months.items()):
        month_rows.append(
            {
                "month": name,
                "n": len(group),
                "n_long": sum(1 for row in group if row["direction"] > 0),
                "n_short": sum(1 for row in group if row["direction"] < 0),
                "mean20": mean([row["ret20"] for row in group]),
                "mean40": mean([row["ret40"] for row in group]),
                "sum20": sum(row["ret20"] for row in group),
            }
        )

    fractions = []
    for coin in universe:
        coin_events = [row for row in rows if row["coin"] == coin and row.get("fill_t") is not None]
        fractions.append(position_fraction(coin_events, bars_by_coin.get(coin, [])))

    return {
        "n_rows": len(rows),
        "n_closed_funded": len(funded),
        "n_funding_incomplete": sum(1 for row in rows if row.get("funding_incomplete")),
        "n_open": sum(1 for row in rows if row.get("unresolved") == "open" and row.get("fill_t") is not None),
        "mean20": mean(ret20),
        "mean40": mean(ret40),
        "gross": mean([row["gross"] for row in funded]),
        "funding_drag": mean([row["direction"] * row["rate_sum"] for row in funded]),
        "std20": pstdev(ret20),
        "long": {
            "n": len(longs),
            "mean20": mean([row["ret20"] for row in longs]),
            "mean40": mean([row["ret40"] for row in longs]),
        },
        "short": {
            "n": len(shorts),
            "mean20": mean([row["ret20"] for row in shorts]),
            "mean40": mean([row["ret40"] for row in shorts]),
        },
        "by_coin": coin_rows,
        "by_month": month_rows,
        "drawdown20": max_drawdown([row["ret20"] for row in by_exit]),
        "drawdown40": max_drawdown([row["ret40"] for row in by_exit]),
        "time_in_market": mean(fractions) if fractions else None,
        "largest": largest_block,
        "june": {"20": june20, "40": june40},
        "hype": {"20": hype20, "40": hype40},
    }


def end_state(event: dict) -> tuple[str, str]:
    mean20 = event["mean20"]
    mean40 = event["mean40"]
    if mean20 is None:
        return (
            "Needs more research",
            "The 12-month daily tape produced no closed, fully funded event, so the event-study mean is undefined. That is ambiguous, not a zero.",
        )
    if mean20 <= 0 or event["largest"]["fires"] or event["june"]["20"]["fires"] or event["hype"]["20"]["fires"]:
        reason = []
        if mean20 <= 0:
            reason.append(
                "The event-study mean net return is not positive at 20bps, so the daily break does not survive costs. "
                "The same mean is not positive at 40bps. "
                "The frozen concentration tests do not decide this result, because there is no positive mean for one coin or one episode to explain"
            )
        if event["largest"]["fires"]:
            reason.append(f"the gains sit in {event['largest']['coin']}")
        if event["june"]["20"]["fires"]:
            reason.append("the gains sit in the June 2026 rebound window")
        if event["hype"]["20"]["fires"]:
            reason.append("the gains sit in the HYPE high window")
        return ("Hypothesis rejected", ". ".join(reason) + ".")
    if mean40 is not None and mean40 > 0:
        return (
            "Promising, forward shadow only",
            "The event-study mean is positive at 20bps and at 40bps, and the frozen concentration tests do not fire. Twelve months is still too short for production. No live ENTER.",
        )
    return (
        "Needs more research",
        "The event-study mean is positive at 20bps and is not one coin or one of the two named episodes, but it is not positive at 40bps. The sign depends on the cost. No filter is added to resolve that.",
    )


def fmt(value: float | None, digits: int = 6) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def fmt_share(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1%}"


def render_results(summary: dict) -> str:
    event = summary["event"]
    book = summary["book"]
    state, because = end_state(event)
    tape = summary["tape"]
    universe = summary["universe"]
    lines = [
        "# `daily-trb-50d-v1` results",
        "",
        "Validation. One run of the frozen page `daily-trb-50d-v1.md`. No parameter was changed after this table. `execution_enabled` stays false. The live scan was not changed. No `ENTER_CONTRACT_v1`.",
        "",
        f"Retrieved {summary['retrieved_at']} from `rocket.providers.hyperliquid.fetch_candles` (`candleSnapshot`, interval `1d` only) and public `fundingHistory` on the same HTTP client. No second candle client. No invented 1h price bars.",
        "",
        "## Screening label",
        "",
        "The PR #31 hourly `trb-50d` result is screening only. On the 6.845-month 1h tape that contract's overlapping net return was about +0.0131 at 20bps and +0.0111 at 40bps, funding included, R undefined. That clock was a 4h close and a 1h fill. It is not this validation and it is not mixed into the means below.",
        "",
        "## Tape",
        "",
        f"Request {tape['request_start']} through {tape['retrieved_at']}. BTC returned {tape['btc_bars']} daily bars, first open {tape['btc_first']}, last open {tape['btc_last']}. Completed BTC bars end at {tape['btc_last_completed']}. The last open is still forming and was not used as a signal or as channel history. BTC gaps in the returned series: {tape['btc_gaps']}.",
        "",
        f"Witness prices. BTC session opened {tape['btc_june_open']} low {tape['btc_june_low']}. HYPE session opened {tape['hype_open']} high {tape['hype_high']}. June fills are counted from 2026-06-25T00:00:00Z through 2026-08-31T23:59:59Z. HYPE fills are counted from 2026-09-15T00:00:00Z through 2026-09-29T23:59:59Z, clipped to this tape (last open {tape['hype_window_clipped_through']}).",
        "",
        "## Universe",
        "",
        universe["rule"],
        "",
        f"Listed perps returned by `fetch_perp_markets`: {universe['listed']}. Candle request failed or empty: {universe['failed_n']}. Fewer than 51 completed daily bars: {universe['short_history']}. Eligible names (at least 51 completed bars and at least one later bar with quote notional >= 5,000,000): {universe['eligible_n']}.",
        "",
        "Failed or empty candle requests: " + (", ".join(universe["failed"]) if universe["failed"] else "none") + ".",
        "",
        f"Breaks on a completed close through the prior 50 closes: {summary['breaks']}. Of those, {summary['thin_breaks']} were below the quote-volume floor and are not events. Eligible events: {summary['eligible_events']}. Unresolved fills: {summary['unresolved_fills']}. Still open (fill known, tenth session not printed): {summary['open_events']}.",
        "",
        "## Event study",
        "",
        "Equal-weighted overlapping events. This is the hypothesis. Closed funded events only. Open events and funding-incomplete events are out of the mean and out of the drawdown.",
        "",
        f"Closed funded events: {event['n_closed_funded']}. Funding incomplete: {event['n_funding_incomplete']}. Still open: {event['n_open']}.",
        "",
        "| | Events | Mean net return, 20bps + funding | Mean net return, 40bps + funding |",
        "|---|---:|---:|---:|",
        f"| All | {event['n_closed_funded']} | {fmt(event['mean20'])} | {fmt(event['mean40'])} |",
        f"| Long | {event['long']['n']} | {fmt(event['long']['mean20'])} | {fmt(event['long']['mean40'])} |",
        f"| Short | {event['short']['n']} | {fmt(event['short']['mean20'])} | {fmt(event['short']['mean40'])} |",
        "",
        f"Gross mean before costs and funding: {fmt(event['gross'])}. Mean funding drag (direction times the rate sum): {fmt(event['funding_drag'])}. A funding print is stamped about 50ms after the hour, so the print on the exit hour falls after the exit open and is outside `(fill, exit]`. Standard deviation of the 20bps event returns: {fmt(event['std20'])}. Events overlap, so that deviation is not an independent-sample error.",
        "",
        f"Drawdown of summed unit-notional event returns, ordered by exit: {fmt(event['drawdown20'], 4)} at 20bps, {fmt(event['drawdown40'], 4)} at 40bps. Fraction of opened days in a position, averaged across the {universe['eligible_n']} eligible names: {fmt_share(event['time_in_market'])}.",
        "",
        "### By calendar month of the fill",
        "",
        "| Month | Events | Long | Short | Mean 20bps | Mean 40bps | Sum 20bps |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in event["by_month"]:
        lines.append(
            f"| {row['month']} | {row['n']} | {row['n_long']} | {row['n_short']} | {fmt(row['mean20'])} | {fmt(row['mean40'])} | {fmt(row['sum20'])} |"
        )
    if not event["by_month"]:
        lines.append("| n/a | 0 | 0 | 0 | n/a | n/a | n/a |")
    lines.extend(
        [
            "",
            "### By asset",
            "",
            "Sorted by summed 20bps net return. Share is that sum divided by the event-study total.",
            "",
            "| Coin | Events | Long | Short | Mean 20bps | Mean 40bps | Sum 20bps | Share of sum |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    total_sum = sum(row["sum20"] for row in event["by_coin"])
    for row in event["by_coin"]:
        lines.append(
            f"| {row['coin']} | {row['n']} | {row['n_long']} | {row['n_short']} | {fmt(row['mean20'])} | {fmt(row['mean40'])} | {fmt(row['sum20'])} | {fmt_share(share_of(total_sum, row['sum20']))} |"
        )
    if not event["by_coin"]:
        lines.append("| n/a | 0 | 0 | 0 | n/a | n/a | n/a | n/a |")
    largest = event["largest"]
    june = event["june"]["20"]
    hype = event["hype"]["20"]
    lines.extend(
        [
            "",
            "### Concentration",
            "",
            "Shares use the summed 20bps net return of closed funded events. They do not remove trades from the mean above.",
            "",
            f"Largest coin by summed net return: {largest['coin']}. Sum {fmt(largest['sum20'])}. Share {fmt_share(largest['share20'])}. Complement events {largest['complement_n']}, complement mean {fmt(largest['complement_mean20'])}. Same coin's share at 40bps: {fmt_share(largest.get('share40'))}.",
            "",
            f"June 2026 rebound window, all names, fills 2026-06-25 through 2026-08-31: {june['n']} closed funded events, sum {fmt(june['sum'])}, share {fmt_share(june['share'])}. Complement events {june['complement_n']}, complement mean {fmt(june['complement_mean'])}.",
            "",
            f"HYPE high window, HYPE fills from 2026-09-15 through seven days after 2026-09-22, clipped to the tape: {hype['n']} closed funded events, sum {fmt(hype['sum'])}, share {fmt_share(hype['share'])}. Complement events {hype['complement_n']}, complement mean {fmt(hype['complement_mean'])}. Open HYPE events in that window (not in the mean): {summary['hype_open']}.",
            "",
            "## Per-name book",
            "",
            "Portfolio construction. A new signal in a name is skipped while that name's prior 10-session window is still open. This section is not the event-study mean and is not a claim the signal improved.",
            "",
            f"Taken fills: {summary['book_taken']}. Skipped because the prior window was open: {summary['book_skipped']}. Closed funded: {book['n_closed_funded']}. Funding incomplete: {book['n_funding_incomplete']}. Still open: {book['n_open']}.",
            "",
            "| | Trades | Mean net return, 20bps + funding | Mean net return, 40bps + funding |",
            "|---|---:|---:|---:|",
            f"| All | {book['n_closed_funded']} | {fmt(book['mean20'])} | {fmt(book['mean40'])} |",
            f"| Long | {book['long']['n']} | {fmt(book['long']['mean20'])} | {fmt(book['long']['mean40'])} |",
            f"| Short | {book['short']['n']} | {fmt(book['short']['mean20'])} | {fmt(book['short']['mean40'])} |",
            "",
            f"Drawdown of summed unit-notional book returns, ordered by exit: {fmt(book['drawdown20'], 4)} at 20bps, {fmt(book['drawdown40'], 4)} at 40bps. Fraction of opened days in a position, same eligible-name average: {fmt_share(book['time_in_market'])}.",
            "",
            "### By calendar month of the fill",
            "",
            "| Month | Trades | Long | Short | Mean 20bps | Mean 40bps | Sum 20bps |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in book["by_month"]:
        lines.append(
            f"| {row['month']} | {row['n']} | {row['n_long']} | {row['n_short']} | {fmt(row['mean20'])} | {fmt(row['mean40'])} | {fmt(row['sum20'])} |"
        )
    if not book["by_month"]:
        lines.append("| n/a | 0 | 0 | 0 | n/a | n/a | n/a |")
    lines.extend(
        [
            "",
            "## Reading",
            "",
            because,
            "",
            "Experiments 2 and 3 were not run. 50, 10, the absent band, and the costs were not changed. No filter was added.",
            "",
            state,
            "",
        ]
    )
    return "\n".join(lines)


def fetch_daily(client: httpx.Client, coin: str, start_ms: int, end_ms: int, run_day: str):
    cache = CACHE / f"{coin}_1d_{run_day}.json"
    cached = load_json(cache)
    if isinstance(cached, list):
        return cached
    last_error = "empty"
    for attempt in range(5):
        result = fetch_candles(coin, interval="1d", start_ms=start_ms, end_ms=end_ms, http=client)
        if result.status is OperationalStatus.HEALTHY and result.records:
            rows = [
                [int(row["timestamp_ms"]), row["open"], row["high"], row["low"], row["close"], row["volume"]]
                for row in result.records
            ]
            save_json(cache, rows)
            return rows
        last_error = result.failure_kind or "empty"
        time.sleep(0.6 * (attempt + 1))
    return {"error": last_error}


def fetch_funding(client: httpx.Client, coin: str, start_ms: int, end_ms: int, run_day: str) -> dict[int, float]:
    cache = CACHE / f"{coin}_funding_{run_day}_{start_ms}_{end_ms}.json"
    cached = load_json(cache)
    if isinstance(cached, dict) and "buckets" in cached:
        loaded = {int(key): float(value) for key, value in cached["buckets"].items()}
        # A download that died mid-page is continuous and then stops early.
        # Do not reuse it. A finished download reaches the last hour before the exit.
        if loaded and max(loaded) >= end_ms - HOUR_MS:
            return loaded
    buckets: dict[int, float] = {}
    cursor = start_ms
    pages = 0
    ended_clean = False
    # Ask slightly past the exit open so a print stamped a few milliseconds
    # after an interior hour is not cut off. The sum still stops before the exit.
    request_end = end_ms + HOUR_MS
    while cursor <= end_ms and pages < 40:
        payload = None
        for attempt in range(6):
            try:
                response = client.post(
                    MAINNET_INFO_URL,
                    json={
                        "type": "fundingHistory",
                        "coin": coin,
                        "startTime": int(cursor),
                        "endTime": int(request_end),
                    },
                )
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, list):
                    raise ValueError("fundingHistory payload must be a list")
                payload = body
                break
            except (httpx.HTTPError, ValueError, TypeError):
                payload = None
                time.sleep(0.8 * (attempt + 1))
        pages += 1
        if payload is None:
            break
        if not payload:
            ended_clean = True
            break
        last = int(payload[-1]["time"])
        for row in payload:
            hour = int(row["time"]) // HOUR_MS * HOUR_MS
            buckets[hour] = float(row["fundingRate"])
        reached = max(buckets) >= end_ms - HOUR_MS
        if len(payload) < 500 or reached:
            ended_clean = True
            break
        if last + 1 <= cursor:
            break
        cursor = last + 1
        time.sleep(0.15)
    if buckets and ended_clean:
        save_json(cache, {"buckets": {str(key): value for key, value in buckets.items()}, "pages": pages})
    return buckets


def witness(bars: list[dict], opened: str) -> dict | None:
    for bar in bars:
        if day_key(bar["t"]) == opened:
            return bar
    return None


def gap_count(bars: list[dict]) -> int:
    gaps = 0
    for left, right in zip(bars, bars[1:]):
        if right["t"] - left["t"] != DAY_MS:
            gaps += 1
    return gaps


def build(now: datetime | None = None) -> dict:
    retrieved = now or datetime.now(UTC)
    now_ms = ms(retrieved)
    start = datetime(retrieved.year, retrieved.month, retrieved.day, tzinfo=UTC) - timedelta(days=LOOKBACK_DAYS)
    start_ms = ms(start)
    end_ms = now_ms
    run_day = retrieved.strftime("%Y-%m-%d")
    CACHE.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(timeout=30.0, headers={"User-Agent": "rocket-research"})
    try:
        markets = fetch_perp_markets(http=client, now=retrieved)
        if markets.status is not OperationalStatus.HEALTHY or not markets.records:
            raise RuntimeError(markets.failure_kind or "perp metadata unavailable")
        names = [str(row["name"]) for row in markets.records]
        print(f"listed {len(names)}", flush=True)
        daily: dict[str, list[dict]] = {}
        failed: list[str] = []
        for index, coin in enumerate(names):
            rows = fetch_daily(client, coin, start_ms, end_ms, run_day)
            if isinstance(rows, dict):
                failed.append(f"{coin} ({rows.get('error') or 'empty'})")
                continue
            bars = as_bars(rows)
            if not bars:
                failed.append(f"{coin} (empty)")
                continue
            daily[coin] = bars
            if index % 25 == 0:
                print(f"  candles {index + 1}/{len(names)} {coin}", flush=True)
            time.sleep(0.08)
        if "BTC" not in daily:
            raise RuntimeError("BTC daily tape missing")
        btc = daily["BTC"]
        btc_done = completed_bars(btc, now_ms)
        hype_bars = daily.get("HYPE", [])
        june_bar = witness(btc_done, "2026-06-25")
        hype_bar = witness(completed_bars(hype_bars, now_ms), "2026-09-22")
        if june_bar is None or hype_bar is None:
            raise RuntimeError("witness sessions missing from the daily tape")

        all_events: list[dict] = []
        thin = 0
        breaks_n = 0
        eligible_names: list[str] = []
        short_history = 0
        for coin, bars in daily.items():
            done = completed_bars(bars, now_ms)
            if len(done) < CHANNEL + 1:
                short_history += 1
                continue
            liquid = any(
                done[index]["v"] * done[index]["c"] >= QUOTE_VOLUME_FLOOR for index in range(CHANNEL, len(done))
            )
            if liquid:
                eligible_names.append(coin)
            found = find_breaks(done)
            breaks_n += len(found)
            thin += sum(1 for item in found if not item["eligible"])
            events = attach_prices(found, bars)
            for event in events:
                event["coin"] = coin
            all_events.extend(events)

        need: dict[str, list[dict]] = {}
        for event in all_events:
            if event.get("fill_t") is not None and event.get("exit_t") is not None:
                need.setdefault(event["coin"], []).append(event)
        buckets: dict[str, dict[int, float]] = {}
        for index, (coin, events) in enumerate(sorted(need.items())):
            start_f = min(event["fill_t"] for event in events)
            end_f = max(event["exit_t"] for event in events)
            buckets[coin] = fetch_funding(client, coin, start_f, end_f, run_day)
            if index % 10 == 0:
                print(f"  funding {index + 1}/{len(need)} {coin} hours={len(buckets[coin])}", flush=True)
    finally:
        client.close()

    book_ids = set()
    taken_n = 0
    skipped_n = 0
    by_coin_events: dict[str, list[dict]] = {}
    for event in all_events:
        if event.get("eligible"):
            by_coin_events.setdefault(event["coin"], []).append(event)
    book_events: list[dict] = []
    for coin, events in by_coin_events.items():
        taken = select_book(events)
        taken_n += len(taken)
        skipped_n += sum(1 for event in events if event.get("book") == "skipped" and event.get("fill_t") is not None)
        for event in taken:
            book_ids.add(id(event))
            book_events.append(event)

    scored_event = []
    scored_book = []
    for event in all_events:
        if not event.get("eligible") or event.get("fill_t") is None:
            continue
        coin_buckets = buckets.get(event["coin"], {})
        scored = score_one(event, coin_buckets)
        scored["coin"] = event["coin"]
        scored_event.append(scored)
        if id(event) in book_ids:
            scored_book.append(scored)

    hype_open = sum(
        1
        for event in all_events
        if event.get("coin") == HYPE_COIN
        and event.get("fill_t") is not None
        and event.get("unresolved") == "open"
        and in_window(event["fill_t"], HYPE_START, HYPE_END)
    )
    last_open = btc[-1]["t"]
    summary = {
        "retrieved_at": retrieved.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tape": {
            "request_start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "retrieved_at": retrieved.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "btc_bars": len(btc),
            "btc_first": iso(btc[0]["t"]),
            "btc_last": iso(btc[-1]["t"]),
            "btc_last_completed": iso(btc_done[-1]["t"]) if btc_done else "n/a",
            "btc_gaps": gap_count(btc),
            "btc_june_open": iso(june_bar["t"]),
            "btc_june_low": f"{june_bar['l']:.6g}",
            "hype_open": iso(hype_bar["t"]),
            "hype_high": f"{hype_bar['h']:.6g}",
            "hype_window_clipped_through": iso(min(ms(HYPE_END), last_open)),
        },
        "universe": {
            "listed": len(names),
            "failed_n": len(failed),
            "failed": failed,
            "short_history": short_history,
            "eligible_n": len(eligible_names),
            "rule": (
                "Eligibility is a point-in-time daily quote-volume floor computed from the daily bar: "
                "base volume times close on the signal day at least 5,000,000. "
                "That is the live scan's 24h quote-volume floor applied to the completed signal day, "
                "not today's dayNtlVlm, open interest, spread, or a backward-stamped top 100. "
                "Missing candles, a failed fetch_candles request, or fewer than 51 completed daily bars "
                "are exclusion. Delisted names are absent from metaAndAssetCtxs and were not reconstructed. "
                "fetch_candles uppercases the coin; a name the venue rejects in uppercase is a failed request."
            ),
        },
        "breaks": breaks_n,
        "thin_breaks": thin,
        "eligible_events": sum(1 for event in all_events if event.get("eligible")),
        "unresolved_fills": sum(1 for event in all_events if event.get("unresolved") in {"gap", "no_fill"}),
        "open_events": sum(1 for event in all_events if event.get("unresolved") == "open"),
        "book_taken": taken_n,
        "book_skipped": skipped_n,
        "hype_open": hype_open,
        "event": summarize(scored_event, daily, eligible_names),
        "book": summarize(scored_book, daily, eligible_names),
    }
    return summary


def self_check() -> None:
    def bar(day: int, close: float, volume: float = 100_000.0, open_: float | None = None) -> dict:
        return {
            "t": day * DAY_MS,
            "o": close if open_ is None else open_,
            "h": close,
            "l": close,
            "c": close,
            "v": volume,
        }

    flat = [bar(day, 100.0) for day in range(50)]
    signal = bar(50, 110.0)
    later = []
    for day in range(51, 67):
        later.append(bar(day, 120.0 if day == 55 else 110.0, open_=100.0 + day))
    bars = flat + [signal] + later
    done = completed_bars(bars, 80 * DAY_MS)
    found = find_breaks(done)
    assert len(found) == 2, found
    assert found[0]["direction"] == 1 and found[0]["level"] == 100.0
    assert found[0]["signal_t"] == 50 * DAY_MS
    assert found[1]["signal_t"] == 55 * DAY_MS
    assert found[1]["level"] == 110.0
    equal = find_breaks(completed_bars(flat + [bar(50, 100.0)], 80 * DAY_MS))
    assert equal == []
    short = find_breaks(completed_bars([bar(day, 100.0) for day in range(50)] + [bar(50, 90.0)], 80 * DAY_MS))
    assert len(short) == 1 and short[0]["direction"] == -1 and short[0]["level"] == 100.0
    thin_bars = [bar(day, 100.0) for day in range(50)] + [bar(50, 110.0, volume=1.0)]
    thin = find_breaks(completed_bars(thin_bars, 80 * DAY_MS))
    assert len(thin) == 1 and thin[0]["eligible"] is False
    poke = [bar(day, 100.0) for day in range(50)] + [bar(50, 100.0 * 1.0000001)]
    assert find_breaks(completed_bars(poke, 80 * DAY_MS))[0]["direction"] == 1

    events = attach_prices(found, bars)
    assert events[0]["fill_t"] == 51 * DAY_MS
    assert events[0]["exit_t"] == 61 * DAY_MS
    gapped = [bar for bar in bars if bar["t"] != 51 * DAY_MS]
    unresolved = attach_prices(found[:1], gapped)
    assert unresolved[0]["fill_t"] is None and unresolved[0]["unresolved"] == "gap"

    taken = select_book(events)
    assert [event["fill_t"] for event in taken] == [51 * DAY_MS]
    assert events[1]["book"] == "skipped"
    # A fill exactly at the prior exit is allowed.
    events[1]["fill_t"] = events[0]["exit_t"]
    events[1]["book"] = None
    retaken = select_book(events)
    assert len(retaken) == 2

    rates = {hour: 0.0001 for hour in range(51 * DAY_MS + HOUR_MS, 61 * DAY_MS, HOUR_MS)}
    rate_sum = funding_rate_sum(rates, 51 * DAY_MS, 61 * DAY_MS)
    assert rate_sum is not None and abs(rate_sum - 0.0001 * 239) < 1e-9
    assert funding_rate_sum({}, 51 * DAY_MS, 61 * DAY_MS) is None
    # The print on the exit hour is after the exit open, so its absence is not a gap.
    assert funding_rate_sum(rates, 51 * DAY_MS, 61 * DAY_MS) is not None
    entry = events[0]["fill"]
    exit_px = events[0]["exit"]
    gross = (exit_px - entry) / entry
    assert abs(net_return(1, entry, exit_px, 20, rate_sum) - (gross - 0.002 - rate_sum)) < 1e-12
    assert abs(net_return(1, entry, exit_px, 40, 0.0) - (gross - 0.004)) < 1e-12
    assert abs(net_return(-1, 100.0, 90.0, 20, 0.0) - (0.10 - 0.002)) < 1e-12

    forming = [bar(day, 100.0) for day in range(51)]
    now = 51 * DAY_MS + 12 * HOUR_MS
    assert completed_bars(forming, now)[-1]["t"] == 50 * DAY_MS
    print("self_check ok", flush=True)


def write_blocker(message: str) -> None:
    text = "\n".join(
        [
            "# `daily-trb-50d-v1` results",
            "",
            "Validation did not produce a table. No numbers were invented.",
            "",
            "## Blocker",
            "",
            message,
            "",
            "The PR #31 hourly `trb-50d` result stays screening only. It is not a substitute for this run.",
            "",
            "`execution_enabled` stays false. No `ENTER_CONTRACT_v1`.",
            "",
        ]
    )
    RESULTS_PATH.write_text(text, encoding="utf-8")


def main(argv: list[str]) -> int:
    self_check()
    if "--check" in argv:
        return 0
    summary_path = CACHE / "summary.json"
    if "--from-summary" in argv:
        summary = load_json(summary_path)
        if not isinstance(summary, dict) or "event" not in summary:
            write_blocker("Summary JSON from the validation run is missing. The tape was not re-fetched and no numbers were invented.")
            return 2
    else:
        try:
            summary = build()
        except Exception as exc:  # noqa: BLE001 — surface the tape blocker, do not invent PnL
            traceback.print_exc()
            write_blocker(f"The daily tape or funding history could not be scored: {type(exc).__name__}: {exc}")
            return 2
        save_json(summary_path, summary)
    RESULTS_PATH.write_text(render_results(summary), encoding="utf-8")
    event = summary["event"]
    print(
        f"event mean20={event['mean20']} mean40={event['mean40']} n={event['n_closed_funded']}",
        flush=True,
    )
    print(end_state(event)[0], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
