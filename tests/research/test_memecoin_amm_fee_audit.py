from __future__ import annotations

import base64
import struct

import pytest

from scripts.research.memecoin_amm_fee_audit import extensions, fee_config


def test_fee_config_decodes_dynamic_tiers_and_rejects_unknown_extension():
    raw = bytearray(256)
    raw[:8] = bytes([143, 52, 146, 187, 219, 123, 76, 155])
    struct.pack_into("<QQQ", raw, 41, 20, 5, 0)
    struct.pack_into("<I", raw, 65, 2)
    raw[69:85] = (0).to_bytes(16, "little")
    struct.pack_into("<QQQ", raw, 85, 2, 93, 30)
    raw[109:125] = (420_000_000_000).to_bytes(16, "little")
    struct.pack_into("<QQQ", raw, 125, 20, 5, 95)
    struct.pack_into("<I", raw, 149, 0)
    struct.pack_into("<QQQ", raw, 153, 25, 5, 0)
    value = {"owner": "pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ",
             "data": [base64.b64encode(raw).decode(), "base64"]}
    parsed = fee_config(value)
    assert [tier["protocol_fee_bps"] for tier in parsed["fee_tiers"]] == [93, 5]

    mint = bytearray(170)
    mint[165] = 1
    struct.pack_into("<HH", mint, 166, 1, 0)
    with pytest.raises(ValueError, match="unsupported Token-2022 extension"):
        extensions(mint, account_type=1, allowed={18, 19})
