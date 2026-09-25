from __future__ import annotations

import base64

import pytest

from scripts.research.memecoin_block_derive import base58_encode, first_signature


def encoded(raw: bytes) -> list[str]:
    return [base64.b64encode(raw).decode(), "base64"]


def test_first_signature_handles_message_first_version_one_and_signature_first_version_zero():
    signature = bytes(range(1, 65))
    assert first_signature(encoded(b"\x81\x01message" + signature), 1) == base58_encode(signature)
    assert first_signature(encoded(b"\x01" + signature + b"message"), 0) == base58_encode(signature)


def test_first_signature_rejects_placeholder():
    with pytest.raises(ValueError, match="placeholder"):
        first_signature(encoded(b"\x81\x01message" + bytes(64)), 1)
