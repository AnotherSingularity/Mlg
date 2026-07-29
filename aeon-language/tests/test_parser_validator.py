"""Parser + formatter + static validator."""

from __future__ import annotations

from dataclasses import fields, is_dataclass, replace

import pytest

from compiler.formatter import format_module
from compiler.parser import ParseError, parse
from compiler.validator import validate


def strip_spans(obj):
    if is_dataclass(obj):
        new = {}
        for f in fields(obj):
            v = getattr(obj, f.name)
            new[f.name] = None if f.name == "span" else strip_spans(v)
        return replace(obj, **new)
    if isinstance(obj, tuple):
        return tuple(strip_spans(x) for x in obj)
    if isinstance(obj, list):
        return [strip_spans(x) for x in obj]
    return obj


_GOOD_SRC = """
source transformer: TransformerSource {
    clock: token
    requires: VectorRead
    offers: VectorRead, VectorDrive, PerTokenStep
}

source persistence: RecurrentSource {
    clock: token
    requires: VectorRead
    offers: VectorRead, VectorDrive, PerTokenStep, MatrixRead
}

recursion continuity: ContractiveManifold {
    dimension: 4
    clock: integration
    contraction_margin: 0.9
}

project transformer.output into continuity
project persistence.state into continuity

schedule {
    every token {
        step transformer
        step persistence
    }
    every integration {
        integrate continuity
    }
}
"""


def test_parses_full_example():
    m = parse(_GOOD_SRC, "ex.aeon", module_id="ex.aeon")
    assert [s.name for s in m.sources] == ["persistence", "transformer"]
    assert [r.name for r in m.recursions] == ["continuity"]
    assert m.schedule is not None
    assert len(m.schedule.blocks) == 2


def test_format_is_idempotent():
    m = parse(_GOOD_SRC, "ex.aeon", module_id="ex.aeon")
    f1 = format_module(m)
    m2 = parse(f1, "ex.aeon", module_id="ex.aeon")
    f2 = format_module(m2)
    assert f1 == f2


def test_source_order_independent():
    a = """
source a: X { clock: token offers: VectorRead, VectorDrive, PerTokenStep }
source b: X { clock: token offers: VectorRead, VectorDrive, PerTokenStep }
recursion r: Y { dimension: 2 clock: integration contraction_margin: 0.9 }
"""
    b = """
source b: X { clock: token offers: VectorRead, VectorDrive, PerTokenStep }
source a: X { clock: token offers: VectorRead, VectorDrive, PerTokenStep }
recursion r: Y { dimension: 2 clock: integration contraction_margin: 0.9 }
"""
    ma = strip_spans(parse(a, "x.aeon", module_id="x"))
    mb = strip_spans(parse(b, "x.aeon", module_id="x"))
    assert ma == mb


def test_validate_accepts_good_example():
    m = parse(_GOOD_SRC, "ex.aeon", module_id="ex.aeon")
    res = validate(m)
    assert res.ok(), [d.code for d in res.errors()]
    assert res.graph is not None


def test_required_capability_missing_rejected():
    src = """
source bad: X { clock: token offers: VectorRead }
recursion r: Y { dimension: 2 clock: integration contraction_margin: 0.9 }
project bad.o into r
"""
    codes = [d.code for d in validate(parse(src, "b.aeon", module_id="b")).errors()]
    assert "REQUIRED_CAPABILITY_MISSING" in codes


def test_invalid_contraction_margin_rejected():
    src = """
source g: X { clock: token offers: VectorRead, VectorDrive, PerTokenStep }
recursion r: Y { dimension: 2 clock: integration contraction_margin: 1.5 }
project g.o into r
"""
    codes = [d.code for d in validate(parse(src, "b.aeon", module_id="b")).errors()]
    assert "INVALID_CONTRACTION_MARGIN" in codes


def test_unknown_capability_rejected():
    src = """
source g: X { clock: token offers: VectorRead, VectorDrive, PerTokenStep, HypotheticalCap }
recursion r: Y { dimension: 2 clock: integration contraction_margin: 0.9 }
project g.o into r
"""
    codes = [d.code for d in validate(parse(src, "b.aeon", module_id="b")).errors()]
    assert "UNKNOWN_CAPABILITY" in codes


def test_clock_crossing_undeclared_rejected():
    src = """
source g: X { clock: token offers: VectorRead, VectorDrive, PerTokenStep }
recursion r: Y { dimension: 2 clock: integration contraction_margin: 0.9 }
project g.o into r
schedule { every token { integrate r } }
"""
    codes = [d.code for d in validate(parse(src, "b.aeon", module_id="b")).errors()]
    assert "CLOCK_CROSSING_UNDECLARED" in codes


def test_parse_error_source_located():
    with pytest.raises(ParseError) as exc:
        parse("source", "err.aeon", module_id="err")
    assert exc.value.file == "err.aeon"
    assert exc.value.line >= 1
