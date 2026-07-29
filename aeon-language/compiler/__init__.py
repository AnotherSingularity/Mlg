"""Aeon compiler — parser, formatter, static validator, IR lowerer.

The compiler consumes an Aeon source module (a string of source
text) and produces a validated :class:`~aeon.ir.IRModule`. Stages
follow specification/00-CONSTITUTION.md §Compiler stages:

    parse -> resolve -> validate types & shapes -> validate ownership
    -> validate ports & capabilities -> validate clocks & causality
    -> bind contracts -> build semantic graph -> canonicalize
    -> lower to IR -> validate IR -> generate execution plan.
"""

from __future__ import annotations
