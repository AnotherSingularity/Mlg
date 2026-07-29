"""Aeon source AST.

Lightweight AST types produced by the parser and consumed by the
lowerer. AST nodes carry source spans for diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple


@dataclass(frozen=True)
class Span:
    line: int
    col: int
    file: str


@dataclass(frozen=True)
class SourceDecl:
    name: str
    impl_type: str
    clock: Optional[str] = None
    requires: Tuple[str, ...] = ()
    offers: Tuple[str, ...] = ()
    attributes: Tuple[Tuple[str, Any], ...] = ()
    span: Optional[Span] = None


@dataclass(frozen=True)
class RecursionDecl:
    name: str
    impl_type: str
    clock: Optional[str] = None
    dimension: Optional[int] = None
    contraction_margin: Optional[float] = None
    attributes: Tuple[Tuple[str, Any], ...] = ()
    span: Optional[Span] = None


@dataclass(frozen=True)
class ProjectionDecl:
    """`project <source>.<port> into <substrate>`."""

    source: str
    port: str
    substrate: str
    span: Optional[Span] = None


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StepStmt:
    target: str
    span: Optional[Span] = None


@dataclass(frozen=True)
class IntegrateStmt:
    target: str
    span: Optional[Span] = None


@dataclass(frozen=True)
class CertifyStmt:
    target: str
    span: Optional[Span] = None


@dataclass(frozen=True)
class EmitStmt:
    target: str
    span: Optional[Span] = None


ScheduleStmt = "StepStmt | IntegrateStmt | CertifyStmt | EmitStmt"


@dataclass(frozen=True)
class EveryBlock:
    every: int  # 1 means "every <clock>"; n means "every n <clock>"
    clock: str
    body: Tuple[Any, ...]  # ScheduleStmt values
    span: Optional[Span] = None


@dataclass(frozen=True)
class ScheduleDecl:
    blocks: Tuple[EveryBlock, ...]
    span: Optional[Span] = None


# ---------------------------------------------------------------------------
# Module
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Module:
    module_id: str
    sources: Tuple[SourceDecl, ...] = ()
    recursions: Tuple[RecursionDecl, ...] = ()
    projections: Tuple[ProjectionDecl, ...] = ()
    schedule: Optional[ScheduleDecl] = None
