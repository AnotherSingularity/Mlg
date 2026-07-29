"""Cross-backend differential parity harness (Phase 0.1 §7.3)."""

from __future__ import annotations

import pytest

pytest.importorskip("numpy")

from aeon.contraction import (
    CertificationMethod,
    Contractive,
    Metric,
    PrecisionPolicy,
)
from aeon.recursion import ReferenceContractiveRecursion
from aeon.sources.dummy import DummyRichSource, DummyVectorSource
from backends.numpy import NumpyBackend, NumpyContractiveRecursion
from backends.python import PythonBackend
from compiler.parser import parse
from compiler.validator import validate
from runtime.scheduler import lower


SRC = """
source t: X { clock: token offers: VectorRead, VectorDrive, PerTokenStep }
source p: Y { clock: token offers: VectorRead, VectorDrive, PerTokenStep, MatrixRead, DecayControl }
recursion c: C { dimension: 4 clock: integration contraction_margin: 0.9 }
project p.state into c
project t.output into c
schedule {
    every token { step p step t }
    every integration { integrate c }
}
"""


def _contract():
    return Contractive(
        metric=Metric.LINF, requested_margin=0.9,
        numerical_tolerance=1e-12,
        precision_policy=PrecisionPolicy("float64"),
        certification_method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
    )


def _sources():
    return {
        "t": DummyVectorSource("t", 4),
        "p": DummyRichSource("p", 4),
    }


def _sub_python():
    return {"c": ReferenceContractiveRecursion(
        4, _contract(), "continuity", 0.5,
        declared_input_radius=10.0, declared_state_radius=10.0,
        declared_projection_scale_upper=1.0,
    )}


def _sub_numpy():
    return {"c": NumpyContractiveRecursion(
        4, _contract(), "continuity", 0.5,
        declared_input_radius=10.0, declared_state_radius=10.0,
        declared_projection_scale_upper=1.0,
    )}


def _run(backend, substrates):
    m = parse(SRC, "d.aeon", module_id="d")
    ir = lower(m, validate(m).graph, seed=1, ticks_per_clock=4)
    return backend.execute(ir, sources=_sources(), substrates=substrates, seed=1)


def test_both_backends_reach_completion():
    a = _run(PythonBackend(), _sub_python())
    b = _run(NumpyBackend(), _sub_numpy())
    assert a.halt_reason == "completed"
    assert b.halt_reason == "completed"


def test_certification_status_agrees_across_backends():
    a = _run(PythonBackend(), _sub_python())
    b = _run(NumpyBackend(), _sub_numpy())
    assert len(a.contraction_certificates) == len(b.contraction_certificates)
    for ca, cb in zip(a.contraction_certificates, b.contraction_certificates):
        assert ca.result is cb.result
        assert ca.metric is cb.metric
        assert ca.requested_margin == cb.requested_margin


def test_state_identities_agree_across_backends():
    """Both backends compute state identities from the same canonical
    payload digest. Even if the *arithmetic* differs at the last
    float64 ULP, the identity paths are byte-identical here because
    the numpy substrate uses the same update rule with the same
    inputs. Numerical variance is permitted only within declared
    tolerance; this test asserts identity match under that tolerance."""
    a = _run(PythonBackend(), _sub_python())
    b = _run(NumpyBackend(), _sub_numpy())
    # The transition_certificate.subject_id records the successor
    # RecursionState id after each integrate.
    aids = [c.subject_id.digest for c in a.certificates]
    bids = [c.subject_id.digest for c in b.certificates]
    assert aids == bids


def test_measured_upper_bound_agrees():
    a = _run(PythonBackend(), _sub_python())
    b = _run(NumpyBackend(), _sub_numpy())
    for ca, cb in zip(a.contraction_certificates, b.contraction_certificates):
        assert ca.measured_upper_bound == pytest.approx(
            cb.measured_upper_bound, abs=1e-12
        )


def test_consumed_inputs_agree():
    a = _run(PythonBackend(), _sub_python())
    b = _run(NumpyBackend(), _sub_numpy())
    for ca, cb in zip(a.contraction_certificates, b.contraction_certificates):
        assert ca.consumed_inputs == cb.consumed_inputs


def test_numpy_backend_info_declares_tolerance():
    info = NumpyBackend.info
    assert info.name == "aeon.backends.numpy"
    assert info.numerical_tolerance <= 1e-9
    assert info.supported_ir_version == "0.1.0-dev"
