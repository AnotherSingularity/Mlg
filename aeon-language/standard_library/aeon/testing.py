"""aeon.testing — test utilities used by conformance fixtures.

Small helper surface. Its goal is not to re-implement pytest but
to provide Aeon-specific comparators for canonical outputs,
certificates, and lineage records.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .contraction import ContractionCertificate
from .serialization import canonical_bytes, canonical_value


def assert_canonical_equal(a: Any, b: Any, *, message: str = "") -> None:
    ab = canonical_bytes(canonical_value(a))
    bb = canonical_bytes(canonical_value(b))
    if ab != bb:
        raise AssertionError(
            f"canonical mismatch{': ' + message if message else ''}\n"
            f"  a: {ab!r}\n  b: {bb!r}"
        )


def assert_certificate_result(cert: ContractionCertificate, expected: str) -> None:
    if cert.result.value != expected:
        raise AssertionError(
            f"expected contraction result {expected!r}, got {cert.result.value!r}"
        )


def assert_within_tolerance(a: float, b: float, tolerance: float) -> None:
    if abs(a - b) > tolerance:
        raise AssertionError(
            f"|{a} - {b}| = {abs(a - b)} > tolerance {tolerance}"
        )


__all__ = [
    "assert_canonical_equal",
    "assert_certificate_result",
    "assert_within_tolerance",
]
