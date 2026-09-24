"""The archive inventory must preserve pagination and reject ambiguous responses."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "research/futures/archive_catalog.py"
SPEC = importlib.util.spec_from_file_location("archive_catalog", MODULE_PATH)
assert SPEC and SPEC.loader
archive_catalog = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(archive_catalog)


def test_parse_page_keeps_delisted_candidate_names_and_token():
    raw = b'''<?xml version="1.0"?>
    <ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
      <IsTruncated>true</IsTruncated>
      <NextContinuationToken>opaque+token=</NextContinuationToken>
      <CommonPrefixes><Prefix>data/futures/um/monthly/klines/OLDUSDT/</Prefix></CommonPrefixes>
    </ListBucketResult>'''
    assert archive_catalog.parse_page(raw) == (
        ["data/futures/um/monthly/klines/OLDUSDT/"], "opaque+token="
    )


def test_parse_page_rejects_truncated_listing_without_token():
    raw = b'''<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
      <IsTruncated>true</IsTruncated>
    </ListBucketResult>'''
    with pytest.raises(ValueError, match="continuation"):
        archive_catalog.parse_page(raw)


def test_catalog_rejects_unknown_data_kind():
    with pytest.raises(ValueError, match="unsupported"):
        archive_catalog.list_contract_directories("current_exchange_info")
