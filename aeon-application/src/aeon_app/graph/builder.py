"""ApplicationGraph and canonical IR compilation.

Builds a typed application graph directly from a resolved
:class:`aeon_app.config.ApplicationConfig`, then lowers it to a
canonical Aeon Language semantic graph and IR module (both
produced by the certified `aeon.graph` and `aeon.ir` machinery).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from aeon.capability import (
    CapabilityRef,
    CapabilityTier,
    VersionConstraint,
    negotiate,
)
from aeon.core import SemVer
from aeon.graph import (
    ClockDomainDecl,
    Edge as LangEdge,
    GraphBuilder as LangGraphBuilder,
    Node as LangNode,
    NodeKind,
    OwnershipEntry,
    SemanticGraph,
)
from aeon.ir import (
    CapabilityRecord,
    ClockRecord,
    ContractRecord,
    Declaration,
    DeclarationKind,
    Instruction,
    IRModule,
    Opcode,
    ScheduleRecord,
    build_module,
    validate as validate_ir,
)
from aeon.serialization import canonical_value, digest

from ..config import ApplicationConfig
from ..identity import app_graph_id, canonical_digest


# ---------------------------------------------------------------------------
# Application node/edge categories
# ---------------------------------------------------------------------------


class AppNodeKind:
    INPUT = "InputNode"
    ATTENTION_SOURCE = "AttentionSourceNode"
    RECURRENT_SOURCE = "RecurrentSourceNode"
    PROJECTION = "ProjectionNode"
    AGGREGATION = "AggregationNode"
    RECURSION = "RecursionNode"
    FEEDBACK = "FeedbackNode"
    CERTIFICATION = "CertificationNode"
    OUTPUT = "OutputNode"
    SNAPSHOT = "SnapshotNode"


class AppEdgeKind:
    SIGNAL = "SignalEdge"
    STATE = "StateEdge"
    CLOCK = "ClockEdge"
    CONTROL = "ControlEdge"
    FEEDBACK = "FeedbackEdge"
    CERTIFICATE = "CertificateEdge"


@dataclass(frozen=True)
class ApplicationNode:
    id: str
    kind: str                # from AppNodeKind
    attributes: Mapping[str, Any]


@dataclass(frozen=True)
class ApplicationEdge:
    id: str
    from_node: str
    to_node: str
    edge_kind: str           # from AppEdgeKind
    payload_type: str
    clock_relation: Optional[str] = None
    causal_relation: str = "forward"
    buffering_policy: str = "immediate"
    projection: Optional[str] = None
    contract: Optional[str] = None
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ApplicationGraph:
    graph_id: str
    graph_name: str
    config_digest: str
    nodes: Tuple[ApplicationNode, ...]
    edges: Tuple[ApplicationEdge, ...]

    def to_canonical(self) -> dict:
        return canonical_value({
            "graph_id": self.graph_id,
            "graph_name": self.graph_name,
            "config_digest": self.config_digest,
            "nodes": sorted(
                [{"id": n.id, "kind": n.kind, "attributes": dict(n.attributes)}
                 for n in self.nodes],
                key=lambda d: d["id"],
            ),
            "edges": sorted(
                [
                    {
                        "id": e.id, "from": e.from_node, "to": e.to_node,
                        "edge_kind": e.edge_kind, "payload_type": e.payload_type,
                        "clock_relation": e.clock_relation,
                        "causal_relation": e.causal_relation,
                        "buffering_policy": e.buffering_policy,
                        "projection": e.projection, "contract": e.contract,
                        "attributes": dict(e.attributes),
                    }
                    for e in self.edges
                ],
                key=lambda d: d["id"],
            ),
        })

    def digest(self) -> str:
        return digest(self.to_canonical())


# ---------------------------------------------------------------------------
# Build application graph from config
# ---------------------------------------------------------------------------


class GraphBuildError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code


_SOURCE_NODE_KIND = {
    "aeon_app.sources.attention:AttentionSource": AppNodeKind.ATTENTION_SOURCE,
    "aeon_app.sources.recurrent:PersistentRecurrentSource": AppNodeKind.RECURRENT_SOURCE,
}


def build_from_config(config: ApplicationConfig) -> ApplicationGraph:
    """Build an ApplicationGraph from a resolved ApplicationConfig.

    Every node/edge is typed. Ports negotiate. Clock crossings
    are explicit. Ownership entries are created for every source
    state and the recursion state.
    """

    nodes: List[ApplicationNode] = []
    edges: List[ApplicationEdge] = []

    cfg_digest = config.semantic_digest()

    # -- Deterministic capability negotiation per source --
    for s in config.sources:
        # Every source declares its offered capabilities; the graph
        # negotiates against the REQUIRED tier to prove compatibility.
        offered = [
            CapabilityRef(name, SemVer(0, 1, 0),
                          CapabilityTier.REQUIRED
                          if name in {"VectorRead", "VectorDrive", "PerTokenStep"}
                          else CapabilityTier.OPTIONAL)
            for name in s.offered_capabilities
        ]
        required = [
            VersionConstraint(name, SemVer(0, 1, 0)) for name in ("VectorRead", "VectorDrive", "PerTokenStep")
        ]
        result = negotiate(offered, required)
        if not result.compatible:
            raise GraphBuildError(
                "NEGOTIATION_FAILURE",
                f"source {s.component_id!r}: capability negotiation failed: "
                f"{[(i.capability_name, i.reason) for i in result.incompatibilities]}",
            )
        kind = _SOURCE_NODE_KIND.get(s.implementation)
        if kind is None:
            raise GraphBuildError(
                "UNKNOWN_SOURCE_IMPLEMENTATION",
                f"source {s.component_id!r}: no known application node kind "
                f"for implementation {s.implementation!r}",
            )
        nodes.append(ApplicationNode(
            id=f"source.{s.component_id}",
            kind=kind,
            attributes={
                "implementation": s.implementation,
                "dimension": s.dimension,
                "clock": s.clock,
                "numerical_precision": s.numerical_precision,
                "seed": s.seed,
                "offered_capabilities": sorted(s.offered_capabilities),
                "negotiated": sorted(result.selected_versions),
            },
        ))
        # Input node feeding this source
        input_id = f"input.{s.component_id}"
        nodes.append(ApplicationNode(
            id=input_id,
            kind=AppNodeKind.INPUT,
            attributes={"drives": s.component_id, "clock": s.clock},
        ))
        edges.append(ApplicationEdge(
            id=f"edge.input.{s.component_id}",
            from_node=input_id, to_node=f"source.{s.component_id}",
            edge_kind=AppEdgeKind.SIGNAL, payload_type="Signal<Vec,source_clock>",
            clock_relation="identity", causal_relation="forward",
            buffering_policy="immediate",
        ))

    # -- Aggregation window + Recursion --
    integration_clock = next(c for c in config.clocks if c.id == config.recursion.clock)
    if integration_clock.aggregates_from:
        agg_id = f"aggregation.{integration_clock.aggregates_from}_to_{integration_clock.id}"
        nodes.append(ApplicationNode(
            id=agg_id,
            kind=AppNodeKind.AGGREGATION,
            attributes={
                "source_clock": integration_clock.aggregates_from,
                "target_clock": integration_clock.id,
                "window_size": integration_clock.window_size,
            },
        ))
    else:
        agg_id = None

    recursion_id = f"recursion.{config.recursion.component_id}"
    nodes.append(ApplicationNode(
        id=recursion_id,
        kind=AppNodeKind.RECURSION,
        attributes={
            "implementation": config.recursion.implementation,
            "dimension": config.recursion.dimension,
            "clock": config.recursion.clock,
            "contraction_margin": config.recursion.contraction_margin,
            "decay": config.recursion.decay,
            "numerical_precision": config.recursion.numerical_precision,
        },
    ))
    nodes.append(ApplicationNode(
        id=f"certification.{config.recursion.component_id}",
        kind=AppNodeKind.CERTIFICATION,
        attributes={
            "subject": recursion_id,
            "scope": "PROJECTED_RECURSION",
            "arithmetic_kind": "ExactRational",
        },
    ))
    edges.append(ApplicationEdge(
        id=f"edge.cert.{config.recursion.component_id}",
        from_node=recursion_id,
        to_node=f"certification.{config.recursion.component_id}",
        edge_kind=AppEdgeKind.CERTIFICATE,
        payload_type="ContractionCertificate",
        clock_relation="identity", causal_relation="forward",
        buffering_policy="immediate",
    ))

    # -- Projections: source -> aggregation (if any) -> recursion, and
    # -- feedback projections recursion -> sources.
    for p in config.projections:
        proj_id = f"projection.{p.component_id}"
        nodes.append(ApplicationNode(
            id=proj_id,
            kind=(AppNodeKind.FEEDBACK
                  if p.target_component in {s.component_id for s in config.sources}
                  else AppNodeKind.PROJECTION),
            attributes={
                "implementation": p.implementation,
                "input_shape": list(p.input_shape),
                "output_shape": list(p.output_shape),
                "scale_upper_bound": p.scale_upper_bound,
                "contract": p.contract,
                "clock_relation": p.clock_relation,
                "numerical_precision": p.numerical_precision,
            },
        ))
        # Determine source / dest node ids in the application graph.
        if p.source_component == config.recursion.component_id:
            src_node = recursion_id
        else:
            src_node = f"source.{p.source_component}"
        if p.target_component == config.recursion.component_id:
            dst_node = agg_id or recursion_id
        else:
            dst_node = f"source.{p.target_component}"

        is_feedback = p.source_component == config.recursion.component_id
        edges.append(ApplicationEdge(
            id=f"edge.projin.{p.component_id}",
            from_node=src_node, to_node=proj_id,
            edge_kind=AppEdgeKind.FEEDBACK if is_feedback else AppEdgeKind.SIGNAL,
            payload_type="Signal<Vec,integration_clock>"
                         if is_feedback else "Signal<Vec,source_clock>",
            clock_relation=p.clock_relation,
            causal_relation="feedback" if is_feedback else "forward",
            buffering_policy="immediate",
            projection=p.component_id,
            contract=p.contract,
        ))
        if is_feedback:
            edges.append(ApplicationEdge(
                id=f"edge.projout.{p.component_id}",
                from_node=proj_id, to_node=dst_node,
                edge_kind=AppEdgeKind.FEEDBACK,
                payload_type="Signal<Vec,source_clock>",
                clock_relation=p.clock_relation, causal_relation="feedback",
                buffering_policy="immediate",
                projection=p.component_id, contract=p.contract,
            ))
        else:
            # Forward projection: proj -> aggregation (if any) -> recursion.
            mid_node = agg_id if agg_id is not None else recursion_id
            edges.append(ApplicationEdge(
                id=f"edge.projout.{p.component_id}",
                from_node=proj_id, to_node=mid_node,
                edge_kind=AppEdgeKind.SIGNAL,
                payload_type="ManifoldInput",
                clock_relation=p.clock_relation, causal_relation="forward",
                buffering_policy="window",
                projection=p.component_id, contract=p.contract,
            ))
            if agg_id is not None:
                # Aggregation to recursion is a single, canonical edge
                # per aggregation window; add once.
                agg_to_rec_id = f"edge.agg_to_recursion"
                if not any(e.id == agg_to_rec_id for e in edges):
                    edges.append(ApplicationEdge(
                        id=agg_to_rec_id,
                        from_node=agg_id, to_node=recursion_id,
                        edge_kind=AppEdgeKind.SIGNAL,
                        payload_type="AggregatedManifoldInputs",
                        clock_relation="aggregation_to_integration",
                        causal_relation="forward", buffering_policy="window",
                    ))

    # -- Output + snapshot nodes --
    nodes.append(ApplicationNode(
        id="output.recursion",
        kind=AppNodeKind.OUTPUT,
        attributes={"subject": recursion_id, "payload": "Vec"},
    ))
    edges.append(ApplicationEdge(
        id="edge.output.recursion",
        from_node=recursion_id, to_node="output.recursion",
        edge_kind=AppEdgeKind.SIGNAL, payload_type="AeonOutput",
        clock_relation="identity", causal_relation="forward",
        buffering_policy="immediate",
    ))
    nodes.append(ApplicationNode(
        id="snapshot.application",
        kind=AppNodeKind.SNAPSHOT,
        attributes={"subject": "application", "policy": "default"},
    ))

    # -- Sort node/edge lists for canonical construction --
    nodes.sort(key=lambda n: n.id)
    edges.sort(key=lambda e: e.id)

    graph = ApplicationGraph(
        graph_id="pending",
        graph_name=config.graph_name,
        config_digest=cfg_digest,
        nodes=tuple(nodes),
        edges=tuple(edges),
    )
    gid = app_graph_id(graph_name=config.graph_name,
                       config_digest=cfg_digest).digest
    return ApplicationGraph(
        graph_id=gid,
        graph_name=graph.graph_name,
        config_digest=graph.config_digest,
        nodes=graph.nodes,
        edges=graph.edges,
    )


# ---------------------------------------------------------------------------
# Compile to canonical Aeon IR
# ---------------------------------------------------------------------------


def _language_node_kind(app_kind: str) -> NodeKind:
    return {
        AppNodeKind.INPUT: NodeKind.SOURCE,
        AppNodeKind.ATTENTION_SOURCE: NodeKind.SOURCE,
        AppNodeKind.RECURRENT_SOURCE: NodeKind.SOURCE,
        AppNodeKind.RECURSION: NodeKind.RECURSION,
        AppNodeKind.PROJECTION: NodeKind.PROJECTION,
        AppNodeKind.FEEDBACK: NodeKind.PROJECTION,
        AppNodeKind.AGGREGATION: NodeKind.WINDOW,
        AppNodeKind.CERTIFICATION: NodeKind.CONTRACT,
        AppNodeKind.OUTPUT: NodeKind.OUTPUT,
        AppNodeKind.SNAPSHOT: NodeKind.SNAPSHOT,
    }[app_kind]


def compile_to_ir(config: ApplicationConfig,
                  graph: ApplicationGraph) -> IRModule:
    """Lower the ApplicationGraph into a canonical Aeon IRModule.

    The instruction stream is scheduled per config.inference.ticks
    with an integration on the integration clock every
    `window_size` source ticks.
    """

    # Build the language SemanticGraph.
    gb = LangGraphBuilder(module_id=graph.graph_id)
    seen_clocks: Dict[str, ClockDomainDecl] = {}
    for n in graph.nodes:
        lang_kind = _language_node_kind(n.kind)
        gb.add_node(LangNode(id=n.id, kind=lang_kind,
                             attributes=dict(n.attributes)))
    for c in config.clocks:
        # The language schema uses "Token", "Integration", "Segment", "UserDefined".
        kind = c.kind if c.kind in ("Token", "Integration", "Segment") else "UserDefined"
        cd = ClockDomainDecl(id=c.id, kind=kind)
        seen_clocks[c.id] = cd
        gb.add_clock(cd)
    for e in graph.edges:
        gb.add_edge(LangEdge(
            id=e.id, from_node=e.from_node, to_node=e.to_node,
            edge_kind=e.edge_kind, attributes=dict(e.attributes or {}),
        ))
    # Ownership entries
    for s in config.sources:
        gb.add_ownership(OwnershipEntry(
            binding=f"state.source.{s.component_id}",
            owner=f"source.{s.component_id}", ownership="own",
        ))
    gb.add_ownership(OwnershipEntry(
        binding=f"state.recursion.{config.recursion.component_id}",
        owner=f"recursion.{config.recursion.component_id}", ownership="own",
    ))
    sg: SemanticGraph = gb.build()

    # Contracts + capabilities + clocks records.
    contracts = [ContractRecord(
        id=f"contract.contractive.{config.recursion.component_id}",
        kind="Contractive",
        body={
            "recursion": config.recursion.component_id,
            "metric": "Linf",
            "requested_margin": config.recursion.contraction_margin,
            "certification_method": "ExactRationalArithmetic",
            "scope": "PROJECTED_RECURSION",
        },
    )]
    capability_records = []
    for s in config.sources:
        for cap in sorted(s.offered_capabilities):
            capability_records.append(CapabilityRecord(
                name=cap, version="0.1.0",
                tier=("REQUIRED" if cap in ("VectorRead", "VectorDrive", "PerTokenStep")
                      else "OPTIONAL"),
            ))
    # Dedup capabilities
    seen = set()
    unique_capabilities = []
    for cr in capability_records:
        key = (cr.name, cr.version, cr.tier)
        if key not in seen:
            seen.add(key)
            unique_capabilities.append(cr)
    clocks_records = [ClockRecord(id=c.id, kind=c.kind) for c in config.clocks]

    # Declarations.
    declarations: List[Declaration] = []
    for s in config.sources:
        declarations.append(Declaration(
            id=f"decl.source.{s.component_id}",
            kind=DeclarationKind.SOURCE,
            body={
                "name": s.component_id,
                "impl_type": s.implementation.split(":")[-1],
                "clock": s.clock,
                "offers": sorted(s.offered_capabilities),
            },
        ))
    declarations.append(Declaration(
        id=f"decl.recursion.{config.recursion.component_id}",
        kind=DeclarationKind.RECURSION,
        body={
            "name": config.recursion.component_id,
            "impl_type": config.recursion.implementation.split(":")[-1],
            "clock": config.recursion.clock,
            "dimension": config.recursion.dimension,
            "contraction_margin": config.recursion.contraction_margin,
        },
    ))
    for p in config.projections:
        declarations.append(Declaration(
            id=f"decl.projection.{p.component_id}",
            kind=DeclarationKind.PROJECTION,
            body={
                "source": p.source_component,
                "target": p.target_component,
                "input_shape": list(p.input_shape),
                "output_shape": list(p.output_shape),
                "scale_upper_bound": p.scale_upper_bound,
            },
        ))

    integration_clock = next(c for c in config.clocks if c.id == config.recursion.clock)

    # Instruction stream: unroll config.inference.ticks source ticks,
    # firing an integration whenever window_size source ticks have
    # accumulated. Every step and every integration produces at least
    # one canonical instruction, so identical configs produce
    # byte-identical IR.
    instructions: List[Instruction] = []
    for c in clocks_records:
        instructions.append(Instruction(
            opcode=Opcode.CLOCK_DEFINE,
            operands=(c.id, c.kind),
            operand_types=("str", "str"),
            clock=c.id,
        ))
    # Source init
    for s in config.sources:
        instructions.append(Instruction(
            opcode=Opcode.SOURCE_INIT,
            operands=(s.component_id, {"impl_type": s.implementation,
                                       "dimension": s.dimension}, s.seed),
            operand_types=("sourceId", "config", "seed"),
            result_binding=f"state.source.{s.component_id}",
            clock=s.clock,
        ))
    # Recursion init
    instructions.append(Instruction(
        opcode=Opcode.RECURSION_INIT,
        operands=(config.recursion.component_id,
                  {"dimension": config.recursion.dimension}, 0),
        operand_types=("recursionId", "config", "seed"),
        result_binding=f"state.recursion.{config.recursion.component_id}",
        clock=config.recursion.clock,
        contract=f"contract.contractive.{config.recursion.component_id}",
    ))
    # Unrolled ticks.
    window_size = integration_clock.window_size or 1
    for tick in range(config.inference.ticks):
        instructions.append(Instruction(
            opcode=Opcode.CLOCK_TICK,
            operands=(config.sources[0].clock,),
            operand_types=("clockId",),
            clock=config.sources[0].clock, clock_position=tick,
        ))
        for s in config.sources:
            instructions.append(Instruction(
                opcode=Opcode.SOURCE_STEP,
                operands=(s.component_id, f"state.source.{s.component_id}"),
                operand_types=("sourceId", "binding"),
                clock=s.clock, clock_position=tick,
            ))
        if (tick + 1) % window_size == 0:
            instructions.append(Instruction(
                opcode=Opcode.CLOCK_TICK,
                operands=(config.recursion.clock,),
                operand_types=("clockId",),
                clock=config.recursion.clock,
                clock_position=(tick + 1) // window_size,
            ))
            instructions.append(Instruction(
                opcode=Opcode.RECURSION_INTEGRATE,
                operands=(config.recursion.component_id,
                          f"state.recursion.{config.recursion.component_id}",
                          tuple(f"minput.{s.component_id}" for s in config.sources)),
                operand_types=("substrateId", "state_binding", "inputs"),
                clock=config.recursion.clock,
                clock_position=(tick + 1) // window_size,
                contract=f"contract.contractive.{config.recursion.component_id}",
            ))

    schedule = ScheduleRecord(
        id="schedule.aeon_app.reference",
        body={"strategy": "unroll", "ticks": config.inference.ticks,
              "window_size": window_size},
    )
    module = build_module(
        graph=sg,
        declarations=declarations,
        contracts=contracts,
        capabilities=unique_capabilities,
        clocks=clocks_records,
        schedule=schedule,
        instructions=instructions,
    )
    # Validate at build time; fail-closed on any error.
    validate_ir(module)
    return module
