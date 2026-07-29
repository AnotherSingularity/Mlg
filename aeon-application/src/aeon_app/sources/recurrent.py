"""PersistentRecurrentSource — Aeon-original recurrent signal source.

Deterministic decay-blended recurrent update with an explicit
per-instance association matrix. Provides:

- REQUIRED: VectorDrive, VectorRead, PerTokenStep
- OPTIONAL: MatrixRead, DecayControl, PerStepTransition,
  Snapshot, Restore, AssociationWrite (when a destination
  advertises it).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Tuple

from aeon.capability import CapabilityRef, CapabilityTier
from aeon.clock import ClockPosition
from aeon.core import SemVer, Validity
from aeon.port import (
    PortDescriptor,
    Ready,
    ReadRequest,
    ReadUnavailable,
    SourceSnapshot,
    SourceStepResult,
    StateModelRef,
    TypeRef,
)
from aeon.provenance import make_identity
from aeon.serialization import canonical_bytes
from aeon.signal import SignalFrame, new_signal_frame


@dataclass(frozen=True)
class RecurrentSourceState:
    id: Any
    payload: Tuple[float, ...]
    matrix: Tuple[Tuple[float, ...], ...]
    decay: float
    dimension: int
    tick: int
    seed: int


def _mv(m: Tuple[Tuple[float, ...], ...], v: Tuple[float, ...]) -> Tuple[float, ...]:
    return tuple(sum(m[i][j] * v[j] for j in range(len(v))) for i in range(len(m)))


class PersistentRecurrentSource:
    IMPL_ID = "aeon_app.sources.recurrent.PersistentRecurrentSource/0.1.0"

    def __init__(self, source_id: str = "recurrent", dimension: int = 4) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self.source_id = source_id
        self.dimension = dimension

    def describe(self) -> PortDescriptor:
        req = [
            CapabilityRef("VectorDrive", SemVer(1, 0, 0), CapabilityTier.REQUIRED),
            CapabilityRef("VectorRead", SemVer(1, 0, 0), CapabilityTier.REQUIRED),
            CapabilityRef("PerTokenStep", SemVer(1, 0, 0), CapabilityTier.REQUIRED),
        ]
        opt = [
            CapabilityRef("MatrixRead", SemVer(0, 1, 0), CapabilityTier.OPTIONAL),
            CapabilityRef("DecayControl", SemVer(0, 1, 0), CapabilityTier.OPTIONAL),
            CapabilityRef("PerStepTransition", SemVer(0, 1, 0), CapabilityTier.OPTIONAL),
            CapabilityRef("Snapshot", SemVer(0, 1, 0), CapabilityTier.OPTIONAL),
            CapabilityRef("Restore", SemVer(0, 1, 0), CapabilityTier.OPTIONAL),
        ]
        return PortDescriptor(
            port_id=f"port.{self.source_id}",
            port_version="0.1.0",
            required_capabilities=tuple(req),
            offered_capabilities=tuple(req + opt),
            accepted_input_types=(TypeRef("Signal<Vec>", "0.1.0"),),
            emitted_output_types=(TypeRef("Signal<Vec>", "0.1.0"),),
            clock_domain="source",
            state_model=StateModelRef("RecurrentSourceState", "0.1.0"),
        )

    def initialize(self, config: Mapping[str, Any], seed: int) -> RecurrentSourceState:
        payload = tuple(float(((seed + i) % 5)) * 0.1 for i in range(self.dimension))
        # Bounded association matrix; every row-sum <= 1 so the linear
        # part contributes at most L∞ radius equal to the source's
        # payload L∞ (a mild boundedness contract, not proof).
        raw = tuple(
            tuple(float(((seed + i * self.dimension + j) % 11)) * 0.05
                  for j in range(self.dimension))
            for i in range(self.dimension)
        )
        matrix = tuple(
            tuple(v / max(sum(abs(x) for x in row), 1.0) for v in row)
            for row in raw
        )
        ident = make_identity("aeon_app.source_state", {
            "impl": self.IMPL_ID, "source_id": self.source_id,
            "seed": seed, "payload": list(payload),
        })
        return RecurrentSourceState(
            id=ident, payload=payload, matrix=matrix,
            decay=0.5, dimension=self.dimension, tick=0, seed=seed,
        )

    def step(self, input: SignalFrame[Any], state: RecurrentSourceState,
             clock: ClockPosition) -> SourceStepResult[RecurrentSourceState]:
        payload_in = tuple(float(x) for x in input.payload)
        if len(payload_in) != self.dimension:
            raise ValueError(
                f"PersistentRecurrentSource.step: input dim {len(payload_in)} != "
                f"state dim {self.dimension}"
            )
        # Update: next = decay * (M @ state) + (1 - decay) * input.
        mv = _mv(state.matrix, state.payload)
        next_payload = tuple(
            state.decay * mv_i + (1.0 - state.decay) * inp
            for mv_i, inp in zip(mv, payload_in)
        )
        next_state = RecurrentSourceState(
            id=make_identity("aeon_app.source_state", {
                "impl": self.IMPL_ID, "parent": state.id.digest,
                "payload": list(next_payload), "tick": clock.tick,
            }),
            payload=next_payload, matrix=state.matrix, decay=state.decay,
            dimension=self.dimension, tick=clock.tick, seed=state.seed,
        )
        emission = new_signal_frame(
            source_id=self.source_id, sequence=clock.tick,
            clock_position=clock, payload=list(next_payload),
            originating_state_id=next_state.id,
        )
        return SourceStepResult(
            next_state=next_state, emissions=(emission,),
            certificates=(), diagnostics=(),
        )

    def read(self, state: RecurrentSourceState, request: ReadRequest) -> Any:
        if request.kind == "vector":
            return Ready(value=tuple(state.payload))
        if request.kind == "matrix":
            return Ready(value=tuple(tuple(row) for row in state.matrix))
        if request.kind == "decay":
            return Ready(value=state.decay)
        if request.kind == "dimension":
            return Ready(value=state.dimension)
        return ReadUnavailable(reason=f"PersistentRecurrentSource does not offer read kind {request.kind!r}")

    def snapshot(self, state: RecurrentSourceState) -> SourceSnapshot:
        canonical = canonical_bytes({
            "impl": self.IMPL_ID,
            "payload": list(state.payload),
            "matrix": [list(r) for r in state.matrix],
            "decay": state.decay,
            "dimension": state.dimension,
            "tick": state.tick,
            "seed": state.seed,
        })
        ident = make_identity("aeon_app.source_snapshot", {
            "of": state.id.digest, "impl": self.IMPL_ID,
        })
        return SourceSnapshot(
            id=ident, canonical=canonical,
            origin_source_id=self.source_id, version="0.1.0",
        )

    def restore(self, snapshot: SourceSnapshot) -> RecurrentSourceState:
        import json
        data = json.loads(snapshot.canonical.decode("utf-8"))
        payload = tuple(float(x) for x in data["payload"])
        matrix = tuple(tuple(float(x) for x in r) for r in data["matrix"])
        ident = make_identity("aeon_app.source_state", {
            "impl": self.IMPL_ID, "restore_from": snapshot.id.digest,
            "payload": list(payload),
        })
        return RecurrentSourceState(
            id=ident, payload=payload, matrix=matrix,
            decay=float(data["decay"]),
            dimension=int(data["dimension"]),
            tick=int(data["tick"]),
            seed=int(data["seed"]),
        )
