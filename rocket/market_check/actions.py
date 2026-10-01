"""Per-consumer actions from a scored day. Research output, not an order."""

from __future__ import annotations

from datetime import date
from typing import Any

from rocket.market_check.calendar import upcoming
from rocket.market_check.config import Config, CurrentBook
from rocket.market_check.panel import SeriesPanel
from rocket.market_check.redeploy import redeploy_picks
from rocket.market_check.rules import (
    add_blockers,
    bounce_threshold,
    cash_target,
    in_bottom_half,
    range_bounds,
    session_return,
    trailing_bounce,
    trim_allowed,
    trim_fraction,
)
from rocket.market_check.score import score_asof


def _options_state(dvol: float | None, config: Config) -> str:
    if dvol is None:
        return "unknown"
    if dvol < config.crypto.dvol_cheap_max:
        return "cheap"
    if dvol > config.crypto.dvol_expensive_min:
        return "expensive"
    return "fair"


def _perps(score: dict[str, Any], config: Config) -> dict[str, Any]:
    crypto = score["pillars"]["crypto"]
    price = crypto.get("price")
    fast = crypto.get("fast")
    slow = crypto.get("slow")
    regime = score["regime"]
    direction, size = "flat", 0.0
    if price is not None and slow is not None and regime == "risk-on" and price > slow:
        direction = "long"
        size = config.derivatives.long_size if fast is not None and price >= fast else config.derivatives.long_size_below_fast
    elif price is not None and fast is not None and regime == "risk-off" and price < fast:
        direction = "short"
        size = config.derivatives.short_size
    elif price is not None and slow is not None and regime == "risk-off" and price < slow:
        direction = "short"
        size = config.derivatives.short_size_below_slow_only
    options = _options_state(crypto.get("dvol"), config)
    event_rows = upcoming(
        date.fromisoformat(score["date"]), config, config.derivatives.cheap_vol_event_days,
    )
    near_event = bool(event_rows)
    hedge_signal = regime == "risk-off" or (options == "cheap" and near_event)
    suppressed = direction == "short" and not config.derivatives.put_with_short
    hedge = "btc_puts" if hedge_signal and not suppressed else "none"
    note = "BTC perp sized by regime and the 50/200-session trend. Caution is flat."
    if hedge == "btc_puts":
        note += (
            f" Put overlay: about {config.derivatives.put_tenor_days} days, "
            f"{config.derivatives.put_otm:.0%} out of the money."
        )
    elif suppressed and hedge_signal:
        note += " Put signal is on, and it is suppressed because the perp is already short."
    return {
        "direction": direction,
        "size": size,
        "options": options,
        "dvol": crypto.get("dvol"),
        "hedge_signal": hedge_signal,
        "hedge": hedge,
        "hedge_events": event_rows,
        "stop": config.derivatives.stop,
        "note": note,
    }


def _book_weights(book: dict[str, float] | None, config: Config, asof: date) -> tuple[dict[str, float], str]:
    if book is not None:
        return dict(book), "caller"
    snap = config.current_book
    if asof >= snap.as_of and snap.weights:
        return dict(snap.weights), "snapshot"
    cash = config.portfolio.initial_cash
    names = config.portfolio.core
    weight = (1 - cash) / len(names) if names else 0
    model = {name: weight for name in names}
    model["USDC"] = cash
    return model, "model"


def _cash_weight(weights: dict[str, float]) -> float:
    for key in ("USDC", "USD", "cash"):
        if key in weights:
            return float(weights[key])
    return 0.0


def decide(
    panel: SeriesPanel,
    day: date,
    config: Config,
    *,
    book: dict[str, float] | None = None,
    regular_hours: bool | None = None,
    score: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if score is None:
        score = score_asof(panel, day, config)
    view = panel.asof(day, config.lags)
    hours = config.portfolio.assume_regular_hours if regular_hours is None else regular_hours
    index_return = session_return(view, "spy")
    index_bounce = trailing_bounce(view, "spy", config.windows.index_bounce_lookback)
    bottom = bool(score.get("bottom"))
    released = bool(score.get("released"))
    version = config.model.version
    holding = (version == "v3" and (bottom or released)) or (
        version in {"v4", "v5", "v6"} and bool(score.get("redeploy_hold"))
    )
    if holding:
        target = config.redeploy.cash_target
    elif version in {"v4", "v5", "v6"} and score["regime"] == "caution":
        target = config.model.v4_light_cash
    else:
        target = cash_target(score["regime"], index_return, config)
    weights, book_basis = _book_weights(book, config, day)
    held = {name for name, weight in weights.items() if name not in {"USDC", "USD", "cash"} and weight > 0}
    trims = []
    for name in config.portfolio.sale_order:
        if name not in held and book_basis == "caller":
            continue
        if book_basis != "caller" and name not in held:
            continue
        name_return = session_return(view, name)
        bounce = trailing_bounce(view, name, config.windows.soft_patch)
        allowed, detail = trim_allowed(
            name=name,
            name_return=name_return,
            bounce=bounce,
            index_return=index_return,
            index_bounce=index_bounce,
            regular_hours=hours,
            config=config,
        )
        if holding:
            allowed = False
            detail = {**detail, "reason": "buy_the_low_release"}
        trims.append({
            "ticker": name,
            "allowed": allowed,
            "fraction_cap": trim_fraction(name, config),
            "bounce": bounce,
            "bounce_threshold": bounce_threshold(name, config),
            "day_return": name_return,
            "bounce_gate": detail["bounce"],
            "index_strength": detail["index_strength"],
            "regular_hours": detail["regular_hours"],
            "reason": detail["reason"],
        })
    blockers = add_blockers(
        regime=score["regime"], oil_shock=bool(score["oil_shock"]), events_today=list(score["events_today"]),
    )
    adds = []
    for name in config.portfolio.add_names:
        bounds = range_bounds(view, name, config.windows.range_lookback)
        price = view.value(name)
        if bounds is None or price is None:
            adds.append({"ticker": name, "in_bottom_half": False, "status": "no_history"})
            continue
        low, high = bounds
        inside = in_bottom_half(price, low, high, config.portfolio.buy_zone_fraction)
        adds.append({
            "ticker": name,
            "price": price,
            "in_bottom_half": inside,
            "permitted": inside and not blockers,
            "blockers": list(blockers),
            "status": "bottom_half" if inside else "outside",
        })
    picks = redeploy_picks(view, config) if bottom else []
    cash = _cash_weight(weights)
    trim_hits = [row for row in trims if row["allowed"]]
    add_hits = [row for row in adds if row.get("permitted")]
    tol = config.portfolio.cash_tolerance
    if score["regime"] == "unknown":
        action = "hold"
        reason = "regime_unknown"
    elif cash < target - tol and trim_hits:
        action = "trim"
        reason = "cash_below_target"
    elif cash < target - tol and not trim_hits:
        action = "hold"
        reason = "cash_below_target_but_trim_blocked"
    elif cash > target + tol and add_hits:
        action = "add"
        reason = "dry_powder_above_target"
    else:
        action = "hold"
        reason = "inside_cash_band"
    shift = 0.0
    stance = "keep"
    if score["regime"] == "risk-on":
        shift = config.phillip.raise_risk_on
        stance = "raise"
    elif score["regime"] == "risk-off":
        shift = -config.phillip.lower_risk_off
        stance = "lower"
    phillip_rows = []
    for name in config.phillip.names:
        # Phillip bands use the Phillip zone fraction via _zone_row's raw_high path.
        row = _phillip_row(view, name, config, shift)
        if row is None:
            phillip_rows.append({"ticker": name, "status": "no_history"})
        else:
            phillip_rows.append(row)
    ranked = sorted(
        (row for row in phillip_rows if row.get("distance") is not None),
        key=lambda item: item["distance"],
    )
    perps = _perps(score, config)
    return {
        "date": day.isoformat(),
        "regime": score["regime"],
        "score": score["score"],
        "stress": score.get("stress"),
        "stress_parts": score.get("stress_parts") or {},
        "pillars": score["pillars"],
        "oil_shock": score["oil_shock"],
        "events_today": score["events_today"],
        "events_upcoming": score["events_upcoming"],
        "regime_rule": score["regime_rule"],
        "perps": perps,
        "porto": {
            "action": action,
            "reason": reason,
            "cash_target": target,
            "cash_weight": cash,
            "cash_band": [config.portfolio.cash_risk_on, config.portfolio.cash_ceiling],
            "book_basis": book_basis,
            "adds_permitted": not blockers,
            "add_blockers": blockers,
            "add_candidates": adds,
            "trim_candidates": trims,
            "redeploy": [
                {"sleeve": sleeve, "ticker": name, "price": price} for sleeve, name, price in picks
            ],
            "rules": (
                "Long-only USDC book. Cash target is 35/40/42/45 percent for risk-on, neutral, caution and "
                "risk-off, and steps up on an up index day, capped at 45. Adds are only the watch names in "
                "the bottom half of the trailing buy zone, and never in caution or risk-off, on an FOMC "
                "decision day, or on an oil shock. "
                "Trims follow the sale order and need two of three gates, and never sell a name that is down "
                "or any name on a hard-down index day."
            ),
        },
        "phillip": {
            "band_stance": stance,
            "band_shift": shift,
            "closest": ranked[: config.phillip.closest_count],
            "names": phillip_rows,
            "note": (
                "Phillip's private buy bands are not in this repo. Bands are the bottom "
                f"{config.phillip.zone_fraction:.0%} of the trailing {config.windows.range_lookback}-session range, "
                "raised in risk-on and lowered in risk-off. Caution keeps the band."
            ),
        },
    }


def _phillip_row(view, name: str, config: Config, shift: float) -> dict[str, Any] | None:
    bounds = range_bounds(view, name, config.windows.range_lookback)
    price_row = view.latest(name)
    if bounds is None or price_row is None:
        return None
    low, high = bounds
    raw_high = low + config.phillip.zone_fraction * (high - low)
    zone_low = low * (1 + shift)
    zone_high = raw_high * (1 + shift)
    width = zone_high - zone_low
    price = price_row[1]
    distance = None if width <= 0 else (price - zone_low) / width
    bottom = in_bottom_half(price, low, high, config.phillip.zone_fraction)
    return {
        "ticker": name,
        "status": "ok",
        "price": price,
        "price_date": price_row[0].isoformat(),
        "zone_low": zone_low,
        "zone_high": zone_high,
        "in_bottom_half": bottom,
        "distance": distance,
    }


def fingerprint(decision: dict[str, Any]) -> dict[str, Any]:
    closest = decision["phillip"]["closest"]
    perps = decision["perps"]
    porto = decision["porto"]
    return {
        "regime": decision["regime"],
        "perps_direction": perps["direction"],
        "perps_size": perps["size"],
        "perps_options": perps["options"],
        "perps_hedge": perps["hedge"],
        "porto_action": porto["action"],
        "porto_cash_target": porto["cash_target"],
        "phillip_band_stance": decision["phillip"]["band_stance"],
        "phillip_closest": closest[0]["ticker"] if closest else "",
    }


def changed_against(today: dict[str, Any], yesterday: dict[str, Any] | None) -> dict[str, Any]:
    current = fingerprint(today)
    if yesterday is None:
        return {
            "changed": True,
            "reason": "no_prior_session",
            "changed_fields": sorted(current),
            "today": current,
            "yesterday": None,
        }
    previous = fingerprint(yesterday)
    fields = [key for key in current if current[key] != previous[key]]
    return {
        "changed": bool(fields),
        "reason": "action_changed" if fields else "unchanged",
        "changed_fields": fields,
        "today": current,
        "yesterday": previous,
    }


def snapshot_book(book: CurrentBook) -> dict[str, Any]:
    return {
        "as_of": book.as_of.isoformat(),
        "nav_usd": book.nav_usd,
        "weights": book.weights,
        "trades": [
            {"date": item.date.isoformat(), "ticker": item.ticker, "side": item.side, "note": item.note}
            for item in book.trades
        ],
        "note": book.note,
    }
