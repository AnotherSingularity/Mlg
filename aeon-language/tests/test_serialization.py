"""Canonical serialization + digest properties."""

from __future__ import annotations

import pytest

from aeon.serialization import (
    CanonicalizationError,
    canonical_bytes,
    canonical_value,
    digest,
)


def test_key_order_independent():
    a = canonical_bytes({"z": 1, "a": [3, 1, 2], "m": {"y": 1, "x": 2}})
    b = canonical_bytes({"a": [3, 1, 2], "m": {"x": 2, "y": 1}, "z": 1})
    assert a == b


def test_digest_deterministic():
    v = {"a": 1, "b": [1.0, 2.5, -3.75]}
    assert digest(v) == digest(dict(reversed(list(v.items()))))


def test_semantic_difference_changes_digest():
    a = digest({"a": 1, "b": 2})
    b = digest({"a": 2, "b": 1})
    assert a != b


def test_set_rejected():
    with pytest.raises(CanonicalizationError):
        canonical_bytes({"s": {1, 2, 3}})


def test_nan_rejected():
    with pytest.raises(CanonicalizationError):
        canonical_bytes({"x": float("nan")})


def test_inf_rejected():
    with pytest.raises(CanonicalizationError):
        canonical_bytes({"x": float("inf")})


def test_utf8_nfc_string():
    a = canonical_bytes({"k": "é"})  # NFC 'é'
    b = canonical_bytes({"k": "é"})  # decomposed 'e' + combining acute
    assert a == b


def test_bytes_encoded_as_hex_object():
    v = canonical_value(b"\x00\xff")
    assert v == {"__aeon_bytes__": "00ff"}


def test_trailing_newline():
    b = canonical_bytes({"x": 1})
    assert b.endswith(b"\n")
