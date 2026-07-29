"""Aeon static type analyzer.

Runs after :mod:`compiler.parser` and before :mod:`compiler.validator`
(the two are being decoupled in a later closure commit; today the
analyzer is called by the validator's staged pipeline).

Given a parsed :class:`compiler.ast.Module`, the analyzer resolves
types for every declaration and produces:

- a :class:`TypeEnv` binding source names, recursion names,
  projection ids, and capability names to their AeonType values;
- a list of typed diagnostics for any static violation.

The analyzer covers, so far as the declarative Aeon syntax permits:

- source declaration: infer emitted payload type (``Signal<Vec<Float,dim>,clock>``);
- recursion declaration: infer state type
  (``State<Vector<Float,dim>, owner, clock>``);
- projection: check emitted source type is convertible into the
  substrate's ManifoldInput vector shape;
- capability references: check names are reserved;
- clock references: check names are declared;
- schedule statements: check that step/integrate/certify/emit
  targets refer to well-typed source/recursion nodes and that the
  ambient clock is compatible with the target's declared clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from aeon.capability import (
    PROVISIONAL_CAPABILITY_NAMES,
    REQUIRED_CAPABILITY_NAMES,
)
from aeon.core import Diagnostic, Severity, SourceSpan
from aeon.types import (
    AeonType,
    Float,
    Frame,
    Signal,
    State,
    Vector,
    can_convert,
    Convertibility,
)

from .ast import (
    CertifyStmt,
    EmitStmt,
    EveryBlock,
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
class TypeEnv:
    sources: Dict[str, Tuple[AeonType, str]] = field(default_factory=dict)   # name -> (Signal type, clock)
    recursions: Dict[str, Tuple[AeonType, int, str, float]] = field(default_factory=dict)
    projections: Dict[str, Tuple[str, str, str]] = field(default_factory=dict)  # id -> (src, port, sub)
    clocks: Dict[str, str] = field(default_factory=dict)  # name -> kind


@dataclass
class TypeAnalysisResult:
    env: TypeEnv
    diagnostics: List[Diagnostic]

    def ok(self) -> bool:
        return not any(d.severity is Severity.ERROR for d in self.diagnostics)

    def errors(self) -> List[Diagnostic]:
        return [d for d in self.diagnostics if d.severity is Severity.ERROR]


def _span(node) -> Optional[SourceSpan]:
    if getattr(node, "span", None) is None:
        return None
    s = node.span
    return SourceSpan(file=s.file, start_line=s.line, start_col=s.col,
                      end_line=s.line, end_col=s.col + 1)


def _err(diags: List[Diagnostic], code: str, message: str, span=None,
         expected: Optional[str] = None, actual: Optional[str] = None,
         remediation: Optional[str] = None) -> None:
    detail = message
    if expected or actual:
        detail = f"{detail} (expected: {expected!r}, actual: {actual!r})"
    diags.append(Diagnostic(
        severity=Severity.ERROR, code=code, message=detail,
        source_span=span, remediation=remediation,
    ))


DEFAULT_DIM = 4  # applied when no explicit dimension is stated on a source.


def analyze(module: Module) -> TypeAnalysisResult:
    diags: List[Diagnostic] = []
    env = TypeEnv()

    source_names = {s.name for s in module.sources}
    recursion_names = {r.name for r in module.recursions}

    # ---- clocks --------------------------------------------------------
    for s in module.sources:
        if s.clock:
            env.clocks.setdefault(s.clock, "Token" if s.clock == "token" else "UserDefined")
    for r in module.recursions:
        if r.clock:
            env.clocks.setdefault(r.clock, "Integration" if r.clock == "integration" else "UserDefined")

    # ---- source types --------------------------------------------------
    for s in module.sources:
        if s.name in recursion_names:
            _err(diags, "NAME_COLLISION",
                 f"source {s.name!r} collides with recursion of the same name",
                 _span(s))
            continue
        # Cap names
        for cap in list(s.requires) + list(s.offers):
            if cap not in ALL_RESERVED_CAPABILITIES:
                _err(diags, "UNKNOWN_CAPABILITY",
                     f"source {s.name!r} references unknown capability {cap!r}",
                     _span(s),
                     expected=f"one of {sorted(ALL_RESERVED_CAPABILITIES)}",
                     actual=cap)
        missing = [c for c in REQUIRED_CAPABILITY_NAMES if c not in s.offers]
        if missing:
            _err(diags, "REQUIRED_CAPABILITY_MISSING",
                 f"source {s.name!r} missing REQUIRED capabilities {sorted(missing)}",
                 _span(s),
                 remediation="Add all of VectorRead, VectorDrive, PerTokenStep to offers.")
        # Emitted signal payload type
        # Sources here declare no dimension in the current syntax;
        # the projection carries the target dim. Assume the source
        # emits Vector<Float,?> until proven otherwise.
        env.sources[s.name] = (Signal(Vector(Float("f64"), None), s.clock or "token"), s.clock or "token")

    # ---- recursion types -----------------------------------------------
    for r in module.recursions:
        if r.dimension is None or r.dimension <= 0:
            _err(diags, "INVALID_DIMENSION",
                 f"recursion {r.name!r}: dimension must be a positive integer",
                 _span(r), actual=str(r.dimension))
            continue
        if r.contraction_margin is None:
            _err(diags, "MISSING_CONTRACTION_MARGIN",
                 f"recursion {r.name!r} MUST declare contraction_margin",
                 _span(r))
            continue
        if not (0.0 < r.contraction_margin < 1.0):
            _err(diags, "INVALID_CONTRACTION_MARGIN",
                 f"recursion {r.name!r}: contraction_margin must lie in (0, 1)",
                 _span(r), actual=str(r.contraction_margin))
            continue
        env.recursions[r.name] = (
            State(Vector(Float("f64"), r.dimension), f"recursion.{r.name}", r.clock or "integration"),
            r.dimension, r.clock or "integration", r.contraction_margin,
        )

    # ---- projections ---------------------------------------------------
    for p in module.projections:
        if p.source not in source_names:
            _err(diags, "UNDEFINED_SOURCE",
                 f"projection references unknown source {p.source!r}", _span(p))
            continue
        if p.substrate not in recursion_names:
            _err(diags, "UNDEFINED_SUBSTRATE",
                 f"projection references unknown recursion {p.substrate!r}", _span(p))
            continue
        # Check shape compatibility: source emits Vector<Float,?>, substrate
        # expects Vector<Float,dim>. `?` matches any concrete dim, so
        # convertibility is LOSSLESS.
        src_ty, _ = env.sources[p.source]
        sub_ty, sub_dim, sub_clock, _ = env.recursions[p.substrate]
        emitted = src_ty.params[0]  # Vector
        expected = Vector(Float("f64"), sub_dim)
        conv = can_convert(emitted, expected)
        if conv is Convertibility.PROHIBITED:
            _err(diags, "PROJECTION_TYPE_MISMATCH",
                 f"projection {p.source}.{p.port} -> {p.substrate} type mismatch",
                 _span(p),
                 expected=str(expected.to_canonical()),
                 actual=str(emitted.to_canonical()))
        pid = f"{p.source}.{p.port}.{p.substrate}"
        env.projections[pid] = (p.source, p.port, p.substrate)

    # ---- schedule / clock consistency ---------------------------------
    if module.schedule is not None:
        for block in module.schedule.blocks:
            if block.clock not in env.clocks:
                _err(diags, "UNDECLARED_CLOCK",
                     f"schedule block references undeclared clock {block.clock!r}",
                     _span(block))
                continue
            if block.every <= 0:
                _err(diags, "INVALID_EVERY",
                     f"'every {block.every}' must be positive", _span(block))
            for stmt in block.body:
                target = getattr(stmt, "target", None)
                if isinstance(stmt, StepStmt):
                    if target not in env.sources:
                        _err(diags, "UNDEFINED_STEP_TARGET",
                             f"step target {target!r} is not a declared source",
                             _span(stmt))
                        continue
                    _, src_clock = env.sources[target]
                    if src_clock != block.clock:
                        _err(diags, "CLOCK_DOMAIN_MISMATCH",
                             f"step {target!r} declared in clock {src_clock!r} "
                             f"but scheduled under clock {block.clock!r}",
                             _span(stmt),
                             remediation="Move the step into the matching clock block, "
                                         "or declare an explicit clock relation.")
                elif isinstance(stmt, (IntegrateStmt, CertifyStmt)):
                    if target not in env.recursions:
                        _err(diags, "UNDEFINED_RECURSION_TARGET",
                             f"target {target!r} is not a declared recursion",
                             _span(stmt))
                        continue
                    _, _, rec_clock, _ = env.recursions[target]
                    if isinstance(stmt, IntegrateStmt) and rec_clock != block.clock:
                        _err(diags, "CLOCK_CROSSING_UNDECLARED",
                             f"integrate {target!r} under clock {block.clock!r} "
                             f"but recursion declared in clock {rec_clock!r}",
                             _span(stmt),
                             remediation="Align the schedule block or declare a clock relation.")
                elif isinstance(stmt, EmitStmt):
                    if target not in env.sources:
                        _err(diags, "UNDEFINED_EMIT_TARGET",
                             f"emit target {target!r} is not a declared source",
                             _span(stmt))

    return TypeAnalysisResult(env=env, diagnostics=diags)
