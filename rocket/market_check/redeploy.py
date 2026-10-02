"""Buy-the-low gate. One definition, shared by the score, the book, and the report."""

from __future__ import annotations

from rocket.market_check.calendar import events_on
from rocket.market_check.config import Config
from rocket.market_check.mathutil import level_change, pct_change
from rocket.market_check.panel import AsOfView


def is_bottom(view: AsOfView, config: Config) -> bool:
    """VIX has fallen off a spike while the index is still in a deep drawdown.

    The March 2025 fade happened only about 8-10% under the high and then failed.
    The April low was still about 12% down when the spike first faded. Credit
    tightening lagged that low by weeks, so it is not part of the entry.
    """
    rules = config.redeploy
    vix = view.closes("vix")
    if len(vix) < rules.spike_lookback:
        return False
    if max(vix[-rules.spike_lookback :]) < rules.vix_spike:
        return False
    fade = level_change(vix, rules.vix_fade_sessions)
    if fade is None or fade >= 0:
        return False
    spy = view.closes("spy")
    if len(spy) < 20:
        return False
    peak = max(spy[-rules.peak_lookback :])
    if peak <= 0 or spy[-1] / peak - 1 > -rules.spy_drawdown:
        return False
    if "fomc" in events_on(view.day, config):
        return False
    oil = pct_change(view.closes("wti"), config.regime.stress.oil_sessions)
    if oil is not None and oil >= config.oil.shock_return:
        return False
    return not (config.model.version == "v6" and not _broad_bounce(view, config))


def _broad_bounce(view: AsOfView, config: Config) -> bool:
    """v6 only: a durable low bounces broadly, not in one or two names.

    Economic reason: participation. A VIX fade with only narrow leadership
    (e.g. the March 2025 fade) fails; the April 2025 low bounced across the
    book. Fixed majority of the 7 core names with a positive 5-session
    return — a fixed structural definition, not a tuned threshold.
    """
    bouncing = 0
    for name in config.portfolio.core:
        rebound = pct_change(view.closes(name), config.redeploy.rebound_sessions)
        if rebound is not None and rebound > 0:
            bouncing += 1
    return bouncing >= (len(config.portfolio.core) // 2 + 1)


def name_state(view: AsOfView, name: str, config: Config) -> tuple[float, float] | None:
    """Drawdown from the trailing high, and the short rebound return."""
    closes = view.closes(name, config.redeploy.peak_lookback)
    if len(closes) < 20 or closes[-1] <= 0:
        return None
    peak = max(closes)
    if peak <= 0:
        return None
    rebound = pct_change(closes, config.redeploy.rebound_sessions)
    if rebound is None:
        return None
    return closes[-1] / peak - 1, rebound


def redeploy_picks(view: AsOfView, config: Config) -> list[tuple[str, str, float]]:
    """One quality name and one high-beta name: the deepest drawdown that has started to bounce."""
    rules = config.redeploy
    chosen = []
    for sleeve, names in (("quality", rules.quality), ("high_beta", rules.high_beta)):
        ranked = []
        for name in names:
            state = name_state(view, name, config)
            if state is None:
                continue
            drawdown, rebound = state
            if drawdown > -rules.name_drawdown or rebound < 0:
                continue
            price = view.value(name)
            if price is None or price <= 0:
                continue
            ranked.append((drawdown, name, price))
        if ranked:
            drawdown, name, price = min(ranked)
            chosen.append((sleeve, name, price))
    return chosen
