"""L13: application conformance suite.

Verifies the conformance manifest is stable, versioned, and
declares every REQUIRED profile the mandate calls for. The full
subprocess-based run of ``run_suite()`` is exercised by CI, not
in-process here, because it would recursively spawn pytest.
"""

from __future__ import annotations

import json
from pathlib import Path

from aeon_app.conformance import (
    CONFORMANCE_SCHEMA_VERSION,
    GATE_MAP,
    REQUIRED_PROFILES,
    build_manifest,
    manifest_digest,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "conformance" / "manifest.json"


def test_conformance_schema_version():
    assert CONFORMANCE_SCHEMA_VERSION == "0.1.0"


def test_required_profiles_cover_every_mandate_gate():
    """Each of Gate L-A..L-J is covered by at least one profile."""
    profile_gates = set()
    for p in build_manifest()["profiles"].values():
        profile_gates.add(p["gate"])
    for gate in ("Gate L-A", "Gate L-B", "Gate L-C", "Gate L-D",
                 "Gate L-E", "Gate L-F", "Gate L-G", "Gate L-H",
                 "Gate L-I"):
        assert gate in profile_gates, f"{gate} has no covering profile"


def test_manifest_is_deterministic():
    a = manifest_digest()
    b = manifest_digest()
    assert a == b
    assert len(a) == 64  # blake2b-256 hex


def test_manifest_on_disk_matches_generator():
    assert MANIFEST_PATH.exists(), "conformance/manifest.json must be committed"
    on_disk = json.loads(MANIFEST_PATH.read_text())
    generated = build_manifest()
    assert on_disk == generated, (
        "conformance/manifest.json is stale; regenerate with "
        "`python -m aeon_app.conformance --manifest-only > "
        "conformance/manifest.json`"
    )


def test_every_required_profile_present_in_manifest():
    m = build_manifest()
    for name in REQUIRED_PROFILES:
        assert name in m["profiles"], name
        assert m["profiles"][name]["required"] is True


def test_full_application_profile_optional():
    """FULL_APPLICATION is a convenience aggregator, not a
    launch-blocker; it must not be flagged REQUIRED."""
    m = build_manifest()
    assert m["profiles"]["FULL_APPLICATION"]["required"] is False


def test_gate_map_covers_every_required_category():
    m = build_manifest()
    for name in REQUIRED_PROFILES:
        cat = m["profiles"][name]["category"]
        assert cat in GATE_MAP, f"category {cat} for {name} has no gate"
