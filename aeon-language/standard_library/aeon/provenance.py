"""aeon.provenance — identity computation, lineage, provenance.

This module centralizes construction of every Aeon Identity value.
All identity fields come from canonical serialization; no host
memory address, no ``id()``, no unordered iteration is ever
consulted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence, Tuple

from .core import Identity
from .serialization import DEFAULT_DIGEST_METHOD, canonical_value, digest


# ---------------------------------------------------------------------------
# Identity constructors
# ---------------------------------------------------------------------------


def make_identity(kind: str, defining_fields: Mapping[str, Any], *,
                  digest_method: str = DEFAULT_DIGEST_METHOD) -> Identity:
    """Compute a canonical Identity for ``kind`` from its defining fields.

    ``defining_fields`` is any dict-like mapping of the schema-declared
    identity fields for the given kind. Field ordering is normalized
    by canonicalization; callers do not need to sort.
    """

    tree = {"kind": kind, "defining_fields": canonical_value(defining_fields)}
    return Identity(
        kind=kind,
        digest_method=digest_method,
        digest=digest(tree, digest_method),
    )


# ---------------------------------------------------------------------------
# Provenance and lineage records (spec 08-PROVENANCE §5, §6)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProvenanceFields:
    language_version: str
    graph_id: Optional[str] = None
    node_id: Optional[str] = None
    transition_id: Optional[str] = None
    clock_domain_id: Optional[str] = None
    clock_tick: Optional[int] = None
    parent_ids: Tuple[str, ...] = ()
    implementation: str = "aeon.reference/0.1.0-dev"
    active_contracts: Tuple[str, ...] = ()
    created_at_tick: int = 0


@dataclass(frozen=True)
class Provenance:
    fields: ProvenanceFields

    def to_canonical(self) -> Any:
        return canonical_value({
            "language_version": self.fields.language_version,
            "graph_id": self.fields.graph_id,
            "node_id": self.fields.node_id,
            "transition_id": self.fields.transition_id,
            "clock_domain_id": self.fields.clock_domain_id,
            "clock_tick": self.fields.clock_tick,
            "parent_ids": list(self.fields.parent_ids),
            "implementation": self.fields.implementation,
            "active_contracts": list(self.fields.active_contracts),
            "created_at_tick": self.fields.created_at_tick,
        })


@dataclass(frozen=True)
class LineageRecord:
    """A single append-only lineage event."""

    child_id: str
    parent_ids: Tuple[str, ...]
    transition_id: str
    clock_domain_id: str
    clock_tick: int
    logical_tick: int


class Lineage:
    """An append-only chain of :class:`LineageRecord`.

    ``Lineage`` is deliberately not a dataclass because it needs
    controlled append semantics. Internal storage is a private list;
    the public interface exposes a read-only tuple view.
    """

    __slots__ = ("_records",)

    def __init__(self, records: Sequence[LineageRecord] = ()) -> None:
        self._records: list[LineageRecord] = list(records)

    def append(self, record: LineageRecord) -> "Lineage":
        """Return a NEW Lineage with the record appended.

        Lineage is append-only. This returns a fresh instance to
        prevent aliasing surprises; the caller's original ``Lineage``
        is unchanged.
        """

        return Lineage(self._records + [record])

    def records(self) -> Tuple[LineageRecord, ...]:
        return tuple(self._records)

    def canonical(self) -> Any:
        return canonical_value([
            {
                "child_id": r.child_id,
                "parent_ids": list(r.parent_ids),
                "transition_id": r.transition_id,
                "clock_domain_id": r.clock_domain_id,
                "clock_tick": r.clock_tick,
                "logical_tick": r.logical_tick,
            }
            for r in self._records
        ])

    def __len__(self) -> int:
        return len(self._records)


# ---------------------------------------------------------------------------
# Convenience identity constructors for common kinds
# ---------------------------------------------------------------------------


def graph_id(module_id: str, canonical_body: Any) -> Identity:
    return make_identity("graph", {"module_id": module_id, "body": canonical_body})


def node_id(graph: str, kind: str, local_name: str) -> Identity:
    return make_identity("node", {"graph": graph, "kind": kind, "local_name": local_name})


def transition_id(node: str, invocation: int) -> Identity:
    return make_identity("transition", {"node": node, "invocation": invocation})


def state_id(*, language_version: str, graph: str, node: str,
             parent_state_ids: Sequence[str], transition: str,
             clock_domain_id: str, clock_tick: int,
             canonical_payload_digest: str) -> Identity:
    # ``StateId`` per 03-STATE-SEMANTICS §6 / 08-PROVENANCE §2.
    return make_identity("state", {
        "language_version": language_version,
        "graph": graph,
        "node": node,
        "parent_state_ids": sorted(parent_state_ids),
        "transition": transition,
        "clock_domain_id": clock_domain_id,
        "clock_tick": clock_tick,
        "canonical_payload_digest": canonical_payload_digest,
    })


def snapshot_id(state: str, policy_id: str) -> Identity:
    return make_identity("snapshot", {"state": state, "policy_id": policy_id})


def signal_id(source: str, clock_domain_id: str, clock_tick: int,
              sequence: int, canonical_payload_digest: str) -> Identity:
    return make_identity("signal", {
        "source": source,
        "clock_domain_id": clock_domain_id,
        "clock_tick": clock_tick,
        "sequence": sequence,
        "canonical_payload_digest": canonical_payload_digest,
    })


def window_id(domain_id: str, start: int, end: int,
              relation_id: Optional[str] = None) -> Identity:
    return make_identity("window", {
        "domain_id": domain_id,
        "start": start,
        "end": end,
        "relation_id": relation_id,
    })
