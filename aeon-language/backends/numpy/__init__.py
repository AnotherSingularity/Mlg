"""Aeon NumPy host backend.

An independent execution backend that lowers the reference
substrate's integration step into NumPy operations. The kernel
imports remain NumPy-free; NumPy is used only inside this backend
module.

The backend is not a wrapper around ``aeon.backends.python``: it
implements the integration arithmetic on numpy arrays via
``NumpyContractiveRecursion``, an alternative substrate that
satisfies the same ``RecursionSubstrate`` protocol. Both backends
share IR, schemas, contracts, and negotiation logic — they
differ only in numerical representation, which is the entire
point of a differential parity harness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence, Tuple

import numpy as np

from aeon.clock import ClockPosition
from aeon.contraction import (
    CertificationMethod,
    ContractionCertificate,
    ContractionResult,
    Contractive,
    Metric,
    PrecisionPolicy,
)
from aeon.core import Certificate, SemVer, Validity
from aeon.ir import IRModule
from aeon.port import ReadRequest, SignalSourcePort
from aeon.provenance import make_identity
from aeon.recursion import (
    Contribution,
    Emission,
    ManifoldInput,
    ProjectionContract,
    RecursionState,
    RecursionStepResult,
    RecursionSubstrate,
    RecursionSnapshot,
)
from aeon.serialization import canonical_bytes
from aeon.signal import SignalFrame, new_signal_frame
from aeon.verifier import DomainBounds, TransitionDefinition, VerifierInput, verify

from runtime.interpreter import ExecutionOutcome, Interpreter


# ---------------------------------------------------------------------------
# Backend descriptor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NumpyBackendInfo:
    name: str = "aeon.backends.numpy"
    version: str = "0.1.0-dev"
    numerical_tolerance: float = 1e-12  # elementwise float64 tolerance
    supported_ir_version: str = "0.1.0-dev"
    numpy_version: str = np.__version__


# ---------------------------------------------------------------------------
# NumPy contractive recursion
# ---------------------------------------------------------------------------


class NumpyContractiveRecursion:
    """RecursionSubstrate implemented on numpy float64 arrays.

    Uses the same update rule as ReferenceContractiveRecursion:

        next = margin * (decay * s + (1-decay) * mean(a))

    but the arithmetic is performed by numpy, not by Python.
    Producing byte-identical certificates from a different
    computational path is the differential parity signal.
    """

    IMPL_ID = "aeon.backends.numpy.NumpyContractiveRecursion/0.1.0-dev"

    def __init__(self, dimension: int, contract: Contractive,
                 substrate_id: str = "recursion.numpy/0.1.0-dev",
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
            raise ValueError(
                f"NumpyContractiveRecursion supports L2 and Linf metrics; "
                f"got {contract.metric.value}"
            )
        self.dimension = dimension
        self.contract = contract
        self.substrate_id = substrate_id
        self.decay = decay
        self.contract_version = SemVer(0, 1, 0, "dev")
        self.declared_input_radius = declared_input_radius
        self.declared_state_radius = declared_state_radius
        self.declared_projection_scale_upper = declared_projection_scale_upper

    def initialize(self, config: Mapping[str, Any], seed: int) -> RecursionState:
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
            id=ident, payload=payload, clock_position=clock,
            dimension=self.dimension, validity=Validity.UNCERTIFIED,
        )

    def project(self, source_frame: SignalFrame[Any],
                projection_contract: ProjectionContract) -> ManifoldInput:
        # Uses numpy dot/scale but produces the SAME canonical
        # ManifoldInput (float list). This is deliberate: the
        # ManifoldInput identity must be byte-identical to the
        # Python reference's for cross-backend replay to work.
        payload_arr = np.asarray(source_frame.payload, dtype=np.float64)
        if payload_arr.shape != (projection_contract.input_shape[0],):
            raise ValueError(
                f"project: shape {payload_arr.shape} != "
                f"{projection_contract.input_shape}"
            )
        scaled = payload_arr * projection_contract.scale
        payload = tuple(float(x) for x in scaled.tolist())
        ident = make_identity("manifold_input", {
            "projection_id": projection_contract.id,
            "source_id": source_frame.source_id,
            "origin_frame_id": source_frame.id.digest,
            "payload": list(payload),
        })
        return ManifoldInput(
            id=ident, projection_id=projection_contract.id,
            source_id=source_frame.source_id,
            origin_frame_id=source_frame.id.digest, payload=payload,
        )

    def integrate(self, inputs: Sequence[ManifoldInput],
                  state: RecursionState,
                  clock_position: ClockPosition) -> RecursionStepResult:
        if clock_position.domain_id != "integration":
            raise ValueError("integrate: clock_position must be integration")
        if clock_position.tick < state.clock_position.tick:
            raise ValueError("integrate: causality violation")

        # Aggregate via numpy.
        if not inputs:
            aggregate = np.zeros(self.dimension, dtype=np.float64)
        else:
            stack = np.stack([np.asarray(inp.payload, dtype=np.float64) for inp in inputs])
            aggregate = stack.mean(axis=0)

        state_arr = np.asarray(state.payload, dtype=np.float64)
        margin = self.contract.requested_margin
        decay = self.decay
        next_arr = margin * (decay * state_arr + (1.0 - decay) * aggregate)

        numerically_invalid = bool(
            (~np.isfinite(next_arr)).any()
        )

        consumed = tuple(sorted(inp.id.digest for inp in inputs))

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
        ))

        if numerically_invalid:
            result = ContractionResult.NUMERICALLY_INVALID
            measured = None
            reason = "NaN/Inf detected in next_payload"
            next_payload = state.payload
            next_state_ident = state.id
        else:
            result = report.result
            measured = report.computed_upper_bound
            reason = report.reason
            # Convert to plain tuple for canonical identity computation.
            next_payload = tuple(float(x) for x in next_arr.tolist())
            next_state_ident = make_identity("recursion_state", {
                "substrate": self.substrate_id,
                "parent": state.id.digest,
                "payload": list(next_payload),
                "clock_domain_id": clock_position.domain_id,
                "clock_tick": clock_position.tick,
                "consumed_inputs": list(consumed),
            })

        cert = ContractionCertificate(
            contract_version=self.contract_version,
            metric=self.contract.metric,
            requested_margin=margin,
            measured_upper_bound=measured,
            numerical_tolerance=self.contract.numerical_tolerance,
            arithmetic_precision=self.contract.precision_policy,
            certification_method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
            result=result,
            consumed_inputs=consumed,
            clock_position=clock_position,
            method_params={
                "parameterization": "linear_scaled_convex_mix",
                "decay": decay,
                "verifier": "aeon.verifier/0.1.0-dev",
                "verifier_reason": reason,
                "computation": "numpy.float64",
            },
        )

        if result is ContractionResult.NUMERICALLY_INVALID:
            next_state = RecursionState(
                id=state.id, payload=state.payload,
                clock_position=state.clock_position, dimension=state.dimension,
                validity=Validity.INVALID,
            )
        else:
            next_state = RecursionState(
                id=next_state_ident, payload=next_payload,
                clock_position=clock_position, dimension=self.dimension,
                validity=(Validity.VALID
                          if result in (ContractionResult.PROVEN_CONTRACTIVE,
                                        ContractionResult.BOUNDED_CONTRACTIVE)
                          else Validity.UNCERTIFIED),
            )

        by_source: dict[str, list[str]] = {}
        magnitudes: dict[str, float] = {}
        for inp in inputs:
            by_source.setdefault(inp.source_id, []).append(inp.origin_frame_id)
            mag_arr = np.abs(np.asarray(inp.payload, dtype=np.float64))
            mag = float(mag_arr.max()) if mag_arr.size else 0.0
            magnitudes[inp.source_id] = max(magnitudes.get(inp.source_id, 0.0), mag)
        contributions = tuple(
            Contribution(
                source_id=src,
                frame_ids=tuple(sorted(by_source[src])),
                magnitude=magnitudes[src],
            )
            for src in sorted(by_source.keys())
        )

        emission_payload = (state.payload
                            if result is ContractionResult.NUMERICALLY_INVALID
                            else next_payload)
        outputs = (Emission(payload=emission_payload, clock_position=clock_position),)

        transition_cert = Certificate(
            contract_id="Contractive",
            contract_version=self.contract_version,
            method=CertificationMethod.SYMBOLIC_PARAMETERIZATION.value,
            subject_id=next_state.id,
            inputs_ids=tuple(inp.id for inp in inputs),
            clock_position=(clock_position.domain_id, clock_position.tick),
            result=result.value,
            detail={"margin": margin, "decay": decay, "backend": "numpy"},
        )

        return RecursionStepResult(
            next_state=next_state, outputs=outputs,
            source_contributions=contributions, unresolved_inputs=(),
            contraction_certificate=cert, transition_certificate=transition_cert,
        )

    def read(self, state: RecursionState, request: ReadRequest) -> Any:
        if request.kind == "vector":
            return tuple(state.payload)
        if request.kind == "dimension":
            return state.dimension
        return None

    def snapshot(self, state: RecursionState) -> RecursionSnapshot:
        canonical = canonical_bytes({
            "substrate": self.substrate_id,
            "payload": list(state.payload),
            "clock_domain_id": state.clock_position.domain_id,
            "clock_tick": state.clock_position.tick,
            "dimension": self.dimension,
        })
        ident = make_identity("recursion_snapshot", {
            "of": state.id.digest, "substrate": self.substrate_id,
        })
        return RecursionSnapshot(
            id=ident, canonical=canonical, dimension=self.dimension,
            version="0.1.0-dev",
        )

    def restore(self, snapshot: RecursionSnapshot) -> RecursionState:
        import json
        data = json.loads(snapshot.canonical.decode("utf-8"))
        payload = tuple(float(x) for x in data["payload"])
        clock = ClockPosition(
            domain_id=data["clock_domain_id"], tick=int(data["clock_tick"]),
        )
        ident = make_identity("recursion_state", {
            "restore_from": snapshot.id.digest,
            "payload": list(payload),
            "clock_domain_id": clock.domain_id, "clock_tick": clock.tick,
        })
        return RecursionState(
            id=ident, payload=payload, clock_position=clock,
            dimension=self.dimension, validity=Validity.UNCERTIFIED,
        )


# ---------------------------------------------------------------------------
# Backend adapter
# ---------------------------------------------------------------------------


class NumpyBackend:
    info = NumpyBackendInfo()

    def execute(
        self,
        module: IRModule,
        *,
        sources: Mapping[str, SignalSourcePort[Any]],
        substrates: Mapping[str, RecursionSubstrate],
        seed: int = 0,
    ) -> ExecutionOutcome:
        # The interpreter is backend-agnostic; the substrate provided
        # here is a NumpyContractiveRecursion, so all arithmetic in
        # RECURSION_INTEGRATE happens through numpy.
        return Interpreter(module, sources=sources, substrates=substrates, seed=seed).run()
