"""aeon.port — port descriptors and the SignalSourcePort protocol.

Implements the SignalSourcePort surface from
``05-PORTS-AND-CAPABILITIES.md §2``. The kernel MUST NOT expose
host-framework implementation details; a source implementation
sits behind this port and is treated by the compiler and runtime
as an opaque implementor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, Mapping, Optional, Protocol, Sequence, Tuple, TypeVar

from .capability import CapabilityRef
from .clock import ClockDomain, ClockPosition
from .core import Certificate, Diagnostic, Identity, Option
from .serialization import canonical_value
from .signal import SignalFrame

T = TypeVar("T")
S = TypeVar("S")


# ---------------------------------------------------------------------------
# PortDescriptor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TypeRef:
    """A stable identifier for an Aeon type."""

    name: str
    version: str  # SemVer string

    def sort_key(self) -> Tuple[str, str]:
        return (self.name, self.version)


@dataclass(frozen=True)
class StateModelRef:
    """A stable identifier for a state model contract."""

    name: str
    version: str


@dataclass(frozen=True)
class PortDescriptor:
    port_id: str
    port_version: str  # SemVer string
    required_capabilities: Tuple[CapabilityRef, ...]
    offered_capabilities: Tuple[CapabilityRef, ...]
    accepted_input_types: Tuple[TypeRef, ...]
    emitted_output_types: Tuple[TypeRef, ...]
    clock_domain: str  # ClockDomain id
    state_model: StateModelRef

    def to_canonical(self) -> dict:
        return canonical_value({
            "port_id": self.port_id,
            "port_version": self.port_version,
            "required_capabilities": sorted(
                [{"name": c.name, "version": str(c.version), "tier": c.tier.value}
                 for c in self.required_capabilities],
                key=lambda d: (d["name"], d["version"]),
            ),
            "offered_capabilities": sorted(
                [{"name": c.name, "version": str(c.version), "tier": c.tier.value}
                 for c in self.offered_capabilities],
                key=lambda d: (d["name"], d["version"]),
            ),
            "accepted_input_types": sorted(
                [{"name": t.name, "version": t.version}
                 for t in self.accepted_input_types],
                key=lambda d: (d["name"], d["version"]),
            ),
            "emitted_output_types": sorted(
                [{"name": t.name, "version": t.version}
                 for t in self.emitted_output_types],
                key=lambda d: (d["name"], d["version"]),
            ),
            "clock_domain": self.clock_domain,
            "state_model": {
                "name": self.state_model.name,
                "version": self.state_model.version,
            },
        })


# ---------------------------------------------------------------------------
# Read results (spec 05 §5)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Ready(Generic[T]):
    value: T


@dataclass(frozen=True)
class ReadUnavailable:
    reason: str


@dataclass(frozen=True)
class Refused:
    violation: str


ReadResult = "Ready[T] | ReadUnavailable | Refused"


@dataclass(frozen=True)
class ReadRequest:
    kind: str
    params: Mapping[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# SourceStepResult (spec 05 §2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceStepResult(Generic[S]):
    next_state: S
    emissions: Tuple[SignalFrame[Any], ...] = ()
    certificates: Tuple[Certificate[Any], ...] = ()
    diagnostics: Tuple[Diagnostic, ...] = ()


# ---------------------------------------------------------------------------
# SourceSnapshot placeholder (concrete kinds live in aeon.snapshot)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceSnapshot:
    id: Identity
    canonical: bytes
    origin_source_id: str
    version: str


# ---------------------------------------------------------------------------
# SignalSourcePort protocol
# ---------------------------------------------------------------------------


class SignalSourcePort(Protocol[S]):
    """The REQUIRED source port interface.

    An implementation is a source-agnostic wrapper the runtime uses
    to drive a specific source. Implementations MUST fulfill every
    method here for the source to participate as a conforming
    source.
    """

    def describe(self) -> PortDescriptor: ...

    def initialize(self, config: Mapping[str, Any], seed: int) -> S: ...

    def step(self, input: SignalFrame[Any], state: S,
             clock: ClockPosition) -> SourceStepResult[S]: ...

    def read(self, state: S, request: ReadRequest) -> Any: ...

    def snapshot(self, state: S) -> SourceSnapshot: ...

    def restore(self, snapshot: SourceSnapshot) -> S: ...
