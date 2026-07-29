"""AttentionSource — Aeon-original attention-based signal source.

Deterministic, pure-Python arithmetic. The state carries a small
key/value memory built from the last `history` step inputs; each
step computes a softmax attention over the memory and blends the
attended value into the state payload.

Version 1 is intentionally small (dimension configurable, default
4; history 4). It is NOT a wrapper for an external transformer
implementation. It is an Aeon-original source that satisfies the
REQUIRED source port with the optional ``AttentionMapRead``
capability.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
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
from aeon.serialization import canonical_bytes, canonical_value
from aeon.signal import SignalFrame, new_signal_frame


@dataclass(frozen=True)
class AttentionSourceState:
    id: Any
    payload: Tuple[float, ...]
    memory_keys: Tuple[Tuple[float, ...], ...]     # last `history` keys
    memory_values: Tuple[Tuple[float, ...], ...]
    dimension: int
    history: int
    tick: int
    seed: int


def _softmax(scores: Tuple[float, ...]) -> Tuple[float, ...]:
    if not scores:
        return ()
    m = max(scores)
    exps = tuple(math.exp(s - m) for s in scores)
    z = sum(exps)
    return tuple(e / z for e in exps)


def _dot(a: Tuple[float, ...], b: Tuple[float, ...]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _add(a: Tuple[float, ...], b: Tuple[float, ...]) -> Tuple[float, ...]:
    return tuple(x + y for x, y in zip(a, b))


def _scale(v: Tuple[float, ...], s: float) -> Tuple[float, ...]:
    return tuple(x * s for x in v)


class AttentionSource:
    """Deterministic attention source implementing the REQUIRED port."""

    IMPL_ID = "aeon_app.sources.attention.AttentionSource/0.1.0"

    def __init__(self, source_id: str = "attention", dimension: int = 4,
                 history: int = 4) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        if history <= 0:
            raise ValueError("history must be positive")
        self.source_id = source_id
        self.dimension = dimension
        self.history = history

    def describe(self) -> PortDescriptor:
        req = [
            CapabilityRef("VectorDrive", SemVer(1, 0, 0), CapabilityTier.REQUIRED),
            CapabilityRef("VectorRead", SemVer(1, 0, 0), CapabilityTier.REQUIRED),
            CapabilityRef("PerTokenStep", SemVer(1, 0, 0), CapabilityTier.REQUIRED),
        ]
        opt = [
            CapabilityRef("AttentionMapRead", SemVer(0, 1, 0), CapabilityTier.OPTIONAL),
        ]
        return PortDescriptor(
            port_id=f"port.{self.source_id}",
            port_version="0.1.0",
            required_capabilities=tuple(req),
            offered_capabilities=tuple(req + opt),
            accepted_input_types=(TypeRef("Signal<Vec>", "0.1.0"),),
            emitted_output_types=(TypeRef("Signal<Vec>", "0.1.0"),),
            clock_domain="source",
            state_model=StateModelRef("AttentionSourceState", "0.1.0"),
        )

    def initialize(self, config: Mapping[str, Any], seed: int) -> AttentionSourceState:
        # Deterministic seeded initialization: payload from seed hash;
        # empty memory that will fill on the first history steps.
        payload = tuple(float(((seed * 31 + i) % 7)) * 0.1
                        for i in range(self.dimension))
        ident = make_identity("aeon_app.source_state", {
            "impl": self.IMPL_ID, "source_id": self.source_id,
            "seed": seed, "dimension": self.dimension,
            "history": self.history, "payload": list(payload),
        })
        return AttentionSourceState(
            id=ident, payload=payload, memory_keys=(), memory_values=(),
            dimension=self.dimension, history=self.history,
            tick=0, seed=seed,
        )

    def step(self, input: SignalFrame[Any], state: AttentionSourceState,
             clock: ClockPosition) -> SourceStepResult[AttentionSourceState]:
        payload_in = tuple(float(x) for x in input.payload)
        if len(payload_in) != self.dimension:
            raise ValueError(
                f"AttentionSource.step: input dim {len(payload_in)} != "
                f"state dim {self.dimension}"
            )
        # Key is the input itself; value is (state XOR input) sum-blended.
        key = payload_in
        value = tuple(0.5 * s + 0.5 * i for s, i in zip(state.payload, payload_in))
        new_keys = state.memory_keys + (key,)
        new_values = state.memory_values + (value,)
        if len(new_keys) > self.history:
            new_keys = new_keys[-self.history:]
            new_values = new_values[-self.history:]

        # Attention scores: dot-product between current state and each key.
        if new_keys:
            scores = tuple(_dot(state.payload, k) for k in new_keys)
            weights = _softmax(scores)
            attended = tuple(
                sum(w * v[j] for w, v in zip(weights, new_values))
                for j in range(self.dimension)
            )
        else:
            attended = tuple(0.0 for _ in range(self.dimension))

        # Blend attended into the payload; the coefficients are fixed
        # so REFERENCE mode is fully deterministic.
        next_payload = tuple(0.5 * s + 0.5 * a
                             for s, a in zip(state.payload, attended))
        next_tick = clock.tick

        next_state = AttentionSourceState(
            id=make_identity("aeon_app.source_state", {
                "impl": self.IMPL_ID, "parent": state.id.digest,
                "payload": list(next_payload), "tick": next_tick,
                "memory_len": len(new_keys),
            }),
            payload=next_payload,
            memory_keys=new_keys,
            memory_values=new_values,
            dimension=self.dimension,
            history=self.history,
            tick=next_tick,
            seed=state.seed,
        )
        emission = new_signal_frame(
            source_id=self.source_id, sequence=next_tick,
            clock_position=clock, payload=list(next_payload),
            originating_state_id=next_state.id,
        )
        return SourceStepResult(
            next_state=next_state, emissions=(emission,),
            certificates=(), diagnostics=(),
        )

    def read(self, state: AttentionSourceState, request: ReadRequest) -> Any:
        if request.kind == "vector":
            return Ready(value=tuple(state.payload))
        if request.kind == "dimension":
            return Ready(value=state.dimension)
        if request.kind == "attention_map":
            # Recompute attention weights over current memory using
            # current payload as query; a repeatable read view.
            if not state.memory_keys:
                return Ready(value=())
            scores = tuple(_dot(state.payload, k) for k in state.memory_keys)
            return Ready(value=tuple(round(w, 12) for w in _softmax(scores)))
        return ReadUnavailable(reason=f"AttentionSource does not offer read kind {request.kind!r}")

    def snapshot(self, state: AttentionSourceState) -> SourceSnapshot:
        canonical = canonical_bytes({
            "impl": self.IMPL_ID,
            "payload": list(state.payload),
            "memory_keys": [list(k) for k in state.memory_keys],
            "memory_values": [list(v) for v in state.memory_values],
            "dimension": state.dimension,
            "history": state.history,
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

    def restore(self, snapshot: SourceSnapshot) -> AttentionSourceState:
        import json
        data = json.loads(snapshot.canonical.decode("utf-8"))
        payload = tuple(float(x) for x in data["payload"])
        keys = tuple(tuple(float(x) for x in k) for k in data["memory_keys"])
        values = tuple(tuple(float(x) for x in v) for v in data["memory_values"])
        ident = make_identity("aeon_app.source_state", {
            "impl": self.IMPL_ID, "restore_from": snapshot.id.digest,
            "payload": list(payload),
        })
        return AttentionSourceState(
            id=ident, payload=payload, memory_keys=keys, memory_values=values,
            dimension=int(data["dimension"]),
            history=int(data["history"]),
            tick=int(data["tick"]),
            seed=int(data["seed"]),
        )
