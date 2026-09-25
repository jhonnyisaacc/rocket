from __future__ import annotations

from scripts.research.memecoin_audit import signature_structure_issue
from scripts.research.memecoin_block_derive import base58_encode


def test_signature_structure_rejects_placeholder_and_malformed_bytes():
    assert signature_structure_issue("1" * 64) == "ZERO_SIGNATURE_PLACEHOLDER"
    assert signature_structure_issue("1" * 63) == "INVALID_SIGNATURE_LENGTH"
    assert signature_structure_issue("0" * 64) == "INVALID_BASE58_SIGNATURE"
    assert signature_structure_issue(base58_encode(bytes(range(1, 65)))) is None
