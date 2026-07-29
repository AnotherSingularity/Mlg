"""aeon.types and static type analyzer."""

from __future__ import annotations

import pytest

from aeon.types import (
    BOOL,
    INTEGER,
    PROBABILITY,
    Bounded,
    Convertibility,
    Float,
    Kind,
    Matrix,
    Result,
    State,
    Signal,
    Tensor,
    Vector,
    can_convert,
)
from compiler.parser import parse
from compiler.type_analyzer import analyze


def test_atomic_kinds():
    assert BOOL.kind is Kind.VALUE
    assert INTEGER.kind is Kind.VALUE
    assert PROBABILITY.kind is Kind.VALUE


def test_float_precisions_widen_lossless():
    assert can_convert(Float("f16"), Float("f64")) is Convertibility.LOSSLESS
    assert can_convert(Float("f32"), Float("f64")) is Convertibility.LOSSLESS


def test_float_precisions_narrow_lossy():
    assert can_convert(Float("f64"), Float("f32")) is Convertibility.LOSSY
    assert can_convert(Float("f64"), Float("f16")) is Convertibility.LOSSY


def test_integer_to_float_is_lossy():
    assert can_convert(INTEGER, Float("f64")) is Convertibility.LOSSY


def test_probability_to_float_lossless():
    assert can_convert(PROBABILITY, Float("f64")) is Convertibility.LOSSLESS


def test_float_to_probability_lossy():
    assert can_convert(Float("f64"), PROBABILITY) is Convertibility.LOSSY


def test_bounded_to_element_lossless():
    b = Bounded(0.0, 1.0, Float("f64"))
    assert can_convert(b, Float("f64")) is Convertibility.LOSSLESS


def test_kind_mismatch_prohibited():
    s = State(Vector(Float("f64"), 4), "owner", "token")
    sig = Signal(Vector(Float("f64"), 4), "token")
    assert can_convert(s, sig) is Convertibility.PROHIBITED


def test_matrix_structural_matches():
    a = Matrix(Float("f64"), 4, 4)
    b = Matrix(Float("f64"), 4, 4)
    assert a.matches(b)
    c = Matrix(Float("f64"), 4, 5)
    assert not a.matches(c)


def test_result_type():
    r = Result(INTEGER, BOOL)
    assert r.name == "Result"
    assert r.params[0].matches(INTEGER)


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


GOOD = """
source transformer: X {
    clock: token
    offers: VectorRead, VectorDrive, PerTokenStep
}
source persistence: Y {
    clock: token
    offers: VectorRead, VectorDrive, PerTokenStep, MatrixRead, DecayControl
}
recursion continuity: C {
    dimension: 4
    clock: integration
    contraction_margin: 0.9
}
project transformer.output into continuity
project persistence.state into continuity
schedule {
    every token { step transformer step persistence }
    every integration { integrate continuity }
}
"""


def test_analyzer_accepts_good_program():
    m = parse(GOOD, "g.aeon", module_id="g")
    r = analyze(m)
    assert r.ok(), [d.code for d in r.errors()]
    assert set(r.env.sources) == {"transformer", "persistence"}
    assert "continuity" in r.env.recursions
    assert r.env.recursions["continuity"][1] == 4  # dim
    assert set(r.env.projections) >= {"transformer.output.continuity",
                                       "persistence.state.continuity"}


def test_analyzer_rejects_missing_required_cap():
    m = parse("""
source s: X { clock: token offers: VectorRead }
recursion r: Y { dimension: 2 clock: integration contraction_margin: 0.9 }
project s.o into r
""", "b.aeon", module_id="b")
    r = analyze(m)
    assert "REQUIRED_CAPABILITY_MISSING" in {d.code for d in r.errors()}


def test_analyzer_rejects_undeclared_clock():
    m = parse("""
source s: X { clock: token offers: VectorRead, VectorDrive, PerTokenStep }
recursion r: Y { dimension: 2 clock: integration contraction_margin: 0.9 }
project s.o into r
schedule { every mystery { step s } }
""", "b.aeon", module_id="b")
    r = analyze(m)
    assert "UNDECLARED_CLOCK" in {d.code for d in r.errors()}


def test_analyzer_rejects_clock_domain_mismatch_on_step():
    m = parse("""
source s: X { clock: token offers: VectorRead, VectorDrive, PerTokenStep }
recursion r: Y { dimension: 2 clock: integration contraction_margin: 0.9 }
project s.o into r
schedule {
    every integration { step s }
}
""", "b.aeon", module_id="b")
    r = analyze(m)
    codes = {d.code for d in r.errors()}
    assert "CLOCK_DOMAIN_MISMATCH" in codes


def test_analyzer_rejects_integrate_on_undefined_recursion():
    m = parse("""
source s: X { clock: token offers: VectorRead, VectorDrive, PerTokenStep }
recursion r: Y { dimension: 2 clock: integration contraction_margin: 0.9 }
project s.o into r
schedule { every integration { integrate ghost } }
""", "b.aeon", module_id="b")
    r = analyze(m)
    assert "UNDEFINED_RECURSION_TARGET" in {d.code for d in r.errors()}


def test_diagnostics_carry_source_spans_and_remediation():
    m = parse("""
source s: X { clock: token offers: VectorRead }
recursion r: Y { dimension: 2 clock: integration contraction_margin: 0.9 }
""", "b.aeon", module_id="b")
    r = analyze(m)
    d = next(d for d in r.errors() if d.code == "REQUIRED_CAPABILITY_MISSING")
    assert d.source_span is not None
    assert d.remediation is not None
