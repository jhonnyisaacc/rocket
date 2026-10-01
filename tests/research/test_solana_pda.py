from rocket.research.solana_pda import (
    PUMP_AMM_PROGRAM,
    PUMP_PROGRAM,
    canonical_pump_pool,
    decode_base58,
    encode_base58,
    find_program_address,
)


def test_base58_roundtrip_and_known_program_pdas():
    assert encode_base58(decode_base58(PUMP_PROGRAM)) == PUMP_PROGRAM
    assert encode_base58(bytes(32)) == "1" * 32
    assert find_program_address([b"global"], PUMP_PROGRAM)[0] == (
        "4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf")
    assert find_program_address([b"global_config"], PUMP_AMM_PROGRAM)[0] == (
        "ADyA8hdefvWN2dbGGWFotbzWxrAvLW83WG6QCVXvJKqw")


def test_canonical_pool_matches_independently_observed_migration():
    assert canonical_pump_pool("DJhAWE4tuVFNw57JLBEw6sJbtF6xntFPFkbmXTMJpump")[1] == (
        "A51EdJCaYLnikrjrsjMkfPGJ1PcpwFSi1x3AH4cQ5zhL")
