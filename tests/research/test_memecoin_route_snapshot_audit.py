import base64
import struct

import pytest

from rocket.research.solana_pda import PUMP_AMM_PROGRAM, WSOL_MINT, decode_base58
from scripts.research.memecoin_route_snapshot_audit import (
    CONFIG_DISCRIMINATOR,
    TOKEN_2022_PROGRAM,
    TOKEN_PROGRAM,
    decode_config,
    decode_pool,
    decode_token_account,
    visible_lifecycle,
)
from scripts.research.memecoin_route_snapshot_capture import POOL_DISCRIMINATOR


def account(raw: bytes, owner: str) -> dict:
    return {"owner": owner, "data": [base64.b64encode(raw).decode(), "base64"]}


def test_pool_and_mixed_token_program_vaults_preserve_virtual_quote():
    mint = "DJhAWE4tuVFNw57JLBEw6sJbtF6xntFPFkbmXTMJpump"
    pool = "A51EdJCaYLnikrjrsjMkfPGJ1PcpwFSi1x3AH4cQ5zhL"
    authority = "3dpjFohkB134vZeXgDgprYRQU4BVSg65Jyd2NyHW1gac"
    base_vault = "DLvJ2otj1ZF6JZncZubUJcVoSYbEYDgm3YHtvMJhEQJa"
    quote_vault = "GvSyxZywCwN2orXz5SUN9AH3mnzDuVgpET1XRrcPTeCs"
    raw = bytearray(301)
    raw[:8] = POOL_DISCRIMINATOR
    raw[11:43] = decode_base58(authority)
    raw[43:75] = decode_base58(mint)
    raw[75:107] = decode_base58(WSOL_MINT)
    raw[139:171] = decode_base58(base_vault)
    raw[171:203] = decode_base58(quote_vault)
    raw[245:261] = (2_000_000_000).to_bytes(16, "little", signed=True)
    decoded = decode_pool(account(raw, PUMP_AMM_PROGRAM), mint, authority)
    assert decoded["virtual_quote_reserves"] == 2_000_000_000
    assert decoded["base_vault"] == base_vault
    with pytest.raises(ValueError, match="POOL_IDENTITY_MISMATCH"):
        decode_pool(account(raw, PUMP_AMM_PROGRAM), WSOL_MINT, authority)

    for vault_mint, program in ((mint, TOKEN_2022_PROGRAM),
                                (WSOL_MINT, TOKEN_PROGRAM)):
        vault = bytearray(170 if program == TOKEN_2022_PROGRAM else 165)
        vault[:32] = decode_base58(vault_mint)
        vault[32:64] = decode_base58(pool)
        struct.pack_into("<Q", vault, 64, 1234)
        assert decode_token_account(account(vault, program), vault_mint, pool)[
            "amount"] == 1234
    with pytest.raises(ValueError, match="TOKEN_MINT_OR_OWNER_MISMATCH"):
        decode_token_account(account(vault, TOKEN_PROGRAM), mint, pool)


def test_config_decodes_pinned_core_fields():
    raw = bytearray(949)
    raw[:8] = CONFIG_DISCRIMINATOR
    struct.pack_into("<Q", raw, 40, 20)
    struct.pack_into("<Q", raw, 48, 5)
    assert decode_config(account(raw, PUMP_AMM_PROGRAM))["protocol_fee_bps"] == 5


def test_later_migration_is_not_backdated_to_first_read():
    observations = [{"mint": "m", "event_type": "CompletePumpAmmMigrationEvent",
                     "available_at": "2026-09-24T10:00:10+00:00", "slot": 9}]
    assert visible_lifecycle(observations, "m", "2026-09-24T10:00:09+00:00")[
        "migration_events"] == 0
    assert visible_lifecycle(observations, "m", "2026-09-24T10:00:11+00:00")[
        "last_migration_slot"] == 9
