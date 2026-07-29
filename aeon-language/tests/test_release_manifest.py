"""Release manifest determinism, coverage, and verification."""

from __future__ import annotations

from pathlib import Path

import pytest

from aeon import (
    IR_VERSION,
    LANGUAGE_VERSION,
    STDLIB_VERSION,
)
from release.manifest import (
    build_release_manifest,
    release_manifest_bytes,
    release_manifest_digest,
    verify_release_manifest,
    write_release_manifest,
)


def test_version_is_final():
    assert LANGUAGE_VERSION == "0.1.0"
    assert IR_VERSION == "0.1.0"
    assert STDLIB_VERSION == "0.1.0"


def test_manifest_contains_every_versioned_stream():
    m = build_release_manifest(sha="deadbeef")
    versions = m["versions"]
    for k in ("language", "ir", "instruction_set", "stdlib",
              "source_grammar", "certificate_schema",
              "snapshot_schema", "conformance_profile",
              "backend_contract", "migration_framework"):
        assert k in versions and versions[k], f"missing version stream: {k}"


def test_manifest_lists_all_mandated_stdlib_modules():
    m = build_release_manifest(sha="deadbeef")
    api = set(m["stdlib_public_api"])
    mandated = {
        "aeon.core", "aeon.types", "aeon.identity", "aeon.state",
        "aeon.signal", "aeon.clock", "aeon.causality", "aeon.port",
        "aeon.capability", "aeon.contract", "aeon.contraction",
        "aeon.recursion", "aeon.projection", "aeon.graph", "aeon.ir",
        "aeon.runtime", "aeon.certificate", "aeon.provenance",
        "aeon.serialization", "aeon.snapshot", "aeon.testing",
        "aeon.math", "aeon.tensor",
    }
    assert mandated <= api


def test_manifest_lists_all_eight_cli_tools_plus_migrate():
    m = build_release_manifest(sha="deadbeef")
    assert set(m["cli_tools"]) == {
        "aeonc", "aeoncheck", "aeonfmt", "aeongraph", "aeonir",
        "aeonmigrate", "aeonreplay", "aeonrun", "aeontest",
    }


def test_manifest_lists_both_backends():
    m = build_release_manifest(sha="deadbeef")
    assert "aeon.backends.python" in m["backends"]
    assert "aeon.backends.numpy" in m["backends"]


def test_manifest_deterministic_bytes():
    a = release_manifest_bytes(build_release_manifest(sha="s"))
    b = release_manifest_bytes(build_release_manifest(sha="s"))
    assert a == b


def test_manifest_digest_changes_with_sha():
    a = release_manifest_digest(build_release_manifest(sha="AAAA"))
    b = release_manifest_digest(build_release_manifest(sha="BBBB"))
    assert a != b


def test_manifest_covers_specification_documents():
    m = build_release_manifest(sha="s")
    # Every one of the fourteen normative documents 00-13 must have a
    # digest recorded.
    assert len(m["specification_digests"]) >= 14
    for name in ["00-CONSTITUTION.md", "01-ONTOLOGY.md",
                 "13-CONFORMANCE.md"]:
        assert name in m["specification_digests"]


def test_manifest_covers_migration_fixtures():
    m = build_release_manifest(sha="s")
    fixture_paths = set(m["fixture_digests"])
    for name in ["migration/v0_0/graph.json", "migration/v0_0/ir.json",
                 "migration/v0_0/snapshot.json",
                 "migration/v0_0/certificate.json"]:
        assert name in fixture_paths


def test_verify_release_manifest_round_trip(tmp_path: Path):
    manifest_path = tmp_path / "release.json"
    write_release_manifest(manifest_path, sha="pinned-sha")
    report = verify_release_manifest(manifest_path)
    assert report["ok"], report
    assert report["mismatches"] == []
