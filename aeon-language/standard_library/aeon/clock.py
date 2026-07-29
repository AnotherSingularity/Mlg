"""aeon.clock — clock domains, positions, and windows.

Implements the objects specified in ``04-TIME-AND-CAUSALITY.md``.
Clocks are pure values; they carry no scheduler state. The
scheduler in ``aeon.runtime`` advances them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple


class ClockKind(Enum):
    SOURCE_LOCAL = "SourceLocal"
    TOKEN = "Token"
    INTEGRATION = "Integration"
    SEGMENT = "Segment"
    USER_DEFINED = "UserDefined"


@dataclass(frozen=True)
class ClockDomain:
    """A named clock domain with a fixed kind and identity."""

    id: str
    kind: ClockKind

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("ClockDomain.id must be non-empty str")

    def position(self, tick: int) -> "ClockPosition":
        return ClockPosition(domain_id=self.id, tick=tick)


@dataclass(frozen=True)
class ClockPosition:
    domain_id: str
    tick: int

    def __post_init__(self) -> None:
        if not isinstance(self.domain_id, str) or not self.domain_id:
            raise ValueError("ClockPosition.domain_id must be non-empty str")
        if not isinstance(self.tick, int) or self.tick < 0:
            raise ValueError("ClockPosition.tick must be a non-negative int")

    def next(self) -> "ClockPosition":
        return ClockPosition(self.domain_id, self.tick + 1)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ClockPosition):
            return NotImplemented
        if other.domain_id != self.domain_id:
            raise ValueError(
                "cannot order ClockPositions from different domains "
                f"({self.domain_id!r} vs {other.domain_id!r}); "
                "declare a ClockRelation instead"
            )
        return self.tick < other.tick


# ---------------------------------------------------------------------------
# Clock relationships (spec 04 §3)
# ---------------------------------------------------------------------------


class ClockRelationKind(Enum):
    AGGREGATES_FROM = "AggregatesFrom"
    DERIVED_FROM = "DerivedFrom"
    INDEPENDENT = "Independent"


@dataclass(frozen=True)
class ClockRelation:
    a: str  # clock domain id (the "faster" domain for AGGREGATES_FROM)
    b: str  # clock domain id (the "slower" domain for AGGREGATES_FROM)
    kind: ClockRelationKind
    window_size: Optional[int] = None
    mapping_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.a == self.b:
            raise ValueError("ClockRelation must relate two distinct domains")
        if self.kind is ClockRelationKind.AGGREGATES_FROM:
            if self.window_size is None or self.window_size <= 0:
                raise ValueError(
                    "AggregatesFrom requires a positive window_size"
                )


# ---------------------------------------------------------------------------
# Windows (spec 04 §4)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Window:
    """A half-open interval [start, end) inside one clock domain."""

    id: str
    domain_id: str
    start: int
    end: int  # exclusive

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("Window.id must be non-empty str")
        if not isinstance(self.domain_id, str) or not self.domain_id:
            raise ValueError("Window.domain_id must be non-empty str")
        if not (isinstance(self.start, int) and isinstance(self.end, int)):
            raise ValueError("Window.start/end must be int")
        if self.start < 0 or self.end <= self.start:
            raise ValueError(
                f"Window must satisfy 0 <= start < end (got {self.start}, {self.end})"
            )

    def contains(self, position: ClockPosition) -> bool:
        return (
            position.domain_id == self.domain_id
            and self.start <= position.tick < self.end
        )

    def size(self) -> int:
        return self.end - self.start
