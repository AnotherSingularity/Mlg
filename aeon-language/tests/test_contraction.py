"""Contraction, certificates, and composition."""

from __future__ import annotations

import pytest

from aeon.clock import ClockDomain, ClockKind
from aeon.contraction import (
    CertificationMethod,
    ContractionResult,
    Contractive,
    Metric,
    PrecisionPolicy,
    compose_margin,
    compose_result,
)
from aeon.recursion import ProjectionContract, ReferenceContractiveRecursion
from aeon.signal import new_signal_frame
from aeon.provenance import make_identity


def _contract(margin=0.9):
    return Contractive(
        metric=Metric.LINF,
        requested_margin=margin,
        numerical_tolerance=1e-12,
        precision_policy=PrecisionPolicy("float64"),
        certification_method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
    )


def _one_input(dim=4, source="src.a", scale=1.0, payload=None):
    integ = ClockDomain("integration", ClockKind.INTEGRATION)
    tok = ClockDomain("token", ClockKind.TOKEN)
    p_tok = tok.position(0)
    origin = make_identity("state", {"src": source})
    frame = new_signal_frame(
        source_id=source, sequence=0, clock_position=p_tok,
        payload=list(payload) if payload is not None else [1.0] * dim,
        originating_state_id=origin,
    )
    contract = ProjectionContract(
        id=f"proj.{source}", source_id=source,
        substrate_id="rec.ref", input_shape=(dim,), scale=scale,
    )
    return frame, contract


def test_contract_margin_bounds():
    with pytest.raises(ValueError):
        _contract(1.5)
    with pytest.raises(ValueError):
        _contract(0.0)


def test_integrate_produces_all_certificate_fields():
    # C12 change: the reference substrate certifies the RECURSION_CORE
    # scope with exact-rational arithmetic. For the isolated Recursion
    # map, no domain bounds are required — the Jacobian bound is
    # uniform. So an unbounded substrate now emits PROVEN_CONTRACTIVE
    # honestly.
    sub = ReferenceContractiveRecursion(4, _contract(0.9))
    state = sub.initialize({}, 0)
    frame, pc = _one_input()
    m = sub.project(frame, pc)
    integ = ClockDomain("integration", ClockKind.INTEGRATION).position(1)
    result = sub.integrate([m], state, integ)
    c = result.contraction_certificate
    assert c.metric is Metric.LINF
    assert c.requested_margin == 0.9
    # measured_upper_bound: exact-rational path yields 9/20 = 0.45.
    assert c.measured_upper_bound == 0.9 * 0.5
    assert c.arithmetic_precision.element_type == "float64"
    assert c.certification_method is CertificationMethod.EXACT_RATIONAL_ARITHMETIC
    assert c.result is ContractionResult.PROVEN_CONTRACTIVE
    assert c.consumed_inputs, "consumed_inputs must be recorded"
    assert c.clock_position.domain_id == "integration"


def test_integrate_with_declared_bounds_is_proven():
    sub = ReferenceContractiveRecursion(
        4, _contract(0.9),
        declared_input_radius=10.0,
        declared_state_radius=10.0,
        declared_projection_scale_upper=1.0,
    )
    state = sub.initialize({}, 0)
    frame, pc = _one_input()
    m = sub.project(frame, pc)
    integ = ClockDomain("integration", ClockKind.INTEGRATION).position(1)
    result = sub.integrate([m], state, integ)
    assert result.contraction_certificate.result is ContractionResult.PROVEN_CONTRACTIVE


def test_not_proven_distinct_from_violated():
    # Enum-value level distinction
    assert ContractionResult.NOT_PROVEN.value != ContractionResult.VIOLATED.value
    # Composition preserves the distinction
    assert (compose_result(ContractionResult.PROVEN_CONTRACTIVE, ContractionResult.NOT_PROVEN)
            is ContractionResult.NOT_PROVEN)
    assert (compose_result(ContractionResult.NOT_PROVEN, ContractionResult.VIOLATED)
            is ContractionResult.VIOLATED)


def test_composition_margin():
    assert compose_margin(0.5, 0.9) == pytest.approx(0.45)


def test_input_order_independence():
    sub = ReferenceContractiveRecursion(4, _contract(0.9))
    state = sub.initialize({}, 0)
    integ = ClockDomain("integration", ClockKind.INTEGRATION).position(1)
    f1, pc1 = _one_input(source="src.a", payload=[1.0, 2.0, 3.0, 4.0])
    f2, pc2 = _one_input(source="src.b", payload=[4.0, 3.0, 2.0, 1.0])
    m1, m2 = sub.project(f1, pc1), sub.project(f2, pc2)
    r_ab = sub.integrate([m1, m2], state, integ)
    r_ba = sub.integrate([m2, m1], state, integ)
    assert r_ab.next_state.payload == r_ba.next_state.payload
    assert (r_ab.contraction_certificate.consumed_inputs
            == r_ba.contraction_certificate.consumed_inputs)


def test_snapshot_restore_yields_same_next_state():
    sub = ReferenceContractiveRecursion(4, _contract(0.9))
    state = sub.initialize({}, 0)
    integ = ClockDomain("integration", ClockKind.INTEGRATION).position(1)
    f, pc = _one_input(payload=[1.0, 2.0, 3.0, 4.0])
    m = sub.project(f, pc)
    baseline = sub.integrate([m], state, integ)
    snap = sub.snapshot(state)
    restored = sub.restore(snap)
    replay = sub.integrate([m], restored, integ)
    assert baseline.next_state.payload == replay.next_state.payload
