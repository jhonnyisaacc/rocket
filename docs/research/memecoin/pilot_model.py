"""Pure integer, research-only Pump curve quotes. No network or execution.

Historical source: pump-public-docs revision 1b822158844a60ca577df6ca122211b595a1a578,
IDL buy_exact_sol_in docs; ordinary buy/sell corroborated against cached trades.
Only the observed native-SOL, non-mayhem, cashback regime is admitted by replay.
"""
from dataclasses import dataclass

VERSION = 'pilot-model-1'
BPS = 10000


def ceildiv(a, b):
    if a < 0 or b <= 0:
        raise ValueError('Invalid unsigned division')
    return (a + b - 1) // b


@dataclass(frozen=True)
class State:
    sol: int
    tokens: int
    real_sol: int
    real_tokens: int


@dataclass(frozen=True)
class Fees:
    protocol: int = 95
    creator: int = 0
    cashback: int = 30
    buyback_share: int = 5000

    def amounts(self, gross):
        # Cashback replaces a creator-fee allocation; not an immediate refund.
        protocol = ceildiv(gross * self.protocol, BPS)
        creator = ceildiv(gross * self.creator, BPS)
        cashback = ceildiv(gross * self.cashback, BPS)
        buyback = protocol * self.buyback_share // BPS
        return dict(protocol=protocol, creator=creator, cashback=cashback,
                    buyback=buyback, protocol_retained=protocol-buyback,
                    charged=protocol+creator+cashback)


def check_state(state):
    if min(state.sol, state.tokens) <= 0 or min(state.real_sol, state.real_tokens) < 0:
        raise ValueError('Invalid curve state')


def buy_exact_output(state, tokens, fees=Fees()):
    check_state(state)
    if tokens <= 0 or tokens >= state.tokens or tokens > state.real_tokens:
        raise ValueError('Insufficient token liquidity')
    gross = state.sol * tokens // (state.tokens - tokens) + 1
    charges = fees.amounts(gross)
    return dict(tokens=tokens, gross=gross, cash=gross+charges['charged'], fees=charges)


def buy_exact_input(state, budget, fees=Fees()):
    check_state(state)
    if budget <= 0:
        raise ValueError('Invalid budget')
    total = fees.protocol + fees.creator + fees.cashback
    gross = budget * BPS // (BPS + total)
    charge = fees.amounts(gross)['charged']
    gross -= max(0, gross + charge - budget)
    if gross <= 1:
        raise ValueError('Budget below integer quote minimum')
    tokens = (gross - 1) * state.tokens // (state.sol + gross - 1)
    # Near completion, instruction behavior needs another validated regime.
    if tokens <= 0 or tokens > state.real_tokens:
        raise ValueError('Unsupported curve completion or zero output')
    charges = fees.amounts(gross)
    if gross + charges['charged'] > budget:
        raise ValueError('Budget conservation failure')
    return dict(tokens=tokens, gross=gross, cash=gross+charges['charged'],
                unused_budget=budget-gross-charges['charged'], fees=charges)


def sell(state, tokens, fees=Fees()):
    check_state(state)
    if tokens <= 0:
        raise ValueError('Invalid token amount')
    gross = tokens * state.sol // (state.tokens + tokens)
    if gross <= 0 or gross > state.real_sol:
        raise ValueError('Insufficient exit liquidity')
    charges = fees.amounts(gross)
    if charges['charged'] >= gross:
        raise ValueError('Fees exhaust output')
    return dict(tokens=tokens, gross=gross, cash=gross-charges['charged'], fees=charges)


def after_buy(state, fill):
    return State(state.sol+fill['gross'], state.tokens-fill['tokens'],
                 state.real_sol+fill['gross'], state.real_tokens-fill['tokens'])


def meets_slippage(expected_output, actual_output, tolerance=200):
    if expected_output <= 0 or not 0 <= tolerance < BPS:
        raise ValueError('Invalid slippage parameters')
    return actual_output >= expected_output * (BPS-tolerance) // BPS


def pre_state(event):
    direction = 1 if event['is_buy'] else -1
    return State(event['virtual_sol_reserves']-direction*event['sol_amount'],
                 event['virtual_token_reserves']+direction*event['token_amount'],
                 event['real_sol_reserves']-direction*event['sol_amount'],
                 event['real_token_reserves']+direction*event['token_amount'])


def post_state(event):
    return State(event['virtual_sol_reserves'], event['virtual_token_reserves'],
                 event['real_sol_reserves'], event['real_token_reserves'])


def continuous(earlier, later):
    return earlier['mint'] == later['mint'] and post_state(earlier) == pre_state(later)
