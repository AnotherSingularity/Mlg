"""Canonical IR determinism + validation."""

from __future__ import annotations

import pytest

from aeon.graph import (
    ClockDomainDecl,
    Edge,
    GraphBuilder,
    Node,
    NodeKind,
    OwnershipEntry,
)
from aeon.ir import (
    CapabilityRecord,
    ClockRecord,
    ContractRecord,
    Declaration,
    DeclarationKind,
    IRValidationError,
    IRModule,
    Instruction,
    Opcode,
    build_module,
    validate,
)


def _make_graph():
    gb = GraphBuilder(module_id="m.t")
    gb.add_node(Node("src.a", NodeKind.SOURCE, {}))
    gb.add_node(Node("rec.a", NodeKind.RECURSION, {"dim": 4}))
    gb.add_edge(Edge("e1", "src.a", "rec.a", "projection"))
    gb.add_clock(ClockDomainDecl("token", "Token"))
    gb.add_clock(ClockDomainDecl("integration", "Integration"))
    gb.add_ownership(OwnershipEntry("s0", "rec.a", "own"))
    return gb.build()


def _make_module():
    g = _make_graph()
    return build_module(
        graph=g,
        declarations=[
            Declaration("d.rec", DeclarationKind.RECURSION, {"dim": 4}),
            Declaration("d.src", DeclarationKind.SOURCE, {"port": "src.a"}),
        ],
        contracts=[ContractRecord("c.contractive", "Contractive", {"margin": 0.98})],
        capabilities=[
            CapabilityRecord("VectorRead", "1.0.0", "REQUIRED"),
            CapabilityRecord("VectorDrive", "1.0.0", "REQUIRED"),
            CapabilityRecord("PerTokenStep", "1.0.0", "REQUIRED"),
        ],
        clocks=[ClockRecord("token", "Token"), ClockRecord("integration", "Integration")],
        instructions=[
            Instruction(Opcode.CLOCK_DEFINE, ("token", "Token"), ("str", "str"), clock="token"),
            Instruction(Opcode.CLOCK_DEFINE, ("integration", "Integration"),
                        ("str", "str"), clock="integration"),
            Instruction(Opcode.RECURSION_INIT, ("rec.a", {}, 0),
                        ("id", "cfg", "seed"),
                        result_binding="s0", clock="integration"),
        ],
    )


def test_module_id_stable_under_reordering():
    m1 = _make_module()
    # Rebuild with reversed input orderings
    g = _make_graph()
    m2 = build_module(
        graph=g,
        declarations=[
            Declaration("d.src", DeclarationKind.SOURCE, {"port": "src.a"}),
            Declaration("d.rec", DeclarationKind.RECURSION, {"dim": 4}),
        ],
        contracts=[ContractRecord("c.contractive", "Contractive", {"margin": 0.98})],
        capabilities=[
            CapabilityRecord("PerTokenStep", "1.0.0", "REQUIRED"),
            CapabilityRecord("VectorDrive", "1.0.0", "REQUIRED"),
            CapabilityRecord("VectorRead", "1.0.0", "REQUIRED"),
        ],
        clocks=[ClockRecord("integration", "Integration"), ClockRecord("token", "Token")],
        instructions=m1.instructions,
    )
    assert m1.module_id == m2.module_id
    assert m1.to_bytes() == m2.to_bytes()


def test_validate_passes():
    validate(_make_module())


def test_validate_catches_double_consumption():
    g = _make_graph()
    m = build_module(
        graph=g,
        instructions=[
            Instruction(Opcode.STATE_REPLACE, ("s0", {}, "t0"), clock="integration"),
            Instruction(Opcode.STATE_REPLACE, ("s0", {}, "t1"), clock="integration"),
        ],
        clocks=[ClockRecord("token", "Token"), ClockRecord("integration", "Integration")],
    )
    with pytest.raises(IRValidationError) as exc:
        validate(m)
    assert exc.value.code == "DOUBLE_CONSUMPTION"


def test_validate_catches_unknown_clock():
    g = _make_graph()
    m = build_module(
        graph=g,
        instructions=[
            Instruction(Opcode.CLOCK_TICK, ("mystery",), clock="mystery"),
        ],
        clocks=[ClockRecord("token", "Token")],
    )
    with pytest.raises(IRValidationError) as exc:
        validate(m)
    assert exc.value.code == "UNKNOWN_CLOCK"


def test_validate_catches_module_id_tamper():
    m = _make_module()
    tampered = IRModule(
        aeon_ir_version=m.aeon_ir_version,
        language_version=m.language_version,
        instruction_set_version=m.instruction_set_version,
        digest_method=m.digest_method,
        declarations=m.declarations,
        graph=m.graph,
        contracts=m.contracts,
        capabilities=m.capabilities,
        clocks=m.clocks,
        schedule=m.schedule,
        instructions=m.instructions,
        module_id="deadbeef",
    )
    with pytest.raises(IRValidationError) as exc:
        validate(tampered)
    assert exc.value.code == "MODULE_ID_MISMATCH"
