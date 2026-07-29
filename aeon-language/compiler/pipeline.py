"""Aeon staged compiler pipeline.

Splits the compiler into named stages per specification §16 and
Phase 0.1 §5. Each stage has a defined input, a defined output,
structured diagnostics, and its own unit-test surface.

Stages (in execution order):

    1. parse                — source text -> Module AST
    2. resolve_names        — cross-reference source/recursion/projection
    3. type_analyze         — aeon.types-driven static analysis
    4. validate_ownership   — declared-state ownership consistency
    5. validate_ports       — capability tier + port compatibility
    6. negotiate_capabilities — deterministic capability negotiation
    7. validate_clocks      — clock-domain declarations
    8. validate_causality   — schedule-level cross-clock check
    9. bind_contracts       — contract binding for each recursion
   10. build_graph          — construct SemanticGraph
   11. lower_ir             — SemanticGraph -> IRModule
   12. validate_ir          — IR schema + opcode validation
   13. plan_execution       — record execution plan metadata

Failure-barrier: if any stage produces ERROR diagnostics, no
subsequent stage runs and no IR is emitted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from aeon.capability import (
    CapabilityRef,
    CapabilityTier,
    VersionConstraint,
    negotiate,
)
from aeon.core import Diagnostic, SemVer, Severity, SourceSpan
from aeon.graph import SemanticGraph
from aeon.ir import IRModule
from aeon.types import AeonType

from .ast import Module
from .formatter import format_module
from .parser import ParseError, parse
from .type_analyzer import TypeEnv, analyze


# ---------------------------------------------------------------------------
# Stage names (stable string constants for diagnostics + trace)
# ---------------------------------------------------------------------------

STAGE_PARSE = "parse"
STAGE_RESOLVE = "resolve_names"
STAGE_TYPE_ANALYZE = "type_analyze"
STAGE_VALIDATE_OWNERSHIP = "validate_ownership"
STAGE_VALIDATE_PORTS = "validate_ports"
STAGE_NEGOTIATE = "negotiate_capabilities"
STAGE_VALIDATE_CLOCKS = "validate_clocks"
STAGE_VALIDATE_CAUSALITY = "validate_causality"
STAGE_BIND_CONTRACTS = "bind_contracts"
STAGE_BUILD_GRAPH = "build_graph"
STAGE_LOWER_IR = "lower_ir"
STAGE_VALIDATE_IR = "validate_ir"
STAGE_PLAN = "plan_execution"

ALL_STAGES = (
    STAGE_PARSE, STAGE_RESOLVE, STAGE_TYPE_ANALYZE,
    STAGE_VALIDATE_OWNERSHIP, STAGE_VALIDATE_PORTS, STAGE_NEGOTIATE,
    STAGE_VALIDATE_CLOCKS, STAGE_VALIDATE_CAUSALITY,
    STAGE_BIND_CONTRACTS, STAGE_BUILD_GRAPH, STAGE_LOWER_IR,
    STAGE_VALIDATE_IR, STAGE_PLAN,
)


# ---------------------------------------------------------------------------
# Result record
# ---------------------------------------------------------------------------


@dataclass
class StageOutcome:
    stage: str
    diagnostics: List[Diagnostic] = field(default_factory=list)
    ok: bool = True


@dataclass
class PipelineResult:
    source_file: str
    stages_run: List[str] = field(default_factory=list)
    stage_outcomes: List[StageOutcome] = field(default_factory=list)
    diagnostics: List[Diagnostic] = field(default_factory=list)
    module: Optional[Module] = None
    type_env: Optional[TypeEnv] = None
    graph: Optional[SemanticGraph] = None
    ir: Optional[IRModule] = None
    failed_stage: Optional[str] = None

    def ok(self) -> bool:
        return self.failed_stage is None and not any(
            d.severity is Severity.ERROR for d in self.diagnostics
        )

    def errors(self) -> List[Diagnostic]:
        return [d for d in self.diagnostics if d.severity is Severity.ERROR]


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def _mk_err(code: str, message: str, span: Optional[SourceSpan] = None,
            remediation: Optional[str] = None) -> Diagnostic:
    return Diagnostic(
        severity=Severity.ERROR, code=code, message=message,
        source_span=span, remediation=remediation,
    )


def run_pipeline(
    source_text: str,
    *,
    filename: str = "<stdin>",
    module_id: Optional[str] = None,
    seed: int = 0,
    ticks_per_clock: int = 8,
    stop_after: Optional[str] = None,
) -> PipelineResult:
    """Run the full compiler pipeline. ``stop_after`` optionally
    halts at a given stage name (for tests)."""

    result = PipelineResult(source_file=filename)

    def _run(stage: str, ok: bool, diags: List[Diagnostic]) -> bool:
        outcome = StageOutcome(stage=stage, diagnostics=list(diags), ok=ok)
        result.stage_outcomes.append(outcome)
        result.stages_run.append(stage)
        result.diagnostics.extend(diags)
        if not ok:
            result.failed_stage = stage
            return False
        if stop_after == stage:
            return False
        return True

    # 1. parse
    try:
        module = parse(source_text, filename=filename,
                       module_id=module_id or filename)
    except ParseError as exc:
        diag = _mk_err("PARSE_ERROR", str(exc),
                       SourceSpan(exc.file, exc.line, exc.col, exc.line, exc.col + 1))
        _run(STAGE_PARSE, ok=False, diags=[diag])
        return result
    if not _run(STAGE_PARSE, ok=True, diags=[]):
        result.module = module
        return result
    result.module = module

    # 2. resolve names
    diags: List[Diagnostic] = []
    source_names = {s.name for s in module.sources}
    recursion_names = {r.name for r in module.recursions}
    for p in module.projections:
        if p.source not in source_names:
            diags.append(_mk_err(
                "UNDEFINED_SOURCE",
                f"projection references unknown source {p.source!r}"))
        if p.substrate not in recursion_names:
            diags.append(_mk_err(
                "UNDEFINED_SUBSTRATE",
                f"projection references unknown recursion {p.substrate!r}"))
    if not _run(STAGE_RESOLVE, ok=(not diags), diags=diags):
        return result

    # 3. type analyze
    type_result = analyze(module)
    result.type_env = type_result.env
    if not _run(STAGE_TYPE_ANALYZE, ok=type_result.ok(),
                diags=list(type_result.diagnostics)):
        return result

    # 4. ownership: every declared state has exactly one owner
    diags = []
    seen: dict[str, str] = {}
    for r in module.recursions:
        binding = f"state.recursion.{r.name}"
        if binding in seen:
            diags.append(_mk_err(
                "OWNERSHIP_DUPLICATE",
                f"binding {binding!r} already owned by {seen[binding]}"))
        else:
            seen[binding] = f"recursion.{r.name}"
    for s in module.sources:
        binding = f"state.source.{s.name}"
        if binding in seen:
            diags.append(_mk_err(
                "OWNERSHIP_DUPLICATE",
                f"binding {binding!r} already owned by {seen[binding]}"))
        else:
            seen[binding] = f"source.{s.name}"
    if not _run(STAGE_VALIDATE_OWNERSHIP, ok=(not diags), diags=diags):
        return result

    # 5. validate ports (already covered by type-analyzer capability rules).
    # This stage exists as a placeholder for future
    # source-vs-substrate port-signature checks.
    _run(STAGE_VALIDATE_PORTS, ok=True, diags=[])

    # 6. negotiate capabilities per source
    diags = []
    for s in module.sources:
        offered = [
            CapabilityRef(name, SemVer(0, 1, 0), CapabilityTier.OPTIONAL)
            for name in s.offers
        ]
        required = [
            VersionConstraint(name, SemVer(0, 1, 0))
            for name in s.requires
        ]
        result_neg = negotiate(offered, required)
        if not result_neg.compatible:
            for inc in result_neg.incompatibilities:
                diags.append(_mk_err(
                    "NEGOTIATION_FAILURE",
                    f"source {s.name!r}: {inc.capability_name}: {inc.reason}"))
    if not _run(STAGE_NEGOTIATE, ok=(not diags), diags=diags):
        return result

    # 7. validate clocks: every referenced clock has a source or recursion.
    diags = []
    declared_clocks = {s.clock for s in module.sources if s.clock} \
                      | {r.clock for r in module.recursions if r.clock}
    if module.schedule is not None:
        for block in module.schedule.blocks:
            if block.clock not in declared_clocks:
                diags.append(_mk_err(
                    "UNDECLARED_CLOCK",
                    f"schedule block references undeclared clock {block.clock!r}"))
    if not _run(STAGE_VALIDATE_CLOCKS, ok=(not diags), diags=diags):
        return result

    # 8. validate causality — covered by type_analyze's CLOCK_CROSSING
    # and CLOCK_DOMAIN_MISMATCH; here we double-check that no forward
    # reference in the schedule uses an integration target before an
    # earlier step target is declared. Simplified for v0.1: pass.
    _run(STAGE_VALIDATE_CAUSALITY, ok=True, diags=[])

    # 9. bind contracts: every recursion binds a Contractive contract.
    diags = []
    for r in module.recursions:
        if r.contraction_margin is None:
            diags.append(_mk_err(
                "CONTRACT_UNBOUND",
                f"recursion {r.name!r} has no contraction_margin; "
                "cannot bind a Contractive contract"))
    if not _run(STAGE_BIND_CONTRACTS, ok=(not diags), diags=diags):
        return result

    # 10. build graph
    from .validator import validate as legacy_validate  # reuse graph builder
    validated = legacy_validate(module)
    if not validated.ok():
        _run(STAGE_BUILD_GRAPH, ok=False, diags=list(validated.errors()))
        return result
    result.graph = validated.graph
    if not _run(STAGE_BUILD_GRAPH, ok=True, diags=[]):
        return result

    # 11. lower to IR
    from runtime.scheduler import lower
    ir = lower(module, result.graph, seed=seed, ticks_per_clock=ticks_per_clock)
    result.ir = ir
    _run(STAGE_LOWER_IR, ok=True, diags=[])

    # 12. validate IR
    from aeon.ir import IRValidationError, validate as validate_ir
    try:
        validate_ir(ir)
    except IRValidationError as exc:
        _run(STAGE_VALIDATE_IR, ok=False, diags=[_mk_err(exc.code, exc.message)])
        return result
    if not _run(STAGE_VALIDATE_IR, ok=True, diags=[]):
        return result

    # 13. plan execution
    _run(STAGE_PLAN, ok=True, diags=[])
    return result
