"""aeon.causality — runtime causality checks.

Enforces the invariants documented in
specification/04-TIME-AND-CAUSALITY.md §5. The checks are pure
predicates over already-constructed Aeon values; they raise
:class:`CausalityViolation` on failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from .clock import ClockPosition, ClockRelation, Window
from .signal import SignalFrame


class CausalityViolation(Exception):
    """A frame or state was observed in a way that violates causality."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


def no_future_leakage(observed: ClockPosition, observer: ClockPosition) -> None:
    """Raise if ``observed`` is later than ``observer`` in the same domain."""
    if observed.domain_id != observer.domain_id:
        raise CausalityViolation(
            "CROSS_DOMAIN",
            f"cannot compare {observed.domain_id!r} to {observer.domain_id!r} "
            "without a declared ClockRelation",
        )
    if observed.tick > observer.tick:
        raise CausalityViolation(
            "FUTURE_LEAKAGE",
            f"observed tick {observed.tick} > observer tick {observer.tick} "
            f"in domain {observed.domain_id!r}",
        )


def enforce_order(frames: Iterable[SignalFrame]) -> None:
    """Raise if the frame sequence is not strictly monotonic in tick."""
    previous = None
    for f in frames:
        if previous is not None:
            if f.clock_position.domain_id != previous.clock_position.domain_id:
                raise CausalityViolation(
                    "CROSS_DOMAIN",
                    "frames span multiple clock domains without a "
                    "declared ClockRelation",
                )
            if f.clock_position.tick <= previous.clock_position.tick:
                raise CausalityViolation(
                    "ORDER_VIOLATION",
                    f"non-monotonic frame sequence: {previous.clock_position.tick} "
                    f"-> {f.clock_position.tick}",
                )
        previous = f


def window_contains(window: Window, position: ClockPosition) -> None:
    """Raise if ``position`` is not a member of ``window``."""
    if not window.contains(position):
        raise CausalityViolation(
            "WINDOW_MEMBERSHIP",
            f"position ({position.domain_id}, {position.tick}) is outside "
            f"window {window.id} [{window.start}, {window.end}) in domain {window.domain_id}",
        )


def cross_domain_authorized(a_domain: str, b_domain: str,
                            relations: Iterable[ClockRelation]) -> Optional[ClockRelation]:
    """Return the ClockRelation authorizing a-domain <-> b-domain, or None."""
    for rel in relations:
        if {rel.a, rel.b} == {a_domain, b_domain}:
            return rel
    return None
