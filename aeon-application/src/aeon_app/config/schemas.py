"""Configuration schemas.

Every configuration is a frozen dataclass with:

- a stable ``schema_version``;
- a stable ``component_id`` where applicable;
- an ``implementation`` identifier;
- a canonical form via :func:`to_canonical`.

Configuration resolution rejects unknown required fields,
incompatible versions, duplicate component identities, invalid
dimensions, missing required capabilities, undeclared clock
crossings, unsupported precision, and invalid contraction
margins.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Sequence, Tuple

from aeon.serialization import canonical_bytes, canonical_value, digest

from .. import (
    APPLICATION_CONFIG_SCHEMA_VERSION,
    APPLICATION_VERSION,
)

# Reserved capability names — must match Aeon Language.
REQUIRED_TIER = frozenset({"VectorRead", "VectorDrive", "PerTokenStep"})
OPTIONAL_TIER = frozenset({
    "MatrixRead", "LayerRead", "DecayControl",
    "AssociationWrite", "ConfigurableCadence",
    "AttentionMapRead", "PerStepTransition", "Snapshot", "Restore",
})


class ConfigError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code


# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceConfig:
    schema_version: str
    component_id: str            # stable name within an application
    implementation: str          # e.g. "aeon_app.sources.attention:AttentionSource"
    dimension: int
    clock: str                   # source-local clock name
    numerical_precision: str = "float64"
    seed: int = 0
    required_capabilities: Tuple[str, ...] = ()
    offered_capabilities: Tuple[str, ...] = ()
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_canonical(self) -> dict:
        return canonical_value({
            "schema_version": self.schema_version,
            "component_id": self.component_id,
            "implementation": self.implementation,
            "dimension": self.dimension,
            "clock": self.clock,
            "numerical_precision": self.numerical_precision,
            "seed": self.seed,
            "required_capabilities": sorted(self.required_capabilities),
            "offered_capabilities": sorted(self.offered_capabilities),
            "parameters": dict(self.parameters),
        })


@dataclass(frozen=True)
class ProjectionConfig:
    schema_version: str
    component_id: str
    implementation: str
    source_component: str
    target_component: str
    input_shape: Tuple[int, ...]
    output_shape: Tuple[int, ...]
    numerical_precision: str = "float64"
    clock_relation: Optional[str] = None
    scale_upper_bound: float = 1.0
    contract: str = "Bounded"
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_canonical(self) -> dict:
        return canonical_value({
            "schema_version": self.schema_version,
            "component_id": self.component_id,
            "implementation": self.implementation,
            "source_component": self.source_component,
            "target_component": self.target_component,
            "input_shape": list(self.input_shape),
            "output_shape": list(self.output_shape),
            "numerical_precision": self.numerical_precision,
            "clock_relation": self.clock_relation,
            "scale_upper_bound": self.scale_upper_bound,
            "contract": self.contract,
            "parameters": dict(self.parameters),
        })


@dataclass(frozen=True)
class RecursionConfig:
    schema_version: str
    component_id: str
    implementation: str
    dimension: int
    clock: str
    contraction_margin: float
    decay: float = 0.5
    numerical_precision: str = "float64"
    declared_input_radius: Optional[float] = 10.0
    declared_state_radius: Optional[float] = 10.0
    declared_projection_scale_upper: Optional[float] = 1.0

    def to_canonical(self) -> dict:
        return canonical_value({
            "schema_version": self.schema_version,
            "component_id": self.component_id,
            "implementation": self.implementation,
            "dimension": self.dimension,
            "clock": self.clock,
            "contraction_margin": self.contraction_margin,
            "decay": self.decay,
            "numerical_precision": self.numerical_precision,
            "declared_input_radius": self.declared_input_radius,
            "declared_state_radius": self.declared_state_radius,
            "declared_projection_scale_upper": self.declared_projection_scale_upper,
        })


@dataclass(frozen=True)
class ClockConfig:
    schema_version: str
    id: str
    kind: str                # Token, Integration, Segment, UserDefined
    aggregates_from: Optional[str] = None
    window_size: Optional[int] = None

    def to_canonical(self) -> dict:
        return canonical_value({
            "schema_version": self.schema_version,
            "id": self.id, "kind": self.kind,
            "aggregates_from": self.aggregates_from,
            "window_size": self.window_size,
        })


@dataclass(frozen=True)
class FeedbackConfig:
    schema_version: str
    id: str
    origin: str              # component_id of the origin (recursion)
    destination: str         # component_id of the destination (a source)
    projection: str          # projection component_id
    gate: float = 0.0
    required_capability: Optional[str] = None
    clock_relation: Optional[str] = None
    scope: str = "PROJECTED_RECURSION"

    def to_canonical(self) -> dict:
        return canonical_value({
            "schema_version": self.schema_version,
            "id": self.id, "origin": self.origin,
            "destination": self.destination,
            "projection": self.projection,
            "gate": self.gate,
            "required_capability": self.required_capability,
            "clock_relation": self.clock_relation,
            "scope": self.scope,
        })


@dataclass(frozen=True)
class BackendConfig:
    schema_version: str
    id: str                  # "python" or "numpy"
    version: str
    numerical_tolerance: float = 0.0

    def to_canonical(self) -> dict:
        return canonical_value({
            "schema_version": self.schema_version,
            "id": self.id, "version": self.version,
            "numerical_tolerance": self.numerical_tolerance,
        })


@dataclass(frozen=True)
class TrainingConfig:
    schema_version: str
    enabled: bool = False
    loss_terms: Tuple[str, ...] = ()
    learning_rate: float = 1e-3
    seed: int = 0

    def to_canonical(self) -> dict:
        return canonical_value({
            "schema_version": self.schema_version,
            "enabled": self.enabled,
            "loss_terms": list(self.loss_terms),
            "learning_rate": self.learning_rate,
            "seed": self.seed,
        })


@dataclass(frozen=True)
class InferenceConfig:
    schema_version: str
    ticks: int = 4                     # source-clock ticks to run

    def to_canonical(self) -> dict:
        return canonical_value({
            "schema_version": self.schema_version,
            "ticks": self.ticks,
        })


@dataclass(frozen=True)
class SnapshotConfig:
    schema_version: str
    schema_version_snapshot: str      # nested snapshot schema
    include_random_state: bool = True
    include_event_log: bool = True

    def to_canonical(self) -> dict:
        return canonical_value({
            "schema_version": self.schema_version,
            "schema_version_snapshot": self.schema_version_snapshot,
            "include_random_state": self.include_random_state,
            "include_event_log": self.include_event_log,
        })


@dataclass(frozen=True)
class ObservabilityConfig:
    schema_version: str
    tracing_enabled: bool = True
    metric_categories: Tuple[str, ...] = ()

    def to_canonical(self) -> dict:
        return canonical_value({
            "schema_version": self.schema_version,
            "tracing_enabled": self.tracing_enabled,
            "metric_categories": sorted(self.metric_categories),
        })


# ---------------------------------------------------------------------------
# ApplicationConfig
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApplicationConfig:
    schema_version: str
    application_version: str
    runtime_mode: str                 # REFERENCE / DEVELOPMENT / CERTIFIED
    graph_name: str
    sources: Tuple[SourceConfig, ...]
    projections: Tuple[ProjectionConfig, ...]
    recursion: RecursionConfig
    clocks: Tuple[ClockConfig, ...]
    feedback: Tuple[FeedbackConfig, ...]
    backend: BackendConfig
    inference: InferenceConfig
    training: TrainingConfig
    snapshot: SnapshotConfig
    observability: ObservabilityConfig

    def to_canonical(self) -> dict:
        return canonical_value({
            "schema_version": self.schema_version,
            "application_version": self.application_version,
            "runtime_mode": self.runtime_mode,
            "graph_name": self.graph_name,
            "sources": sorted(
                [s.to_canonical() for s in self.sources],
                key=lambda d: d["component_id"],
            ),
            "projections": sorted(
                [p.to_canonical() for p in self.projections],
                key=lambda d: d["component_id"],
            ),
            "recursion": self.recursion.to_canonical(),
            "clocks": sorted(
                [c.to_canonical() for c in self.clocks],
                key=lambda d: d["id"],
            ),
            "feedback": sorted(
                [f.to_canonical() for f in self.feedback],
                key=lambda d: d["id"],
            ),
            "backend": self.backend.to_canonical(),
            "inference": self.inference.to_canonical(),
            "training": self.training.to_canonical(),
            "snapshot": self.snapshot.to_canonical(),
            "observability": self.observability.to_canonical(),
        })

    def digest(self) -> str:
        return digest(self.to_canonical())

    def semantic_canonical(self) -> dict:
        """Same as ``to_canonical`` but excludes fields that only
        affect observability, not semantics. Used to compute the
        graph identity so that toggling tracing does not change
        semantic outputs (mandate §20)."""
        c = self.to_canonical()
        c.pop("observability", None)
        return c

    def semantic_digest(self) -> str:
        return digest(self.semantic_canonical())


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


SUPPORTED_PRECISIONS = frozenset({"float64", "float32", "bf16"})
SUPPORTED_MODES = frozenset({"REFERENCE", "DEVELOPMENT", "CERTIFIED"})
SUPPORTED_BACKENDS = frozenset({"python", "numpy"})


def resolve(config: ApplicationConfig) -> ApplicationConfig:
    """Validate an ApplicationConfig; return the same value if OK,
    otherwise raise ConfigError."""

    if config.schema_version != APPLICATION_CONFIG_SCHEMA_VERSION:
        raise ConfigError(
            "SCHEMA_VERSION_MISMATCH",
            f"expected {APPLICATION_CONFIG_SCHEMA_VERSION}, "
            f"got {config.schema_version!r}",
        )
    if config.application_version != APPLICATION_VERSION:
        raise ConfigError(
            "APP_VERSION_MISMATCH",
            f"expected {APPLICATION_VERSION}, got "
            f"{config.application_version!r}",
        )
    if config.runtime_mode not in SUPPORTED_MODES:
        raise ConfigError(
            "UNKNOWN_RUNTIME_MODE",
            f"runtime_mode {config.runtime_mode!r} not in {sorted(SUPPORTED_MODES)}",
        )
    if config.backend.id not in SUPPORTED_BACKENDS:
        raise ConfigError(
            "UNSUPPORTED_BACKEND",
            f"backend {config.backend.id!r} not in {sorted(SUPPORTED_BACKENDS)}",
        )
    if not config.sources:
        raise ConfigError("NO_SOURCES", "application requires at least one source")

    # Component-id uniqueness across sources, projections, recursion, feedback.
    ids: List[str] = [s.component_id for s in config.sources]
    ids += [p.component_id for p in config.projections]
    ids.append(config.recursion.component_id)
    ids += [f.id for f in config.feedback]
    dup = _first_duplicate(ids)
    if dup is not None:
        raise ConfigError("DUPLICATE_COMPONENT_ID",
                          f"component id {dup!r} declared more than once")

    # Sources
    for s in config.sources:
        if s.dimension <= 0:
            raise ConfigError("INVALID_DIMENSION",
                              f"source {s.component_id}: dimension must be > 0")
        if s.numerical_precision not in SUPPORTED_PRECISIONS:
            raise ConfigError("UNSUPPORTED_PRECISION",
                              f"source {s.component_id}: precision "
                              f"{s.numerical_precision!r} not supported")
        for c in s.offered_capabilities:
            if c not in REQUIRED_TIER and c not in OPTIONAL_TIER:
                raise ConfigError("UNKNOWN_CAPABILITY",
                                  f"source {s.component_id}: capability {c!r} not reserved")
        missing = [c for c in REQUIRED_TIER if c not in s.offered_capabilities]
        if missing:
            raise ConfigError("MISSING_REQUIRED_CAPABILITY",
                              f"source {s.component_id}: missing REQUIRED capability "
                              f"{sorted(missing)}")

    # Recursion
    if config.recursion.dimension <= 0:
        raise ConfigError("INVALID_DIMENSION",
                          f"recursion {config.recursion.component_id}: dimension must be > 0")
    if not (0.0 < config.recursion.contraction_margin < 1.0):
        raise ConfigError("INVALID_CONTRACTION_MARGIN",
                          f"recursion contraction_margin must lie in (0, 1)")
    if config.recursion.numerical_precision not in SUPPORTED_PRECISIONS:
        raise ConfigError("UNSUPPORTED_PRECISION",
                          f"recursion precision {config.recursion.numerical_precision!r}"
                          " not supported")

    # Projections
    source_ids = {s.component_id for s in config.sources}
    recursion_ids = {config.recursion.component_id}
    known = source_ids | recursion_ids
    for p in config.projections:
        if p.source_component not in known:
            raise ConfigError("UNKNOWN_PROJECTION_SOURCE",
                              f"projection {p.component_id}: source {p.source_component!r}"
                              " not declared")
        if p.target_component not in known:
            raise ConfigError("UNKNOWN_PROJECTION_TARGET",
                              f"projection {p.component_id}: target {p.target_component!r}"
                              " not declared")
        if not (0.0 <= p.scale_upper_bound <= 1.0):
            raise ConfigError("INVALID_PROJECTION_SCALE",
                              f"projection {p.component_id}: scale_upper_bound must lie in [0, 1]")
        if p.numerical_precision not in SUPPORTED_PRECISIONS:
            raise ConfigError("UNSUPPORTED_PRECISION",
                              f"projection {p.component_id}: precision"
                              f" {p.numerical_precision!r} not supported")

    # Clocks
    clock_ids = {c.id for c in config.clocks}
    for s in config.sources:
        if s.clock not in clock_ids:
            raise ConfigError("UNDECLARED_CLOCK",
                              f"source {s.component_id} references undeclared "
                              f"clock {s.clock!r}")
    if config.recursion.clock not in clock_ids:
        raise ConfigError("UNDECLARED_CLOCK",
                          f"recursion references undeclared clock "
                          f"{config.recursion.clock!r}")

    # Clock crossings must be declared: any source clock that differs
    # from the recursion clock must appear as an `aggregates_from`
    # relation on the recursion clock.
    integration_clock = next(c for c in config.clocks if c.id == config.recursion.clock)
    for s in config.sources:
        if s.clock != config.recursion.clock:
            if integration_clock.aggregates_from != s.clock:
                raise ConfigError(
                    "UNDECLARED_CLOCK_CROSSING",
                    f"source {s.component_id} clock {s.clock!r} does not aggregate into "
                    f"recursion clock {config.recursion.clock!r}",
                )
            if integration_clock.window_size is None or integration_clock.window_size <= 0:
                raise ConfigError(
                    "INVALID_WINDOW_SIZE",
                    f"clock {integration_clock.id!r} aggregates_from is set but "
                    "window_size is missing or non-positive",
                )

    # Feedback references
    for f in config.feedback:
        if f.origin != config.recursion.component_id:
            raise ConfigError("INVALID_FEEDBACK_ORIGIN",
                              f"feedback {f.id!r}: origin must be the recursion component")
        if f.destination not in source_ids:
            raise ConfigError("INVALID_FEEDBACK_DESTINATION",
                              f"feedback {f.id!r}: destination {f.destination!r} not a source")
        if f.projection not in {p.component_id for p in config.projections}:
            raise ConfigError("INVALID_FEEDBACK_PROJECTION",
                              f"feedback {f.id!r}: projection {f.projection!r} not declared")
        if f.gate < 0.0:
            raise ConfigError("INVALID_FEEDBACK_GATE",
                              f"feedback {f.id!r}: gate must be >= 0")
        if f.gate > 0.0 and f.required_capability is None:
            raise ConfigError("FEEDBACK_CAPABILITY_MISSING",
                              f"feedback {f.id!r}: nonzero gate requires "
                              "a required_capability declaration")

    return config


def _first_duplicate(items: Sequence[str]) -> Optional[str]:
    seen = set()
    for i in items:
        if i in seen:
            return i
        seen.add(i)
    return None


# ---------------------------------------------------------------------------
# Reference config
# ---------------------------------------------------------------------------


def reference_config(*, mode: str = "REFERENCE") -> ApplicationConfig:
    """Construct the canonical reference configuration used by
    the example program (Gate L §22).
    """

    sv = APPLICATION_CONFIG_SCHEMA_VERSION
    clocks = (
        ClockConfig(schema_version=sv, id="source", kind="Token"),
        ClockConfig(schema_version=sv, id="integration", kind="Integration",
                    aggregates_from="source", window_size=2),
    )
    sources = (
        SourceConfig(
            schema_version=sv,
            component_id="attention",
            implementation="aeon_app.sources.attention:AttentionSource",
            dimension=4, clock="source", seed=1,
            required_capabilities=("VectorRead", "VectorDrive", "PerTokenStep"),
            offered_capabilities=("VectorRead", "VectorDrive", "PerTokenStep",
                                  "AttentionMapRead"),
        ),
        SourceConfig(
            schema_version=sv,
            component_id="recurrent",
            implementation="aeon_app.sources.recurrent:PersistentRecurrentSource",
            dimension=4, clock="source", seed=2,
            required_capabilities=("VectorRead", "VectorDrive", "PerTokenStep"),
            offered_capabilities=("VectorRead", "VectorDrive", "PerTokenStep",
                                  "MatrixRead", "DecayControl", "PerStepTransition",
                                  "Snapshot", "Restore"),
        ),
    )
    projections = (
        ProjectionConfig(
            schema_version=sv, component_id="attention_to_recursion",
            implementation="aeon_app.projections.attention_to_recursion:AttentionToRecursion",
            source_component="attention", target_component="recursion",
            input_shape=(4,), output_shape=(4,), clock_relation="source_to_integration",
            scale_upper_bound=1.0, contract="Bounded",
        ),
        ProjectionConfig(
            schema_version=sv, component_id="recurrent_to_recursion",
            implementation="aeon_app.projections.recurrent_to_recursion:RecurrentToRecursion",
            source_component="recurrent", target_component="recursion",
            input_shape=(4,), output_shape=(4,), clock_relation="source_to_integration",
            scale_upper_bound=1.0, contract="Bounded",
        ),
        ProjectionConfig(
            schema_version=sv, component_id="feedback_to_attention",
            implementation="aeon_app.projections.feedback:RecursionToAttentionFeedback",
            source_component="recursion", target_component="attention",
            input_shape=(4,), output_shape=(4,), clock_relation="integration_to_source",
            scale_upper_bound=0.5, contract="Bounded",
        ),
        ProjectionConfig(
            schema_version=sv, component_id="feedback_to_recurrent",
            implementation="aeon_app.projections.feedback:RecursionToRecurrentFeedback",
            source_component="recursion", target_component="recurrent",
            input_shape=(4,), output_shape=(4,), clock_relation="integration_to_source",
            scale_upper_bound=0.5, contract="Bounded",
        ),
    )
    feedback = (
        FeedbackConfig(schema_version=sv, id="feedback.attention",
                       origin="recursion", destination="attention",
                       projection="feedback_to_attention",
                       gate=0.0, required_capability="VectorDrive",
                       clock_relation="integration_to_source",
                       scope="PROJECTED_RECURSION"),
        FeedbackConfig(schema_version=sv, id="feedback.recurrent",
                       origin="recursion", destination="recurrent",
                       projection="feedback_to_recurrent",
                       gate=0.0, required_capability="VectorDrive",
                       clock_relation="integration_to_source",
                       scope="PROJECTED_RECURSION"),
    )
    recursion = RecursionConfig(
        schema_version=sv, component_id="recursion",
        implementation="aeon_app.recursion.substrate:ApplicationContractiveRecursion",
        dimension=4, clock="integration",
        contraction_margin=0.9, decay=0.5,
    )
    return ApplicationConfig(
        schema_version=sv,
        application_version=APPLICATION_VERSION,
        runtime_mode=mode,
        graph_name="reference_two_sources",
        sources=sources,
        projections=projections,
        recursion=recursion,
        clocks=clocks,
        feedback=feedback,
        backend=BackendConfig(schema_version=sv, id="python",
                              version="0.1.0", numerical_tolerance=0.0),
        inference=InferenceConfig(schema_version=sv, ticks=4),
        training=TrainingConfig(schema_version=sv, enabled=False),
        snapshot=SnapshotConfig(schema_version=sv,
                                schema_version_snapshot="0.1.0"),
        observability=ObservabilityConfig(
            schema_version=sv, tracing_enabled=True,
            metric_categories=("source_step_duration", "integration_duration",
                               "window_occupancy", "certificate_status"),
        ),
    )
