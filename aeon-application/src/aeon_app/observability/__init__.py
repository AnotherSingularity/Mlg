"""aeon_app.observability — append-only event log + non-invasive metrics.

The mandate §14 requires an append-only semantic event log; §20
requires tracing that is semantically neutral (enabled vs disabled
must produce identical semantic outputs).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional, Tuple

from aeon.serialization import canonical_bytes, canonical_value, digest

from ..identity import app_event_id


EVENT_KINDS = (
    "ApplicationInitialized",
    "CertifiedStartupVerified",
    "SourceInitialized",
    "SourceStepped",
    "FrameEmitted",
    "WindowOpened",
    "FrameAggregated",
    "WindowClosed",
    "ProjectionApplied",
    "RecursionIntegrated",
    "FeedbackApplied",
    "CertificateIssued",
    "OutputEmitted",
    "SnapshotCreated",
    "SnapshotRestored",
    "TrainingStepCompleted",
    "RuntimeRejected",
    "RuntimeFailed",
)


@dataclass(frozen=True)
class Event:
    id: str                        # digest of event fields
    sequence: int                  # logical order (0-based)
    kind: str
    component_id: Optional[str]
    clock_domain_id: Optional[str]
    clock_tick: Optional[int]
    parent_event_ids: Tuple[str, ...]
    state_ids: Tuple[str, ...]
    result_status: str
    body: Mapping[str, Any]

    def to_canonical(self) -> dict:
        return canonical_value({
            "id": self.id,
            "sequence": self.sequence,
            "kind": self.kind,
            "component_id": self.component_id,
            "clock_domain_id": self.clock_domain_id,
            "clock_tick": self.clock_tick,
            "parent_event_ids": sorted(self.parent_event_ids),
            "state_ids": sorted(self.state_ids),
            "result_status": self.result_status,
            "body": dict(self.body),
        })


class EventLog:
    """Append-only. `record(...)` returns the new Event."""

    def __init__(self, *, tracing_enabled: bool = True) -> None:
        self._events: List[Event] = []
        self.tracing_enabled = tracing_enabled

    def record(self, *, kind: str, component_id: Optional[str] = None,
               clock_domain_id: Optional[str] = None,
               clock_tick: Optional[int] = None,
               parent_event_ids: Tuple[str, ...] = (),
               state_ids: Tuple[str, ...] = (),
               result_status: str = "APPLIED",
               body: Optional[Mapping[str, Any]] = None) -> Event:
        if kind not in EVENT_KINDS:
            raise ValueError(f"unknown event kind {kind!r}")
        body = dict(body or {})
        sequence = len(self._events)
        body_digest = digest(canonical_value(body))
        ident = app_event_id(kind=kind, sequence=sequence,
                             parent_event_ids=parent_event_ids,
                             body_digest=body_digest)
        e = Event(id=ident.digest, sequence=sequence, kind=kind,
                  component_id=component_id,
                  clock_domain_id=clock_domain_id, clock_tick=clock_tick,
                  parent_event_ids=parent_event_ids,
                  state_ids=state_ids, result_status=result_status,
                  body=body)
        if self.tracing_enabled:
            self._events.append(e)
        return e

    def events(self) -> Tuple[Event, ...]:
        return tuple(self._events)

    def canonical(self) -> list:
        return [e.to_canonical() for e in self._events]

    def digest(self) -> str:
        return digest(self.canonical())
