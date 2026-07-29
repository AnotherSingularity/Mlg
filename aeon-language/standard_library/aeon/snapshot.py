"""aeon.snapshot — snapshot envelope and restore utilities.

Provides the mandated snapshot envelope from Phase 0.1 §12: every
snapshot MUST include or reference language version, IR version,
graph identity, backend identity, state identities, payloads,
owners, lineage, clock positions, active windows, active contracts,
capability negotiation result, random-state, and implementation
version.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence, Tuple

from . import INSTRUCTION_SET_VERSION, IR_VERSION, LANGUAGE_VERSION, STDLIB_VERSION
from .core import Identity
from .provenance import make_identity
from .serialization import canonical_bytes, canonical_value


@dataclass(frozen=True)
class SnapshotEnvelope:
    """Complete snapshot record. Mandate §12."""

    id: Identity
    language_version: str
    ir_version: str
    instruction_set_version: str
    stdlib_version: str
    graph_id: str
    backend_id: str
    state_snapshots: Tuple[Any, ...]  # substrate/source snapshots
    active_contracts: Tuple[str, ...]
    active_windows: Tuple[Any, ...]
    negotiation_result: Optional[dict]
    random_state: Optional[dict]
    implementation: str

    def to_canonical(self) -> dict:
        return canonical_value({
            "id": self.id.digest,
            "language_version": self.language_version,
            "ir_version": self.ir_version,
            "instruction_set_version": self.instruction_set_version,
            "stdlib_version": self.stdlib_version,
            "graph_id": self.graph_id,
            "backend_id": self.backend_id,
            "state_snapshots": [_snap_canonical(s) for s in self.state_snapshots],
            "active_contracts": list(self.active_contracts),
            "active_windows": [_window_canonical(w) for w in self.active_windows],
            "negotiation_result": self.negotiation_result,
            "random_state": self.random_state,
            "implementation": self.implementation,
        })

    def to_bytes(self) -> bytes:
        return canonical_bytes(self.to_canonical())


def _snap_canonical(snap: Any) -> dict:
    if hasattr(snap, "to_canonical"):
        return snap.to_canonical()
    return {
        "kind": type(snap).__name__,
        "id": getattr(getattr(snap, "id", None), "digest", None),
    }


def _window_canonical(win: Any) -> dict:
    return {
        "id": getattr(win, "id", None),
        "domain_id": getattr(win, "domain_id", None),
        "start": getattr(win, "start", None),
        "end": getattr(win, "end", None),
    }


def envelope(
    *,
    graph_id: str,
    backend_id: str,
    state_snapshots: Sequence[Any] = (),
    active_contracts: Sequence[str] = (),
    active_windows: Sequence[Any] = (),
    negotiation_result: Optional[dict] = None,
    random_state: Optional[dict] = None,
    implementation: str = "aeon.reference/0.1.0-dev",
) -> SnapshotEnvelope:
    ident_body = {
        "graph_id": graph_id,
        "backend_id": backend_id,
        "state_snapshots": [
            getattr(getattr(s, "id", None), "digest", None)
            for s in state_snapshots
        ],
        "active_contracts": sorted(active_contracts),
    }
    return SnapshotEnvelope(
        id=make_identity("snapshot_envelope", ident_body),
        language_version=LANGUAGE_VERSION,
        ir_version=IR_VERSION,
        instruction_set_version=INSTRUCTION_SET_VERSION,
        stdlib_version=STDLIB_VERSION,
        graph_id=graph_id,
        backend_id=backend_id,
        state_snapshots=tuple(state_snapshots),
        active_contracts=tuple(sorted(active_contracts)),
        active_windows=tuple(active_windows),
        negotiation_result=negotiation_result,
        random_state=random_state,
        implementation=implementation,
    )


__all__ = ["SnapshotEnvelope", "envelope"]
