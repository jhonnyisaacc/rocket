import base64

from rocket.research.solana_pda import PUMP_AMM_PROGRAM, WSOL_MINT, decode_base58
from scripts.research.memecoin_route_snapshot_capture import POOL_DISCRIMINATOR, pool_vaults


def test_pool_vaults_requires_owner_discriminator_and_mint():
    mint = "DJhAWE4tuVFNw57JLBEw6sJbtF6xntFPFkbmXTMJpump"
    base_vault = "5jMpkf4JF4noHftLgNKyPNh6roVfPSGSjuEk3U4eLKRa"
    quote_vault = "43DVcZR4kQFjh4Xm2i3DcneRxNjZp7HMud8yDrJWrDr8"
    raw = bytearray(301)
    raw[:8] = POOL_DISCRIMINATOR
    raw[43:75] = decode_base58(mint)
    raw[75:107] = decode_base58(WSOL_MINT)
    raw[139:171] = decode_base58(base_vault)
    raw[171:203] = decode_base58(quote_vault)
    account = {"owner": PUMP_AMM_PROGRAM, "data": [base64.b64encode(raw).decode(),
                                                     "base64"]}
    assert pool_vaults(account, mint) == (base_vault, quote_vault)
    assert pool_vaults({**account, "owner": "11111111111111111111111111111111"},
                       mint) is None
    assert pool_vaults(account, WSOL_MINT) is None
