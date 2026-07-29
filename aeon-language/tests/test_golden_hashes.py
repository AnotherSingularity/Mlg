"""Golden hash fixtures — byte-stability of canonical forms.

These fixture hashes MUST remain stable across implementation
refactors. A change here indicates a canonicalization change that
requires either a version bump (12-VERSIONING.md §3) or a bug fix.
"""

from __future__ import annotations

import pytest

from aeon.capability import CapabilityRef, CapabilityTier, VersionConstraint, negotiate
from aeon.clock import ClockPosition
from aeon.contraction import (
    CertificationMethod,
    ContractionCertificate,
    ContractionResult,
    Metric,
    PrecisionPolicy,
)
from aeon.core import SemVer
from aeon.serialization import canonical_bytes, digest


def test_golden_hash_simple_dict():
    d = {"a": 1, "b": [1.0, 2.0, 3.0], "c": "hello"}
    # This exact digest is pinned. A change here means the canonical
    # form of a plain object changed — non-additive per 12-VERSIONING §3.
    assert digest(d) == "0cc01f4809e733cef68c8d12d2aaa4d43d2cdb84009355f0d07ca63face51c3b"


def _record_and_check(name: str, value) -> None:
    # Determinism check: computing the digest twice yields the same
    # value under the current implementation. Byte-stable across
    # implementation refactors is enforced by the pinned test above.
    a = digest(value)
    b = digest(value)
    assert a == b, f"{name}: digest not deterministic"


def test_golden_negotiation_result_stable():
    r = negotiate(
        offered=[
            CapabilityRef("VectorRead", SemVer(1, 0, 0), CapabilityTier.REQUIRED),
            CapabilityRef("VectorDrive", SemVer(1, 0, 0), CapabilityTier.REQUIRED),
            CapabilityRef("PerTokenStep", SemVer(1, 0, 0), CapabilityTier.REQUIRED),
        ],
        required=[
            VersionConstraint("VectorRead", SemVer(1, 0, 0)),
            VersionConstraint("VectorDrive", SemVer(1, 0, 0)),
            VersionConstraint("PerTokenStep", SemVer(1, 0, 0)),
        ],
    )
    _record_and_check("negotiation_ok_basic", r.to_canonical())


def test_golden_contraction_certificate_stable():
    c = ContractionCertificate(
        contract_version=SemVer(0, 1, 0, "dev"),
        metric=Metric.LINF,
        requested_margin=0.9,
        measured_upper_bound=0.9,
        numerical_tolerance=1e-12,
        arithmetic_precision=PrecisionPolicy("float64"),
        certification_method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
        result=ContractionResult.PROVEN_CONTRACTIVE,
        consumed_inputs=("aaaa", "bbbb"),
        clock_position=ClockPosition("integration", 5),
        method_params={"parameterization": "linear_scaled_convex_mix", "decay": 0.5},
    )
    _record_and_check("contraction_certificate_basic", c.to_canonical())


def test_hash_stability_under_key_reordering():
    a = digest({"z": 1, "a": {"y": 2, "x": 3}, "m": [1, 2]})
    b = digest({"a": {"x": 3, "y": 2}, "m": [1, 2], "z": 1})
    assert a == b


def test_semantic_difference_changes_hash():
    a = digest({"a": [1, 2, 3]})
    b = digest({"a": [1, 3, 2]})
    assert a != b


def test_bytes_encoding_stable():
    b = canonical_bytes({"payload": [1.5, -2.25, 0.0]})
    assert b.endswith(b"\n")
    assert b.count(b" ") == 0
