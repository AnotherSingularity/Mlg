"""Contraction proof-soundness (v0.1 final closure §3.6, §3.7)."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import pytest

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
from aeon.certificate import recheck_contraction
from aeon.core import SemVer
from aeon.verifier import (
    ArithmeticKind,
    DomainBounds,
    TransitionDefinition,
    VerifierInput,
    recompute_reference_bound,
    recompute_reference_bound_exact,
    verify,
)


def _contract(margin=Fraction(9, 10), precision="float64",
              method=CertificationMethod.EXACT_RATIONAL_ARITHMETIC):
    return Contractive(
        metric=Metric.LINF, requested_margin=float(margin),
        numerical_tolerance=1e-12,
        precision_policy=PrecisionPolicy(precision),
        certification_method=method,
    )


def _transition(decay=Fraction(1, 2), margin=Fraction(9, 10)):
    return TransitionDefinition(
        kind="linear_scaled_convex_mix",
        parameters={"decay": decay, "margin": margin},
    )


def _bounded_domain():
    return DomainBounds(input_radius=1.0, state_radius=1.0,
                        projection_scale_upper=1.0)


# ---------------------------------------------------------------------------
# §3.1: float64 alone MUST NOT establish PROVEN_CONTRACTIVE
# ---------------------------------------------------------------------------


def test_float64_arithmetic_downgrades_to_bounded():
    r = verify(VerifierInput(
        _transition(decay=0.5, margin=0.9),
        _contract(0.9), _bounded_domain(),
        arithmetic=ArithmeticKind.FLOAT64,
    ))
    assert r.result is ContractionResult.BOUNDED_CONTRACTIVE
    assert r.arithmetic is ArithmeticKind.FLOAT64


def test_exact_rational_arithmetic_admits_proven():
    r = verify(VerifierInput(
        _transition(decay=Fraction(1, 2), margin=Fraction(9, 10)),
        _contract(Fraction(9, 10)), _bounded_domain(),
        arithmetic=ArithmeticKind.EXACT_RATIONAL,
    ))
    assert r.result is ContractionResult.PROVEN_CONTRACTIVE
    assert r.arithmetic is ArithmeticKind.EXACT_RATIONAL


# ---------------------------------------------------------------------------
# §3.6 boundary matrix
# ---------------------------------------------------------------------------


def test_bound_safely_below_margin_is_proven():
    r = verify(VerifierInput(
        _transition(decay=Fraction(1, 2), margin=Fraction(9, 10)),
        _contract(Fraction(9, 10)), _bounded_domain(),
    ))
    assert r.result is ContractionResult.PROVEN_CONTRACTIVE


def test_bound_equal_to_margin_is_not_proven():
    # decay=1 -> state_lip = margin * 1 = margin. strict `<` fails.
    r = verify(VerifierInput(
        _transition(decay=Fraction(1), margin=Fraction(9, 10)),
        _contract(Fraction(9, 10)), _bounded_domain(),
    ))
    assert r.result is ContractionResult.NOT_PROVEN


def test_bound_above_margin_is_not_proven():
    # decay > 1 is a VIOLATED precondition.
    r = verify(VerifierInput(
        _transition(decay=Fraction(11, 10), margin=Fraction(9, 10)),
        _contract(Fraction(9, 10)), _bounded_domain(),
    ))
    assert r.result is ContractionResult.VIOLATED


def test_margin_at_1_is_violated():
    r = verify(VerifierInput(
        _transition(decay=Fraction(1, 2), margin=Fraction(1)),
        _contract(Fraction(1)), _bounded_domain(),
    ))
    assert r.result is ContractionResult.VIOLATED


def test_margin_above_1_is_rejected_at_contract_construction():
    with pytest.raises(ValueError):
        Contractive(metric=Metric.LINF, requested_margin=1.5,
                    numerical_tolerance=1e-12,
                    precision_policy=PrecisionPolicy("float64"),
                    certification_method=CertificationMethod.EXACT_RATIONAL_ARITHMETIC)


def test_nan_parameter_via_bad_string_yields_not_proven():
    r = verify(VerifierInput(
        TransitionDefinition(
            kind="linear_scaled_convex_mix",
            parameters={"decay": "not-a-number", "margin": Fraction(9, 10)},
        ),
        _contract(Fraction(9, 10)), _bounded_domain(),
    ))
    assert r.result is ContractionResult.NOT_PROVEN


def test_projection_that_breaks_contraction_downgrades():
    # PROJECTED_RECURSION scope but no projection_scale_upper -> BOUNDED
    r = verify(VerifierInput(
        _transition(),
        _contract(Fraction(9, 10)),
        DomainBounds(),  # no domain hypotheses
        scope=ContractionScope.PROJECTED_RECURSION,
    ))
    assert r.result is ContractionResult.BOUNDED_CONTRACTIVE


def test_closed_loop_scope_always_bounded_at_best_in_v0_1():
    r = verify(VerifierInput(
        _transition(),
        _contract(Fraction(9, 10)),
        _bounded_domain(),
        scope=ContractionScope.CLOSED_LOOP_TRANSITION,
    ))
    # v0.1 doesn't implement the feedback bound -> BOUNDED at best.
    assert r.result is ContractionResult.BOUNDED_CONTRACTIVE


def test_unknown_transition_kind_not_proven():
    r = verify(VerifierInput(
        TransitionDefinition(kind="not-a-known-kind", parameters={}),
        _contract(Fraction(9, 10)), _bounded_domain(),
    ))
    assert r.result is ContractionResult.NOT_PROVEN


# ---------------------------------------------------------------------------
# §3.7 tamper-test matrix: recheck rejects mutated certificates
# ---------------------------------------------------------------------------


def _issue_proven_certificate() -> ContractionCertificate:
    transition = _transition()
    domain = _bounded_domain()
    contract = _contract(Fraction(9, 10))
    report = verify(VerifierInput(transition, contract, domain,
                                  arithmetic=ArithmeticKind.EXACT_RATIONAL,
                                  scope=ContractionScope.RECURSION_CORE))
    assert report.result is ContractionResult.PROVEN_CONTRACTIVE
    return report.to_certificate(
        contract, contract_version=SemVer(0, 1, 0),
        consumed_inputs=("aaaa",),
        clock_position=ClockPosition("integration", 1),
    )


def _recheck_ok(cert: ContractionCertificate) -> bool:
    return recheck_contraction(cert, _transition(), _bounded_domain())


def test_pristine_certificate_rechecks():
    assert _recheck_ok(_issue_proven_certificate())


def test_tamper_status_from_bounded_to_proven_fails_recheck():
    # Start from an honest BOUNDED_CONTRACTIVE and forge PROVEN.
    contract = _contract(Fraction(9, 10))
    domain = _bounded_domain()
    report = verify(VerifierInput(_transition(), contract, domain,
                                  arithmetic=ArithmeticKind.FLOAT64))
    cert = report.to_certificate(
        contract, contract_version=SemVer(0, 1, 0),
        consumed_inputs=(),
        clock_position=ClockPosition("integration", 1),
    )
    forged = replace(cert, result=ContractionResult.PROVEN_CONTRACTIVE)
    assert not recheck_contraction(forged, _transition(), domain,
                                   arithmetic=ArithmeticKind.FLOAT64)


def test_tamper_measured_upper_bound_fails_recheck():
    cert = _issue_proven_certificate()
    forged = replace(cert, measured_upper_bound=0.0)
    assert not _recheck_ok(forged)


def test_tamper_certified_scope_fails_recheck():
    cert = _issue_proven_certificate()
    forged = replace(cert, certified_scope=ContractionScope.CLOSED_LOOP_TRANSITION)
    assert not _recheck_ok(forged)


def test_tamper_arithmetic_kind_fails_recheck():
    cert = _issue_proven_certificate()
    forged = replace(cert, arithmetic_kind="Float64")
    # Recheck defaults to EXACT_RATIONAL and sees a Float64 claim on
    # the certificate: mismatch.
    assert not _recheck_ok(forged)


def test_tamper_requested_margin_fails_recheck():
    cert = _issue_proven_certificate()
    forged = replace(cert, requested_margin=0.5)  # different contract
    # Recheck uses the (forged) contract to run the verifier, which
    # will compute state_lip = 0.5*0.5 = 0.25 < 0.5. That yields
    # PROVEN, but the ORIGINAL measured_upper_bound (0.45) does not
    # equal the recomputed 0.25 -> fails.
    assert not _recheck_ok(forged)


def test_recompute_helpers_agree():
    # The recompute helpers are the independent path used by tests.
    assert recompute_reference_bound(0.9, 0.5, PrecisionPolicy("float64")) == 0.45
    exact = recompute_reference_bound_exact(Fraction(9, 10), Fraction(1, 2))
    assert exact == Fraction(9, 20)


# ---------------------------------------------------------------------------
# §3.4 certified_scope reporting
# ---------------------------------------------------------------------------


def test_reference_substrate_certificate_reports_recursion_core_scope():
    from aeon.recursion import ReferenceContractiveRecursion, ProjectionContract, project_frame
    from aeon.provenance import make_identity
    from aeon.signal import new_signal_frame
    sub = ReferenceContractiveRecursion(
        4, _contract(0.9),
        declared_input_radius=10.0,
        declared_state_radius=10.0,
        declared_projection_scale_upper=1.0,
    )
    s = sub.initialize({}, 0)
    origin = make_identity("state", {})
    frame = new_signal_frame(source_id="src", sequence=0,
                              clock_position=ClockPosition("token", 0),
                              payload=[1.0, 2.0, 3.0, 4.0],
                              originating_state_id=origin)
    m = sub.project(frame, ProjectionContract(
        id="p", source_id="src", substrate_id="rc",
        input_shape=(4,), scale=1.0,
    ))
    result = sub.integrate([m], s, ClockPosition("integration", 1))
    c = result.contraction_certificate
    assert c.certified_scope is ContractionScope.RECURSION_CORE
    assert c.arithmetic_kind == ArithmeticKind.EXACT_RATIONAL.value
    assert c.result is ContractionResult.PROVEN_CONTRACTIVE
    assert c.certification_method is CertificationMethod.EXACT_RATIONAL_ARITHMETIC
