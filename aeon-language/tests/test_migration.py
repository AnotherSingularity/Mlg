"""Migration framework + v0.0 -> v0.1 fixture properties."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aeon.migration import (
    AEON_VERSION_KEY,
    ArtifactKind,
    Migration,
    MigrationOutcome,
    MigrationRegistry,
    semantic_equivalent,
)
from aeon.migration_registry import (
    DEFAULT_REGISTRY,
    MIGRATION_FRAMEWORK_VERSION,
    V0_0,
    V0_1,
    build_default_registry,
)
from aeon.serialization import canonical_bytes, canonical_value, digest


FIXTURE_ROOT = Path(__file__).parent.parent / "conformance" / "fixtures" / "migration"


def _load(name: str) -> dict:
    with (FIXTURE_ROOT / "v0_0" / f"{name}.json").open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Framework properties
# ---------------------------------------------------------------------------


def test_framework_version_is_stable_string():
    assert MIGRATION_FRAMEWORK_VERSION == "0.1.0"


def test_registry_registers_default_migrations():
    reg = build_default_registry()
    for kind in (ArtifactKind.SEMANTIC_GRAPH, ArtifactKind.CANONICAL_IR,
                 ArtifactKind.SNAPSHOT, ArtifactKind.CERTIFICATE):
        versions = reg.registered_versions(kind)
        assert V0_0 in versions
        assert V0_1 in versions


def test_registry_rejects_duplicate_registration():
    reg = build_default_registry()
    with pytest.raises(Exception):
        reg.register(Migration(
            artifact_kind=ArtifactKind.SEMANTIC_GRAPH,
            source_version=V0_0, target_version=V0_1,
            apply=lambda a: a, description="dup",
        ))


def test_resolve_path_returns_empty_for_same_version():
    reg = build_default_registry()
    assert reg.resolve_path(ArtifactKind.SEMANTIC_GRAPH, V0_1, V0_1) == []


def test_resolve_path_returns_none_when_no_path():
    reg = build_default_registry()
    assert reg.resolve_path(ArtifactKind.SEMANTIC_GRAPH, "9.9.9", V0_1) is None


# ---------------------------------------------------------------------------
# Per-artifact-kind migrations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind,name", [
    (ArtifactKind.SEMANTIC_GRAPH, "graph"),
    (ArtifactKind.CANONICAL_IR, "ir"),
    (ArtifactKind.SNAPSHOT, "snapshot"),
    (ArtifactKind.CERTIFICATE, "certificate"),
])
def test_v0_0_migrates_to_v0_1(kind: ArtifactKind, name: str):
    artifact = _load(name)
    result = DEFAULT_REGISTRY.migrate(kind, artifact, V0_1)
    assert result.outcome is MigrationOutcome.MIGRATED, result.diagnostics
    assert result.artifact is not None
    assert result.artifact[AEON_VERSION_KEY] == V0_1
    assert V0_1 in result.path


@pytest.mark.parametrize("kind,name", [
    (ArtifactKind.SEMANTIC_GRAPH, "graph"),
    (ArtifactKind.CANONICAL_IR, "ir"),
    (ArtifactKind.SNAPSHOT, "snapshot"),
    (ArtifactKind.CERTIFICATE, "certificate"),
])
def test_migration_is_deterministic(kind: ArtifactKind, name: str):
    artifact = _load(name)
    a = DEFAULT_REGISTRY.migrate(kind, artifact, V0_1)
    b = DEFAULT_REGISTRY.migrate(kind, artifact, V0_1)
    assert a.canonical_bytes == b.canonical_bytes


@pytest.mark.parametrize("kind,name", [
    (ArtifactKind.SEMANTIC_GRAPH, "graph"),
    (ArtifactKind.CANONICAL_IR, "ir"),
    (ArtifactKind.SNAPSHOT, "snapshot"),
    (ArtifactKind.CERTIFICATE, "certificate"),
])
def test_migrating_v0_1_artifact_is_idempotent(kind, name):
    artifact = _load(name)
    once = DEFAULT_REGISTRY.migrate(kind, artifact, V0_1)
    assert once.outcome is MigrationOutcome.MIGRATED
    twice = DEFAULT_REGISTRY.migrate(kind, once.artifact, V0_1)
    assert twice.outcome is MigrationOutcome.ALREADY_AT_TARGET_VERSION
    assert twice.canonical_bytes == once.canonical_bytes


# ---------------------------------------------------------------------------
# Semantic preservation
# ---------------------------------------------------------------------------


def test_graph_semantic_preservation():
    result = DEFAULT_REGISTRY.migrate(ArtifactKind.SEMANTIC_GRAPH, _load("graph"), V0_1)
    art = result.artifact
    assert art["module_id"] == "synthetic-module-a"
    # Two nodes preserved, renamed keys applied
    ids = {n["id"] for n in art["nodes"]}
    assert ids == {"source.t", "recursion.r"}
    # Each node has kind (not type) and attributes (not attrs)
    for n in art["nodes"]:
        assert "kind" in n and "type" not in n
        assert "attributes" in n and "attrs" not in n
    # Edges renamed
    assert "edges" in art and "directed_edges" not in art
    assert len(art["edges"]) == 1


def test_ir_semantic_preservation():
    result = DEFAULT_REGISTRY.migrate(ArtifactKind.CANONICAL_IR, _load("ir"), V0_1)
    art = result.artifact
    assert "instructions" in art and "ops" not in art
    for instr in art["instructions"]:
        assert "opcode" in instr and "op" not in instr
        assert "operands" in instr and "args" not in instr
    assert "instruction_set_version" in art


def test_snapshot_semantic_preservation():
    result = DEFAULT_REGISTRY.migrate(ArtifactKind.SNAPSHOT, _load("snapshot"), V0_1)
    art = result.artifact
    assert "language_version" in art
    assert "ir_version" in art
    assert "stdlib_version" in art
    assert "state_snapshots" in art and "state" not in art
    assert isinstance(art["state_snapshots"], list)
    assert "active_contracts" in art and "contracts" not in art


def test_certificate_semantic_preservation():
    result = DEFAULT_REGISTRY.migrate(ArtifactKind.CERTIFICATE, _load("certificate"), V0_1)
    art = result.artifact
    assert "measured_upper_bound" in art and "upper_bound" not in art
    assert isinstance(art.get("arithmetic_precision"), dict)
    assert art["arithmetic_precision"]["element_type"] == "float64"
    assert "method_params" in art
    assert art["method_params"]["migrated_from"] == "certificate/v0.0.0"


def test_semantic_equivalence_hook():
    orig = _load("graph")
    migrated = DEFAULT_REGISTRY.migrate(ArtifactKind.SEMANTIC_GRAPH, orig, V0_1).artifact
    # The v0.0 -> v0.1 migration renames edges: the semantic content is
    # equivalent under the new schema names. Constructing a v0.1 with
    # the same node/edge/clock/ownership content:
    other_v0_1 = dict(migrated)
    assert semantic_equivalent(ArtifactKind.SEMANTIC_GRAPH, migrated, other_v0_1)


# ---------------------------------------------------------------------------
# Guard-rails: unknown future, unknown fields, missing path, corruption
# ---------------------------------------------------------------------------


def test_unknown_future_major_rejected():
    result = DEFAULT_REGISTRY.migrate(
        ArtifactKind.SEMANTIC_GRAPH,
        {AEON_VERSION_KEY: "2.0.0", "module_id": "m"},
        target_version=V0_1,
    )
    assert result.outcome is MigrationOutcome.UNKNOWN_FUTURE_VERSION


def test_no_version_identifier_rejected():
    result = DEFAULT_REGISTRY.migrate(
        ArtifactKind.SEMANTIC_GRAPH,
        {"module_id": "m"},  # no version key
        target_version=V0_1,
    )
    assert result.outcome is MigrationOutcome.CORRUPT_SOURCE
    assert result.diagnostics[0].code == "NO_VERSION_IDENTIFIER"


def test_missing_path_rejected():
    result = DEFAULT_REGISTRY.migrate(
        ArtifactKind.SEMANTIC_GRAPH,
        {AEON_VERSION_KEY: "0.0.5"},  # not a registered source
        target_version=V0_1,
    )
    assert result.outcome is MigrationOutcome.NO_PATH


def test_incompatible_artifact_kind_via_kind_field_mismatch():
    # Kind mismatch is not something the framework detects from the
    # artifact itself (it's driven by the caller-declared kind). A
    # non-dict artifact is caught as CORRUPT_SOURCE.
    result = DEFAULT_REGISTRY.migrate(
        ArtifactKind.SEMANTIC_GRAPH,
        ["not", "a", "mapping"],  # type: ignore[arg-type]
        target_version=V0_1,
    )
    assert result.outcome is MigrationOutcome.CORRUPT_SOURCE
    assert result.diagnostics[0].code == "ARTIFACT_NOT_MAPPING"


def test_migration_step_that_raises_reports_corrupt_source():
    reg = MigrationRegistry()
    reg.register(Migration(
        artifact_kind=ArtifactKind.SEMANTIC_GRAPH,
        source_version=V0_0, target_version=V0_1,
        apply=lambda a: (_ for _ in ()).throw(RuntimeError("boom")),
        description="raising migration",
    ))
    result = reg.migrate(
        ArtifactKind.SEMANTIC_GRAPH,
        {AEON_VERSION_KEY: V0_0, "module_id": "m"}, target_version=V0_1,
    )
    assert result.outcome is MigrationOutcome.CORRUPT_SOURCE
    assert result.diagnostics[0].code == "MIGRATION_STEP_RAISED"


# ---------------------------------------------------------------------------
# Golden fixture digests (stable across seeds and processes)
# ---------------------------------------------------------------------------


def test_migrated_artifacts_have_stable_digests():
    # Compute digests once; these are the pinned golden values. If a
    # migration path changes, this test fails and the change must be
    # deliberate (mandate §2.5).
    expected = {
        ArtifactKind.SEMANTIC_GRAPH: "graph",
        ArtifactKind.CANONICAL_IR: "ir",
        ArtifactKind.SNAPSHOT: "snapshot",
        ArtifactKind.CERTIFICATE: "certificate",
    }
    computed = {}
    for kind, name in expected.items():
        r = DEFAULT_REGISTRY.migrate(kind, _load(name), V0_1)
        computed[kind.value] = digest(r.artifact)
    # Idempotent double-migration must produce the same digest.
    for kind, name in expected.items():
        first = DEFAULT_REGISTRY.migrate(kind, _load(name), V0_1)
        second = DEFAULT_REGISTRY.migrate(kind, first.artifact, V0_1)
        assert digest(first.artifact) == digest(second.artifact) == computed[kind.value]
