"""aeon.verifier — independent contraction verifier with SOUND proof rules.

Implements the Phase 0.1 §3 correction plus the v0.1 final closure
§3 mandate: PROVEN_CONTRACTIVE is a **sound** claim. Ordinary
float64 arithmetic can round an estimated upper bound downward,
therefore float64 alone MUST NOT establish PROVEN_CONTRACTIVE
(final mandate §3.1).

Sound methods available in v0.1:

- ``ExactRational`` — for closed-form linear parameterizations
  whose bound is a rational function of rational parameters.
  Computes ``margin * decay`` in Python ``Fraction`` and compares
  ``state_lip < margin`` exactly. This is the only method that
  yields PROVEN_CONTRACTIVE in v0.1.

- ``Float64`` — the numerical evaluation path. Produces at most
  BOUNDED_CONTRACTIVE, never PROVEN_CONTRACTIVE.

Everything else (nonlinearities, gating, residuals, feedback
loops, general recurrent operators) is not covered by v0.1's
proof surface and produces NOT_PROVEN by default; see
``ContractionScope`` for the exact certified-scope reporting.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
from typing import Any, Mapping, Optional, Sequence, Tuple

from .contraction import (
    CertificationMethod,
    ContractionCertificate,
    ContractionResult,
    ContractionScope,
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


class ArithmeticKind(Enum):
    """The arithmetic used to establish the bound."""

    EXACT_RATIONAL = "ExactRational"
    FLOAT64 = "Float64"
    INTERVAL = "Interval"  # reserved for future implementation


@dataclass(frozen=True)
class VerifierInput:
    transition: TransitionDefinition
    contract: Contractive
    domain: DomainBounds
    arithmetic: ArithmeticKind = ArithmeticKind.EXACT_RATIONAL
    scope: ContractionScope = ContractionScope.RECURSION_CORE


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
    arithmetic: ArithmeticKind = ArithmeticKind.FLOAT64
    certified_scope: ContractionScope = ContractionScope.RECURSION_CORE

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
            certified_scope=self.certified_scope,
            arithmetic_kind=self.arithmetic.value,
            method_params={
                "verifier": "aeon.verifier/0.1.0",
                "reason": self.reason,
                **self.checked_bounds,
            },
        )


# ---------------------------------------------------------------------------
# Rational conversion utilities
# ---------------------------------------------------------------------------


def _to_exact_fraction(value: Any) -> Optional[Fraction]:
    """Best-effort exact conversion. Returns None if the value cannot
    be represented in Fraction without loss.

    - int and Fraction: exact.
    - str "p/q" or decimal string: exact via Fraction(str).
    - float: represented EXACTLY as a dyadic rational
      (``Fraction(float)`` does not round). This is exact but the
      value may not equal the decimal a human typed. We consider it
      exact for the arithmetic that follows.
    """
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, str):
        try:
            return Fraction(value)
        except (ValueError, ZeroDivisionError):
            return None
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return Fraction(value)  # exact dyadic conversion
    return None


# ---------------------------------------------------------------------------
# Verifier implementation
# ---------------------------------------------------------------------------


def verify(input: VerifierInput) -> VerifierReport:
    contract = input.contract
    transition = input.transition
    domain = input.domain
    arithmetic = input.arithmetic
    scope = input.scope

    if transition.kind == "linear_scaled_convex_mix":
        return _verify_linear(input)

    return VerifierReport(
        result=ContractionResult.NOT_PROVEN,
        computed_upper_bound=None,
        method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
        reason=f"verifier has no closed-form for transition kind {transition.kind!r}",
        checked_bounds={"transition_kind": transition.kind},
        arithmetic=arithmetic,
        certified_scope=scope,
    )


def _verify_linear(input: VerifierInput) -> VerifierReport:
    contract = input.contract
    decay_raw = input.transition.parameters.get("decay", 0.5)
    margin_raw = contract.requested_margin

    # --- precondition: parameter validity ---
    try:
        decay_f = float(decay_raw)
        margin_f = float(margin_raw)
    except (TypeError, ValueError):
        return VerifierReport(
            result=ContractionResult.NOT_PROVEN,
            computed_upper_bound=None,
            method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
            reason="parameters not numeric",
            checked_bounds={"decay_raw": str(decay_raw),
                            "margin_raw": str(margin_raw)},
            arithmetic=input.arithmetic,
            certified_scope=input.scope,
        )
    if not (0.0 <= decay_f <= 1.0):
        return VerifierReport(
            result=ContractionResult.VIOLATED,
            computed_upper_bound=None,
            method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
            reason=f"decay={decay_f} outside [0, 1]",
            checked_bounds={"decay": decay_f},
            arithmetic=input.arithmetic,
            certified_scope=input.scope,
        )
    # For a strict `< 1` contract, margin >= 1 cannot succeed even
    # if the transition's own coefficient is < margin.
    if margin_f >= 1.0 or margin_f <= 0.0:
        return VerifierReport(
            result=ContractionResult.VIOLATED,
            computed_upper_bound=margin_f,
            method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
            reason=f"margin={margin_f} does not satisfy 0 < margin < 1",
            checked_bounds={"margin": margin_f},
            arithmetic=input.arithmetic,
            certified_scope=input.scope,
        )

    proj_scale = input.domain.projection_scale_upper
    state_r = input.domain.state_radius
    input_r = input.domain.input_radius

    # --- attempt exact-rational proof ---
    if input.arithmetic is ArithmeticKind.EXACT_RATIONAL:
        margin_q = _to_exact_fraction(margin_raw)
        decay_q = _to_exact_fraction(decay_raw)
        if margin_q is None or decay_q is None:
            # Parameter that cannot be represented exactly (e.g. a
            # non-numeric value): degrade to NOT_PROVEN, not to a
            # silently unsound PROVEN.
            return VerifierReport(
                result=ContractionResult.NOT_PROVEN,
                computed_upper_bound=None,
                method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
                reason="parameters not convertible to exact Fraction",
                checked_bounds={"margin_raw": str(margin_raw),
                                "decay_raw": str(decay_raw)},
                arithmetic=input.arithmetic,
                certified_scope=input.scope,
            )
        state_lip_q = margin_q * decay_q  # exact
        # Sound comparison: `<` on Fraction is exact.
        # For the RECURSION_CORE scope we also need margin_q < 1 to
        # satisfy the constitutional strict-contraction requirement.
        if not (state_lip_q < margin_q < Fraction(1)):
            return VerifierReport(
                result=ContractionResult.NOT_PROVEN,
                computed_upper_bound=float(state_lip_q),
                method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
                reason=(
                    f"exact state_lip={state_lip_q} not strictly "
                    f"below margin={margin_q}"
                ),
                checked_bounds={"margin": str(margin_q),
                                "decay": str(decay_q),
                                "state_lipschitz": str(state_lip_q)},
                arithmetic=input.arithmetic,
                certified_scope=input.scope,
            )

        # --- runtime precision policy ---
        # A mathematical proof on Fractions is sound about the
        # ABSTRACT map. The substrate's *declared* runtime arithmetic
        # can nonetheless deviate: bf16 / f16 introduce rounding
        # error that could push the effective transition past the
        # margin. Only float64 is admitted as "PROVEN-compatible".
        # Other precisions produce at most BOUNDED_CONTRACTIVE.
        precision_ok = contract.precision_policy.element_type == "float64"

        # --- domain hypotheses required for the DECLARED scope ---
        missing = _missing_domain_hypotheses(input.scope, proj_scale, state_r, input_r)
        if not precision_ok:
            return VerifierReport(
                result=ContractionResult.BOUNDED_CONTRACTIVE,
                computed_upper_bound=float(state_lip_q),
                method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
                reason=(
                    f"exact-rational bound proven mathematically, but the "
                    f"declared runtime precision "
                    f"{contract.precision_policy.element_type!r} is not "
                    "float64: BOUNDED, not PROVEN"
                ),
                checked_bounds={
                    "margin": str(margin_q), "decay": str(decay_q),
                    "state_lipschitz": str(state_lip_q),
                    "precision_policy": contract.precision_policy.element_type,
                },
                arithmetic=input.arithmetic,
                certified_scope=input.scope,
            )
        if missing:
            return VerifierReport(
                result=ContractionResult.BOUNDED_CONTRACTIVE,
                computed_upper_bound=float(state_lip_q),
                method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
                reason=(
                    f"exact bound proven but scope {input.scope.value!r} "
                    f"lacks domain hypotheses: {missing}"
                ),
                checked_bounds={
                    "margin": str(margin_q), "decay": str(decay_q),
                    "state_lipschitz": str(state_lip_q),
                    "missing": missing,
                },
                arithmetic=input.arithmetic,
                certified_scope=input.scope,
            )

        return VerifierReport(
            result=ContractionResult.PROVEN_CONTRACTIVE,
            computed_upper_bound=float(state_lip_q),
            method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
            reason=(
                f"exact-rational Jacobian bound: "
                f"||∂t/∂s||_∞ = margin*decay = {state_lip_q} < "
                f"margin = {margin_q} < 1; scope={input.scope.value}"
            ),
            checked_bounds={
                "margin": str(margin_q), "decay": str(decay_q),
                "state_lipschitz": str(state_lip_q),
                "input_radius": input_r, "state_radius": state_r,
                "projection_scale_upper": proj_scale,
                "precision_policy": contract.precision_policy.element_type,
                "arithmetic": ArithmeticKind.EXACT_RATIONAL.value,
            },
            arithmetic=input.arithmetic,
            certified_scope=input.scope,
        )

    # --- FLOAT64 evaluation path: BOUNDED_CONTRACTIVE at best ---
    state_lip_f = margin_f * decay_f
    if not (state_lip_f < margin_f < 1.0):
        return VerifierReport(
            result=ContractionResult.NOT_PROVEN,
            computed_upper_bound=state_lip_f,
            method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
            reason=(
                f"float64 state_lip={state_lip_f:.17g} not strictly "
                f"below margin={margin_f:.17g}"
            ),
            checked_bounds={"margin": margin_f, "decay": decay_f,
                            "state_lipschitz": state_lip_f},
            arithmetic=input.arithmetic,
            certified_scope=input.scope,
        )
    return VerifierReport(
        result=ContractionResult.BOUNDED_CONTRACTIVE,
        computed_upper_bound=state_lip_f,
        method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
        reason=(
            "float64 evaluation supports contraction but is insufficient "
            "for PROVEN_CONTRACTIVE per mandate §3.1"
        ),
        checked_bounds={
            "margin": margin_f, "decay": decay_f,
            "state_lipschitz": state_lip_f,
            "arithmetic": ArithmeticKind.FLOAT64.value,
            "precision_policy": contract.precision_policy.element_type,
        },
        arithmetic=input.arithmetic,
        certified_scope=input.scope,
    )


def _missing_domain_hypotheses(scope: ContractionScope,
                               proj_scale: Optional[float],
                               state_r: Optional[float],
                               input_r: Optional[float]) -> list[str]:
    missing: list[str] = []
    if scope in (ContractionScope.PROJECTED_RECURSION,
                 ContractionScope.INTEGRATION_TRANSITION,
                 ContractionScope.CLOSED_LOOP_TRANSITION):
        if proj_scale is None or not (0.0 <= proj_scale <= 1.0):
            missing.append("projection_scale_upper")
    if scope in (ContractionScope.INTEGRATION_TRANSITION,
                 ContractionScope.CLOSED_LOOP_TRANSITION):
        if input_r is None or not (isinstance(input_r, (int, float)) and math.isfinite(input_r)):
            missing.append("input_radius")
        if state_r is None or not (isinstance(state_r, (int, float)) and math.isfinite(state_r)):
            missing.append("state_radius")
    if scope is ContractionScope.CLOSED_LOOP_TRANSITION:
        # Feedback path is NOT covered by v0.1's proof surface.
        missing.append("closed_loop_feedback_bound (not implemented in v0.1)")
    return missing


# ---------------------------------------------------------------------------
# Independent recomputation of the reference substrate
# ---------------------------------------------------------------------------


def recompute_reference_bound(margin: float, decay: float,
                              precision_policy: PrecisionPolicy) -> float:
    """Independent recomputation of the L∞ operator bound.

    Used by tests to prove the verifier is not simply echoing the
    substrate's own claim.
    """
    if not (0.0 <= decay <= 1.0) or not (0.0 < margin <= 1.0):
        raise ValueError("margin/decay outside bounds")
    # Compute exactly via Fraction, then round to float for display.
    m = Fraction(margin)
    d = Fraction(decay)
    return float(m * d)


def recompute_reference_bound_exact(margin, decay) -> Fraction:
    """Exact-rational recomputation used by tamper tests."""
    return _to_exact_fraction(margin) * _to_exact_fraction(decay)
