"""Capability negotiation properties."""

from __future__ import annotations

from aeon.capability import (
    CapabilityRef,
    CapabilityTier,
    VersionConstraint,
    negotiate,
    REQUIRED_CAPABILITY_NAMES,
)
from aeon.core import SemVer
from aeon.serialization import canonical_bytes


def _base_required():
    return [
        VersionConstraint("VectorRead", SemVer(1, 0, 0)),
        VersionConstraint("VectorDrive", SemVer(1, 0, 0)),
        VersionConstraint("PerTokenStep", SemVer(1, 0, 0)),
    ]


def _base_offered():
    return [
        CapabilityRef("VectorRead", SemVer(1, 0, 0), CapabilityTier.REQUIRED),
        CapabilityRef("VectorDrive", SemVer(1, 0, 0), CapabilityTier.REQUIRED),
        CapabilityRef("PerTokenStep", SemVer(1, 1, 0), CapabilityTier.REQUIRED),
        CapabilityRef("MatrixRead", SemVer(0, 3, 0), CapabilityTier.OPTIONAL),
        CapabilityRef("MatrixRead", SemVer(0, 2, 5), CapabilityTier.OPTIONAL),
    ]


def test_ordering_does_not_change_result():
    r1 = negotiate(_base_offered(), _base_required(), [VersionConstraint("MatrixRead", SemVer(0, 2, 0))])
    r2 = negotiate(list(reversed(_base_offered())),
                   list(reversed(_base_required())),
                   [VersionConstraint("MatrixRead", SemVer(0, 2, 0))])
    assert r1 == r2
    assert canonical_bytes(r1.to_canonical()) == canonical_bytes(r2.to_canonical())


def test_missing_required_produces_explicit_incompatibility():
    r = negotiate(
        [CapabilityRef("VectorRead", SemVer(1, 0, 0), CapabilityTier.REQUIRED)],
        _base_required(),
    )
    assert not r.compatible
    codes = {i.capability_name for i in r.incompatibilities}
    assert "VectorDrive" in codes
    assert "PerTokenStep" in codes


def test_absent_optional_is_not_an_incompatibility():
    r = negotiate(
        [
            CapabilityRef("VectorRead", SemVer(1, 0, 0), CapabilityTier.REQUIRED),
            CapabilityRef("VectorDrive", SemVer(1, 0, 0), CapabilityTier.REQUIRED),
            CapabilityRef("PerTokenStep", SemVer(1, 0, 0), CapabilityTier.REQUIRED),
        ],
        _base_required(),
        [VersionConstraint("MatrixRead", SemVer(0, 2, 0))],
    )
    assert r.compatible
    assert r.incompatibilities == ()
    assert r.optional_paths == ()


def test_selects_highest_matching_version():
    r = negotiate(_base_offered(), _base_required(),
                  [VersionConstraint("MatrixRead", SemVer(0, 2, 0))])
    sel = dict(r.selected_versions)
    assert sel["MatrixRead"] == "0.3.0"


def test_all_required_names_reserved():
    assert set(REQUIRED_CAPABILITY_NAMES) == {"VectorRead", "VectorDrive", "PerTokenStep"}
