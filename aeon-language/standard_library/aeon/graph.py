"""aeon.graph — the typed semantic graph produced by resolution.

Implements the semantic graph specified in ``09-CANONICAL-IR.md §5``.
The graph is a pure data structure; construction is deterministic
and canonicalization sorts nodes/edges by id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Tuple

from .core import Identity
from .provenance import make_identity
from .serialization import canonical_value


class NodeKind(Enum):
    SOURCE = "source"
    RECURSION = "recursion"
    PROJECTION = "projection"
    CLOCK = "clock"
    WINDOW = "window"
    OUTPUT = "output"
    SNAPSHOT = "snapshot"
    CONTRACT = "contract"


@dataclass(frozen=True)
class Node:
    id: str
    kind: NodeKind
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Edge:
    id: str
    from_node: str
    to_node: str
    edge_kind: str  # e.g. "projection", "feedback", "route"
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ClockDomainDecl:
    id: str
    kind: str  # ClockKind.value


@dataclass(frozen=True)
class OwnershipEntry:
    binding: str
    owner: str
    ownership: str  # Ownership.value


@dataclass(frozen=True)
class SemanticGraph:
    graph_id: Identity
    nodes: Tuple[Node, ...]                    # sorted by id
    edges: Tuple[Edge, ...]                    # sorted by id
    clock_domains: Tuple[ClockDomainDecl, ...]  # sorted by id
    ownership_map: Tuple[OwnershipEntry, ...]  # sorted by binding

    def to_canonical(self) -> dict:
        return canonical_value({
            "graph_id": self.graph_id.digest,
            "nodes": [
                {
                    "id": n.id,
                    "kind": n.kind.value,
                    "attributes": dict(n.attributes),
                }
                for n in sorted(self.nodes, key=lambda x: x.id)
            ],
            "edges": [
                {
                    "id": e.id,
                    "from": e.from_node,
                    "to": e.to_node,
                    "edge_kind": e.edge_kind,
                    "attributes": dict(e.attributes),
                }
                for e in sorted(self.edges, key=lambda x: x.id)
            ],
            "clock_domains": [
                {"id": c.id, "kind": c.kind}
                for c in sorted(self.clock_domains, key=lambda x: x.id)
            ],
            "ownership_map": [
                {"binding": o.binding, "owner": o.owner, "ownership": o.ownership}
                for o in sorted(self.ownership_map, key=lambda x: x.binding)
            ],
        })


# ---------------------------------------------------------------------------
# GraphBuilder — used by the compiler to construct graphs deterministically
# ---------------------------------------------------------------------------


class GraphBuilder:
    def __init__(self, module_id: str) -> None:
        self.module_id = module_id
        self._nodes: dict[str, Node] = {}
        self._edges: dict[str, Edge] = {}
        self._clocks: dict[str, ClockDomainDecl] = {}
        self._ownership: dict[str, OwnershipEntry] = {}

    def add_node(self, node: Node) -> None:
        if node.id in self._nodes:
            raise ValueError(f"duplicate node id: {node.id}")
        self._nodes[node.id] = node

    def add_edge(self, edge: Edge) -> None:
        if edge.id in self._edges:
            raise ValueError(f"duplicate edge id: {edge.id}")
        if edge.from_node not in self._nodes:
            raise ValueError(f"edge {edge.id} refers to unknown from-node {edge.from_node}")
        if edge.to_node not in self._nodes:
            raise ValueError(f"edge {edge.id} refers to unknown to-node {edge.to_node}")
        self._edges[edge.id] = edge

    def add_clock(self, clock: ClockDomainDecl) -> None:
        if clock.id in self._clocks:
            raise ValueError(f"duplicate clock id: {clock.id}")
        self._clocks[clock.id] = clock

    def add_ownership(self, entry: OwnershipEntry) -> None:
        if entry.binding in self._ownership:
            raise ValueError(f"duplicate binding: {entry.binding}")
        self._ownership[entry.binding] = entry

    def build(self) -> SemanticGraph:
        nodes = tuple(sorted(self._nodes.values(), key=lambda n: n.id))
        edges = tuple(sorted(self._edges.values(), key=lambda e: e.id))
        clocks = tuple(sorted(self._clocks.values(), key=lambda c: c.id))
        ownership = tuple(sorted(self._ownership.values(), key=lambda o: o.binding))
        body = canonical_value({
            "module_id": self.module_id,
            "nodes": [
                {"id": n.id, "kind": n.kind.value, "attributes": dict(n.attributes)}
                for n in nodes
            ],
            "edges": [
                {
                    "id": e.id,
                    "from": e.from_node,
                    "to": e.to_node,
                    "edge_kind": e.edge_kind,
                    "attributes": dict(e.attributes),
                }
                for e in edges
            ],
            "clock_domains": [
                {"id": c.id, "kind": c.kind} for c in clocks
            ],
            "ownership_map": [
                {"binding": o.binding, "owner": o.owner, "ownership": o.ownership}
                for o in ownership
            ],
        })
        gid = make_identity("graph", {"module_id": self.module_id, "body": body})
        return SemanticGraph(
            graph_id=gid,
            nodes=nodes,
            edges=edges,
            clock_domains=clocks,
            ownership_map=ownership,
        )
