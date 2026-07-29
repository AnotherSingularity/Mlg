"""aeon.state — state, ownership, moves, snapshots.

Implements ``03-STATE-SEMANTICS.md``. States are pure values;
ownership is enforced by an :class:`OwnershipTable` maintained by
the interpreter. This module provides the type and the check
primitives; the interpreter drives them.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Generic, Optional, Sequence, Tuple, TypeVar

from .clock import ClockPosition
from .core import Certificate, Identity, Validity
from .provenance import Lineage, state_id
from .serialization import canonical_value, digest

T = TypeVar("T")


class Ownership(Enum):
    OWN = "own"
    BORROW = "borrow"
    SHARED_IMMUT = "shared_immut"
    FROZEN = "frozen"


@dataclass(frozen=True)
class Shape:
    """A shape as an ordered tuple of dimensions.

    Each dimension is either a non-negative int (concrete), a str
    (named symbolic dim), or ``None`` (shape variable). Structural
    equality follows tuple equality.
    """

    dims: Tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        for d in self.dims:
            if d is None:
                continue
            if isinstance(d, int):
                if d < 0:
                    raise ValueError(f"Shape dim must be >= 0, got {d}")
            elif isinstance(d, str):
                if not d:
                    raise ValueError("Shape dim str must be non-empty")
            else:
                raise TypeError(f"Shape dim type {type(d).__name__} not permitted")

    def is_concrete(self) -> bool:
        return all(isinstance(d, int) for d in self.dims)

    def matches(self, other: "Shape") -> bool:
        if len(self.dims) != len(other.dims):
            return False
        for a, b in zip(self.dims, other.dims):
            if a is None or b is None:
                continue
            if a != b:
                return False
        return True


@dataclass(frozen=True)
class State(Generic[T]):
    """A single Aeon state value.

    ``State`` is immutable. A transition consumes an owned state and
    produces a new state; the old value remains as a historical
    record but MUST NOT be re-mutated (ownership is enforced by the
    interpreter, not by Python).
    """

    id: Identity
    owner: str
    value: T
    shape: Shape
    clock_position: ClockPosition
    lineage: Lineage
    validity: Validity
    contract_bindings: Tuple[str, ...] = ()
    certificate: Optional[Certificate[Any]] = None


# ---------------------------------------------------------------------------
# Ownership table
# ---------------------------------------------------------------------------


class OwnershipError(Exception):
    """Raised when an ownership rule is violated."""


class OwnershipTable:
    """Tracks the ownership status of live state identities.

    The interpreter consults this table before every state
    operation. Rules:

    - A state may be introduced only once.
    - A state may transition OWN -> FROZEN via ``consume``.
    - A FROZEN state may be read (as a historical view) but not
      re-consumed and not mutated.
    - BORROW / SHARED_IMMUT are transient permissions granted for
      one read.
    """

    __slots__ = ("_status",)

    def __init__(self) -> None:
        self._status: dict[str, Ownership] = {}

    def introduce(self, state_identity: Identity, ownership: Ownership = Ownership.OWN) -> None:
        key = state_identity.digest
        if key in self._status:
            raise OwnershipError(f"state {state_identity.short()} already introduced")
        self._status[key] = ownership

    def status(self, state_identity: Identity) -> Ownership:
        key = state_identity.digest
        if key not in self._status:
            raise OwnershipError(f"state {state_identity.short()} not tracked")
        return self._status[key]

    def consume(self, state_identity: Identity) -> None:
        key = state_identity.digest
        current = self._status.get(key)
        if current is None:
            raise OwnershipError(f"state {state_identity.short()} not tracked")
        if current is not Ownership.OWN:
            raise OwnershipError(
                f"cannot consume state {state_identity.short()}: "
                f"status is {current.value}"
            )
        self._status[key] = Ownership.FROZEN

    def borrow(self, state_identity: Identity) -> None:
        key = state_identity.digest
        current = self._status.get(key)
        if current is None:
            raise OwnershipError(f"state {state_identity.short()} not tracked")
        # Reads permitted from OWN, SHARED_IMMUT, or FROZEN (historical).
        if current is Ownership.OWN or current is Ownership.SHARED_IMMUT or current is Ownership.FROZEN:
            return
        raise OwnershipError(
            f"cannot borrow state {state_identity.short()}: status is {current.value}"
        )


# ---------------------------------------------------------------------------
# Convenience constructors
# ---------------------------------------------------------------------------


def payload_digest(value: Any) -> str:
    return digest(canonical_value(value))


def new_state(*, language_version: str, graph: str, node: str,
              owner: str, value: Any, shape: Shape,
              clock_position: ClockPosition,
              transition: str, parent_ids: Sequence[Identity] = (),
              validity: Validity = Validity.UNCERTIFIED,
              contract_bindings: Sequence[str] = (),
              lineage: Optional[Lineage] = None,
              certificate: Optional[Certificate[Any]] = None) -> State[Any]:
    """Construct a fresh :class:`State` with a computed identity."""

    parent_digests = tuple(p.digest for p in parent_ids)
    sid = state_id(
        language_version=language_version,
        graph=graph,
        node=node,
        parent_state_ids=parent_digests,
        transition=transition,
        clock_domain_id=clock_position.domain_id,
        clock_tick=clock_position.tick,
        canonical_payload_digest=payload_digest(value),
    )
    return State(
        id=sid,
        owner=owner,
        value=value,
        shape=shape,
        clock_position=clock_position,
        lineage=(lineage or Lineage()),
        validity=validity,
        contract_bindings=tuple(contract_bindings),
        certificate=certificate,
    )
