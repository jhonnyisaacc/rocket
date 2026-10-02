"""Shared Porto gates. The daily check and the backtest both call these."""

from __future__ import annotations

from datetime import date

from rocket.market_check.config import Config
from rocket.market_check.mathutil import min_close, pct_change
from rocket.market_check.panel import AsOfView


def session_return(view: AsOfView, name: str) -> float | None:
    return pct_change(view.closes(name), 1)


def trailing_bounce(view: AsOfView, name: str, window: int) -> float | None:
    closes = view.closes(name, window)
    trough = min_close(closes, window)
    if not closes or trough in (None, 0):
        return None
    return closes[-1] / trough - 1


def range_bounds(view: AsOfView, name: str, window: int) -> tuple[float, float] | None:
    closes = view.closes(name, window)
    if len(closes) < max(20, window // 5):
        return None
    low, high = min(closes), max(closes)
    if high <= 0:
        return None
    return low, high


def buy_zone(low: float, high: float, fraction: float) -> tuple[float, float, float]:
    """Return zone low, zone high, and the bottom-half ceiling."""
    zone_high = low + fraction * (high - low)
    midpoint = low + 0.5 * (zone_high - low)
    return low, zone_high, midpoint


def in_bottom_half(price: float, low: float, high: float, fraction: float) -> bool:
    _, _, midpoint = buy_zone(low, high, fraction)
    return price <= midpoint


def holding_cash_target(config: Config) -> float:
    """Cash target while holding redeployed shares. v6 holds less cash
    (30%) so tranches deploy more fully; older versions keep 35%."""
    if config.model.version == "v6":
        return config.model.v6_hold_cash
    return config.redeploy.cash_target


def cash_target(regime: str, index_return: float | None, config: Config) -> float:
    base = {
        "risk-on": config.portfolio.cash_risk_on,
        "neutral": config.portfolio.cash_neutral,
        "caution": config.portfolio.cash_caution,
        "risk-off": config.portfolio.cash_risk_off,
    }.get(regime, config.portfolio.cash_neutral)
    if index_return is not None and index_return > 0:
        base = min(config.portfolio.cash_ceiling, base + config.portfolio.cash_strength_bump)
    return base


def index_is_hard_down(index_return: float | None, config: Config) -> bool:
    return index_return is not None and index_return <= config.portfolio.hard_down_return


def index_strength(index_return: float | None, index_bounce: float | None, config: Config) -> bool:
    """Gate II: the index is up today, or bouncing off its short low and not hard-down."""
    if index_return is not None and index_return >= 0:
        return True
    if index_is_hard_down(index_return, config):
        return False
    return index_bounce is not None and index_bounce >= config.portfolio.index_bounce_min


def bounce_threshold(name: str, config: Config) -> float:
    if name in config.portfolio.megacaps:
        return config.portfolio.megacap_bounce
    return config.portfolio.cyclical_bounce


def trim_fraction(name: str, config: Config) -> float:
    if name in config.portfolio.half_names:
        return config.portfolio.half_trim
    if name in config.portfolio.light_names:
        return config.portfolio.light_trim
    return 1.0


def trim_allowed(
    *,
    name: str,
    name_return: float | None,
    bounce: float | None,
    index_return: float | None,
    index_bounce: float | None,
    regular_hours: bool,
    config: Config,
) -> tuple[bool, dict[str, bool | str]]:
    """2 of 3 gates, plus the hard blocks: no selling a red name, no selling a hard-down index."""
    gate_i = bounce is not None and bounce >= bounce_threshold(name, config)
    gate_ii = index_strength(index_return, index_bounce, config)
    gate_iii = regular_hours
    detail: dict[str, bool | str] = {
        "bounce": gate_i,
        "index_strength": gate_ii,
        "regular_hours": gate_iii,
        "name_red": name_return is not None and name_return < 0,
        "index_hard_down": index_is_hard_down(index_return, config),
    }
    if name_return is None:
        return False, {**detail, "reason": "no_price"}
    if detail["name_red"]:
        return False, {**detail, "reason": "name_red"}
    if detail["index_hard_down"]:
        return False, {**detail, "reason": "index_hard_down"}
    if sum(bool(detail[key]) for key in ("bounce", "index_strength", "regular_hours")) < 2:
        return False, {**detail, "reason": "gates"}
    return True, {**detail, "reason": "ok"}


def add_blockers(*, regime: str, oil_shock: bool, events_today: list[str]) -> list[str]:
    """Book-level add blocks. The buy-zone test is applied per name."""
    blockers = []
    if regime == "risk-off":
        blockers.append("risk_off")
    if regime == "caution":
        blockers.append("caution")
    if regime == "unknown":
        blockers.append("regime_unknown")
    if oil_shock:
        blockers.append("oil_shock")
    if "fomc" in events_today:
        blockers.append("fomc")
    return blockers


def plan_trims(
    shares: dict[str, float],
    prices: dict[str, float],
    cash: float,
    nav: float,
    target: float,
    allowed: set[str],
    config: Config,
) -> list[tuple[str, float]]:
    """Sale order, capped by the name's fraction, stopping once cash would reach the target."""
    need = target * nav - cash
    if need <= 1e-8:
        return []
    plans: list[tuple[str, float]] = []
    for name in config.portfolio.sale_order:
        if name not in allowed or need <= 1e-8:
            continue
        held = shares.get(name, 0.0)
        price = prices.get(name)
        if held <= 0 or price is None or price <= 0:
            continue
        cap = trim_fraction(name, config)
        full = held * cap * price
        fraction = cap if full <= need else need / (held * price)
        if fraction <= 1e-8:
            continue
        plans.append((name, fraction))
        need -= held * fraction * price
    return plans


def last_add_gap(previous: date | None, day: date, minimum: int) -> bool:
    if previous is None:
        return True
    return (day - previous).days >= minimum
