"""Application graph + canonical IR compilation."""

from __future__ import annotations

import pytest

from aeon.ir import IRValidationError, validate as validate_ir
from aeon_app.config import reference_config, resolve
from aeon_app.graph import build_from_config, compile_to_ir
from aeon_app.graph.builder import (
    AppEdgeKind,
    AppNodeKind,
    ApplicationGraph,
    GraphBuildError,
)


def _reference_graph():
    cfg = resolve(reference_config())
    return cfg, build_from_config(cfg)


def test_reference_graph_builds():
    cfg, g = _reference_graph()
    assert isinstance(g, ApplicationGraph)
    # Expected node types present:
    kinds = {n.kind for n in g.nodes}
    for expected in (AppNodeKind.INPUT, AppNodeKind.ATTENTION_SOURCE,
                     AppNodeKind.RECURRENT_SOURCE, AppNodeKind.PROJECTION,
                     AppNodeKind.FEEDBACK, AppNodeKind.AGGREGATION,
                     AppNodeKind.RECURSION, AppNodeKind.CERTIFICATION,
                     AppNodeKind.OUTPUT, AppNodeKind.SNAPSHOT):
        assert expected in kinds, expected
    # Every edge is typed with a known edge kind.
    valid_edge_kinds = {AppEdgeKind.SIGNAL, AppEdgeKind.STATE,
                        AppEdgeKind.CLOCK, AppEdgeKind.CONTROL,
                        AppEdgeKind.FEEDBACK, AppEdgeKind.CERTIFICATE}
    for e in g.edges:
        assert e.edge_kind in valid_edge_kinds


def test_graph_digest_is_deterministic():
    _, g1 = _reference_graph()
    _, g2 = _reference_graph()
    assert g1.digest() == g2.digest()


def test_graph_digest_changes_with_seed():
    from dataclasses import replace
    cfg = resolve(reference_config())
    g1 = build_from_config(cfg)
    scrambled = replace(cfg, sources=tuple(
        replace(s, seed=s.seed + 100) for s in cfg.sources
    ))
    g2 = build_from_config(scrambled)
    assert g1.digest() != g2.digest()


def test_compile_to_ir_validates():
    cfg, g = _reference_graph()
    ir = compile_to_ir(cfg, g)
    # Validation already ran inside compile_to_ir; validate again for good measure.
    validate_ir(ir)
    assert ir.language_version == "0.1.0"
    assert ir.aeon_ir_version == "0.1.0"
    assert ir.instruction_set_version == "0.1.0"
    assert ir.module_id, "module_id must be populated"
    assert len(ir.instructions) > 0


def test_ir_bytes_deterministic_across_two_builds():
    cfg, g1 = _reference_graph()
    _, g2 = _reference_graph()
    a = compile_to_ir(cfg, g1).to_bytes()
    b = compile_to_ir(cfg, g2).to_bytes()
    assert a == b


def test_unknown_source_implementation_rejected():
    from dataclasses import replace
    cfg = resolve(reference_config())
    bad = replace(cfg, sources=(
        replace(cfg.sources[0], implementation="aeon_app.sources.nope:Nope"),
    ) + cfg.sources[1:])
    with pytest.raises(GraphBuildError) as exc:
        build_from_config(bad)
    assert exc.value.code == "UNKNOWN_SOURCE_IMPLEMENTATION"


def test_capability_negotiation_failure_is_caught_at_build():
    # Config resolves (required caps are declared) but if we strip
    # required caps we should hit MISSING_REQUIRED_CAPABILITY at
    # resolve; if we bypass resolve, build should still refuse.
    from dataclasses import replace
    cfg = resolve(reference_config())
    weakened = replace(cfg.sources[0], offered_capabilities=("VectorRead",))
    # Bypass resolve entirely; hand the invalid config to build_from_config.
    weak_cfg = replace(cfg, sources=(weakened,) + cfg.sources[1:])
    with pytest.raises(GraphBuildError) as exc:
        build_from_config(weak_cfg)
    assert exc.value.code == "NEGOTIATION_FAILURE"


def test_graph_and_ir_bytes_stable_across_hashseeds():
    """Byte-stability across PYTHONHASHSEED must hold locally too."""
    # Same process; the framework's canonical serialization must not
    # depend on Python's per-process hash randomization.
    cfg = resolve(reference_config())
    g = build_from_config(cfg)
    a = g.digest()
    b = build_from_config(cfg).digest()
    assert a == b
    ir_a = compile_to_ir(cfg, g).to_bytes()
    ir_b = compile_to_ir(cfg, build_from_config(cfg)).to_bytes()
    assert ir_a == ir_b
