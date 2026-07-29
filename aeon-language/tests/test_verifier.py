"""Independent contraction verifier — negative fixture matrix.

Per Phase 0.1 mandate §3.4, every one of the following scenarios
MUST land on its specified result tag.
"""

from __future__ import annotations

import pytest

from aeon.clock import ClockPosition
from aeon.contraction import (
    CertificationMethod,
    ContractionResult,
    Contractive,
    Metric,
    PrecisionPolicy,
)
from aeon.recursion import (
    ProjectionContract,
    ReferenceContractiveRecursion,
    project_frame,
)
from aeon.provenance import make_identity
from aeon.signal import new_signal_frame
from aeon.verifier import (
    DomainBounds,
    TransitionDefinition,
    VerifierInput,
    recompute_reference_bound,
    verify,
)


def _contract(margin=0.9, precision="float64"):
    return Contractive(
        metric=Metric.LINF,
        requested_margin=margin,
        numerical_tolerance=1e-12,
        precision_policy=PrecisionPolicy(precision),
        certification_method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
    )


def _transition(decay=0.5, margin=0.9):
    return TransitionDefinition(
        kind="linear_scaled_convex_mix",
        parameters={"decay": decay, "margin": margin},
    )


def _bounded_domain():
    return DomainBounds(
        input_radius=1.0,
        state_radius=1.0,
        projection_scale_upper=1.0,
    )


# ---------------------------------------------------------------------------
# Independent recomputation
# ---------------------------------------------------------------------------


def test_verifier_recomputation_matches_direct_form():
    assert recompute_reference_bound(0.9, 0.5, PrecisionPolicy("float64")) == 0.45
    assert recompute_reference_bound(0.98, 0.5, PrecisionPolicy("float64")) == pytest.approx(0.49)


def test_verifier_report_bound_matches_recomputation():
    r = verify(VerifierInput(_transition(0.5, 0.9), _contract(0.9), _bounded_domain()))
    assert r.computed_upper_bound == recompute_reference_bound(0.9, 0.5, PrecisionPolicy("float64"))


# ---------------------------------------------------------------------------
# Positive cases
# ---------------------------------------------------------------------------


def test_bounded_domain_and_float64_yields_proven():
    r = verify(VerifierInput(_transition(0.5, 0.9), _contract(0.9), _bounded_domain()))
    assert r.result is ContractionResult.PROVEN_CONTRACTIVE


def test_missing_domain_bounds_ok_for_recursion_core_scope():
    # C12: RECURSION_CORE requires no domain bounds — the Jacobian
    # bound is uniform. PROVEN honestly.
    r = verify(VerifierInput(_transition(0.5, 0.9), _contract(0.9), DomainBounds()))
    assert r.result is ContractionResult.PROVEN_CONTRACTIVE


def test_missing_domain_bounds_downgrades_projected_scope():
    from aeon.contraction import ContractionScope
    r = verify(VerifierInput(_transition(0.5, 0.9), _contract(0.9),
                             DomainBounds(),
                             scope=ContractionScope.PROJECTED_RECURSION))
    assert r.result is ContractionResult.BOUNDED_CONTRACTIVE


def test_non_float64_precision_downgrades_from_proven():
    r = verify(VerifierInput(_transition(0.5, 0.9),
                             _contract(0.9, "bf16"), _bounded_domain()))
    # bf16 runtime deviates from the abstract math; the mathematical
    # proof holds but the substrate label must be BOUNDED, not PROVEN.
    assert r.result is ContractionResult.BOUNDED_CONTRACTIVE


# ---------------------------------------------------------------------------
# Boundary cases (mandate §3.4)
# ---------------------------------------------------------------------------


def test_margin_at_1_is_violated_by_verifier():
    # requested_margin=1.0 constructs (0 < m <= 1 admits it), but the
    # verifier rejects it because margin < 1 is required.
    r = verify(VerifierInput(_transition(0.5, 1.0), _contract(1.0),
                             _bounded_domain()))
    assert r.result is ContractionResult.VIOLATED


def test_margin_at_state_lipschitz_is_not_proven():
    # decay=1.0 forces state_lip = margin, which is not strictly < margin.
    r = verify(VerifierInput(_transition(1.0, 0.999), _contract(0.999),
                             _bounded_domain()))
    assert r.result is ContractionResult.NOT_PROVEN


def test_margin_above_1_rejected_by_contract():
    with pytest.raises(ValueError):
        Contractive(
            metric=Metric.LINF, requested_margin=1.5,
            numerical_tolerance=1e-12,
            precision_policy=PrecisionPolicy("float64"),
            certification_method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
        )


def test_decay_out_of_range_violated():
    r = verify(VerifierInput(_transition(1.5, 0.9), _contract(0.9),
                             _bounded_domain()))
    assert r.result is ContractionResult.VIOLATED


def test_unknown_transition_kind_not_proven():
    r = verify(VerifierInput(TransitionDefinition(kind="custom", parameters={}),
                             _contract(0.9), _bounded_domain()))
    assert r.result is ContractionResult.NOT_PROVEN


# ---------------------------------------------------------------------------
# Substrate-emitted certificate now uses the verifier
# ---------------------------------------------------------------------------


def _frame(payload, source="src.a"):
    return new_signal_frame(
        source_id=source, sequence=0,
        clock_position=ClockPosition("token", 0),
        payload=list(payload),
        originating_state_id=make_identity("state", {"src": source}),
    )


def _pc(source="src.a", scale=1.0):
    return ProjectionContract(
        id=f"proj.{source}", source_id=source,
        substrate_id="rec.ref", input_shape=(4,), scale=scale,
    )


def test_substrate_without_bounds_recursion_core_still_proven():
    """C12: RECURSION_CORE scope with exact-rational proof honestly emits PROVEN.

    Domain bounds are required for larger scopes (PROJECTED_RECURSION
    and above); the reference substrate certifies only the isolated
    Recursion map, which does not need them.
    """
    sub = ReferenceContractiveRecursion(4, _contract(0.9))
    s = sub.initialize({}, 0)
    m = sub.project(_frame([1, 2, 3, 4]), _pc())
    integ = ClockPosition("integration", 1)
    result = sub.integrate([m], s, integ)
    assert result.contraction_certificate.result is ContractionResult.PROVEN_CONTRACTIVE


def test_substrate_with_bounds_emits_proven():
    """Substrate with declared bounds and float64 upgrades to PROVEN."""
    sub = ReferenceContractiveRecursion(
        4, _contract(0.9),
        declared_input_radius=10.0,
        declared_state_radius=10.0,
        declared_projection_scale_upper=1.0,
    )
    s = sub.initialize({}, 0)
    m = sub.project(_frame([1, 2, 3, 4]), _pc())
    integ = ClockPosition("integration", 1)
    result = sub.integrate([m], s, integ)
    assert result.contraction_certificate.result is ContractionResult.PROVEN_CONTRACTIVE
    # measured_upper_bound reflects the closed-form state Lipschitz bound.
    assert result.contraction_certificate.measured_upper_bound == pytest.approx(0.9 * 0.5)


def test_numerically_invalid_forces_numerical_invalid_certificate():
    """Inf in the state payload propagates to NUMERICALLY_INVALID.

    Constructed by hand rather than injected through the canonical
    serialization layer (which rightly rejects NaN/Inf on ingress).
    """
    from dataclasses import replace
    sub = ReferenceContractiveRecursion(4, _contract(0.9),
        declared_input_radius=1.0, declared_state_radius=1.0,
        declared_projection_scale_upper=1.0)
    s = sub.initialize({}, 0)
    # Replace the state's payload with (inf, 0, 0, 0); the identity
    # was already computed from the canonical initial payload.
    s_inf = replace(s, payload=(float("inf"), 0.0, 0.0, 0.0))
    m = sub.project(_frame([1, 2, 3, 4]), _pc())
    integ = ClockPosition("integration", 1)
    result = sub.integrate([m], s_inf, integ)
    assert result.contraction_certificate.result is ContractionResult.NUMERICALLY_INVALID
    assert result.contraction_certificate.measured_upper_bound is None
