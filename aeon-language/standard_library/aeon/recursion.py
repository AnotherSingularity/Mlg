"""aeon.recursion — Recursion substrate contract + reference substrate.

Implements the ``RecursionSubstrate`` protocol from
``06-RECURSION.md`` and a small pure-Python reference substrate.

The reference substrate is deliberately not a source-specific
optimization. It contains no branches on source implementation
class or framework. Every integration produces a fully-populated
:class:`~aeon.contraction.ContractionCertificate`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Generic, Iterable, Mapping, Optional, Protocol, Sequence, Tuple, TypeVar

# Type-checking-only import to avoid a circular dependency at import
# time. The verifier is imported inside integrate() at call time.

from .clock import ClockPosition
from .contraction import (
    CertificationMethod,
    ContractionCertificate,
    ContractionResult,
    Contractive,
    Metric,
    PrecisionPolicy,
)
from .core import Certificate, Identity, SemVer, Validity
from .port import ReadRequest
from .provenance import make_identity
from .serialization import canonical_value, digest
from .signal import SignalFrame

R = TypeVar("R")


# ---------------------------------------------------------------------------
# Projection contract
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectionContract:
    """Contract-bounded mapping from a source frame to a manifold input."""

    id: str
    source_id: str
    substrate_id: str
    input_shape: Tuple[int, ...]
    scale: float = 1.0

    def __post_init__(self) -> None:
        if not (0.0 <= self.scale <= 1.0):
            raise ValueError("ProjectionContract.scale must be in [0, 1]")


@dataclass(frozen=True)
class ManifoldInput:
    """Opaque, contract-bounded input into the Recursion substrate.

    Payloads are pure-Python vectors (tuple of floats). Backend
    implementations may swap this for framework-native tensors,
    but the kernel MUST NOT rely on any framework here.
    """

    id: Identity
    projection_id: str
    source_id: str
    origin_frame_id: str
    payload: Tuple[float, ...]

    def payload_digest(self) -> str:
        return digest(canonical_value(list(self.payload)))


def project_frame(frame: SignalFrame[Any],
                  contract: ProjectionContract) -> ManifoldInput:
    """Deterministic reference projection.

    The payload is expected to be a sequence of floats of the
    contract's declared input shape. The projection scales the
    input by ``contract.scale``. Shape mismatches raise; callers
    should convert this into a ContractViolation as appropriate.
    """

    payload = tuple(frame.payload) if isinstance(frame.payload, (list, tuple)) else None
    if payload is None:
        raise ValueError(
            f"project_frame: frame payload must be a sequence, got "
            f"{type(frame.payload).__name__}"
        )
    if len(payload) != contract.input_shape[0]:
        raise ValueError(
            f"project_frame: input shape mismatch "
            f"(expected {contract.input_shape[0]}, got {len(payload)})"
        )
    scaled = tuple(float(x) * contract.scale for x in payload)
    ident = make_identity("manifold_input", {
        "projection_id": contract.id,
        "source_id": frame.source_id,
        "origin_frame_id": frame.id.digest,
        "payload": list(scaled),
    })
    return ManifoldInput(
        id=ident,
        projection_id=contract.id,
        source_id=frame.source_id,
        origin_frame_id=frame.id.digest,
        payload=scaled,
    )


# ---------------------------------------------------------------------------
# RecursionState + StepResult (spec 06 §2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecursionState:
    id: Identity
    payload: Tuple[float, ...]
    clock_position: ClockPosition
    dimension: int
    validity: Validity = Validity.UNCERTIFIED


@dataclass(frozen=True)
class Contribution:
    source_id: str
    frame_ids: Tuple[str, ...]
    magnitude: float  # L2 magnitude of the contribution


@dataclass(frozen=True)
class UnresolvedInput:
    projection_id: str
    reason: str


@dataclass(frozen=True)
class Emission:
    """A Recursion output frame."""

    payload: Tuple[float, ...]
    clock_position: ClockPosition


@dataclass(frozen=True)
class RecursionStepResult:
    next_state: RecursionState
    outputs: Tuple[Emission, ...]
    source_contributions: Tuple[Contribution, ...]      # sorted by source_id
    unresolved_inputs: Tuple[UnresolvedInput, ...]
    contraction_certificate: ContractionCertificate
    transition_certificate: Certificate[RecursionState]


# ---------------------------------------------------------------------------
# RecursionSubstrate protocol
# ---------------------------------------------------------------------------


class RecursionSubstrate(Protocol):
    def initialize(self, config: Mapping[str, Any], seed: int) -> RecursionState: ...
    def project(self, source_frame: SignalFrame[Any],
                projection_contract: ProjectionContract) -> ManifoldInput: ...
    def integrate(self, inputs: Sequence[ManifoldInput],
                  state: RecursionState,
                  clock_position: ClockPosition) -> RecursionStepResult: ...
    def read(self, state: RecursionState, request: ReadRequest) -> Any: ...
    def snapshot(self, state: RecursionState) -> "RecursionSnapshot": ...
    def restore(self, snapshot: "RecursionSnapshot") -> RecursionState: ...


@dataclass(frozen=True)
class RecursionSnapshot:
    id: Identity
    canonical: bytes
    dimension: int
    version: str


# ---------------------------------------------------------------------------
# Reference contractive substrate
# ---------------------------------------------------------------------------


class ReferenceContractiveRecursion:
    """A small, deterministic, contractive recursion in pure Python.

    Update rule (per-step):

        next[i] = margin * ( decay * state[i]
                             + (1 - decay) * mean(inputs)[i] )

    The scalar ``margin`` is the declared Contractive margin and
    is strictly < 1, making the update **provably** L∞-contractive
    by construction (a symbolic method). The certificate records
    this as ``PROVEN_CONTRACTIVE`` via
    ``CertificationMethod.SYMBOLIC_PARAMETERIZATION``.

    This substrate MUST NOT branch on source implementation. It
    branches only on the number of provided ManifoldInputs (aggregate
    by mean) — a semantic operation.
    """

    def __init__(self, dimension: int, contract: Contractive,
                 substrate_id: str = "recursion.reference/0.1.0-dev",
                 decay: float = 0.5,
                 *,
                 declared_input_radius: Optional[float] = None,
                 declared_state_radius: Optional[float] = None,
                 declared_projection_scale_upper: Optional[float] = None):
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        if not (0.0 <= decay <= 1.0):
            raise ValueError("decay must be in [0, 1]")
        if contract.metric is not Metric.LINF and contract.metric is not Metric.L2:
            # Reference implementation supports L2 and L∞.
            raise ValueError(
                f"ReferenceContractiveRecursion supports L2 and Linf metrics; "
                f"got {contract.metric.value}"
            )
        self.dimension = dimension
        self.contract = contract
        self.substrate_id = substrate_id
        self.decay = decay
        self.contract_version = SemVer(0, 1, 0, "dev")
        # Domain bounds declared by the constructor caller. When
        # omitted the substrate MAY only claim BOUNDED_CONTRACTIVE
        # (verifier downgrades). Declaring bounds is what allows the
        # verifier to upgrade to PROVEN_CONTRACTIVE.
        self.declared_input_radius = declared_input_radius
        self.declared_state_radius = declared_state_radius
        self.declared_projection_scale_upper = declared_projection_scale_upper

    # -- protocol methods -------------------------------------------------

    def initialize(self, config: Mapping[str, Any], seed: int) -> RecursionState:
        # Deterministic zero initialization; ``seed`` is recorded in identity.
        payload = tuple(0.0 for _ in range(self.dimension))
        clock = ClockPosition("integration", 0)
        ident = make_identity("recursion_state", {
            "substrate": self.substrate_id,
            "seed": seed,
            "config": dict(config),
            "payload": list(payload),
            "clock_domain_id": clock.domain_id,
            "clock_tick": clock.tick,
        })
        return RecursionState(
            id=ident,
            payload=payload,
            clock_position=clock,
            dimension=self.dimension,
            validity=Validity.UNCERTIFIED,
        )

    def project(self, source_frame: SignalFrame[Any],
                projection_contract: ProjectionContract) -> ManifoldInput:
        return project_frame(source_frame, projection_contract)

    def integrate(self, inputs: Sequence[ManifoldInput],
                  state: RecursionState,
                  clock_position: ClockPosition) -> RecursionStepResult:
        if clock_position.domain_id != "integration":
            raise ValueError(
                "integrate: clock_position must be in the integration domain"
            )
        if clock_position.tick < state.clock_position.tick:
            # Causality: no future/past leakage.
            raise ValueError(
                "integrate: causality violation "
                f"({clock_position.tick} < {state.clock_position.tick})"
            )

        # Aggregate inputs by dimension-wise mean; empty aggregate = zeros.
        aggregate = self._mean_aggregate(inputs)

        margin = self.contract.requested_margin
        decay = self.decay
        next_payload = tuple(
            margin * (decay * s + (1.0 - decay) * a)
            for s, a in zip(state.payload, aggregate)
        )

        # Numerical sanity: detect NaN/Inf that would corrupt any
        # certificate the verifier could issue.
        numerically_invalid = any(
            v != v or math.isinf(v) for v in next_payload
        )

        # Consumed input digests (sorted for canonical determinism).
        consumed = tuple(sorted(inp.id.digest for inp in inputs))

        # Independent verification: hand the transition and its
        # declared domain bounds to aeon.verifier and let it
        # recompute the bound. The substrate MUST NOT emit its own
        # status field into the certificate — that is now the
        # verifier's job. C12: the verifier is invoked with
        # ArithmeticKind.EXACT_RATIONAL so PROVEN_CONTRACTIVE
        # verdicts are sound.
        from .contraction import ContractionScope
        from .verifier import (
            ArithmeticKind,
            DomainBounds,
            TransitionDefinition,
            VerifierInput,
            verify,
        )
        # The reference substrate certifies only the isolated
        # Recursion core map (mandate §3.4). A larger scope would
        # require projection and feedback bounds we do not yet
        # verify.
        report = verify(VerifierInput(
            transition=TransitionDefinition(
                kind="linear_scaled_convex_mix",
                parameters={"decay": decay, "margin": margin,
                            "dimension": self.dimension},
            ),
            contract=self.contract,
            domain=DomainBounds(
                input_radius=self.declared_input_radius,
                state_radius=self.declared_state_radius,
                projection_scale_upper=self.declared_projection_scale_upper,
            ),
            arithmetic=ArithmeticKind.EXACT_RATIONAL,
            scope=ContractionScope.RECURSION_CORE,
        ))

        if numerically_invalid:
            result = ContractionResult.NUMERICALLY_INVALID
            measured = None
            reason = "NaN/Inf detected in next_payload"
            # Per 11-ERROR-MODEL §7: a partial/corrupted execution
            # MUST NOT produce a successor visible to downstream
            # consumers; the pre-transition state remains current.
            next_payload = state.payload
        else:
            result = report.result
            measured = report.computed_upper_bound
            reason = report.reason

        cert = ContractionCertificate(
            contract_version=self.contract_version,
            metric=self.contract.metric,
            requested_margin=margin,
            measured_upper_bound=measured,
            numerical_tolerance=self.contract.numerical_tolerance,
            arithmetic_precision=self.contract.precision_policy,
            certification_method=(
                CertificationMethod.EXACT_RATIONAL_ARITHMETIC
                if result is ContractionResult.PROVEN_CONTRACTIVE
                else CertificationMethod.SYMBOLIC_PARAMETERIZATION
            ),
            result=result,
            consumed_inputs=consumed,
            clock_position=clock_position,
            certified_scope=report.certified_scope,
            arithmetic_kind=report.arithmetic.value,
            method_params={
                "parameterization": "linear_scaled_convex_mix",
                "decay": decay,
                "verifier": "aeon.verifier/0.1.0",
                "verifier_reason": reason,
            },
        )

        if result is not ContractionResult.NUMERICALLY_INVALID:
            next_state_ident = make_identity("recursion_state", {
                "substrate": self.substrate_id,
                "parent": state.id.digest,
                "payload": list(next_payload),
                "clock_domain_id": clock_position.domain_id,
                "clock_tick": clock_position.tick,
                "consumed_inputs": list(consumed),
            })
        else:
            next_state_ident = state.id
        if result is ContractionResult.NUMERICALLY_INVALID:
            # The "next" state is the unchanged prior state, but its
            # validity is marked INVALID for downstream consumers.
            next_state = RecursionState(
                id=state.id,
                payload=state.payload,
                clock_position=state.clock_position,
                dimension=state.dimension,
                validity=Validity.INVALID,
            )
        else:
            next_state = RecursionState(
                id=next_state_ident,
                payload=next_payload,
                clock_position=clock_position,
                dimension=self.dimension,
                validity=(Validity.VALID
                          if result in (ContractionResult.PROVEN_CONTRACTIVE,
                                        ContractionResult.BOUNDED_CONTRACTIVE)
                          else Validity.UNCERTIFIED),
            )

        # source_contributions: L∞ magnitude per source
        by_source: dict[str, list[str]] = {}
        magnitudes: dict[str, float] = {}
        for inp in inputs:
            by_source.setdefault(inp.source_id, []).append(inp.origin_frame_id)
            mag = max((abs(x) for x in inp.payload), default=0.0)
            magnitudes[inp.source_id] = max(magnitudes.get(inp.source_id, 0.0), mag)
        contributions = tuple(
            Contribution(
                source_id=src,
                frame_ids=tuple(sorted(by_source[src])),
                magnitude=magnitudes[src],
            )
            for src in sorted(by_source.keys())
        )

        # Do not emit a corrupted payload as an output.
        emission_payload = (state.payload
                            if result is ContractionResult.NUMERICALLY_INVALID
                            else next_payload)
        outputs = (Emission(payload=emission_payload, clock_position=clock_position),)

        transition_cert: Certificate[RecursionState] = Certificate(
            contract_id="Contractive",
            contract_version=self.contract_version,
            method=CertificationMethod.SYMBOLIC_PARAMETERIZATION.value,
            subject_id=next_state.id,
            inputs_ids=tuple(inp.id for inp in inputs),
            clock_position=(clock_position.domain_id, clock_position.tick),
            result=result.value,
            detail={"margin": margin, "decay": decay},
        )

        return RecursionStepResult(
            next_state=next_state,
            outputs=outputs,
            source_contributions=contributions,
            unresolved_inputs=(),
            contraction_certificate=cert,
            transition_certificate=transition_cert,
        )

    def read(self, state: RecursionState, request: ReadRequest) -> Any:
        if request.kind == "vector":
            return tuple(state.payload)
        if request.kind == "dimension":
            return state.dimension
        return None

    def snapshot(self, state: RecursionState) -> RecursionSnapshot:
        from .serialization import canonical_bytes
        canonical = canonical_bytes({
            "substrate": self.substrate_id,
            "payload": list(state.payload),
            "clock_domain_id": state.clock_position.domain_id,
            "clock_tick": state.clock_position.tick,
            "dimension": self.dimension,
        })
        ident = make_identity("recursion_snapshot", {
            "of": state.id.digest,
            "substrate": self.substrate_id,
        })
        return RecursionSnapshot(
            id=ident,
            canonical=canonical,
            dimension=self.dimension,
            version="0.1.0-dev",
        )

    def restore(self, snapshot: RecursionSnapshot) -> RecursionState:
        import json
        data = json.loads(snapshot.canonical.decode("utf-8"))
        payload = tuple(float(x) for x in data["payload"])
        clock = ClockPosition(
            domain_id=data["clock_domain_id"],
            tick=int(data["clock_tick"]),
        )
        ident = make_identity("recursion_state", {
            "restore_from": snapshot.id.digest,
            "payload": list(payload),
            "clock_domain_id": clock.domain_id,
            "clock_tick": clock.tick,
        })
        return RecursionState(
            id=ident,
            payload=payload,
            clock_position=clock,
            dimension=self.dimension,
            validity=Validity.UNCERTIFIED,
        )

    # -- helpers ----------------------------------------------------------

    def _mean_aggregate(self, inputs: Sequence[ManifoldInput]) -> Tuple[float, ...]:
        if not inputs:
            return tuple(0.0 for _ in range(self.dimension))
        acc = [0.0] * self.dimension
        for inp in inputs:
            if len(inp.payload) != self.dimension:
                raise ValueError(
                    "integrate: ManifoldInput dim "
                    f"{len(inp.payload)} != substrate dim {self.dimension}"
                )
            for i, v in enumerate(inp.payload):
                acc[i] += v
        n = len(inputs)
        return tuple(v / n for v in acc)
