"""Aeon canonical source formatter.

Produces one canonical source representation given a parsed
:class:`~.ast.Module`. Two source texts that parse to equivalent
modules format to identical text.
"""

from __future__ import annotations

from typing import Any

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


def format_module(module: Module) -> str:
    lines: list[str] = []

    for src in module.sources:
        lines.append(_format_source(src))
        lines.append("")
    for rec in module.recursions:
        lines.append(_format_recursion(rec))
        lines.append("")
    for proj in module.projections:
        lines.append(_format_projection(proj))
    if module.projections:
        lines.append("")
    if module.schedule is not None:
        lines.append(_format_schedule(module.schedule))
        lines.append("")

    text = "\n".join(lines).rstrip() + "\n"
    return text


def _format_source(src: SourceDecl) -> str:
    body_lines = [f"source {src.name}: {src.impl_type} {{"]
    if src.clock is not None:
        body_lines.append(f"    clock: {src.clock}")
    if src.requires:
        body_lines.append(f"    requires: {', '.join(src.requires)}")
    if src.offers:
        body_lines.append(f"    offers: {', '.join(src.offers)}")
    for k, v in src.attributes:
        body_lines.append(f"    {k}: {_format_value(v)}")
    body_lines.append("}")
    return "\n".join(body_lines)


def _format_recursion(rec: RecursionDecl) -> str:
    body_lines = [f"recursion {rec.name}: {rec.impl_type} {{"]
    if rec.dimension is not None:
        body_lines.append(f"    dimension: {rec.dimension}")
    if rec.clock is not None:
        body_lines.append(f"    clock: {rec.clock}")
    if rec.contraction_margin is not None:
        body_lines.append(f"    contraction_margin: {_format_value(rec.contraction_margin)}")
    for k, v in rec.attributes:
        body_lines.append(f"    {k}: {_format_value(v)}")
    body_lines.append("}")
    return "\n".join(body_lines)


def _format_projection(proj: ProjectionDecl) -> str:
    return f"project {proj.source}.{proj.port} into {proj.substrate}"


def _format_schedule(sched: ScheduleDecl) -> str:
    out = ["schedule {"]
    for i, block in enumerate(sched.blocks):
        if i:
            out.append("")
        prefix = "    every " + (f"{block.every} {block.clock}" if block.every != 1 else block.clock)
        out.append(f"{prefix} {{")
        for stmt in block.body:
            out.append(f"        {_format_stmt(stmt)}")
        out.append("    }")
    out.append("}")
    return "\n".join(out)


def _format_stmt(stmt: Any) -> str:
    if isinstance(stmt, StepStmt):
        return f"step {stmt.target}"
    if isinstance(stmt, IntegrateStmt):
        return f"integrate {stmt.target}"
    if isinstance(stmt, CertifyStmt):
        return f"certify {stmt.target}"
    if isinstance(stmt, EmitStmt):
        return f"emit {stmt.target}"
    raise TypeError(f"unknown schedule statement type {type(stmt).__name__}")


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        # Shortest round-trip.
        text = repr(value)
        return text
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ", ".join(_format_value(v) for v in value)
    raise TypeError(f"unformattable value {type(value).__name__}")
