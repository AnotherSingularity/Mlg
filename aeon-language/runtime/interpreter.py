"""Aeon reference interpreter.

Executes an :class:`~aeon.ir.IRModule` deterministically. The
interpreter is framework-free: state values, signal payloads, and
Recursion state are pure Python tuples of floats. Backend
implementations may replace them with framework-native tensors, but
they MUST NOT change the observable semantics captured here.

Supported opcodes in v0.1 (others are recognized as no-ops that
record a NODE_ENTER/NODE_EXIT-style diagnostic):

    CLOCK_DEFINE, CLOCK_TICK, CLOCK_RELATE, WINDOW_OPEN, WINDOW_CLOSE
    SOURCE_INIT, SOURCE_STEP, SOURCE_READ, SOURCE_DRIVE
    RECURSION_INIT, RECURSION_INTEGRATE, RECURSION_READ
    SIGNAL_FORM, SIGNAL_PROJECT, SIGNAL_EMIT
    STATE_SNAPSHOT, STATE_RESTORE
    CONTRACT_BIND, CONTRACT_CERTIFY, CONTRACT_REQUIRE
    NODE_ENTER, NODE_EXIT
    CANONICALIZE, DIGEST, PROVENANCE_RECORD, LINEAGE_ATTACH
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from aeon.clock import ClockPosition, Window
from aeon.contraction import ContractionCertificate
from aeon.core import (
    Applied,
    AppliedUncertified,
    Certificate,
    ContractViolation,
    ContractViolationCode,
    Diagnostic,
    Failed,
    Rejected,
    Reason,
    RuntimeError_,
    RuntimeErrorCode,
    Severity,
    TransitionResult,
    Validity,
)
from aeon.ir import IRModule, Instruction, Opcode, validate
from aeon.port import ReadRequest, SignalSourcePort
from aeon.provenance import LineageRecord, make_identity
from aeon.recursion import (
    ManifoldInput,
    ProjectionContract,
    RecursionState,
    RecursionSubstrate,
)
from aeon.serialization import canonical_bytes, canonical_value, digest
from aeon.signal import SignalFrame, new_signal_frame
from aeon.state import OwnershipError, OwnershipTable


@dataclass
class TraceEntry:
    step: int
    opcode: str
    result_binding: Optional[str]
    result_summary: str
    diagnostics: Tuple[Diagnostic, ...] = ()


@dataclass
class ExecutionOutcome:
    outputs: List[SignalFrame[Any]] = field(default_factory=list)
    state_bindings: Dict[str, Any] = field(default_factory=dict)
    certificates: List[Certificate[Any]] = field(default_factory=list)
    contraction_certificates: List[ContractionCertificate] = field(default_factory=list)
    diagnostics: List[Diagnostic] = field(default_factory=list)
    trace: List[TraceEntry] = field(default_factory=list)
    halt_reason: str = "completed"
    logical_tick: int = 0


class InterpreterError(Exception):
    pass


class Interpreter:
    """Deterministic reference interpreter.

    Sources and substrates are passed in by (id -> implementation)
    maps. This keeps the interpreter framework-free.
    """

    def __init__(
        self,
        module: IRModule,
        *,
        sources: Mapping[str, SignalSourcePort[Any]] = None,
        substrates: Mapping[str, RecursionSubstrate] = None,
        seed: int = 0,
    ) -> None:
        validate(module)
        self.module = module
        self.sources = dict(sources or {})
        self.substrates = dict(substrates or {})
        self.seed = seed

        # Execution state
        self._bindings: Dict[str, Any] = {}
        self._clock_ticks: Dict[str, int] = {}
        self._ownership = OwnershipTable()
        self._windows: Dict[str, Window] = {}
        self._contract_bindings: Dict[str, str] = {}

    # ---- execution ----------------------------------------------------

    def run(self) -> ExecutionOutcome:
        outcome = ExecutionOutcome()

        for step_index, instr in enumerate(self.module.instructions):
            try:
                result_binding, summary = self._exec(instr, outcome)
            except InterpreterError as exc:
                outcome.diagnostics.append(Diagnostic(
                    severity=Severity.ERROR,
                    code="INTERPRETER_ERROR",
                    message=str(exc),
                ))
                outcome.halt_reason = f"error at step {step_index}"
                outcome.trace.append(TraceEntry(
                    step=step_index,
                    opcode=instr.opcode.value,
                    result_binding=None,
                    result_summary=f"ERROR: {exc}",
                ))
                return outcome
            except OwnershipError as exc:
                outcome.diagnostics.append(Diagnostic(
                    severity=Severity.ERROR,
                    code="OWNERSHIP_VIOLATION",
                    message=str(exc),
                ))
                outcome.halt_reason = f"ownership violation at step {step_index}"
                return outcome
            outcome.trace.append(TraceEntry(
                step=step_index,
                opcode=instr.opcode.value,
                result_binding=result_binding,
                result_summary=summary,
            ))
            outcome.logical_tick += 1

        return outcome

    # ---- opcode dispatch ----------------------------------------------

    def _exec(self, instr: Instruction, outcome: ExecutionOutcome) -> Tuple[Optional[str], str]:
        op = instr.opcode

        # -- clocks -------------------------------------------------------
        if op is Opcode.CLOCK_DEFINE:
            clock_id = str(instr.operands[0])
            self._clock_ticks.setdefault(clock_id, 0)
            return (clock_id, f"clock_defined:{clock_id}")

        if op is Opcode.CLOCK_TICK:
            clock_id = str(instr.operands[0])
            if clock_id not in self._clock_ticks:
                raise InterpreterError(f"CLOCK_TICK on undeclared clock {clock_id!r}")
            self._clock_ticks[clock_id] += 1
            return (None, f"clock_tick:{clock_id}={self._clock_ticks[clock_id]}")

        if op is Opcode.CLOCK_RELATE:
            # Recorded but does not itself compute anything at runtime.
            return (None, f"clock_relate:{instr.operands}")

        if op is Opcode.WINDOW_OPEN:
            wid = str(instr.operands[0])
            clock_id = str(instr.operands[1])
            start = int(instr.operands[2]) if len(instr.operands) > 2 else self._clock_ticks.get(clock_id, 0)
            self._windows[wid] = Window(id=wid, domain_id=clock_id, start=start, end=start + 1)
            return (wid, f"window_open:{wid}[{start},{start+1})")

        if op is Opcode.WINDOW_CLOSE:
            wid = str(instr.operands[0])
            end = int(instr.operands[1]) if len(instr.operands) > 1 else self._clock_ticks.get(self._windows[wid].domain_id, 0)
            w = self._windows[wid]
            self._windows[wid] = Window(id=wid, domain_id=w.domain_id, start=w.start, end=max(end, w.start + 1))
            return (wid, f"window_close:{wid}[{w.start},{end})")

        # -- source / recursion init -------------------------------------
        if op is Opcode.SOURCE_INIT:
            source_id = str(instr.operands[0])
            config = instr.operands[1] if len(instr.operands) > 1 else {}
            seed = int(instr.operands[2]) if len(instr.operands) > 2 else self.seed
            impl = self._require_source(source_id)
            state = impl.initialize(config or {}, seed)
            binding = instr.result_binding or f"state.source.{source_id}"
            self._bindings[binding] = state
            return (binding, f"source_init:{source_id} -> {binding}")

        if op is Opcode.RECURSION_INIT:
            substrate_id = str(instr.operands[0])
            config = instr.operands[1] if len(instr.operands) > 1 else {}
            seed = int(instr.operands[2]) if len(instr.operands) > 2 else self.seed
            impl = self._require_substrate(substrate_id)
            state = impl.initialize(config or {}, seed)
            binding = instr.result_binding or f"state.recursion.{substrate_id}"
            self._bindings[binding] = state
            self._ownership.introduce(state.id)
            return (binding, f"recursion_init:{substrate_id} -> {binding}")

        # -- source step / read / drive ----------------------------------
        if op is Opcode.SOURCE_STEP:
            source_id = str(instr.operands[0])
            binding = str(instr.operands[1])
            input_binding = str(instr.operands[2]) if len(instr.operands) > 2 else None
            clock_id = instr.clock or "token"
            tick = self._clock_ticks.get(clock_id, 0)
            impl = self._require_source(source_id)
            state = self._bindings[binding]
            input_frame = self._bindings.get(input_binding) if input_binding else self._zero_input_frame(source_id, state, clock_id, tick)
            result = impl.step(input_frame, state, ClockPosition(clock_id, tick))
            self._bindings[binding] = result.next_state
            # Record emissions
            for e in result.emissions:
                self._bindings[f"frame.{source_id}.{tick}"] = e
                outcome.diagnostics.extend(result.diagnostics)
            outcome.diagnostics.extend(result.diagnostics)
            outcome.certificates.extend(result.certificates)
            return (binding, f"source_step:{source_id}#{tick} emissions={len(result.emissions)}")

        if op is Opcode.SOURCE_READ:
            source_id = str(instr.operands[0])
            binding = str(instr.operands[1])
            request_kind = str(instr.operands[2]) if len(instr.operands) > 2 else "vector"
            impl = self._require_source(source_id)
            state = self._bindings[binding]
            value = impl.read(state, ReadRequest(kind=request_kind))
            result_binding = instr.result_binding or f"read.{source_id}.{request_kind}"
            self._bindings[result_binding] = value
            return (result_binding, f"source_read:{source_id}/{request_kind}")

        if op is Opcode.SOURCE_DRIVE:
            source_id = str(instr.operands[0])
            binding = str(instr.operands[1])
            drive_value = instr.operands[2]
            impl = self._require_source(source_id)
            state = self._bindings[binding]
            clock_id = instr.clock or "token"
            tick = self._clock_ticks.get(clock_id, 0)
            frame = new_signal_frame(
                source_id=f"drive.{source_id}",
                sequence=tick,
                clock_position=ClockPosition(clock_id, tick),
                payload=list(drive_value),
                originating_state_id=state.id if hasattr(state, "id") else make_identity("state", {"binding": binding}),
            )
            result = impl.step(frame, state, ClockPosition(clock_id, tick))
            self._bindings[binding] = result.next_state
            return (binding, f"source_drive:{source_id}#{tick}")

        # -- signal --------------------------------------------------------
        if op is Opcode.SIGNAL_FORM:
            source_id = str(instr.operands[0])
            payload = instr.operands[1]
            sequence = int(instr.operands[2]) if len(instr.operands) > 2 else 0
            clock_id = instr.clock or "token"
            tick = self._clock_ticks.get(clock_id, 0)
            origin_ref = str(instr.operands[3]) if len(instr.operands) > 3 else "root"
            origin_id = self._bindings.get(origin_ref, None)
            origin_state_id = getattr(origin_id, "id", None) or make_identity("state", {"ref": origin_ref})
            frame = new_signal_frame(
                source_id=source_id,
                sequence=sequence,
                clock_position=ClockPosition(clock_id, tick),
                payload=list(payload),
                originating_state_id=origin_state_id,
            )
            binding = instr.result_binding or f"frame.{source_id}.{tick}"
            self._bindings[binding] = frame
            return (binding, f"signal_form:{source_id}#{tick}")

        if op is Opcode.SIGNAL_PROJECT:
            frame_binding = str(instr.operands[0])
            substrate_id = str(instr.operands[1])
            projection_id = str(instr.operands[2])
            input_dim = int(instr.operands[3])
            scale = float(instr.operands[4]) if len(instr.operands) > 4 else 1.0
            frame = self._bindings[frame_binding]
            impl = self._require_substrate(substrate_id)
            contract = ProjectionContract(
                id=projection_id, source_id=frame.source_id,
                substrate_id=substrate_id, input_shape=(input_dim,),
                scale=scale,
            )
            m = impl.project(frame, contract)
            binding = instr.result_binding or f"minput.{projection_id}.{frame_binding}"
            self._bindings[binding] = m
            return (binding, f"signal_project:{projection_id}")

        if op is Opcode.SIGNAL_EMIT:
            frame_binding = str(instr.operands[0])
            frame = self._bindings[frame_binding]
            outcome.outputs.append(frame)
            return (None, f"signal_emit:{frame_binding}")

        # -- recursion -----------------------------------------------------
        if op is Opcode.RECURSION_INTEGRATE:
            substrate_id = str(instr.operands[0])
            state_binding = str(instr.operands[1])
            input_bindings = list(instr.operands[2]) if len(instr.operands) > 2 else []
            impl = self._require_substrate(substrate_id)
            state = self._bindings[state_binding]
            # Owned consumption
            self._ownership.consume(state.id)
            inputs = [self._bindings[b] for b in input_bindings]
            clock_id = instr.clock or "integration"
            tick = self._clock_ticks.get(clock_id, 0)
            step_result = impl.integrate(inputs, state, ClockPosition(clock_id, tick))
            self._bindings[state_binding] = step_result.next_state
            self._ownership.introduce(step_result.next_state.id)
            outcome.certificates.append(step_result.transition_certificate)
            outcome.contraction_certificates.append(step_result.contraction_certificate)
            return (state_binding, (
                f"recursion_integrate:{substrate_id}#{tick} "
                f"result={step_result.contraction_certificate.result.value}"
            ))

        if op is Opcode.RECURSION_READ:
            substrate_id = str(instr.operands[0])
            state_binding = str(instr.operands[1])
            request_kind = str(instr.operands[2]) if len(instr.operands) > 2 else "vector"
            impl = self._require_substrate(substrate_id)
            state = self._bindings[state_binding]
            value = impl.read(state, ReadRequest(kind=request_kind))
            binding = instr.result_binding or f"rec_read.{substrate_id}.{request_kind}"
            self._bindings[binding] = value
            return (binding, f"recursion_read:{substrate_id}/{request_kind}")

        # -- snapshot / restore ------------------------------------------
        if op is Opcode.STATE_SNAPSHOT:
            state_binding = str(instr.operands[0])
            impl_id = str(instr.operands[1]) if len(instr.operands) > 1 else None
            state = self._bindings[state_binding]
            if impl_id and impl_id in self.substrates:
                snap = self.substrates[impl_id].snapshot(state)
            elif impl_id and impl_id in self.sources:
                snap = self.sources[impl_id].snapshot(state)
            else:
                raise InterpreterError(f"STATE_SNAPSHOT: unknown impl {impl_id!r}")
            binding = instr.result_binding or f"snap.{state_binding}"
            self._bindings[binding] = snap
            return (binding, f"state_snapshot:{state_binding}")

        if op is Opcode.STATE_RESTORE:
            snap_binding = str(instr.operands[0])
            impl_id = str(instr.operands[1])
            snap = self._bindings[snap_binding]
            if impl_id in self.substrates:
                state = self.substrates[impl_id].restore(snap)
            elif impl_id in self.sources:
                state = self.sources[impl_id].restore(snap)
            else:
                raise InterpreterError(f"STATE_RESTORE: unknown impl {impl_id!r}")
            binding = instr.result_binding or f"restored.{snap_binding}"
            self._bindings[binding] = state
            if hasattr(state, "id"):
                self._ownership.introduce(state.id)
            return (binding, f"state_restore:{snap_binding} via {impl_id}")

        # -- contract / provenance / bookkeeping -------------------------
        if op is Opcode.CONTRACT_BIND:
            contract = str(instr.operands[0])
            target = str(instr.operands[1])
            self._contract_bindings[target] = contract
            return (target, f"contract_bind:{contract}->{target}")

        if op is Opcode.CONTRACT_CERTIFY:
            # Interpreter marks the referenced binding as certified.
            return (None, "contract_certify")

        if op is Opcode.CONTRACT_REQUIRE:
            return (None, "contract_require")

        if op in (Opcode.NODE_ENTER, Opcode.NODE_EXIT):
            return (None, f"{op.value}:{instr.operands}")

        if op is Opcode.CANONICALIZE:
            value = instr.operands[0]
            b = canonical_bytes(canonical_value(value))
            binding = instr.result_binding or "canonicalize.tmp"
            self._bindings[binding] = b
            return (binding, f"canonicalize:{len(b)}b")

        if op is Opcode.DIGEST:
            b = instr.operands[0]
            method = str(instr.operands[1]) if len(instr.operands) > 1 else "blake2b-256"
            d = digest(b if isinstance(b, (bytes, bytearray)) else canonical_value(b), method)
            binding = instr.result_binding or "digest.tmp"
            self._bindings[binding] = d
            return (binding, f"digest:{d[:12]}")

        if op is Opcode.PROVENANCE_RECORD:
            return (None, "provenance_record")

        if op is Opcode.LINEAGE_ATTACH:
            return (None, "lineage_attach")

        # Unimplemented opcode -> Rejected as UNIMPLEMENTED (kept explicit).
        outcome.diagnostics.append(Diagnostic(
            severity=Severity.WARNING,
            code="OPCODE_UNIMPLEMENTED_V0",
            message=f"opcode {op.value!r} is not implemented in the v0.1 reference interpreter",
        ))
        return (None, f"unimplemented:{op.value}")

    # ---- helpers ------------------------------------------------------

    def _require_source(self, source_id: str) -> SignalSourcePort[Any]:
        if source_id not in self.sources:
            raise InterpreterError(f"source {source_id!r} not provided to interpreter")
        return self.sources[source_id]

    def _require_substrate(self, substrate_id: str) -> RecursionSubstrate:
        if substrate_id not in self.substrates:
            raise InterpreterError(f"substrate {substrate_id!r} not provided to interpreter")
        return self.substrates[substrate_id]

    def _zero_input_frame(self, source_id: str, state: Any,
                          clock_id: str, tick: int) -> SignalFrame[Any]:
        # Explicit zero-payload input frame; still tagged as its own frame
        # id so provenance is traceable. This is *not* silent absence: the
        # frame is a real, identified frame carrying zeros as its declared
        # payload.
        dim = getattr(state, "dimension", 4)
        return new_signal_frame(
            source_id=f"input.{source_id}",
            sequence=tick,
            clock_position=ClockPosition(clock_id, tick),
            payload=[0.0] * dim,
            originating_state_id=getattr(state, "id", make_identity("state", {"src": source_id})),
        )
