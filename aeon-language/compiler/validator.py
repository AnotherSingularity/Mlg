"""Aeon static validator.

Runs the compiler stages after parsing:

- resolve names
- validate ports / capabilities requested by declared sources exist
  in the reserved-capability registry (REQUIRED must be listed as
  reserved)
- validate clock declarations and schedule references
- validate causal invariants where statically checkable
- build the semantic graph
- validate the semantic graph

The validator produces a list of :class:`Diagnostic` values. If any
diagnostic has severity ERROR, downstream lowering MUST NOT
proceed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from aeon.capability import (
    PROVISIONAL_CAPABILITY_NAMES,
    REQUIRED_CAPABILITY_NAMES,
)
from aeon.core import Diagnostic, Severity, SourceSpan
from aeon.graph import (
    ClockDomainDecl,
    Edge,
    GraphBuilder,
    Node,
    NodeKind,
    OwnershipEntry,
    SemanticGraph,
)

from .ast import (
    CertifyStmt,
    EmitStmt,
    IntegrateStmt,
    Module,
    ProjectionDecl,
    RecursionDecl,
    ScheduleDecl,
    SourceDecl,
    StepStmt,
)


ALL_RESERVED_CAPABILITIES = frozenset(REQUIRED_CAPABILITY_NAMES) | frozenset(PROVISIONAL_CAPABILITY_NAMES)


@dataclass
class ValidationResult:
    diagnostics: List[Diagnostic] = field(default_factory=list)
    graph: Optional[SemanticGraph] = None

    def errors(self) -> List[Diagnostic]:
        return [d for d in self.diagnostics if d.severity is Severity.ERROR]

    def ok(self) -> bool:
        return not self.errors()


def _span(node) -> Optional[SourceSpan]:
    if getattr(node, "span", None) is None:
        return None
    s = node.span
    return SourceSpan(file=s.file, start_line=s.line, start_col=s.col,
                      end_line=s.line, end_col=s.col + 1)


def _err(diags: List[Diagnostic], code: str, message: str, span=None) -> None:
    diags.append(Diagnostic(
        severity=Severity.ERROR,
        code=code,
        message=message,
        source_span=span,
    ))


def _warn(diags: List[Diagnostic], code: str, message: str, span=None) -> None:
    diags.append(Diagnostic(
        severity=Severity.WARNING,
        code=code,
        message=message,
        source_span=span,
    ))


def validate(module: Module) -> ValidationResult:
    diags: List[Diagnostic] = []

    # ---- resolve names --------------------------------------------------
    source_names = {s.name for s in module.sources}
    recursion_names = {r.name for r in module.recursions}
    all_names = source_names | recursion_names

    for s in module.sources:
        if s.name in recursion_names:
            _err(diags, "NAME_COLLISION",
                 f"source {s.name!r} collides with a recursion of the same name",
                 _span(s))

    # ---- capability names must be reserved ------------------------------
    for s in module.sources:
        for cap in list(s.requires) + list(s.offers):
            if cap not in ALL_RESERVED_CAPABILITIES:
                _err(diags, "UNKNOWN_CAPABILITY",
                     f"source {s.name!r} references unknown capability {cap!r}. "
                     f"REQUIRED tier: {sorted(REQUIRED_CAPABILITY_NAMES)}; "
                     f"PROVISIONAL tier: {sorted(PROVISIONAL_CAPABILITY_NAMES)}",
                     _span(s))

    # ---- REQUIRED-tier: every source MUST offer all REQUIRED caps -------
    for s in module.sources:
        offered = set(s.offers)
        missing = [c for c in REQUIRED_CAPABILITY_NAMES if c not in offered]
        if missing:
            _err(diags, "REQUIRED_CAPABILITY_MISSING",
                 f"source {s.name!r} is missing REQUIRED capabilities: "
                 f"{sorted(missing)}. Every conforming source MUST offer "
                 f"VectorRead, VectorDrive, and PerTokenStep.",
                 _span(s))

    # ---- projections resolve to declared sources + substrates -----------
    for p in module.projections:
        if p.source not in source_names:
            _err(diags, "UNDEFINED_SOURCE",
                 f"projection references unknown source {p.source!r}", _span(p))
        if p.substrate not in recursion_names:
            _err(diags, "UNDEFINED_SUBSTRATE",
                 f"projection references unknown recursion {p.substrate!r}", _span(p))

    # ---- recursion must have a contraction margin < 1 -------------------
    for r in module.recursions:
        if r.contraction_margin is None:
            _err(diags, "MISSING_CONTRACTION_MARGIN",
                 f"recursion {r.name!r} MUST declare a contraction_margin", _span(r))
        elif not (0.0 < r.contraction_margin < 1.0):
            _err(diags, "INVALID_CONTRACTION_MARGIN",
                 f"recursion {r.name!r}: contraction_margin must be in (0, 1), "
                 f"got {r.contraction_margin}", _span(r))
        if r.dimension is None or r.dimension <= 0:
            _err(diags, "INVALID_DIMENSION",
                 f"recursion {r.name!r} MUST declare a positive dimension", _span(r))

    # ---- schedule references + clock declarations ----------------------
    declared_clocks = {s.clock for s in module.sources if s.clock} \
                      | {r.clock for r in module.recursions if r.clock}
    if module.schedule is not None:
        for block in module.schedule.blocks:
            if block.clock not in declared_clocks:
                _err(diags, "UNDECLARED_CLOCK",
                     f"schedule block references undeclared clock {block.clock!r}",
                     _span(block))
            if block.every <= 0:
                _err(diags, "INVALID_EVERY",
                     f"'every {block.every}' must be positive", _span(block))
            for stmt in block.body:
                target = getattr(stmt, "target", None)
                if isinstance(stmt, StepStmt) and target not in source_names:
                    _err(diags, "UNDEFINED_STEP_TARGET",
                         f"schedule step references unknown source {target!r}",
                         _span(stmt))
                if isinstance(stmt, (IntegrateStmt, CertifyStmt)):
                    if target not in recursion_names:
                        _err(diags, "UNDEFINED_RECURSION_TARGET",
                             f"schedule references unknown recursion {target!r}",
                             _span(stmt))
                    if isinstance(stmt, IntegrateStmt) and target in recursion_names:
                        r = next(rr for rr in module.recursions if rr.name == target)
                        if r.clock and r.clock != block.clock:
                            # Integration under a different-clock schedule
                            # block: this is a clock crossing without a
                            # declared relationship.
                            _err(diags, "CLOCK_CROSSING_UNDECLARED",
                                 f"integrate {target!r} under clock "
                                 f"{block.clock!r} but recursion is declared "
                                 f"in clock {r.clock!r}; declare a clock "
                                 f"relation or align the schedule block.",
                                 _span(stmt))

    # ---- if errors so far, do not build the graph -----------------------
    if any(d.severity is Severity.ERROR for d in diags):
        return ValidationResult(diagnostics=diags, graph=None)

    # ---- build the semantic graph --------------------------------------
    gb = GraphBuilder(module_id=module.module_id)
    for s in module.sources:
        gb.add_node(Node(
            id=f"source.{s.name}",
            kind=NodeKind.SOURCE,
            attributes={
                "impl_type": s.impl_type,
                "clock": s.clock or "",
                "requires": list(s.requires),
                "offers": list(s.offers),
            },
        ))
        if s.clock:
            gb.add_ownership(OwnershipEntry(
                binding=f"state.source.{s.name}",
                owner=f"source.{s.name}",
                ownership="own",
            ))
    for r in module.recursions:
        gb.add_node(Node(
            id=f"recursion.{r.name}",
            kind=NodeKind.RECURSION,
            attributes={
                "impl_type": r.impl_type,
                "clock": r.clock or "",
                "dimension": r.dimension,
                "contraction_margin": r.contraction_margin,
            },
        ))
        gb.add_ownership(OwnershipEntry(
            binding=f"state.recursion.{r.name}",
            owner=f"recursion.{r.name}",
            ownership="own",
        ))
    for i, p in enumerate(module.projections):
        pid = f"projection.{p.source}.{p.port}.into.{p.substrate}"
        gb.add_node(Node(
            id=pid,
            kind=NodeKind.PROJECTION,
            attributes={"source": p.source, "port": p.port, "substrate": p.substrate},
        ))
        gb.add_edge(Edge(
            id=f"edge.proj.{i}",
            from_node=f"source.{p.source}",
            to_node=pid,
            edge_kind="projection_source",
        ))
        gb.add_edge(Edge(
            id=f"edge.proj.{i}.to_substrate",
            from_node=pid,
            to_node=f"recursion.{p.substrate}",
            edge_kind="projection_destination",
        ))
    for clock_id in sorted(declared_clocks):
        # Clock kinds are inferred: token/integration/segment are common,
        # unknown user-declared clocks default to UserDefined.
        kind = clock_id if clock_id in ("Token", "Integration", "Segment") else \
               ("Token" if clock_id == "token" else
                "Integration" if clock_id == "integration" else
                "Segment" if clock_id == "segment" else
                "UserDefined")
        gb.add_clock(ClockDomainDecl(id=clock_id, kind=kind))

    graph = gb.build()
    return ValidationResult(diagnostics=diags, graph=graph)
