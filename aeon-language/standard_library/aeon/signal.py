"""aeon.signal — signal frames and frame ranges."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, Sequence, Tuple, TypeVar

from .clock import ClockPosition
from .core import Identity
from .provenance import signal_id
from .serialization import canonical_value, digest

T = TypeVar("T")


@dataclass(frozen=True)
class SignalFrame(Generic[T]):
    """A typed, versioned signal frame emitted by a source."""

    id: Identity
    source_id: str
    sequence: int
    clock_position: ClockPosition
    payload: T
    originating_state_id: Identity
    provenance_ref: str = ""

    def payload_digest(self) -> str:
        return digest(canonical_value(self.payload))


def new_signal_frame(*, source_id: str, sequence: int,
                     clock_position: ClockPosition, payload: Any,
                     originating_state_id: Identity,
                     provenance_ref: str = "") -> SignalFrame[Any]:
    ident = signal_id(
        source=source_id,
        clock_domain_id=clock_position.domain_id,
        clock_tick=clock_position.tick,
        sequence=sequence,
        canonical_payload_digest=digest(canonical_value(payload)),
    )
    return SignalFrame(
        id=ident,
        source_id=source_id,
        sequence=sequence,
        clock_position=clock_position,
        payload=payload,
        originating_state_id=originating_state_id,
        provenance_ref=provenance_ref,
    )


@dataclass(frozen=True)
class FrameRange:
    """An identified range of frames in one clock domain."""

    id: Identity
    domain_id: str
    frame_ids: Tuple[str, ...]  # ordered by sequence
