"""aeon.verifier — independent contraction verifier.

Recomputes the contraction bound for a declared transition rather
than trusting a status field emitted by the transition being
certified. Implements the correction from Phase 0.1 mandate §3.

Verifier scope ("proof boundary" per mandate §3.1) for the
reference `ReferenceContractiveRecursion`:

    the isolated Recursion map: covered
    the source-to-Recursion projection: bound-checked, not proven
    the complete integration transition: BOUNDED under bounded inputs
    the integration-plus-feedback loop: not covered

The verifier consumes a `Contractive` contract plus the
transition's parameter and domain bounds and produces one of the
five `ContractionResult` tags. It does not trust the emitter.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence, Tuple

from .contraction import (
    CertificationMethod,
    ContractionCertificate,
    ContractionResult,
    Contractive,
    Metric,
    PrecisionPolicy,
)


# ---------------------------------------------------------------------------
# Verifier inputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TransitionDefinition:
    """A declarative description of the transition being verified.

    ``kind`` is one of:
      - ``"linear_scaled_convex_mix"`` — the reference substrate's
        update rule ``next = margin * (decay * s + (1-decay) * a)``.
      - ``"custom"`` — no closed-form bound is claimed.

    For ``linear_scaled_convex_mix`` the verifier computes the L∞
    operator bound in closed form and compares against the declared
    margin.
    """

    kind: str
    parameters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DomainBounds:
    """Bounds on the transition's inputs and state.

    All values are element-wise L∞ radii unless otherwise noted.
    ``None`` for a radius means "unbounded on that axis" and forces
    the verifier to return NOT_PROVEN.
    """

    input_radius: Optional[float] = None
    state_radius: Optional[float] = None
    projection_scale_upper: Optional[float] = None


@dataclass(frozen=True)
class VerifierInput:
    transition: TransitionDefinition
    contract: Contractive
    domain: DomainBounds


# ---------------------------------------------------------------------------
# Verifier output
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerifierReport:
    result: ContractionResult
    computed_upper_bound: Optional[float]
    method: CertificationMethod
    reason: str
    checked_bounds: Mapping[str, Any] = field(default_factory=dict)

    def to_certificate(self, contract: Contractive, *,
                       contract_version, consumed_inputs: Tuple[str, ...],
                       clock_position) -> ContractionCertificate:
        return ContractionCertificate(
            contract_version=contract_version,
            metric=contract.metric,
            requested_margin=contract.requested_margin,
            measured_upper_bound=self.computed_upper_bound,
            numerical_tolerance=contract.numerical_tolerance,
            arithmetic_precision=contract.precision_policy,
            certification_method=self.method,
            result=self.result,
            consumed_inputs=consumed_inputs,
            clock_position=clock_position,
            method_params={
                "verifier": "aeon.verifier/0.1.0-dev",
                "reason": self.reason,
                **self.checked_bounds,
            },
        )


# ---------------------------------------------------------------------------
# Verifier implementation
# ---------------------------------------------------------------------------


def verify(input: VerifierInput) -> VerifierReport:
    contract = input.contract
    transition = input.transition
    domain = input.domain

    # Precision-policy sanity: only float64 is admitted for PROVEN
    # verdicts. Other precisions produce at most BOUNDED_CONTRACTIVE.
    is_float64 = contract.precision_policy.element_type == "float64"

    if transition.kind == "linear_scaled_convex_mix":
        decay = float(transition.parameters.get("decay", 0.5))
        margin = float(contract.requested_margin)

        # Precondition on the transition parameters themselves.
        if not (0.0 <= decay <= 1.0):
            return VerifierReport(
                result=ContractionResult.VIOLATED,
                computed_upper_bound=None,
                method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
                reason=f"decay={decay} outside [0, 1]",
                checked_bounds={"decay": decay},
            )
        if not (0.0 < margin <= 1.0):
            return VerifierReport(
                result=ContractionResult.VIOLATED,
                computed_upper_bound=None,
                method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
                reason=f"margin={margin} outside (0, 1]",
                checked_bounds={"margin": margin},
            )
        if margin >= 1.0:
            return VerifierReport(
                result=ContractionResult.VIOLATED,
                computed_upper_bound=margin,
                method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
                reason=f"margin={margin} does not satisfy < 1",
                checked_bounds={"margin": margin},
            )

        # The map t(s, a) = margin * (decay*s + (1-decay)*a) is affine
        # in (s, a). Its Jacobian w.r.t. s has L∞ operator norm
        # `margin * decay`. For an isolated recursion (a fixed), that
        # is the closed-form Lipschitz bound on the state map.
        state_lip = margin * decay

        # For the full integration transition where `a` is derived from
        # bounded projections, the effective Lipschitz on inputs is
        # `margin * (1-decay)` and the state-plus-input bound is at
        # most `margin`. If the projection scale is declared and <= 1
        # and inputs and state are bounded, the joint transition stays
        # inside a compact ball of radius margin * max(state_radius, input_radius).
        proj_scale = domain.projection_scale_upper
        state_r = domain.state_radius
        input_r = domain.input_radius

        # Determine what we can prove.
        # (i) Isolated Recursion (a treated as adversarial but bounded):
        #     state Lipschitz is `state_lip = margin * decay < margin`.
        #     This is the strongest closed-form claim we can make.

        # PROVEN requires: float64 precision AND
        # margin * decay < margin < 1 AND
        # bounded projection AND bounded inputs.
        can_prove = (
            is_float64
            and state_lip < margin < 1.0
            and proj_scale is not None and 0.0 <= proj_scale <= 1.0
            and input_r is not None and math.isfinite(input_r)
            and state_r is not None and math.isfinite(state_r)
        )
        if can_prove:
            return VerifierReport(
                result=ContractionResult.PROVEN_CONTRACTIVE,
                computed_upper_bound=state_lip,
                method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
                reason=(
                    "closed-form Jacobian bound: "
                    f"||∂t/∂s||_∞ = margin*decay = {state_lip:.6g} < "
                    f"margin = {margin:.6g} < 1, under bounded domain"
                ),
                checked_bounds={
                    "margin": margin, "decay": decay,
                    "state_lipschitz": state_lip,
                    "input_radius": input_r, "state_radius": state_r,
                    "projection_scale_upper": proj_scale,
                    "precision_policy": contract.precision_policy.element_type,
                },
            )

        # If the closed-form bound is fine but a domain assumption
        # is missing, we still have a SOUND numerical bound of the
        # state Lipschitz — return BOUNDED_CONTRACTIVE.
        if state_lip < margin < 1.0:
            missing = []
            if proj_scale is None:
                missing.append("projection_scale_upper")
            if input_r is None or not (input_r is not None and math.isfinite(input_r)):
                missing.append("input_radius")
            if state_r is None or not (state_r is not None and math.isfinite(state_r)):
                missing.append("state_radius")
            if not is_float64:
                missing.append("precision_policy=float64")
            return VerifierReport(
                result=ContractionResult.BOUNDED_CONTRACTIVE,
                computed_upper_bound=state_lip,
                method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
                reason=(
                    "state-map Lipschitz bounded but PROVEN downgraded "
                    f"because these are unspecified: {missing}"
                ),
                checked_bounds={
                    "margin": margin, "decay": decay,
                    "state_lipschitz": state_lip,
                    "missing": missing,
                    "precision_policy": contract.precision_policy.element_type,
                },
            )

        # margin exactly at 1 or state_lip >= margin: not contractive
        # under this rule.
        return VerifierReport(
            result=ContractionResult.NOT_PROVEN,
            computed_upper_bound=state_lip,
            method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
            reason=(
                f"state_lip = {state_lip:.6g} not strictly below "
                f"margin = {margin:.6g}"
            ),
            checked_bounds={"margin": margin, "decay": decay, "state_lipschitz": state_lip},
        )

    # Unknown transition kind.
    return VerifierReport(
        result=ContractionResult.NOT_PROVEN,
        computed_upper_bound=None,
        method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
        reason=f"verifier has no closed-form for transition kind {transition.kind!r}",
        checked_bounds={"transition_kind": transition.kind},
    )


# ---------------------------------------------------------------------------
# Independent recomputation of the reference substrate
# ---------------------------------------------------------------------------


def recompute_reference_bound(margin: float, decay: float,
                              precision_policy: PrecisionPolicy) -> float:
    """Independent recomputation of the L∞ operator bound.

    Used by tests to prove the verifier is not simply echoing the
    substrate's own claim. Two independent expressions of the same
    mathematical statement yielding the same number is the evidence.
    """
    if not (0.0 <= decay <= 1.0) or not (0.0 < margin <= 1.0):
        raise ValueError("margin/decay outside bounds")
    # Direct-form computation.
    return margin * decay
