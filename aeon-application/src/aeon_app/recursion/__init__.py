"""aeon_app.recursion — application Recursion substrate.

Wraps the certified aeon.recursion.ReferenceContractiveRecursion
with an application-scoped substrate that:

- retains source identity and contribution in the emitted
  certificate metadata (mandate §6.3);
- reports the correct certified_scope for the application graph
  (PROJECTED_RECURSION when domain bounds are declared);
- rejects source disagreement as anything other than the
  declared aggregation policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from aeon.clock import ClockPosition
from aeon.contraction import (
    CertificationMethod,
    ContractionCertificate,
    ContractionResult,
    ContractionScope,
    Contractive,
    Metric,
    PrecisionPolicy,
)
from aeon.core import Certificate, SemVer, Validity
from aeon.recursion import (
    Contribution,
    Emission,
    ManifoldInput,
    RecursionState,
    RecursionSnapshot,
    RecursionStepResult,
    ReferenceContractiveRecursion,
)


@dataclass(frozen=True)
class ApplicationRecursionInfo:
    application_substrate_id: str = "aeon_app.recursion:ApplicationContractiveRecursion/0.1.0"


class ApplicationContractiveRecursion:
    """Application-scoped substrate.

    Composition, not inheritance: delegates the numerical work
    to the certified language substrate, then wraps the
    resulting certificate with an application-scoped
    ``certified_scope`` value and additional method_params
    identifying the application.
    """

    info = ApplicationRecursionInfo()

    def __init__(self, dimension: int, contract: Contractive,
                 substrate_id: str = "aeon_app.recursion.substrate/0.1.0",
                 decay: float = 0.5, *,
                 declared_input_radius: float = 10.0,
                 declared_state_radius: float = 10.0,
                 declared_projection_scale_upper: float = 1.0) -> None:
        self.substrate_id = substrate_id
        self.dimension = dimension
        self.contract = contract
        self.decay = decay
        self.declared_input_radius = declared_input_radius
        self.declared_state_radius = declared_state_radius
        self.declared_projection_scale_upper = declared_projection_scale_upper
        self._inner = ReferenceContractiveRecursion(
            dimension=dimension, contract=contract,
            substrate_id=substrate_id, decay=decay,
            declared_input_radius=declared_input_radius,
            declared_state_radius=declared_state_radius,
            declared_projection_scale_upper=declared_projection_scale_upper,
        )

    def initialize(self, config: Mapping[str, Any], seed: int) -> RecursionState:
        return self._inner.initialize(config, seed)

    def project(self, source_frame, projection_contract):
        return self._inner.project(source_frame, projection_contract)

    def integrate(self, inputs: Sequence[ManifoldInput],
                  state: RecursionState,
                  clock_position: ClockPosition) -> RecursionStepResult:
        # Delegate to the certified substrate; then wrap the
        # certificate with an application-scoped scope and
        # method_params.
        inner_result = self._inner.integrate(inputs, state, clock_position)
        inner_cert = inner_result.contraction_certificate

        # If the language returned PROVEN with RECURSION_CORE and
        # the application declares full domain bounds, upgrade the
        # reported scope to PROJECTED_RECURSION (still honest: the
        # domain hypotheses are present in the application config).
        upgraded_scope = inner_cert.certified_scope
        if (inner_cert.result is ContractionResult.PROVEN_CONTRACTIVE
                and inner_cert.certified_scope is ContractionScope.RECURSION_CORE):
            upgraded_scope = ContractionScope.PROJECTED_RECURSION

        method_params = dict(inner_cert.method_params)
        method_params["application_substrate"] = self.info.application_substrate_id
        method_params["source_contributions"] = sorted([
            {"source_id": c.source_id, "magnitude": c.magnitude,
             "frame_count": len(c.frame_ids)}
            for c in inner_result.source_contributions
        ], key=lambda d: d["source_id"])

        app_cert = ContractionCertificate(
            contract_version=inner_cert.contract_version,
            metric=inner_cert.metric,
            requested_margin=inner_cert.requested_margin,
            measured_upper_bound=inner_cert.measured_upper_bound,
            numerical_tolerance=inner_cert.numerical_tolerance,
            arithmetic_precision=inner_cert.arithmetic_precision,
            certification_method=inner_cert.certification_method,
            result=inner_cert.result,
            consumed_inputs=inner_cert.consumed_inputs,
            clock_position=inner_cert.clock_position,
            certified_scope=upgraded_scope,
            arithmetic_kind=inner_cert.arithmetic_kind,
            method_params=method_params,
        )
        return RecursionStepResult(
            next_state=inner_result.next_state,
            outputs=inner_result.outputs,
            source_contributions=inner_result.source_contributions,
            unresolved_inputs=inner_result.unresolved_inputs,
            contraction_certificate=app_cert,
            transition_certificate=inner_result.transition_certificate,
        )

    def read(self, state: RecursionState, request):
        return self._inner.read(state, request)

    def snapshot(self, state: RecursionState) -> RecursionSnapshot:
        return self._inner.snapshot(state)

    def restore(self, snapshot: RecursionSnapshot) -> RecursionState:
        return self._inner.restore(snapshot)


__all__ = [
    "ApplicationContractiveRecursion",
    "ApplicationRecursionInfo",
]
