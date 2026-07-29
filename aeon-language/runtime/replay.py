"""Aeon deterministic replay driver.

Runs the reference interpreter twice on the same IR module and
verifies that the two runs produce byte-identical outputs, state
identifiers, and certificate contents.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from aeon.ir import IRModule
from aeon.port import SignalSourcePort
from aeon.recursion import RecursionSubstrate
from aeon.serialization import canonical_bytes, canonical_value

from .interpreter import ExecutionOutcome, Interpreter


@dataclass
class ReplayReport:
    identical: bool
    difference: str = ""
    outcome_a: ExecutionOutcome = None
    outcome_b: ExecutionOutcome = None


def replay(
    module: IRModule,
    *,
    sources_factory,
    substrates_factory,
    seed: int = 0,
) -> ReplayReport:
    """Run the same module twice and diff the canonical outputs.

    ``sources_factory`` and ``substrates_factory`` are callables
    returning fresh instances each time (so the two runs do not
    share mutable state).
    """

    sa = sources_factory()
    da = substrates_factory()
    outcome_a = Interpreter(module, sources=sa, substrates=da, seed=seed).run()

    sb = sources_factory()
    db = substrates_factory()
    outcome_b = Interpreter(module, sources=sb, substrates=db, seed=seed).run()

    def summarize(o: ExecutionOutcome) -> bytes:
        return canonical_bytes(canonical_value({
            "outputs": [
                {"id": f.id.digest, "payload_digest": f.payload_digest(),
                 "clock_domain_id": f.clock_position.domain_id,
                 "clock_tick": f.clock_position.tick}
                for f in o.outputs
            ],
            "contraction_certificates": [c.to_canonical() for c in o.contraction_certificates],
            "trace_opcodes": [t.opcode for t in o.trace],
            "trace_summaries": [t.result_summary for t in o.trace],
            "halt_reason": o.halt_reason,
        }))

    a = summarize(outcome_a)
    b = summarize(outcome_b)
    if a == b:
        return ReplayReport(identical=True, outcome_a=outcome_a, outcome_b=outcome_b)
    return ReplayReport(
        identical=False,
        difference=f"len {len(a)} vs {len(b)} bytes",
        outcome_a=outcome_a,
        outcome_b=outcome_b,
    )
