"""aeon.migration — versioned artifact migration framework.

Implements the migration mechanism required by Phase 0.1 §13 and
extended by the v0.1 final closure mandate §2. The framework is
generic over the seven artifact kinds enumerated in the mandate
§2.1; the concrete registrations live in
:mod:`aeon.migration_registry` and cover the synthetic v0.0 →
v0.1 migrations.

The framework is a **mechanism**, not a claim about a historical
production version. The v0.0 fixtures exist solely to prove that
the migration mechanism is real and testable (mandate §2.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from .serialization import canonical_bytes, canonical_value


class ArtifactKind(Enum):
    SEMANTIC_GRAPH = "semantic_graph"
    CANONICAL_IR = "canonical_ir"
    SNAPSHOT = "snapshot"
    CERTIFICATE = "certificate"
    CONFORMANCE_MANIFEST = "conformance_manifest"
    BACKEND_CONTRACT = "backend_contract"
    SOURCE_MODULE = "source_module"


class MigrationOutcome(Enum):
    MIGRATED = "MIGRATED"
    ALREADY_AT_TARGET_VERSION = "ALREADY_AT_TARGET_VERSION"
    NO_PATH = "NO_PATH"
    UNKNOWN_FUTURE_VERSION = "UNKNOWN_FUTURE_VERSION"
    UNKNOWN_REQUIRED_FIELD = "UNKNOWN_REQUIRED_FIELD"
    CORRUPT_SOURCE = "CORRUPT_SOURCE"
    INCOMPATIBLE_ARTIFACT_KIND = "INCOMPATIBLE_ARTIFACT_KIND"


@dataclass(frozen=True)
class MigrationDiagnostic:
    code: str
    message: str
    field_path: Optional[str] = None


@dataclass(frozen=True)
class Migration:
    """One directed edge in the version-migration graph.

    ``apply`` receives a canonical-form artifact dict and returns
    the migrated canonical-form artifact dict. Migrations are pure
    functions: identical input → identical output.
    """

    artifact_kind: ArtifactKind
    source_version: str
    target_version: str
    apply: Callable[[Dict[str, Any]], Dict[str, Any]]
    description: str = ""

    def key(self) -> Tuple[str, str, str]:
        return (self.artifact_kind.value, self.source_version, self.target_version)


@dataclass(frozen=True)
class MigrationResult:
    outcome: MigrationOutcome
    artifact: Optional[Dict[str, Any]] = None
    canonical_bytes: Optional[bytes] = None
    path: Tuple[str, ...] = ()  # visited version list, e.g. ("0.0.0", "0.1.0")
    diagnostics: Tuple[MigrationDiagnostic, ...] = ()

    def ok(self) -> bool:
        return self.outcome in (MigrationOutcome.MIGRATED,
                                MigrationOutcome.ALREADY_AT_TARGET_VERSION)


class MigrationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class MigrationRegistry:
    """Registry of directed migration edges.

    Path resolution is deterministic: shortest edge chain, ties
    broken by lexicographic source_version ordering. Registration
    order does NOT influence resolution.
    """

    def __init__(self) -> None:
        # kind -> {source -> list[(target, migration)]}
        self._edges: Dict[str, Dict[str, List[Tuple[str, Migration]]]] = {}
        # kind -> set of every version we know as source or target
        self._versions: Dict[str, set] = {}

    def register(self, migration: Migration) -> None:
        kind = migration.artifact_kind.value
        bucket = self._edges.setdefault(kind, {}).setdefault(
            migration.source_version, []
        )
        # Reject duplicate (source, target) pairs.
        for tgt, existing in bucket:
            if tgt == migration.target_version:
                raise MigrationError(
                    "DUPLICATE_MIGRATION",
                    f"migration {kind} {migration.source_version} -> "
                    f"{migration.target_version} already registered",
                )
        bucket.append((migration.target_version, migration))
        # Track versions.
        vs = self._versions.setdefault(kind, set())
        vs.add(migration.source_version)
        vs.add(migration.target_version)

    def registered_versions(self, artifact_kind: ArtifactKind) -> Tuple[str, ...]:
        return tuple(sorted(self._versions.get(artifact_kind.value, set())))

    def resolve_path(
        self,
        artifact_kind: ArtifactKind,
        source_version: str,
        target_version: str,
    ) -> Optional[List[Migration]]:
        if source_version == target_version:
            return []
        kind = artifact_kind.value
        edges = self._edges.get(kind, {})
        # Deterministic BFS with sorted expansion.
        from collections import deque
        prev: Dict[str, Tuple[str, Migration]] = {}
        seen = {source_version}
        q = deque([source_version])
        while q:
            cur = q.popleft()
            for tgt, mig in sorted(edges.get(cur, []), key=lambda x: x[0]):
                if tgt in seen:
                    continue
                seen.add(tgt)
                prev[tgt] = (cur, mig)
                if tgt == target_version:
                    # Rebuild path
                    path: List[Migration] = []
                    node = target_version
                    while node != source_version:
                        pnode, pmig = prev[node]
                        path.append(pmig)
                        node = pnode
                    return list(reversed(path))
                q.append(tgt)
        return None

    def migrate(
        self,
        artifact_kind: ArtifactKind,
        artifact: Mapping[str, Any],
        target_version: str,
    ) -> MigrationResult:
        if not isinstance(artifact, Mapping):
            return MigrationResult(
                outcome=MigrationOutcome.CORRUPT_SOURCE,
                diagnostics=(MigrationDiagnostic(
                    code="ARTIFACT_NOT_MAPPING",
                    message=f"artifact must be a mapping, got {type(artifact).__name__}",
                ),),
            )
        art = dict(artifact)
        # Version discovery: MUST use explicit version identifiers,
        # NOT inference from field presence (mandate §2.2).
        current = _explicit_version(art)
        if current is None:
            return MigrationResult(
                outcome=MigrationOutcome.CORRUPT_SOURCE,
                diagnostics=(MigrationDiagnostic(
                    code="NO_VERSION_IDENTIFIER",
                    message="artifact lacks an explicit version identifier "
                            "(expected key: __aeon_artifact_version__ or "
                            "aeon_artifact_version)",
                ),),
            )

        # Unknown-future-major guard.
        if _major_of(current) > _major_of(target_version):
            return MigrationResult(
                outcome=MigrationOutcome.UNKNOWN_FUTURE_VERSION,
                diagnostics=(MigrationDiagnostic(
                    code="UNKNOWN_FUTURE_MAJOR",
                    message=f"source major version {current!r} is newer than "
                            f"target major version {target_version!r}",
                ),),
            )

        if current == target_version:
            return MigrationResult(
                outcome=MigrationOutcome.ALREADY_AT_TARGET_VERSION,
                artifact=canonical_value(art),
                canonical_bytes=canonical_bytes(canonical_value(art)),
                path=(current,),
                diagnostics=(),
            )

        path = self.resolve_path(artifact_kind, current, target_version)
        if path is None:
            return MigrationResult(
                outcome=MigrationOutcome.NO_PATH,
                diagnostics=(MigrationDiagnostic(
                    code="NO_MIGRATION_PATH",
                    message=f"no migration path for {artifact_kind.value} "
                            f"{current!r} -> {target_version!r}",
                ),),
            )

        visited: List[str] = [current]
        for step in path:
            if step.artifact_kind is not artifact_kind:
                return MigrationResult(
                    outcome=MigrationOutcome.INCOMPATIBLE_ARTIFACT_KIND,
                    diagnostics=(MigrationDiagnostic(
                        code="INCOMPATIBLE_KIND",
                        message=f"migration step declares "
                                f"kind={step.artifact_kind.value!r}, "
                                f"expected {artifact_kind.value!r}",
                    ),),
                )
            try:
                art = step.apply(art)
            except Exception as exc:  # noqa: BLE001 - deliberately broad
                return MigrationResult(
                    outcome=MigrationOutcome.CORRUPT_SOURCE,
                    diagnostics=(MigrationDiagnostic(
                        code="MIGRATION_STEP_RAISED",
                        message=f"migration step "
                                f"{step.source_version} -> "
                                f"{step.target_version} raised: {exc}",
                    ),),
                )
            new_version = _explicit_version(art)
            if new_version != step.target_version:
                return MigrationResult(
                    outcome=MigrationOutcome.CORRUPT_SOURCE,
                    diagnostics=(MigrationDiagnostic(
                        code="MIGRATION_VERSION_MISMATCH",
                        message=f"step {step.source_version} -> "
                                f"{step.target_version} did not set version "
                                f"identifier to {step.target_version!r}",
                    ),),
                )
            visited.append(step.target_version)

        canonical_art = canonical_value(art)
        return MigrationResult(
            outcome=MigrationOutcome.MIGRATED,
            artifact=canonical_art,
            canonical_bytes=canonical_bytes(canonical_art),
            path=tuple(visited),
            diagnostics=(),
        )


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------


AEON_VERSION_KEY = "__aeon_artifact_version__"
AEON_VERSION_KEY_LEGACY = "aeon_artifact_version"


def _explicit_version(artifact: Mapping[str, Any]) -> Optional[str]:
    if AEON_VERSION_KEY in artifact:
        return str(artifact[AEON_VERSION_KEY])
    if AEON_VERSION_KEY_LEGACY in artifact:
        return str(artifact[AEON_VERSION_KEY_LEGACY])
    return None


def _major_of(version: str) -> int:
    return int(version.split(".", 1)[0])


# ---------------------------------------------------------------------------
# Semantic equivalence hooks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SemanticEquivalence:
    """Artifact-kind-specific semantic equivalence declaration.

    Migration correctness is not "the JSON matches"; it is "the
    semantic content is preserved". Every artifact kind names the
    fields whose preservation is required.
    """

    artifact_kind: ArtifactKind
    identifying_fields: Tuple[str, ...]
    semantic_fields: Tuple[str, ...]


DEFAULT_EQUIVALENCES: Dict[str, SemanticEquivalence] = {
    ArtifactKind.SEMANTIC_GRAPH.value: SemanticEquivalence(
        artifact_kind=ArtifactKind.SEMANTIC_GRAPH,
        identifying_fields=("module_id",),
        semantic_fields=("nodes", "edges", "clock_domains", "ownership_map"),
    ),
    ArtifactKind.CANONICAL_IR.value: SemanticEquivalence(
        artifact_kind=ArtifactKind.CANONICAL_IR,
        identifying_fields=("module_id",),
        semantic_fields=("instructions", "declarations", "graph",
                         "contracts", "capabilities", "clocks"),
    ),
    ArtifactKind.SNAPSHOT.value: SemanticEquivalence(
        artifact_kind=ArtifactKind.SNAPSHOT,
        identifying_fields=("graph_id",),
        semantic_fields=("state_snapshots", "active_contracts",
                         "language_version", "ir_version"),
    ),
    ArtifactKind.CERTIFICATE.value: SemanticEquivalence(
        artifact_kind=ArtifactKind.CERTIFICATE,
        identifying_fields=("contract_version", "certification_method"),
        semantic_fields=("metric", "requested_margin",
                         "measured_upper_bound", "result",
                         "consumed_inputs", "clock_position"),
    ),
}


def semantic_equivalent(kind: ArtifactKind, a: Mapping[str, Any],
                        b: Mapping[str, Any]) -> bool:
    """Return True iff two canonical-form artifacts of ``kind`` agree
    on every declared semantic field.

    Version-envelope fields (``__aeon_artifact_version__``) are
    ignored — migration by definition changes them.
    """

    eq = DEFAULT_EQUIVALENCES.get(kind.value)
    if eq is None:
        raise MigrationError(
            "NO_EQUIVALENCE_HOOK",
            f"no SemanticEquivalence registered for {kind.value!r}",
        )
    for f in eq.semantic_fields:
        if canonical_value(a.get(f)) != canonical_value(b.get(f)):
            return False
    return True
