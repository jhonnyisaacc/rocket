"""Small standard-library Solana PDA derivation for read-only research."""

from __future__ import annotations

import hashlib

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
P = 2**255 - 19
D = (-121665 * pow(121666, -1, P)) % P
SQRT_MINUS_ONE = pow(2, (P - 1) // 4, P)
PUMP_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
PUMP_AMM_PROGRAM = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
WSOL_MINT = "So11111111111111111111111111111111111111112"


def decode_base58(value: str) -> bytes:
    number = 0
    for char in value:
        number = number * 58 + ALPHABET.index(char)
    data = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    return b"\0" * (len(value) - len(value.lstrip("1"))) + data


def encode_base58(value: bytes) -> str:
    number = int.from_bytes(value, "big")
    digits = ""
    while number:
        number, index = divmod(number, 58)
        digits = ALPHABET[index] + digits
    return "1" * (len(value) - len(value.lstrip(b"\0"))) + digits


def compressed_edwards_y_is_on_curve(value: bytes) -> bool:
    if len(value) != 32:
        return False
    encoded = int.from_bytes(value, "little")
    y = encoded & ((1 << 255) - 1)
    sign = encoded >> 255
    if y >= P:
        return False
    y_squared = y * y % P
    denominator = (D * y_squared + 1) % P
    if denominator == 0:
        return False
    x_squared = (y_squared - 1) * pow(denominator, -1, P) % P
    x = pow(x_squared, (P + 3) // 8, P)
    if x * x % P != x_squared:
        x = x * SQRT_MINUS_ONE % P
    return x * x % P == x_squared and not (x == 0 and sign)


def find_program_address(seeds: list[bytes], program: str) -> tuple[str, int]:
    if any(len(seed) > 32 for seed in seeds) or len(seeds) > 16:
        raise ValueError("Solana PDA seed bound exceeded")
    program_bytes = decode_base58(program)
    if len(program_bytes) != 32:
        raise ValueError("program id must be 32 bytes")
    for bump in range(255, -1, -1):
        address = hashlib.sha256(b"".join([*seeds, bytes([bump]), program_bytes,
                                           b"ProgramDerivedAddress"])).digest()
        if not compressed_edwards_y_is_on_curve(address):
            return encode_base58(address), bump
    raise ValueError("no off-curve PDA found")


def canonical_pump_pool(mint: str) -> tuple[str, str]:
    mint_bytes = decode_base58(mint)
    if len(mint_bytes) != 32:
        raise ValueError("mint must be 32 bytes")
    authority, _ = find_program_address([b"pool-authority", mint_bytes], PUMP_PROGRAM)
    pool, _ = find_program_address([b"pool", bytes(2), decode_base58(authority),
                                    mint_bytes, decode_base58(WSOL_MINT)], PUMP_AMM_PROGRAM)
    return authority, pool
