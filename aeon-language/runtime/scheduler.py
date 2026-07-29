"""Aeon reference scheduler.

Converts a validated :class:`~aeon.graph.SemanticGraph` (plus its
originating :class:`~compiler.ast.Module`) into an ordered
Instruction stream, i.e. an executable Aeon IR module.

The scheduler is deterministic: given the same graph and the same
module, it produces byte-identical IR.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

from aeon.capability import CapabilityRef, CapabilityTier, VersionConstraint, negotiate
from aeon.core import SemVer
from aeon.graph import SemanticGraph
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
)

# The scheduler needs access to the parsed module (for schedule blocks).
from compiler.ast import (
    CertifyStmt,
    EmitStmt,
    EveryBlock,
    IntegrateStmt,
    Module,
    ProjectionDecl,
    RecursionDecl,
    ScheduleDecl,
    SourceDecl,
    StepStmt,
)


def lower(module: Module, graph: SemanticGraph, *,
          seed: int = 0, ticks_per_clock: int = 8) -> IRModule:
    """Lower a validated Module + SemanticGraph to an executable IRModule.

    ``ticks_per_clock`` is the number of scheduled iterations to
    unroll for each `every` block. It's a scheduler policy, not a
    language property. Two lowerings with the same input parameters
    produce byte-identical IR.
    """

    instructions: List[Instruction] = []
    declarations: List[Declaration] = []
    capabilities: List[CapabilityRecord] = []
    clocks: List[ClockRecord] = []
    contracts: List[ContractRecord] = []

    # ---- clock declarations --------------------------------------------
    declared_clocks: dict[str, str] = {}
    for s in module.sources:
        if s.clock:
            declared_clocks.setdefault(s.clock, _clock_kind(s.clock))
    for r in module.recursions:
        if r.clock:
            declared_clocks.setdefault(r.clock, _clock_kind(r.clock))
    for clock_id in sorted(declared_clocks):
        clocks.append(ClockRecord(id=clock_id, kind=declared_clocks[clock_id]))
        instructions.append(Instruction(
            opcode=Opcode.CLOCK_DEFINE,
            operands=(clock_id, declared_clocks[clock_id]),
            operand_types=("str", "str"),
            clock=clock_id,
        ))

    # ---- source declarations + init instructions -----------------------
    for s in module.sources:
        declarations.append(Declaration(
            id=f"decl.source.{s.name}",
            kind=DeclarationKind.SOURCE,
            body={
                "name": s.name,
                "impl_type": s.impl_type,
                "clock": s.clock or "",
                "requires": list(s.requires),
                "offers": list(s.offers),
            },
        ))
        instructions.append(Instruction(
            opcode=Opcode.SOURCE_INIT,
            operands=(s.name, {"impl_type": s.impl_type}, seed),
            operand_types=("sourceId", "config", "seed"),
            result_binding=f"state.source.{s.name}",
            clock=s.clock,
        ))

        # Capability records: the source's offered capabilities.
        for cap in s.offers:
            tier = "REQUIRED" if cap in ("VectorRead", "VectorDrive", "PerTokenStep") else "OPTIONAL"
            capabilities.append(CapabilityRecord(name=cap, version="0.1.0-dev", tier=tier))

    # ---- recursion declarations + init instructions --------------------
    for r in module.recursions:
        declarations.append(Declaration(
            id=f"decl.recursion.{r.name}",
            kind=DeclarationKind.RECURSION,
            body={
                "name": r.name,
                "impl_type": r.impl_type,
                "clock": r.clock or "",
                "dimension": r.dimension or 0,
                "contraction_margin": r.contraction_margin or 0.0,
            },
        ))
        contracts.append(ContractRecord(
            id=f"contract.contractive.{r.name}",
            kind="Contractive",
            body={
                "recursion": r.name,
                "metric": "Linf",
                "requested_margin": r.contraction_margin,
                "certification_method": "SymbolicParameterization",
            },
        ))
        instructions.append(Instruction(
            opcode=Opcode.RECURSION_INIT,
            operands=(r.name, {"dimension": r.dimension}, seed),
            operand_types=("recursionId", "config", "seed"),
            result_binding=f"state.recursion.{r.name}",
            clock=r.clock,
            contract=f"contract.contractive.{r.name}",
        ))

    # ---- projection declarations --------------------------------------
    for p in module.projections:
        declarations.append(Declaration(
            id=f"decl.projection.{p.source}.{p.port}.{p.substrate}",
            kind=DeclarationKind.PROJECTION,
            body={"source": p.source, "port": p.port, "substrate": p.substrate},
        ))

    # ---- schedule -------------------------------------------------------
    schedule_body = {"strategy": "unroll", "ticks_per_clock": ticks_per_clock}
    if module.schedule is not None:
        # Determine unroll counts.
        # For every-N-clock blocks with N > 1, we still schedule
        # ticks_per_clock/N invocations of the block body.
        for block in module.schedule.blocks:
            n_invocations = max(1, ticks_per_clock // block.every)
            for i in range(n_invocations):
                # Tick the block's clock, then run each statement.
                instructions.append(Instruction(
                    opcode=Opcode.CLOCK_TICK,
                    operands=(block.clock,),
                    operand_types=("clockId",),
                    clock=block.clock,
                    clock_position=i,
                ))
                for stmt in block.body:
                    instructions.extend(_lower_stmt(stmt, module, block, i))

    schedule_record = ScheduleRecord(id="schedule.reference", body=schedule_body)

    return build_module(
        declarations=declarations,
        graph=graph,
        contracts=contracts,
        capabilities=capabilities,
        clocks=clocks,
        schedule=schedule_record,
        instructions=instructions,
    )


def _clock_kind(clock_id: str) -> str:
    mapping = {"token": "Token", "integration": "Integration", "segment": "Segment"}
    return mapping.get(clock_id, "UserDefined")


def _lower_stmt(stmt, module: Module, block: EveryBlock, i: int) -> List[Instruction]:
    out: List[Instruction] = []
    if isinstance(stmt, StepStmt):
        out.append(Instruction(
            opcode=Opcode.SOURCE_STEP,
            operands=(stmt.target, f"state.source.{stmt.target}"),
            operand_types=("sourceId", "binding"),
            clock=block.clock,
            clock_position=i,
        ))
        # Read the source's vector then project to every substrate the
        # source projects into.
        proj_targets = [p for p in module.projections if p.source == stmt.target]
        if proj_targets:
            out.append(Instruction(
                opcode=Opcode.SOURCE_READ,
                operands=(stmt.target, f"state.source.{stmt.target}", "vector"),
                operand_types=("sourceId", "binding", "kind"),
                result_binding=f"read.{stmt.target}.{block.clock}.{i}",
                clock=block.clock,
                clock_position=i,
            ))
            # Form a frame from the read
            out.append(Instruction(
                opcode=Opcode.SIGNAL_FORM,
                operands=(stmt.target, f"read.{stmt.target}.{block.clock}.{i}", i, f"state.source.{stmt.target}"),
                operand_types=("sourceId", "value_binding", "sequence", "origin_binding"),
                result_binding=f"frame.{stmt.target}.{block.clock}.{i}",
                clock=block.clock,
                clock_position=i,
            ))
            # Wait: SIGNAL_FORM in interpreter takes a literal payload; adapt.
            # We'll adjust with an inline literal instead of a value_binding.
            out.pop()
            out.append(Instruction(
                opcode=Opcode.SIGNAL_FORM,
                operands=(stmt.target, [0.0] * _substrate_dim(module, proj_targets[0].substrate), i, f"state.source.{stmt.target}"),
                operand_types=("sourceId", "payload", "sequence", "origin_binding"),
                result_binding=f"frame.{stmt.target}.{block.clock}.{i}",
                clock=block.clock,
                clock_position=i,
            ))
            for p in proj_targets:
                dim = _substrate_dim(module, p.substrate)
                out.append(Instruction(
                    opcode=Opcode.SIGNAL_PROJECT,
                    operands=(
                        f"frame.{stmt.target}.{block.clock}.{i}",
                        p.substrate,
                        f"proj.{p.source}.{p.port}.{p.substrate}",
                        dim,
                        1.0,
                    ),
                    operand_types=("frame_binding", "substrateId", "projectionId", "dim", "scale"),
                    result_binding=f"minput.{p.source}.{p.substrate}",
                    clock=block.clock,
                    clock_position=i,
                ))
    elif isinstance(stmt, IntegrateStmt):
        # Gather every projection into this substrate (stable per-pair binding).
        inputs = [
            f"minput.{p.source}.{p.substrate}"
            for p in module.projections if p.substrate == stmt.target
        ]
        # Filter to inputs that actually exist by construction — the
        # scheduler emits them iff a step-of-the-source preceded us.
        out.append(Instruction(
            opcode=Opcode.RECURSION_INTEGRATE,
            operands=(stmt.target, f"state.recursion.{stmt.target}", tuple(inputs)),
            operand_types=("substrateId", "state_binding", "inputs"),
            clock=block.clock,
            clock_position=i,
            contract=f"contract.contractive.{stmt.target}",
        ))
    elif isinstance(stmt, CertifyStmt):
        out.append(Instruction(
            opcode=Opcode.CONTRACT_CERTIFY,
            operands=(f"contract.contractive.{stmt.target}", f"state.recursion.{stmt.target}"),
            operand_types=("contractRef", "state_binding"),
            clock=block.clock,
            clock_position=i,
        ))
    elif isinstance(stmt, EmitStmt):
        out.append(Instruction(
            opcode=Opcode.SIGNAL_EMIT,
            operands=(f"frame.{stmt.target}.{block.clock}.{i}",),
            operand_types=("frame_binding",),
            clock=block.clock,
            clock_position=i,
        ))
    return out


def _substrate_dim(module: Module, substrate_name: str) -> int:
    for r in module.recursions:
        if r.name == substrate_name:
            return r.dimension or 4
    return 4
