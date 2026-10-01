"""Load the single market-check parameter file."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from rocket.config import PACKAGE_ROOT, load_toml

DEFAULT_PATH = PACKAGE_ROOT / "config" / "market_check.toml"


def _date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _dates(values: Any) -> tuple[date, ...]:
    return tuple(_date(item) for item in values or ())


def _floats(mapping: Any) -> dict[str, float]:
    return {str(key): float(value) for key, value in dict(mapping or {}).items()}


def _strings(values: Any) -> tuple[str, ...]:
    return tuple(str(item) for item in values or ())


@dataclass(frozen=True)
class Window:
    start: date
    end: date
    oos_start: date
    ondo_live: date
    warmup_start: date


@dataclass(frozen=True)
class Windows:
    trend: int
    shock: int
    rv: int
    sma_fast: int
    sma_slow: int
    funding_days: int
    range_lookback: int
    soft_patch: int
    index_bounce_lookback: int


@dataclass(frozen=True)
class Rollup:
    green_min: float
    red_max: float


@dataclass(frozen=True)
class Stress:
    """Rate-of-change stress points and the hysteresis bands around them."""

    vix_jump_sessions: int
    vix_jump_caution: float
    vix_jump_risk: float
    vix_level_caution: float
    vix_level_risk: float
    vix_cap: int
    credit_sessions: int
    credit_widen_caution: float
    credit_widen_risk: float
    yield_sessions: int
    yield_caution: float
    yield_risk: float
    yield_breakout_sessions: int
    yield_breakout_min_change: float
    yield_cap: int
    oil_sessions: int
    oil_caution: float
    oil_risk: float
    btc_roc_sessions: int
    btc_roc_caution: float
    btc_roc_risk: float
    btc_dd_sessions: int
    btc_dd_caution: float
    btc_dd_risk: float
    btc_cap: int
    enter_risk_off: float
    exit_risk_off: float
    enter_caution: float
    exit_caution: float
    spy_drawdown: float
    btc_drawdown: float
    lead_sessions: int


@dataclass(frozen=True)
class Regime:
    risk_on_min: float
    min_pillars: int
    weights: dict[str, float]
    stress: Stress


@dataclass(frozen=True)
class Rates:
    yield_10y_green_max: float
    yield_10y_red_min: float
    yield_30y_green_max: float
    yield_30y_red_min: float
    trend_abs: float
    curve_invert_red: float
    curve_stress_red: float
    curve_healthy_max: float
    hike_spread_red: float
    cut_spread_green: float


@dataclass(frozen=True)
class Oil:
    wti_green_max: float
    wti_red_min: float
    brent_green_max: float
    brent_red_min: float
    momentum_red: float
    momentum_green: float
    shock_return: float


@dataclass(frozen=True)
class Volatility:
    vix_green_max: float
    vix_red_min: float
    tlt_rv_green_max: float
    tlt_rv_red_min: float


@dataclass(frozen=True)
class Credit:
    hy_green_max: float
    hy_red_min: float
    hy_widen_red: float
    hy_tighten_green: float
    hyg_lqd_red: float
    hyg_lqd_green: float


@dataclass(frozen=True)
class DollarGold:
    dxy_trend_red: float
    dxy_trend_green: float
    gold_stress: float


@dataclass(frozen=True)
class CryptoThresholds:
    dvol_cheap_max: float
    dvol_expensive_min: float
    funding_hot: float
    funding_cold: float
    funding_panic: float


@dataclass(frozen=True)
class Portfolio:
    cash_risk_on: float
    cash_neutral: float
    cash_caution: float
    cash_risk_off: float
    cash_strength_bump: float
    cash_ceiling: float
    cash_tolerance: float
    initial_cash: float
    megacap_bounce: float
    cyclical_bounce: float
    hard_down_return: float
    index_bounce_min: float
    half_trim: float
    light_trim: float
    tranche_nav: float
    min_days_between_adds: int
    assume_regular_hours: bool
    core: tuple[str, ...]
    megacaps: tuple[str, ...]
    cyclicals: tuple[str, ...]
    sale_order: tuple[str, ...]
    half_names: tuple[str, ...]
    light_names: tuple[str, ...]
    add_names: tuple[str, ...]
    buy_zone_fraction: float

    @property
    def universe(self) -> tuple[str, ...]:
        seen: list[str] = []
        for name in (*self.core, *self.add_names):
            if name not in seen:
                seen.append(name)
        return tuple(seen)


@dataclass(frozen=True)
class Costs:
    equity_slippage_bps: float
    perp_fee_bps: float
    perp_slippage_bps: float
    option_fee_bps_underlying: float
    option_iv_slippage: float


@dataclass(frozen=True)
class Derivatives:
    stop: float
    long_size: float
    long_size_below_fast: float
    short_size: float
    short_size_below_slow_only: float
    put_otm: float
    put_tenor_days: int
    cheap_vol_event_days: int
    put_with_short: bool
    fallback_rate: float


@dataclass(frozen=True)
class Phillip:
    names: tuple[str, ...]
    zone_fraction: float
    raise_risk_on: float
    lower_risk_off: float
    closest_count: int


@dataclass(frozen=True)
class Events:
    horizon_days: int
    fomc: tuple[date, ...]


@dataclass(frozen=True)
class ScorecardCfg:
    within_days: int


@dataclass(frozen=True)
class LoggedTrade:
    date: date
    ticker: str
    side: str
    note: str


@dataclass(frozen=True)
class CurrentBook:
    as_of: date
    nav_usd: float
    note: str
    weights: dict[str, float]
    trades: tuple[LoggedTrade, ...]


@dataclass(frozen=True)
class Model:
    version: str
    v1_risk_off_max: float


@dataclass(frozen=True)
class Redeploy:
    spy_drawdown: float
    vix_spike: float
    vix_fade_sessions: int
    spike_lookback: int
    peak_lookback: int
    name_drawdown: float
    rebound_sessions: int
    tranches: int
    gap_days: int
    episode_gap_days: int
    cash_target: float
    btc_drawdown: float
    hold_sessions: int
    quality: tuple[str, ...]
    high_beta: tuple[str, ...]


@dataclass(frozen=True)
class Config:
    window: Window
    windows: Windows
    rollup: Rollup
    regime: Regime
    lags: dict[str, int]
    rates: Rates
    oil: Oil
    volatility: Volatility
    credit: Credit
    dollar_gold: DollarGold
    crypto: CryptoThresholds
    portfolio: Portfolio
    costs: Costs
    derivatives: Derivatives
    phillip: Phillip
    events: Events
    scorecard: ScorecardCfg
    current_book: CurrentBook
    model: Model
    redeploy: Redeploy

    def lag(self, series: str) -> int:
        return int(self.lags.get(series, 0))


def _stress(raw: dict[str, Any]) -> Stress:
    integers = {
        "vix_jump_sessions", "vix_cap", "credit_sessions", "yield_sessions",
        "yield_breakout_sessions", "yield_cap", "oil_sessions", "btc_roc_sessions",
        "btc_dd_sessions", "btc_cap", "lead_sessions",
    }
    values: dict[str, Any] = {}
    for key in Stress.__dataclass_fields__:
        if key not in raw:
            raise ValueError(f"regime.stress is missing {key}")
        values[key] = int(raw[key]) if key in integers else float(raw[key])
    return Stress(**values)


def _section(raw: dict[str, Any], name: str) -> dict[str, Any]:
    value = raw.get(name) or {}
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a table")
    return value


def load_config(path: Path | None = None) -> Config:
    """Read config/market_check.toml. Thresholds live there, not in code."""
    raw = load_toml(path or DEFAULT_PATH)
    window = _section(raw, "window")
    windows = _section(raw, "windows")
    rollup = _section(raw, "rollup")
    regime = _section(raw, "regime")
    pillars = raw.get("pillars") or {}
    rates = pillars.get("rates") or {}
    oil = pillars.get("oil") or {}
    volatility = pillars.get("volatility") or {}
    credit = pillars.get("credit") or {}
    dollar_gold = pillars.get("dollar_gold") or {}
    crypto = pillars.get("crypto") or {}
    portfolio = _section(raw, "portfolio")
    costs = _section(raw, "costs")
    derivatives = _section(raw, "derivatives")
    phillip = _section(raw, "phillip")
    events = _section(raw, "events")
    scorecard = _section(raw, "scorecard")
    book = _section(raw, "current_book")
    model = _section(raw, "model")
    redeploy = _section(raw, "redeploy")
    trades = tuple(
        LoggedTrade(_date(item["date"]), str(item["ticker"]), str(item["side"]), str(item.get("note") or ""))
        for item in book.get("trades") or []
    )
    cfg = Config(
        window=Window(
            _date(window["start"]), _date(window["end"]), _date(window["oos_start"]),
            _date(window["ondo_live"]), _date(window["warmup_start"]),
        ),
        windows=Windows(
            int(windows["trend"]), int(windows["shock"]), int(windows["rv"]),
            int(windows["sma_fast"]), int(windows["sma_slow"]), int(windows["funding_days"]),
            int(windows["range_lookback"]), int(windows["soft_patch"]),
            int(windows["index_bounce_lookback"]),
        ),
        rollup=Rollup(float(rollup["green_min"]), float(rollup["red_max"])),
        regime=Regime(
            float(regime["risk_on_min"]), int(regime["min_pillars"]),
            _floats(regime.get("weights")), _stress(_section(regime, "stress")),
        ),
        lags={str(key): int(value) for key, value in dict(raw.get("lags_calendar_days") or {}).items()},
        rates=Rates(**{key: float(rates[key]) for key in (
            "yield_10y_green_max", "yield_10y_red_min", "yield_30y_green_max", "yield_30y_red_min",
            "trend_abs", "curve_invert_red", "curve_stress_red", "curve_healthy_max",
            "hike_spread_red", "cut_spread_green",
        )}),
        oil=Oil(**{key: float(oil[key]) for key in (
            "wti_green_max", "wti_red_min", "brent_green_max", "brent_red_min",
            "momentum_red", "momentum_green", "shock_return",
        )}),
        volatility=Volatility(**{key: float(volatility[key]) for key in (
            "vix_green_max", "vix_red_min", "tlt_rv_green_max", "tlt_rv_red_min",
        )}),
        credit=Credit(**{key: float(credit[key]) for key in (
            "hy_green_max", "hy_red_min", "hy_widen_red", "hy_tighten_green",
            "hyg_lqd_red", "hyg_lqd_green",
        )}),
        dollar_gold=DollarGold(**{key: float(dollar_gold[key]) for key in (
            "dxy_trend_red", "dxy_trend_green", "gold_stress",
        )}),
        crypto=CryptoThresholds(**{key: float(crypto[key]) for key in (
            "dvol_cheap_max", "dvol_expensive_min", "funding_hot", "funding_cold", "funding_panic",
        )}),
        portfolio=Portfolio(
            cash_risk_on=float(portfolio["cash_risk_on"]),
            cash_neutral=float(portfolio["cash_neutral"]),
            cash_caution=float(portfolio["cash_caution"]),
            cash_risk_off=float(portfolio["cash_risk_off"]),
            cash_strength_bump=float(portfolio["cash_strength_bump"]),
            cash_ceiling=float(portfolio["cash_ceiling"]),
            cash_tolerance=float(portfolio["cash_tolerance"]),
            initial_cash=float(portfolio["initial_cash"]),
            megacap_bounce=float(portfolio["megacap_bounce"]),
            cyclical_bounce=float(portfolio["cyclical_bounce"]),
            hard_down_return=float(portfolio["hard_down_return"]),
            index_bounce_min=float(portfolio["index_bounce_min"]),
            half_trim=float(portfolio["half_trim"]),
            light_trim=float(portfolio["light_trim"]),
            tranche_nav=float(portfolio["tranche_nav"]),
            min_days_between_adds=int(portfolio["min_days_between_adds"]),
            assume_regular_hours=bool(portfolio["assume_regular_hours"]),
            core=_strings(portfolio["core"]),
            megacaps=_strings(portfolio["megacaps"]),
            cyclicals=_strings(portfolio["cyclicals"]),
            sale_order=_strings(portfolio["sale_order"]),
            half_names=_strings(portfolio["half_names"]),
            light_names=_strings(portfolio["light_names"]),
            add_names=_strings(portfolio["add_names"]),
            buy_zone_fraction=float(portfolio["buy_zone_fraction"]),
        ),
        costs=Costs(**{key: float(costs[key]) for key in (
            "equity_slippage_bps", "perp_fee_bps", "perp_slippage_bps",
            "option_fee_bps_underlying", "option_iv_slippage",
        )}),
        derivatives=Derivatives(
            stop=float(derivatives["stop"]),
            long_size=float(derivatives["long_size"]),
            long_size_below_fast=float(derivatives["long_size_below_fast"]),
            short_size=float(derivatives["short_size"]),
            short_size_below_slow_only=float(derivatives["short_size_below_slow_only"]),
            put_otm=float(derivatives["put_otm"]),
            put_tenor_days=int(derivatives["put_tenor_days"]),
            cheap_vol_event_days=int(derivatives["cheap_vol_event_days"]),
            put_with_short=bool(derivatives["put_with_short"]),
            fallback_rate=float(derivatives["fallback_rate"]),
        ),
        phillip=Phillip(
            _strings(phillip["names"]), float(phillip["zone_fraction"]),
            float(phillip["raise_risk_on"]), float(phillip["lower_risk_off"]),
            int(phillip["closest_count"]),
        ),
        events=Events(int(events["horizon_days"]), _dates(events.get("fomc"))),
        scorecard=ScorecardCfg(int(scorecard["within_days"])),
        current_book=CurrentBook(
            _date(book["as_of"]), float(book["nav_usd"]), str(book.get("note") or ""),
            _floats(book.get("weights")), trades,
        ),
        model=Model(str(model["version"]), float(model["v1_risk_off_max"])),
        redeploy=Redeploy(
            spy_drawdown=float(redeploy["spy_drawdown"]),
            vix_spike=float(redeploy["vix_spike"]),
            vix_fade_sessions=int(redeploy["vix_fade_sessions"]),
            spike_lookback=int(redeploy["spike_lookback"]),
            peak_lookback=int(redeploy["peak_lookback"]),
            name_drawdown=float(redeploy["name_drawdown"]),
            rebound_sessions=int(redeploy["rebound_sessions"]),
            tranches=int(redeploy["tranches"]),
            gap_days=int(redeploy["gap_days"]),
            episode_gap_days=int(redeploy["episode_gap_days"]),
            cash_target=float(redeploy["cash_target"]),
            btc_drawdown=float(redeploy["btc_drawdown"]),
            hold_sessions=int(redeploy["hold_sessions"]),
            quality=_strings(redeploy["quality"]),
            high_beta=_strings(redeploy["high_beta"]),
        ),
    )
    _validate(cfg)
    return cfg


def _validate(cfg: Config) -> None:
    if not cfg.rollup.red_max < 0 < cfg.rollup.green_min:
        raise ValueError("rollup thresholds must bracket zero")
    stress = cfg.regime.stress
    if not stress.exit_caution < stress.exit_risk_off <= stress.enter_caution < stress.enter_risk_off:
        raise ValueError("stress hysteresis must rise from exit-caution to enter-risk-off")
    rising = (
        (stress.vix_jump_caution, stress.vix_jump_risk, "vix jump"),
        (stress.vix_level_caution, stress.vix_level_risk, "vix level"),
        (stress.credit_widen_caution, stress.credit_widen_risk, "credit widening"),
        (stress.yield_caution, stress.yield_risk, "30y change"),
        (stress.oil_caution, stress.oil_risk, "oil shock"),
    )
    for mild, severe, name in rising:
        if mild >= severe:
            raise ValueError(f"{name} caution cut must sit below its risk-off cut")
    falling = (
        (stress.btc_roc_caution, stress.btc_roc_risk, "btc return"),
        (stress.btc_dd_caution, stress.btc_dd_risk, "btc drawdown"),
    )
    for mild, severe, name in falling:
        if mild <= severe:
            raise ValueError(f"{name} caution cut must sit above its risk-off cut")
    pairs = (
        (cfg.rates.yield_10y_green_max, cfg.rates.yield_10y_red_min, "10y"),
        (cfg.rates.yield_30y_green_max, cfg.rates.yield_30y_red_min, "30y"),
        (cfg.oil.wti_green_max, cfg.oil.wti_red_min, "wti"),
        (cfg.volatility.vix_green_max, cfg.volatility.vix_red_min, "vix"),
        (cfg.credit.hy_green_max, cfg.credit.hy_red_min, "hy"),
        (cfg.crypto.dvol_cheap_max, cfg.crypto.dvol_expensive_min, "dvol"),
    )
    for low, high, name in pairs:
        if low >= high:
            raise ValueError(f"{name} green max must be below its red min")
    band = (
        cfg.portfolio.cash_risk_on, cfg.portfolio.cash_neutral,
        cfg.portfolio.cash_caution, cfg.portfolio.cash_risk_off,
    )
    if not band[0] <= band[1] <= band[2] <= band[3] <= cfg.portfolio.cash_ceiling:
        raise ValueError("cash targets must rise from risk-on to risk-off and stay inside the ceiling")
    if cfg.window.start >= cfg.window.oos_start or cfg.window.oos_start > cfg.window.end:
        raise ValueError("out-of-sample split must sit inside the backtest window")
    if cfg.model.version not in {"v1", "v2", "v3"}:
        raise ValueError("model version must be v1, v2, or v3")
    if not 0 < cfg.redeploy.spy_drawdown < 1 or not 0 < cfg.redeploy.name_drawdown < 1:
        raise ValueError("redeploy drawdowns must sit between 0 and 1")
    if cfg.redeploy.tranches < 1:
        raise ValueError("redeploy needs at least one tranche")
