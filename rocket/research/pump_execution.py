"""Research-only native SOL Pump curve quotes for observed non-mayhem events.

Fees are supplied from an as-of event. These deterministic quotes do not model
transaction inclusion, adversarial flow or subsequent market response.
"""

from __future__ import annotations

from dataclasses import dataclass

BPS = 10_000


def ceildiv(value: int, divisor: int) -> int:
    if value < 0 or divisor <= 0:
        raise ValueError("invalid unsigned division")
    return (value + divisor - 1) // divisor


@dataclass(frozen=True)
class CurveState:
    virtual_quote: int
    virtual_tokens: int
    real_quote: int
    real_tokens: int

    def validate(self) -> None:
        if min(self.virtual_quote, self.virtual_tokens) <= 0 or min(
            self.real_quote, self.real_tokens) < 0:
            raise ValueError("invalid curve state")


@dataclass(frozen=True)
class FeeSchedule:
    protocol_bps: int
    creator_bps: int
    creator_enabled: bool = True

    def charges(self, gross: int) -> int:
        if gross < 0 or min(self.protocol_bps, self.creator_bps) < 0:
            raise ValueError("invalid fee schedule")
        creator = self.creator_bps if self.creator_enabled else 0
        return ceildiv(gross * self.protocol_bps, BPS) + ceildiv(gross * creator, BPS)


def buy_exact_input(state: CurveState, budget: int, fees: FeeSchedule) -> dict[str, int]:
    state.validate()
    if budget <= 0:
        raise ValueError("invalid input budget")
    creator = fees.creator_bps if fees.creator_enabled else 0
    gross = budget * BPS // (BPS + fees.protocol_bps + creator)
    gross -= max(0, gross + fees.charges(gross) - budget)
    if gross <= 1:
        raise ValueError("budget below quote minimum")
    tokens = (gross - 1) * state.virtual_tokens // (state.virtual_quote + gross - 1)
    if tokens <= 0 or tokens > state.real_tokens:
        raise ValueError("insufficient token liquidity")
    cash = gross + fees.charges(gross)
    if cash > budget:
        raise ValueError("budget conservation failure")
    return {"gross": gross, "tokens": tokens, "cash": cash, "unused_budget": budget - cash}


def buy_exact_output(state: CurveState, tokens: int, fees: FeeSchedule) -> dict[str, int]:
    state.validate()
    if tokens <= 0 or tokens >= state.virtual_tokens or tokens > state.real_tokens:
        raise ValueError("insufficient token liquidity")
    gross = state.virtual_quote * tokens // (state.virtual_tokens - tokens) + 1
    return {"gross": gross, "tokens": tokens, "cash": gross + fees.charges(gross)}


def sell(state: CurveState, tokens: int, fees: FeeSchedule) -> dict[str, int]:
    state.validate()
    if tokens <= 0:
        raise ValueError("invalid token amount")
    gross = tokens * state.virtual_quote // (state.virtual_tokens + tokens)
    if gross <= 0 or gross > state.real_quote:
        raise ValueError("insufficient exit liquidity")
    cash = gross - fees.charges(gross)
    if cash <= 0:
        raise ValueError("fees exhaust output")
    return {"gross": gross, "tokens": tokens, "cash": cash}


def pre_trade_state(event: dict) -> CurveState:
    direction = 1 if event["is_buy"] else -1
    amount = event["sol_amount"]
    tokens = event["token_amount"]
    return CurveState(
        event["virtual_sol_reserves"] - direction * amount,
        event["virtual_token_reserves"] + direction * tokens,
        event["real_sol_reserves"] - direction * amount,
        event["real_token_reserves"] + direction * tokens,
    )
