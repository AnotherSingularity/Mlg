"""aeon_app.clocks — application clocks + aggregation windows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from aeon.clock import ClockPosition


@dataclass(frozen=True)
class Window:
    id: str
    domain_id: str
    start: int
    end: int                        # exclusive
    frame_ids: Tuple[str, ...] = ()

    def contains(self, position: ClockPosition) -> bool:
        return (position.domain_id == self.domain_id
                and self.start <= position.tick < self.end)


__all__ = ["Window", "ClockPosition"]
