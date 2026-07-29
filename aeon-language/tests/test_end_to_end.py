"""End-to-end: source -> validate -> lower -> interpret -> replay."""

from __future__ import annotations

import pytest

from aeon.contraction import (
    CertificationMethod,
    ContractionResult,
    Contractive,
    Metric,
    PrecisionPolicy,
)
from aeon.recursion import ReferenceContractiveRecursion
from aeon.sources.dummy import DummyRichSource, DummyVectorSource
from compiler.parser import parse
from compiler.validator import validate
from runtime.interpreter import Interpreter
from runtime.replay import replay
from runtime.scheduler import lower


SRC = """
source transformer: TransformerSource {
    clock: token
    requires: VectorRead
    offers: VectorRead, VectorDrive, PerTokenStep
}
source persistence: RecurrentSource {
    clock: token
    requires: VectorRead
    offers: VectorRead, VectorDrive, PerTokenStep, MatrixRead, DecayControl
}
recursion continuity: ContractiveManifold {
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


def _mk_contract():
    return Contractive(
        metric=Metric.LINF, requested_margin=0.9,
        numerical_tolerance=1e-12,
        precision_policy=PrecisionPolicy("float64"),
        certification_method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
    )


def _sources_factory():
    return {
        "transformer": DummyVectorSource("transformer", 4),
        "persistence": DummyRichSource("persistence", 4),
    }


def _substrates_factory():
    # Declared domain bounds so the verifier can upgrade the result
    # from BOUNDED_CONTRACTIVE to PROVEN_CONTRACTIVE.
    return {"continuity": ReferenceContractiveRecursion(
        4, _mk_contract(), "continuity", 0.5,
        declared_input_radius=10.0,
        declared_state_radius=10.0,
        declared_projection_scale_upper=1.0,
    )}


def test_compile_and_run_produces_certificates():
    m = parse(SRC, "e.aeon", module_id="e")
    res = validate(m)
    assert res.ok(), [d.code for d in res.errors()]
    ir = lower(m, res.graph, seed=1, ticks_per_clock=4)
    outcome = Interpreter(ir, sources=_sources_factory(), substrates=_substrates_factory(), seed=1).run()
    assert outcome.halt_reason == "completed"
    assert len(outcome.contraction_certificates) == 4  # 4 integration ticks
    for c in outcome.contraction_certificates:
        assert c.result is ContractionResult.PROVEN_CONTRACTIVE
        assert c.consumed_inputs, "consumed_inputs must be recorded"


def test_replay_is_byte_identical():
    m = parse(SRC, "e.aeon", module_id="e")
    ir = lower(m, validate(m).graph, seed=7, ticks_per_clock=4)
    report = replay(ir, sources_factory=_sources_factory,
                    substrates_factory=_substrates_factory, seed=7)
    assert report.identical, report.difference


def test_lower_is_deterministic():
    m = parse(SRC, "e.aeon", module_id="e")
    g = validate(m).graph
    a = lower(m, g, seed=1, ticks_per_clock=4).to_bytes()
    b = lower(m, g, seed=1, ticks_per_clock=4).to_bytes()
    assert a == b


def test_ir_bytes_change_when_seed_or_unroll_changes():
    m = parse(SRC, "e.aeon", module_id="e")
    g = validate(m).graph
    a = lower(m, g, seed=1, ticks_per_clock=4).to_bytes()
    b = lower(m, g, seed=2, ticks_per_clock=4).to_bytes()
    c = lower(m, g, seed=1, ticks_per_clock=8).to_bytes()
    assert a != b
    assert a != c
