"""L3+L4+L5: sources, projections, and Recursion substrate."""

from __future__ import annotations

import pytest

from aeon.capability import CapabilityRef, CapabilityTier, VersionConstraint, negotiate
from aeon.clock import ClockPosition
from aeon.contraction import (
    CertificationMethod,
    ContractionResult,
    ContractionScope,
    Contractive,
    Metric,
    PrecisionPolicy,
)
from aeon.core import SemVer, Validity
from aeon.port import ReadRequest, Ready, ReadUnavailable
from aeon.provenance import make_identity
from aeon.signal import new_signal_frame

from aeon_app.projections import (
    AttentionToRecursion,
    RecursionToAttentionFeedback,
    RecursionToRecurrentFeedback,
    RecurrentToRecursion,
    resolve_projection,
)
from aeon_app.recursion import ApplicationContractiveRecursion
from aeon_app.sources import (
    AttentionSource,
    AttentionSourceState,
    PersistentRecurrentSource,
    RecurrentSourceState,
)


def _frame(payload, source_id="drive"):
    return new_signal_frame(
        source_id=source_id, sequence=0,
        clock_position=ClockPosition("source", 0),
        payload=list(payload),
        originating_state_id=make_identity("aeon_app.state", {"drive": source_id}),
    )


# ---------------------------------------------------------------------------
# AttentionSource
# ---------------------------------------------------------------------------


def test_attention_source_offers_required_and_attention_map():
    src = AttentionSource(dimension=4, history=4)
    desc = src.describe()
    offered = {c.name for c in desc.offered_capabilities}
    assert {"VectorRead", "VectorDrive", "PerTokenStep"} <= offered
    assert "AttentionMapRead" in offered


def test_attention_source_step_deterministic():
    src = AttentionSource(dimension=4, history=4)
    s0 = src.initialize({}, seed=1)
    s_a = src.step(_frame([1, 2, 3, 4]), s0, ClockPosition("source", 1)).next_state
    s_b = src.step(_frame([1, 2, 3, 4]), s0, ClockPosition("source", 1)).next_state
    assert s_a.payload == s_b.payload
    assert s_a.id == s_b.id


def test_attention_source_reads_and_unavailable():
    src = AttentionSource(dimension=4, history=4)
    s = src.initialize({}, seed=1)
    r = src.read(s, ReadRequest(kind="vector"))
    assert isinstance(r, Ready) and len(r.value) == 4
    # After a step, attention_map has one row.
    s1 = src.step(_frame([1, 0, 0, 0]), s, ClockPosition("source", 1)).next_state
    r_map = src.read(s1, ReadRequest(kind="attention_map"))
    assert isinstance(r_map, Ready) and len(r_map.value) == 1
    # Unknown read → Unavailable (never None, never zero).
    r_bad = src.read(s, ReadRequest(kind="matrix"))
    assert isinstance(r_bad, ReadUnavailable)


def test_attention_source_snapshot_restore_round_trip():
    src = AttentionSource(dimension=4, history=4)
    s = src.initialize({}, seed=3)
    for tick in range(1, 4):
        s = src.step(_frame([1.0] * 4), s, ClockPosition("source", tick)).next_state
    snap = src.snapshot(s)
    restored = src.restore(snap)
    assert restored.payload == s.payload
    assert restored.memory_keys == s.memory_keys
    assert restored.memory_values == s.memory_values
    # Next transition must reproduce exactly.
    a = src.step(_frame([0.5] * 4), s, ClockPosition("source", 4)).next_state.payload
    b = src.step(_frame([0.5] * 4), restored, ClockPosition("source", 4)).next_state.payload
    assert a == b


def test_attention_source_input_dim_mismatch_raises():
    src = AttentionSource(dimension=4, history=4)
    s = src.initialize({}, seed=0)
    with pytest.raises(ValueError):
        src.step(_frame([1, 2]), s, ClockPosition("source", 1))


# ---------------------------------------------------------------------------
# PersistentRecurrentSource
# ---------------------------------------------------------------------------


def test_recurrent_source_offers_required_plus_matrix_and_decay():
    src = PersistentRecurrentSource(dimension=4)
    desc = src.describe()
    offered = {c.name for c in desc.offered_capabilities}
    assert {"VectorRead", "VectorDrive", "PerTokenStep",
            "MatrixRead", "DecayControl", "PerStepTransition",
            "Snapshot", "Restore"} <= offered


def test_recurrent_source_step_deterministic_and_bounded():
    src = PersistentRecurrentSource(dimension=4)
    s = src.initialize({}, seed=2)
    for tick in range(1, 5):
        s = src.step(_frame([1.0] * 4), s, ClockPosition("source", tick)).next_state
        assert max(abs(x) for x in s.payload) <= 1.5, "payload should stay bounded"


def test_recurrent_source_snapshot_restore_reproduces_next():
    src = PersistentRecurrentSource(dimension=4)
    s = src.initialize({}, seed=7)
    s = src.step(_frame([0.2] * 4), s, ClockPosition("source", 1)).next_state
    snap = src.snapshot(s)
    restored = src.restore(snap)
    a = src.step(_frame([0.1] * 4), s, ClockPosition("source", 2)).next_state
    b = src.step(_frame([0.1] * 4), restored, ClockPosition("source", 2)).next_state
    assert a.payload == b.payload


def test_recurrent_matrix_read_and_dimension_read():
    src = PersistentRecurrentSource(dimension=4)
    s = src.initialize({}, seed=1)
    m = src.read(s, ReadRequest(kind="matrix"))
    assert isinstance(m, Ready) and len(m.value) == 4
    d = src.read(s, ReadRequest(kind="dimension"))
    assert isinstance(d, Ready) and d.value == 4


def test_recurrent_source_capability_negotiation_passes_required():
    src = PersistentRecurrentSource()
    desc = src.describe()
    result = negotiate(
        list(desc.offered_capabilities),
        [VersionConstraint(c.name, c.version) for c in desc.required_capabilities],
    )
    assert result.compatible


# ---------------------------------------------------------------------------
# Projections
# ---------------------------------------------------------------------------


def test_all_four_projections_registered():
    for impl in [
        "aeon_app.projections.attention_to_recursion:AttentionToRecursion",
        "aeon_app.projections.recurrent_to_recursion:RecurrentToRecursion",
        "aeon_app.projections.feedback:RecursionToAttentionFeedback",
        "aeon_app.projections.feedback:RecursionToRecurrentFeedback",
    ]:
        cls = resolve_projection(impl)
        assert cls().descriptor.id


def test_projection_apply_scales_within_bound():
    p = AttentionToRecursion()
    m = p.apply(_frame([1.0, 2.0, 3.0, 4.0]))
    assert m.payload == (1.0, 2.0, 3.0, 4.0)  # default scale=1.0
    p_half = RecursionToAttentionFeedback()  # scale=0.5
    m2 = p_half.apply(_frame([2.0, 4.0, 6.0, 8.0]))
    assert m2.payload == (1.0, 2.0, 3.0, 4.0)


def test_projection_scale_bound_enforced():
    from aeon_app.projections import ProjectionParameters
    with pytest.raises(ValueError):
        RecursionToAttentionFeedback(ProjectionParameters(scale=0.9))


def test_projection_input_dim_mismatch_raises():
    p = AttentionToRecursion()
    with pytest.raises(ValueError):
        p.apply(_frame([1.0]))


def test_projection_descriptor_is_stable_json():
    from aeon.serialization import canonical_bytes
    a = canonical_bytes(AttentionToRecursion().descriptor.to_canonical())
    b = canonical_bytes(AttentionToRecursion().descriptor.to_canonical())
    assert a == b


# ---------------------------------------------------------------------------
# ApplicationContractiveRecursion
# ---------------------------------------------------------------------------


def _contract(margin=0.9):
    return Contractive(
        metric=Metric.LINF, requested_margin=margin,
        numerical_tolerance=1e-12,
        precision_policy=PrecisionPolicy("float64"),
        certification_method=CertificationMethod.EXACT_RATIONAL_ARITHMETIC,
    )


def test_recursion_substrate_produces_proven_projected_scope():
    sub = ApplicationContractiveRecursion(4, _contract(0.9))
    s = sub.initialize({}, 0)
    p_att = AttentionToRecursion()
    p_rec = RecurrentToRecursion()
    m_a = p_att.apply(_frame([1, 2, 3, 4], source_id="attention"))
    m_r = p_rec.apply(_frame([4, 3, 2, 1], source_id="recurrent"))
    integ = ClockPosition("integration", 1)
    result = sub.integrate([m_a, m_r], s, integ)
    c = result.contraction_certificate
    assert c.result is ContractionResult.PROVEN_CONTRACTIVE
    assert c.certified_scope is ContractionScope.PROJECTED_RECURSION
    # Method params carry the application substrate id and per-source
    # contributions (sorted by source_id).
    assert "application_substrate" in c.method_params
    src_ids = [d["source_id"] for d in c.method_params["source_contributions"]]
    assert src_ids == sorted(src_ids)
    assert set(src_ids) == {"attention", "recurrent"}


def test_recursion_substrate_deterministic():
    sub_a = ApplicationContractiveRecursion(4, _contract(0.9))
    sub_b = ApplicationContractiveRecursion(4, _contract(0.9))
    s_a = sub_a.initialize({}, 0)
    s_b = sub_b.initialize({}, 0)
    p = AttentionToRecursion()
    m = p.apply(_frame([1, 2, 3, 4], source_id="attention"))
    integ = ClockPosition("integration", 1)
    r_a = sub_a.integrate([m], s_a, integ)
    r_b = sub_b.integrate([m], s_b, integ)
    assert r_a.next_state.payload == r_b.next_state.payload
    assert r_a.contraction_certificate.measured_upper_bound == r_b.contraction_certificate.measured_upper_bound


def test_recursion_source_disagreement_not_hidden():
    """Multiple sources contributing very different signals must appear
    in source_contributions with distinct magnitudes (spec §6.3: source
    disagreement is not represented as a simple average unless
    specified). The certificate's method_params surfaces per-source
    magnitudes even though the integrator uses a mean policy."""
    sub = ApplicationContractiveRecursion(4, _contract(0.9))
    s = sub.initialize({}, 0)
    p = AttentionToRecursion()
    m_a = p.apply(_frame([10.0, 0, 0, 0], source_id="attention"))
    m_r = p.apply(_frame([0, 0, 0, 0.1], source_id="recurrent"))
    integ = ClockPosition("integration", 1)
    result = sub.integrate([m_a, m_r], s, integ)
    contribs = {c["source_id"]: c["magnitude"]
                for c in result.contraction_certificate.method_params["source_contributions"]}
    # Attention's contribution magnitude (L∞ of its projected payload) is
    # much larger than the recurrent's.
    assert contribs["attention"] > contribs["recurrent"]
