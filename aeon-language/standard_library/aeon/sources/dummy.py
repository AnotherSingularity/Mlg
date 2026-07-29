"""Reference dummy sources.

Two deterministic pure-Python sources for testing:

- :class:`DummyVectorSource` implements the REQUIRED tier only.
- :class:`DummyRichSource` adds MatrixRead, LayerRead, DecayControl.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Tuple

from aeon.capability import CapabilityRef, CapabilityTier
from aeon.clock import ClockPosition
from aeon.core import SemVer, Validity
from aeon.port import (
    PortDescriptor,
    Ready,
    ReadRequest,
    SourceSnapshot,
    SourceStepResult,
    StateModelRef,
    TypeRef,
)
from aeon.provenance import make_identity
from aeon.serialization import canonical_bytes, canonical_value
from aeon.signal import SignalFrame, new_signal_frame


@dataclass(frozen=True)
class _VectorSourceState:
    id: Any
    payload: Tuple[float, ...]
    dimension: int
    tick: int
    seed: int


def _vec_add(a: Tuple[float, ...], b: Tuple[float, ...]) -> Tuple[float, ...]:
    if len(a) != len(b):
        raise ValueError(f"vector length mismatch {len(a)} vs {len(b)}")
    return tuple(x + y for x, y in zip(a, b))


class DummyVectorSource:
    """A deterministic vector source with the REQUIRED tier only."""

    IMPL_ID = "aeon.sources.DummyVectorSource/0.1.0-dev"

    def __init__(self, source_id: str = "dummy_vector", dimension: int = 4):
        self.source_id = source_id
        self.dimension = dimension

    def describe(self) -> PortDescriptor:
        req = [
            CapabilityRef("VectorDrive", SemVer(1, 0, 0), CapabilityTier.REQUIRED),
            CapabilityRef("VectorRead", SemVer(1, 0, 0), CapabilityTier.REQUIRED),
            CapabilityRef("PerTokenStep", SemVer(1, 0, 0), CapabilityTier.REQUIRED),
        ]
        return PortDescriptor(
            port_id=f"port.{self.source_id}",
            port_version="0.1.0-dev",
            required_capabilities=tuple(req),
            offered_capabilities=tuple(req),
            accepted_input_types=(TypeRef("Signal<Vec>", "0.1.0"),),
            emitted_output_types=(TypeRef("Signal<Vec>", "0.1.0"),),
            clock_domain="token",
            state_model=StateModelRef("VectorSource", "0.1.0"),
        )

    def initialize(self, config: Mapping[str, Any], seed: int) -> _VectorSourceState:
        payload = tuple(0.0 for _ in range(self.dimension))
        ident = make_identity("source_state", {
            "impl": self.IMPL_ID,
            "source_id": self.source_id,
            "seed": seed,
            "payload": list(payload),
            "tick": 0,
        })
        return _VectorSourceState(
            id=ident, payload=payload, dimension=self.dimension, tick=0, seed=seed,
        )

    def step(self, input: SignalFrame[Any], state: _VectorSourceState,
             clock: ClockPosition) -> SourceStepResult[_VectorSourceState]:
        # Deterministic increment: state <- state + input
        payload_in = tuple(float(x) for x in input.payload)
        # Pad or truncate to state dimension explicitly (no silent zero-fill;
        # any length mismatch raises).
        if len(payload_in) != self.dimension:
            raise ValueError(
                f"DummyVectorSource.step: input dim {len(payload_in)} != "
                f"state dim {self.dimension}"
            )
        next_payload = _vec_add(state.payload, payload_in)
        next_tick = clock.tick
        next_state = _VectorSourceState(
            id=make_identity("source_state", {
                "impl": self.IMPL_ID,
                "source_id": self.source_id,
                "seed": state.seed,
                "payload": list(next_payload),
                "tick": next_tick,
                "parent": state.id.digest,
            }),
            payload=next_payload,
            dimension=self.dimension,
            tick=next_tick,
            seed=state.seed,
        )
        emission = new_signal_frame(
            source_id=self.source_id,
            sequence=next_tick,
            clock_position=clock,
            payload=list(next_payload),
            originating_state_id=next_state.id,
        )
        return SourceStepResult(
            next_state=next_state,
            emissions=(emission,),
            certificates=(),
            diagnostics=(),
        )

    def read(self, state: _VectorSourceState, request: ReadRequest) -> Any:
        if request.kind == "vector":
            return Ready(value=tuple(state.payload))
        if request.kind == "dimension":
            return Ready(value=state.dimension)
        # Absence is explicit.
        from aeon.port import ReadUnavailable
        return ReadUnavailable(reason=f"DummyVectorSource does not offer read kind {request.kind!r}")

    def snapshot(self, state: _VectorSourceState) -> SourceSnapshot:
        canonical = canonical_bytes({
            "impl": self.IMPL_ID,
            "payload": list(state.payload),
            "dimension": state.dimension,
            "tick": state.tick,
            "seed": state.seed,
        })
        ident = make_identity("source_snapshot", {
            "of": state.id.digest,
            "impl": self.IMPL_ID,
        })
        return SourceSnapshot(
            id=ident, canonical=canonical,
            origin_source_id=self.source_id, version="0.1.0-dev",
        )

    def restore(self, snapshot: SourceSnapshot) -> _VectorSourceState:
        import json
        data = json.loads(snapshot.canonical.decode("utf-8"))
        payload = tuple(float(x) for x in data["payload"])
        ident = make_identity("source_state", {
            "impl": self.IMPL_ID,
            "restore_from": snapshot.id.digest,
            "payload": list(payload),
        })
        return _VectorSourceState(
            id=ident, payload=payload,
            dimension=int(data["dimension"]),
            tick=int(data["tick"]),
            seed=int(data["seed"]),
        )


# ---------------------------------------------------------------------------
# DummyRichSource: required tier + MatrixRead + LayerRead + DecayControl
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _RichSourceState:
    id: Any
    payload: Tuple[float, ...]
    matrix: Tuple[Tuple[float, ...], ...]
    layers: Tuple[Tuple[float, ...], ...]
    decay: float
    dimension: int
    tick: int
    seed: int


class DummyRichSource:
    """Reference source demonstrating optional-capability negotiation.

    Offers: VectorRead, VectorDrive, PerTokenStep, MatrixRead,
    LayerRead, DecayControl. All optional-capability reads are pure
    deterministic reads from a per-instance matrix / layer stack.
    """

    IMPL_ID = "aeon.sources.DummyRichSource/0.1.0-dev"

    def __init__(self, source_id: str = "dummy_rich",
                 dimension: int = 4, layers: int = 3):
        self.source_id = source_id
        self.dimension = dimension
        self.layers = layers

    def describe(self) -> PortDescriptor:
        req = [
            CapabilityRef("VectorDrive", SemVer(1, 0, 0), CapabilityTier.REQUIRED),
            CapabilityRef("VectorRead", SemVer(1, 0, 0), CapabilityTier.REQUIRED),
            CapabilityRef("PerTokenStep", SemVer(1, 0, 0), CapabilityTier.REQUIRED),
        ]
        opt = [
            CapabilityRef("DecayControl", SemVer(0, 1, 0), CapabilityTier.OPTIONAL),
            CapabilityRef("LayerRead", SemVer(0, 1, 0), CapabilityTier.OPTIONAL),
            CapabilityRef("MatrixRead", SemVer(0, 1, 0), CapabilityTier.OPTIONAL),
        ]
        return PortDescriptor(
            port_id=f"port.{self.source_id}",
            port_version="0.1.0-dev",
            required_capabilities=tuple(req),
            offered_capabilities=tuple(req + opt),
            accepted_input_types=(TypeRef("Signal<Vec>", "0.1.0"),),
            emitted_output_types=(TypeRef("Signal<Vec>", "0.1.0"),),
            clock_domain="token",
            state_model=StateModelRef("RichSource", "0.1.0"),
        )

    def initialize(self, config: Mapping[str, Any], seed: int) -> _RichSourceState:
        # Deterministic non-zero initialization derived from seed.
        payload = tuple(float((seed + i) % 7) * 0.1 for i in range(self.dimension))
        matrix = tuple(
            tuple(float((seed + i * self.dimension + j) % 11) * 0.01
                  for j in range(self.dimension))
            for i in range(self.dimension)
        )
        layers = tuple(
            tuple(float((seed + l * 3 + i) % 5) * 0.2 for i in range(self.dimension))
            for l in range(self.layers)
        )
        ident = make_identity("source_state", {
            "impl": self.IMPL_ID,
            "source_id": self.source_id,
            "seed": seed,
            "payload": list(payload),
        })
        return _RichSourceState(
            id=ident, payload=payload, matrix=matrix, layers=layers,
            decay=0.5, dimension=self.dimension, tick=0, seed=seed,
        )

    def step(self, input: SignalFrame[Any], state: _RichSourceState,
             clock: ClockPosition) -> SourceStepResult[_RichSourceState]:
        payload_in = tuple(float(x) for x in input.payload)
        if len(payload_in) != self.dimension:
            raise ValueError(
                f"DummyRichSource.step: input dim mismatch "
                f"({len(payload_in)} vs {self.dimension})"
            )
        # Decay-blended update.
        next_payload = tuple(
            state.decay * s + (1.0 - state.decay) * i
            for s, i in zip(state.payload, payload_in)
        )
        next_state = _RichSourceState(
            id=make_identity("source_state", {
                "impl": self.IMPL_ID,
                "parent": state.id.digest,
                "payload": list(next_payload),
                "tick": clock.tick,
            }),
            payload=next_payload,
            matrix=state.matrix,
            layers=state.layers,
            decay=state.decay,
            dimension=self.dimension,
            tick=clock.tick,
            seed=state.seed,
        )
        emission = new_signal_frame(
            source_id=self.source_id,
            sequence=clock.tick,
            clock_position=clock,
            payload=list(next_payload),
            originating_state_id=next_state.id,
        )
        return SourceStepResult(
            next_state=next_state, emissions=(emission,),
            certificates=(), diagnostics=(),
        )

    def read(self, state: _RichSourceState, request: ReadRequest) -> Any:
        from aeon.port import ReadUnavailable
        if request.kind == "vector":
            return Ready(value=tuple(state.payload))
        if request.kind == "matrix":
            return Ready(value=tuple(tuple(row) for row in state.matrix))
        if request.kind == "layer":
            idx = int(request.params.get("index", 0))
            if not (0 <= idx < self.layers):
                return ReadUnavailable(reason=f"layer index {idx} out of range")
            return Ready(value=tuple(state.layers[idx]))
        if request.kind == "decay":
            return Ready(value=state.decay)
        return ReadUnavailable(reason=f"DummyRichSource does not offer read kind {request.kind!r}")

    def snapshot(self, state: _RichSourceState) -> SourceSnapshot:
        canonical = canonical_bytes({
            "impl": self.IMPL_ID,
            "payload": list(state.payload),
            "matrix": [list(r) for r in state.matrix],
            "layers": [list(l) for l in state.layers],
            "decay": state.decay,
            "dimension": state.dimension,
            "tick": state.tick,
            "seed": state.seed,
        })
        ident = make_identity("source_snapshot", {
            "of": state.id.digest,
            "impl": self.IMPL_ID,
        })
        return SourceSnapshot(
            id=ident, canonical=canonical,
            origin_source_id=self.source_id, version="0.1.0-dev",
        )

    def restore(self, snapshot: SourceSnapshot) -> _RichSourceState:
        import json
        data = json.loads(snapshot.canonical.decode("utf-8"))
        payload = tuple(float(x) for x in data["payload"])
        matrix = tuple(tuple(float(x) for x in row) for row in data["matrix"])
        layers = tuple(tuple(float(x) for x in l) for l in data["layers"])
        ident = make_identity("source_state", {
            "impl": self.IMPL_ID,
            "restore_from": snapshot.id.digest,
            "payload": list(payload),
        })
        return _RichSourceState(
            id=ident, payload=payload, matrix=matrix, layers=layers,
            decay=float(data["decay"]),
            dimension=int(data["dimension"]),
            tick=int(data["tick"]),
            seed=int(data["seed"]),
        )
