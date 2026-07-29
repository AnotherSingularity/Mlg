"""Staged compiler pipeline — per-stage failure barrier."""

from __future__ import annotations

import pytest

from compiler.pipeline import (
    ALL_STAGES,
    PipelineResult,
    STAGE_BUILD_GRAPH,
    STAGE_LOWER_IR,
    STAGE_NEGOTIATE,
    STAGE_PARSE,
    STAGE_RESOLVE,
    STAGE_TYPE_ANALYZE,
    STAGE_VALIDATE_CLOCKS,
    STAGE_VALIDATE_IR,
    run_pipeline,
)


GOOD = """
source t: X { clock: token offers: VectorRead, VectorDrive, PerTokenStep }
recursion r: Y { dimension: 4 clock: integration contraction_margin: 0.9 }
project t.o into r
schedule {
    every token { step t }
    every integration { integrate r }
}
"""


def test_good_program_reaches_ir():
    r = run_pipeline(GOOD, filename="g.aeon", module_id="g")
    assert r.ok(), [d.code for d in r.errors()]
    assert r.ir is not None
    assert r.graph is not None
    assert r.stages_run[-1] == "plan_execution"


def test_parse_error_stops_after_parse():
    r = run_pipeline("source", filename="e.aeon", module_id="e")
    assert not r.ok()
    assert r.failed_stage == STAGE_PARSE
    # No later stage ran.
    assert set(r.stages_run) == {STAGE_PARSE}


def test_missing_required_capability_stops_at_type_analyze():
    src = """
source s: X { clock: token offers: VectorRead }
recursion r: Y { dimension: 2 clock: integration contraction_margin: 0.9 }
project s.o into r
"""
    r = run_pipeline(src, filename="b.aeon", module_id="b")
    assert not r.ok()
    assert r.failed_stage == STAGE_TYPE_ANALYZE
    # Later stages did NOT run.
    assert STAGE_LOWER_IR not in r.stages_run
    assert STAGE_VALIDATE_IR not in r.stages_run
    # And no IR was emitted.
    assert r.ir is None


def test_undefined_source_stops_at_resolve():
    src = """
recursion r: Y { dimension: 2 clock: integration contraction_margin: 0.9 }
project ghost.out into r
"""
    r = run_pipeline(src, filename="b.aeon", module_id="b")
    assert not r.ok()
    assert r.failed_stage == STAGE_RESOLVE
    assert r.ir is None


def test_undeclared_clock_stops_at_validate_clocks_or_earlier():
    src = """
source s: X { clock: token offers: VectorRead, VectorDrive, PerTokenStep }
recursion r: Y { dimension: 2 clock: integration contraction_margin: 0.9 }
project s.o into r
schedule { every mystery { step s } }
"""
    r = run_pipeline(src, filename="b.aeon", module_id="b")
    assert not r.ok()
    assert r.failed_stage in (STAGE_TYPE_ANALYZE, STAGE_VALIDATE_CLOCKS)


def test_pipeline_records_every_stage_up_to_first_failure():
    src = """
source s: X { clock: token offers: VectorRead }
recursion r: Y { dimension: 2 clock: integration contraction_margin: 0.9 }
project s.o into r
"""
    r = run_pipeline(src, filename="b.aeon", module_id="b")
    # We should see PARSE, RESOLVE, TYPE_ANALYZE in order.
    assert r.stages_run.index(STAGE_PARSE) < r.stages_run.index(STAGE_RESOLVE) < r.stages_run.index(STAGE_TYPE_ANALYZE)


def test_stop_after_at_type_analyze_short_circuits():
    r = run_pipeline(GOOD, filename="g.aeon", module_id="g",
                     stop_after=STAGE_TYPE_ANALYZE)
    assert r.type_env is not None
    assert r.ir is None
    assert r.graph is None
    assert STAGE_LOWER_IR not in r.stages_run


def test_all_stages_have_stable_names():
    assert ALL_STAGES == (
        "parse", "resolve_names", "type_analyze",
        "validate_ownership", "validate_ports", "negotiate_capabilities",
        "validate_clocks", "validate_causality",
        "bind_contracts", "build_graph", "lower_ir",
        "validate_ir", "plan_execution",
    )
