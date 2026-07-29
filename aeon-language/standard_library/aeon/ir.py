"""aeon.ir — the Canonical Aeon IR data model.

Implements ``09-CANONICAL-IR.md``. IR modules are pure data:
declarations, a graph reference, contracts, capabilities, clocks,
a schedule, and an instruction stream. Canonical bytes are
produced by :mod:`aeon.serialization` and hashed to give the
module id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Tuple

from . import INSTRUCTION_SET_VERSION, IR_VERSION, LANGUAGE_VERSION
from .graph import SemanticGraph
from .serialization import DEFAULT_DIGEST_METHOD, canonical_bytes, canonical_value, digest


# ---------------------------------------------------------------------------
# Opcodes (spec 10-INSTRUCTION-SET.md)
# ---------------------------------------------------------------------------


class Opcode(Enum):
    # State
    STATE_NEW = "STATE_NEW"
    STATE_READ = "STATE_READ"
    STATE_REPLACE = "STATE_REPLACE"
    STATE_SNAPSHOT = "STATE_SNAPSHOT"
    STATE_RESTORE = "STATE_RESTORE"
    STATE_RELEASE = "STATE_RELEASE"
    # Signal
    SIGNAL_FORM = "SIGNAL_FORM"
    SIGNAL_PROJECT = "SIGNAL_PROJECT"
    SIGNAL_ROUTE = "SIGNAL_ROUTE"
    SIGNAL_BUFFER = "SIGNAL_BUFFER"
    SIGNAL_AGGREGATE = "SIGNAL_AGGREGATE"
    SIGNAL_EMIT = "SIGNAL_EMIT"
    # Source
    SOURCE_INIT = "SOURCE_INIT"
    SOURCE_STEP = "SOURCE_STEP"
    SOURCE_READ = "SOURCE_READ"
    SOURCE_DRIVE = "SOURCE_DRIVE"
    SOURCE_QUERY_CAPABILITY = "SOURCE_QUERY_CAPABILITY"
    # Recursion
    RECURSION_INIT = "RECURSION_INIT"
    RECURSION_PROJECT = "RECURSION_PROJECT"
    RECURSION_INTEGRATE = "RECURSION_INTEGRATE"
    RECURSION_READ = "RECURSION_READ"
    RECURSION_FEEDBACK = "RECURSION_FEEDBACK"
    # Temporal
    CLOCK_DEFINE = "CLOCK_DEFINE"
    CLOCK_TICK = "CLOCK_TICK"
    CLOCK_RELATE = "CLOCK_RELATE"
    WINDOW_OPEN = "WINDOW_OPEN"
    WINDOW_CLOSE = "WINDOW_CLOSE"
    # Contract
    CONTRACT_BIND = "CONTRACT_BIND"
    CONTRACT_CHECK = "CONTRACT_CHECK"
    CONTRACT_REQUIRE = "CONTRACT_REQUIRE"
    CONTRACT_REJECT = "CONTRACT_REJECT"
    CONTRACT_CERTIFY = "CONTRACT_CERTIFY"
    # Graph
    NODE_ENTER = "NODE_ENTER"
    NODE_EXIT = "NODE_EXIT"
    EDGE_TRANSFER = "EDGE_TRANSFER"
    FORK = "FORK"
    JOIN = "JOIN"
    SELECT = "SELECT"
    # Provenance
    LINEAGE_ATTACH = "LINEAGE_ATTACH"
    LINEAGE_DERIVE = "LINEAGE_DERIVE"
    PROVENANCE_RECORD = "PROVENANCE_RECORD"
    CANONICALIZE = "CANONICALIZE"
    DIGEST = "DIGEST"


# The set of opcode strings, precomputed for fast validation.
OPCODE_VALUES = frozenset(op.value for op in Opcode)


# ---------------------------------------------------------------------------
# Instruction record (spec 09 §6)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Instruction:
    opcode: Opcode
    operands: Tuple[Any, ...] = ()
    operand_types: Tuple[str, ...] = ()
    preconditions: Tuple[str, ...] = ()
    clock: Optional[str] = None
    clock_position: Optional[int] = None
    contract: Optional[str] = None
    result_binding: Optional[str] = None
    source_span: Optional[str] = None

    def to_canonical(self) -> dict:
        d: dict = {
            "opcode": self.opcode.value,
            "operands": list(self.operands),
            "operand_types": list(self.operand_types),
            "preconditions": list(self.preconditions),
        }
        if self.clock is not None:
            d["clock"] = self.clock
        if self.clock_position is not None:
            d["clock_position"] = self.clock_position
        if self.contract is not None:
            d["contract"] = self.contract
        if self.result_binding is not None:
            d["result_binding"] = self.result_binding
        if self.source_span is not None:
            d["source_span"] = self.source_span
        return canonical_value(d)


# ---------------------------------------------------------------------------
# Declarations
# ---------------------------------------------------------------------------


class DeclarationKind(Enum):
    SOURCE = "source_declaration"
    RECURSION = "recursion_declaration"
    PROJECTION = "projection_declaration"
    CLOCK = "clock_declaration"
    CLOCK_RELATION = "clock_relation"
    CONTRACT_BINDING = "contract_binding"
    WINDOW = "window_declaration"
    OUTPUT = "output_declaration"
    SNAPSHOT = "snapshot_declaration"


@dataclass(frozen=True)
class Declaration:
    id: str
    kind: DeclarationKind
    body: Mapping[str, Any]

    def to_canonical(self) -> dict:
        return canonical_value({
            "id": self.id,
            "kind": self.kind.value,
            "body": dict(self.body),
        })


# ---------------------------------------------------------------------------
# IR module envelope (spec 09 §2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContractRecord:
    id: str
    kind: str
    body: Mapping[str, Any]


@dataclass(frozen=True)
class CapabilityRecord:
    name: str
    version: str
    tier: str  # "REQUIRED" or "OPTIONAL"


@dataclass(frozen=True)
class ClockRecord:
    id: str
    kind: str


@dataclass(frozen=True)
class ScheduleRecord:
    id: str
    body: Mapping[str, Any]


@dataclass(frozen=True)
class IRModule:
    aeon_ir_version: str
    language_version: str
    instruction_set_version: str
    digest_method: str
    declarations: Tuple[Declaration, ...]
    graph: SemanticGraph
    contracts: Tuple[ContractRecord, ...]
    capabilities: Tuple[CapabilityRecord, ...]
    clocks: Tuple[ClockRecord, ...]
    schedule: ScheduleRecord
    instructions: Tuple[Instruction, ...]
    module_id: str = ""  # computed by finalize()

    def body_canonical(self) -> dict:
        return canonical_value({
            "aeon_ir_version": self.aeon_ir_version,
            "language_version": self.language_version,
            "instruction_set_version": self.instruction_set_version,
            "digest_method": self.digest_method,
            "declarations": [d.to_canonical()
                             for d in sorted(self.declarations, key=lambda d: d.id)],
            "graph": self.graph.to_canonical(),
            "contracts": [
                {"id": c.id, "kind": c.kind, "body": dict(c.body)}
                for c in sorted(self.contracts, key=lambda c: c.id)
            ],
            "capabilities": [
                {"name": c.name, "version": c.version, "tier": c.tier}
                for c in sorted(self.capabilities, key=lambda c: (c.name, c.version))
            ],
            "clocks": [
                {"id": c.id, "kind": c.kind}
                for c in sorted(self.clocks, key=lambda c: c.id)
            ],
            "schedule": {
                "id": self.schedule.id,
                "body": dict(self.schedule.body),
            },
            "instructions": [i.to_canonical() for i in self.instructions],
        })

    def compute_module_id(self) -> str:
        return digest(self.body_canonical(), self.digest_method)

    def to_canonical(self) -> dict:
        body = self.body_canonical()
        return {
            "aeon_ir_version": self.aeon_ir_version,
            "language_version": self.language_version,
            "instruction_set_version": self.instruction_set_version,
            "digest_method": self.digest_method,
            "module_id": self.module_id or self.compute_module_id(),
            "body": body,
        }

    def to_bytes(self) -> bytes:
        return canonical_bytes(self.to_canonical())


# ---------------------------------------------------------------------------
# IR validation (spec 09 §7)
# ---------------------------------------------------------------------------


class IRValidationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


def validate(module: IRModule) -> None:
    """Validate an IR module per 09-CANONICAL-IR.md §7.

    Raises :class:`IRValidationError` on the first failure.
    """

    # 1. Version envelope
    if module.aeon_ir_version != IR_VERSION:
        raise IRValidationError(
            "IR_VERSION_MISMATCH",
            f"expected {IR_VERSION}, got {module.aeon_ir_version!r}",
        )
    if module.language_version != LANGUAGE_VERSION:
        raise IRValidationError(
            "LANG_VERSION_MISMATCH",
            f"expected {LANGUAGE_VERSION}, got {module.language_version!r}",
        )
    if module.instruction_set_version != INSTRUCTION_SET_VERSION:
        raise IRValidationError(
            "ISA_VERSION_MISMATCH",
            f"expected {INSTRUCTION_SET_VERSION}, "
            f"got {module.instruction_set_version!r}",
        )

    # 2. Module id equals digest(body)
    expected_id = module.compute_module_id()
    if module.module_id and module.module_id != expected_id:
        raise IRValidationError(
            "MODULE_ID_MISMATCH",
            f"declared module_id does not equal computed digest "
            f"(declared={module.module_id[:16]}..., "
            f"computed={expected_id[:16]}...)",
        )

    # 3. Every opcode is recognized
    for i, instr in enumerate(module.instructions):
        if instr.opcode.value not in OPCODE_VALUES:
            raise IRValidationError(
                "UNKNOWN_OPCODE",
                f"instruction #{i}: unknown opcode {instr.opcode!r}",
            )
        # 4. operand_types count matches operands count
        if instr.operand_types and len(instr.operand_types) != len(instr.operands):
            raise IRValidationError(
                "OPERAND_TYPE_COUNT",
                f"instruction #{i} ({instr.opcode.value}): operand_types "
                f"count {len(instr.operand_types)} != operands count "
                f"{len(instr.operands)}",
            )

    # 5. Every referenced identifier resolves
    node_ids = {n.id for n in module.graph.nodes}
    clock_ids = {c.id for c in module.clocks}
    for i, instr in enumerate(module.instructions):
        if instr.clock is not None and instr.clock not in clock_ids:
            raise IRValidationError(
                "UNKNOWN_CLOCK",
                f"instruction #{i}: clock {instr.clock!r} not declared",
            )

    # 6. Ownership: every consumption is followed by no further mutation
    # (approximate: track by result_binding; a STATE_REPLACE / STATE_RELEASE
    # / FORK consumes; a later STATE_REPLACE / STATE_RELEASE / STATE_READ_MUT
    # of the same binding is a violation).
    consumed_bindings: set[str] = set()
    consuming_opcodes = {
        Opcode.STATE_REPLACE, Opcode.STATE_RELEASE, Opcode.FORK,
    }
    for i, instr in enumerate(module.instructions):
        if instr.opcode in consuming_opcodes:
            # The first operand is the state binding being consumed (by
            # convention of the reference interpreter).
            if not instr.operands:
                raise IRValidationError(
                    "CONSUME_NO_OPERAND",
                    f"instruction #{i} ({instr.opcode.value}) has no operands",
                )
            binding = str(instr.operands[0])
            if binding in consumed_bindings:
                raise IRValidationError(
                    "DOUBLE_CONSUMPTION",
                    f"instruction #{i} ({instr.opcode.value}) consumes "
                    f"binding {binding!r} that was already consumed",
                )
            consumed_bindings.add(binding)


# ---------------------------------------------------------------------------
# Convenience: build a minimal IR module
# ---------------------------------------------------------------------------


def build_module(
    *,
    declarations: Sequence[Declaration] = (),
    graph: SemanticGraph,
    contracts: Sequence[ContractRecord] = (),
    capabilities: Sequence[CapabilityRecord] = (),
    clocks: Sequence[ClockRecord] = (),
    schedule: Optional[ScheduleRecord] = None,
    instructions: Sequence[Instruction] = (),
) -> IRModule:
    schedule_record = schedule or ScheduleRecord(id="schedule.default", body={})
    module = IRModule(
        aeon_ir_version=IR_VERSION,
        language_version=LANGUAGE_VERSION,
        instruction_set_version=INSTRUCTION_SET_VERSION,
        digest_method=DEFAULT_DIGEST_METHOD,
        declarations=tuple(declarations),
        graph=graph,
        contracts=tuple(contracts),
        capabilities=tuple(capabilities),
        clocks=tuple(clocks),
        schedule=schedule_record,
        instructions=tuple(instructions),
    )
    # Compute + attach module_id via a fresh instance (module is frozen).
    return IRModule(
        aeon_ir_version=module.aeon_ir_version,
        language_version=module.language_version,
        instruction_set_version=module.instruction_set_version,
        digest_method=module.digest_method,
        declarations=module.declarations,
        graph=module.graph,
        contracts=module.contracts,
        capabilities=module.capabilities,
        clocks=module.clocks,
        schedule=module.schedule,
        instructions=module.instructions,
        module_id=module.compute_module_id(),
    )
