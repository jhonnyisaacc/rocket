"""Option pricing sanity: pins units (DVOL percent points) and value scale."""

from rocket.crypto import puts as puts_mod


def test_otm_put_costs_thousands_not_pennies():
    # 90-day 15% OTM on 40k BTC at 80% IV must cost low thousands.
    premium = puts_mod.buy_premium(40000.0, 34000.0, 90 / 365, 0.80)
    assert 1000.0 < premium < 8000.0


def test_expired_put_pays_intrinsic():
    assert puts_mod.exit_value(30000.0, 34000.0, 0.0, 0.80) == 4000.0
    assert puts_mod.exit_value(40000.0, 34000.0, 0.0, 0.80) == 0.0
