"""aeon_app.application — top-level session, output contract, replay driver.

An ApplicationSession bundles:

- resolved config
- semantic graph + canonical IR
- source instances + Recursion substrate
- scheduler
- persistence + event log

Its ``run(ticks)`` method executes deterministic inference and
produces a list of ``AeonOutput`` values. ``snapshot()`` serializes
the entire session state; ``restore()`` reconstructs an
equivalent session.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from aeon.capability import (
    CapabilityRef,
    CapabilityTier,
    VersionConstraint,
    negotiate,
)
from aeon.clock import ClockPosition
from aeon.contraction import (
    CertificationMethod,
    ContractionCertificate,
    ContractionScope,
    Contractive,
    Metric,
    PrecisionPolicy,
)
from aeon.core import Certificate, SemVer, Validity
from aeon.provenance import make_identity
from aeon.recursion import RecursionState
from aeon.signal import SignalFrame, new_signal_frame

from .. import (
    APPLICATION_SNAPSHOT_SCHEMA_VERSION,
    APPLICATION_VERSION,
    AEON_LANGUAGE_CERTIFIED_COMMIT,
    AEON_LANGUAGE_REQUIRED_VERSION,
)
from ..config import ApplicationConfig, resolve
from ..config.language_lock import verify_language_lock
from ..feedback import FeedbackDecision, FeedbackRefused, apply_feedback
from ..graph import build_from_config, compile_to_ir
from ..identity import canonical_digest
from ..observability import EventLog
from ..persistence import (
    APPLICATION_SNAPSHOT_KIND,
    ApplicationSnapshot,
    load_snapshot,
    verify_snapshot_version,
)
from ..projections import resolve_projection, ProjectionParameters
from ..recursion import ApplicationContractiveRecursion
from ..sources import AttentionSource, PersistentRecurrentSource
from ..clocks import Window


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AeonOutput:
    output_id: str
    payload: Tuple[float, ...]
    originating_state_id: str
    application_graph_id: str
    clock_position: Tuple[str, int]                # (domain, tick)
    source_contributions: Tuple[Mapping[str, Any], ...]
    validity: Validity
    transition_certificate: Mapping[str, Any]
    contraction_certificate: Mapping[str, Any]
    provenance: Mapping[str, Any]


class RuntimeRejected(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code


class RuntimeFailure(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code


# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------


SOURCE_REGISTRY = {
    "aeon_app.sources.attention:AttentionSource": AttentionSource,
    "aeon_app.sources.recurrent:PersistentRecurrentSource": PersistentRecurrentSource,
}


def _resolve_source(implementation: str):
    if implementation not in SOURCE_REGISTRY:
        raise RuntimeRejected(
            "UNKNOWN_SOURCE_IMPLEMENTATION",
            f"source implementation {implementation!r} not registered",
        )
    return SOURCE_REGISTRY[implementation]


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


@dataclass
class ApplicationSession:
    config: ApplicationConfig
    graph_id: str
    ir_module_id: str
    sources: Dict[str, Any]
    source_states: Dict[str, Any]
    recursion_impl: ApplicationContractiveRecursion
    recursion_state: RecursionState
    projections: Dict[str, Any]                 # component_id -> instance
    scheduler_state: Dict[str, Any] = field(default_factory=dict)
    clock_positions: Dict[str, int] = field(default_factory=dict)
    active_windows: List[Window] = field(default_factory=list)
    event_log: EventLog = field(default_factory=EventLog)
    outputs: List[AeonOutput] = field(default_factory=list)
    _seq: int = 0
    # Pending feedback signals to add to the next step's input (per-source).
    _feedback_biases: Dict[str, Tuple[float, ...]] = field(default_factory=dict)

    def _fresh_frame_for(self, source_id: str, tick: int) -> SignalFrame:
        # Deterministic input sequence for REFERENCE mode: the input
        # payload is a function of (source_id hash, tick).
        cfg = next(s for s in self.config.sources if s.component_id == source_id)
        base = sum(ord(c) for c in source_id) % 7
        payload = [float(((base + tick + i) % 5)) * 0.2
                   for i in range(cfg.dimension)]
        return new_signal_frame(
            source_id=f"input.{source_id}", sequence=tick,
            clock_position=ClockPosition("source", tick), payload=payload,
            originating_state_id=make_identity("aeon_app.input", {
                "source_id": source_id, "tick": tick, "payload": payload,
            }),
        )

    def step_tick(self, tick: int) -> None:
        # Advance the source clock.
        self.clock_positions["source"] = tick
        window = self._current_window_or_open(tick)
        for s_cfg in self.config.sources:
            src = self.sources[s_cfg.component_id]
            state = self.source_states[s_cfg.component_id]
            frame = self._fresh_frame_for(s_cfg.component_id, tick)
            # Apply and clear any pending feedback bias for this source.
            bias = self._feedback_biases.pop(s_cfg.component_id, None)
            if bias is not None:
                biased_payload = tuple(f + b for f, b in zip(frame.payload, bias))
                frame = new_signal_frame(
                    source_id=frame.source_id, sequence=frame.sequence,
                    clock_position=frame.clock_position,
                    payload=list(biased_payload),
                    originating_state_id=frame.originating_state_id,
                )
            result = src.step(frame, state, ClockPosition("source", tick))
            self.source_states[s_cfg.component_id] = result.next_state
            self.event_log.record(
                kind="SourceStepped",
                component_id=s_cfg.component_id,
                clock_domain_id="source", clock_tick=tick,
                state_ids=(result.next_state.id.digest,),
                body={"emissions": len(result.emissions),
                      "frames": [f.id.digest for f in result.emissions]},
            )
            # Append emitted frame IDs to the current window.
            for f in result.emissions:
                window = replace_window_frames(window, window.frame_ids + (f.id.digest,))
        # Update the mutable window in the list.
        self.active_windows[-1] = window
        self.event_log.record(
            kind="FrameAggregated",
            clock_domain_id="source", clock_tick=tick,
            body={"window_id": window.id,
                  "window_start": window.start, "window_end": window.end,
                  "frames": len(window.frame_ids)},
        )

    def _current_window_or_open(self, tick: int) -> Window:
        integration = next(c for c in self.config.clocks
                           if c.id == self.config.recursion.clock)
        window_size = integration.window_size or 1
        # Ticks start at 1; window k covers ticks [1 + (k-1)*w, 1 + k*w).
        window_start = ((tick - 1) // window_size) * window_size + 1
        window_end = window_start + window_size
        if not self.active_windows or self.active_windows[-1].end <= tick:
            w = Window(id=f"window.source[{window_start},{window_end})",
                       domain_id="source", start=window_start, end=window_end,
                       frame_ids=())
            self.active_windows.append(w)
            self.event_log.record(
                kind="WindowOpened",
                clock_domain_id="source", clock_tick=tick,
                body={"window_id": w.id, "start": w.start, "end": w.end},
            )
        return self.active_windows[-1]

    def integrate_window(self) -> AeonOutput:
        # Take the last window, project each source's most-recent
        # emission into the substrate, integrate.
        if not self.active_windows:
            raise RuntimeFailure("NO_WINDOW",
                                 "integrate_window called with no open window")
        window = self.active_windows[-1]
        # Only integrate a *closed* window (all its ticks recorded).
        source_tick = self.clock_positions.get("source", 0)
        if source_tick < window.end - 1:
            raise RuntimeRejected(
                "WINDOW_NOT_CLOSED",
                f"integrate_window: window {window.id} still open at tick {source_tick}",
            )
        # For each source's projection into the recursion, build a
        # ManifoldInput from the source's *current* payload.
        manifold_inputs = []
        proj_targets = [
            p for p in self.config.projections
            if p.target_component == self.config.recursion.component_id
        ]
        for p_cfg in proj_targets:
            proj = self.projections[p_cfg.component_id]
            src_state = self.source_states[p_cfg.source_component]
            # Build a synthetic frame from the source's current payload.
            src_frame = new_signal_frame(
                source_id=p_cfg.source_component,
                sequence=source_tick,
                clock_position=ClockPosition("source", source_tick),
                payload=list(src_state.payload),
                originating_state_id=src_state.id,
            )
            manifold_inputs.append(proj.apply(src_frame))
            self.event_log.record(
                kind="ProjectionApplied",
                component_id=p_cfg.component_id,
                clock_domain_id="source", clock_tick=source_tick,
                body={"source": p_cfg.source_component,
                      "target": p_cfg.target_component},
            )
        integ_tick = self.clock_positions.get("integration", 0) + 1
        self.clock_positions["integration"] = integ_tick
        integ_position = ClockPosition("integration", integ_tick)
        result = self.recursion_impl.integrate(
            manifold_inputs, self.recursion_state, integ_position,
        )
        self.recursion_state = result.next_state
        cert = result.contraction_certificate
        tcert = result.transition_certificate
        self.event_log.record(
            kind="RecursionIntegrated",
            component_id=self.config.recursion.component_id,
            clock_domain_id="integration", clock_tick=integ_tick,
            state_ids=(result.next_state.id.digest,),
            body={"result": cert.result.value,
                  "certified_scope": cert.certified_scope.value,
                  "arithmetic_kind": cert.arithmetic_kind,
                  "measured_upper_bound": cert.measured_upper_bound,
                  "consumed_inputs": len(cert.consumed_inputs)},
        )
        self.event_log.record(
            kind="CertificateIssued",
            component_id=self.config.recursion.component_id,
            clock_domain_id="integration", clock_tick=integ_tick,
            body={"result": cert.result.value,
                  "certified_scope": cert.certified_scope.value},
        )
        self.event_log.record(
            kind="WindowClosed",
            clock_domain_id="source",
            clock_tick=source_tick,
            body={"window_id": window.id,
                  "frames": len(window.frame_ids)},
        )
        # Emit application output.
        # Validity per §17: VALID iff cert.result is PROVEN_CONTRACTIVE
        # and the next state is VALID; otherwise map from cert.result.
        validity = _validity_from_certificate(cert)
        contribs = tuple(
            {"source_id": c.source_id, "magnitude": c.magnitude,
             "frame_count": len(c.frame_ids)}
            for c in sorted(result.source_contributions, key=lambda x: x.source_id)
        )
        output = AeonOutput(
            output_id=make_identity("aeon_app.output", {
                "graph_id": self.graph_id,
                "next_state_id": result.next_state.id.digest,
                "integration_tick": integ_tick,
            }).digest,
            payload=tuple(float(x) for x in result.next_state.payload),
            originating_state_id=result.next_state.id.digest,
            application_graph_id=self.graph_id,
            clock_position=("integration", integ_tick),
            source_contributions=contribs,
            validity=validity,
            transition_certificate={
                "contract_id": tcert.contract_id,
                "contract_version": str(tcert.contract_version),
                "method": tcert.method,
                "result": tcert.result,
            },
            contraction_certificate={
                "metric": cert.metric.value,
                "requested_margin": cert.requested_margin,
                "measured_upper_bound": cert.measured_upper_bound,
                "certified_scope": cert.certified_scope.value,
                "arithmetic_kind": cert.arithmetic_kind,
                "certification_method": cert.certification_method.value,
                "result": cert.result.value,
                "consumed_inputs": list(cert.consumed_inputs),
                "clock_position": {"domain_id": cert.clock_position.domain_id,
                                    "tick": cert.clock_position.tick},
            },
            provenance={
                "application_graph_id": self.graph_id,
                "ir_module_id": self.ir_module_id,
                "language_version": AEON_LANGUAGE_REQUIRED_VERSION,
                "language_certified_commit": AEON_LANGUAGE_CERTIFIED_COMMIT,
                "config_digest": self.config.digest(),
                "runtime_mode": self.config.runtime_mode,
            },
        )
        self.outputs.append(output)
        self.event_log.record(
            kind="OutputEmitted",
            clock_domain_id="integration", clock_tick=integ_tick,
            state_ids=(output.originating_state_id,),
            body={"output_id": output.output_id,
                  "validity": output.validity.value},
        )
        # Apply feedback (may be neutral if all gates are 0).
        self._maybe_apply_feedback(integ_position)
        return output

    def _maybe_apply_feedback(self, integration_position: ClockPosition) -> None:
        for f_cfg in self.config.feedback:
            projection = self.projections[f_cfg.projection]
            dest_source_cfg = next(s for s in self.config.sources
                                   if s.component_id == f_cfg.destination)
            try:
                decision, signal = apply_feedback(
                    feedback_id=f_cfg.id,
                    recursion_state=self.recursion_state,
                    projection=projection,
                    destination_offered_capabilities=tuple(dest_source_cfg.offered_capabilities),
                    required_capability=f_cfg.required_capability,
                    gate=f_cfg.gate,
                    clock_relation=f_cfg.clock_relation or "integration_to_source",
                    scope=f_cfg.scope,
                    integration_clock_position=integration_position,
                )
            except FeedbackRefused as exc:
                self.event_log.record(
                    kind="RuntimeRejected",
                    component_id=f_cfg.id,
                    body={"reason": exc.code, "message": str(exc)},
                    result_status="REJECTED",
                )
                raise RuntimeRejected(exc.code, str(exc))
            self.event_log.record(
                kind="FeedbackApplied",
                component_id=f_cfg.id,
                clock_domain_id="integration",
                clock_tick=integration_position.tick,
                body={"applied": decision.applied,
                      "gate": decision.gate,
                      "reason": decision.reason},
            )
            if decision.applied and signal is not None:
                # Store as a bias to be added to the destination source's
                # next input frame. This is the runtime channel through
                # which feedback affects behavior; source-private state
                # is NOT mutated directly.
                self._feedback_biases[f_cfg.destination] = tuple(signal.payload)

    # -- snapshot / restore ---------------------------------------------

    def snapshot(self) -> ApplicationSnapshot:
        source_snaps = {}
        for s_cfg in self.config.sources:
            src = self.sources[s_cfg.component_id]
            snap = src.snapshot(self.source_states[s_cfg.component_id])
            source_snaps[s_cfg.component_id] = snap.canonical
        rec_snap = self.recursion_impl.snapshot(self.recursion_state)
        return ApplicationSnapshot(
            schema_version=APPLICATION_SNAPSHOT_SCHEMA_VERSION,
            application_version=APPLICATION_VERSION,
            language_version=AEON_LANGUAGE_REQUIRED_VERSION,
            language_certified_commit=AEON_LANGUAGE_CERTIFIED_COMMIT,
            ir_version="0.1.0",
            graph_id=self.graph_id,
            ir_module_id=self.ir_module_id,
            runtime_mode=self.config.runtime_mode,
            backend_id=self.config.backend.id,
            config_digest=self.config.digest(),
            source_snapshots=source_snaps,
            recursion_snapshot=rec_snap.canonical,
            scheduler_state=dict(self.scheduler_state),
            clock_positions=dict(self.clock_positions),
            active_windows=tuple({
                "id": w.id, "domain_id": w.domain_id,
                "start": w.start, "end": w.end,
                "frame_ids": list(w.frame_ids),
            } for w in self.active_windows),
            negotiation_result=None,   # captured elsewhere if needed
            active_contracts=(f"contract.contractive.{self.config.recursion.component_id}",),
            random_state=None,
            event_log_digest=self.event_log.digest(),
        )


def replace_window_frames(w: Window, frame_ids: Tuple[str, ...]) -> Window:
    return Window(id=w.id, domain_id=w.domain_id, start=w.start,
                  end=w.end, frame_ids=frame_ids)


def _validity_from_certificate(cert: ContractionCertificate) -> Validity:
    from aeon.contraction import ContractionResult
    if cert.result is ContractionResult.PROVEN_CONTRACTIVE:
        return Validity.VALID
    if cert.result is ContractionResult.BOUNDED_CONTRACTIVE:
        return Validity.PROVISIONALLY_VALID
    if cert.result is ContractionResult.NOT_PROVEN:
        return Validity.UNCERTIFIED
    if cert.result is ContractionResult.VIOLATED:
        return Validity.CONTRACT_VIOLATED
    return Validity.INVALID


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------


def new_session(config: ApplicationConfig) -> ApplicationSession:
    verify_language_lock()
    cfg = resolve(config)
    if cfg.runtime_mode == "CERTIFIED":
        # CERTIFIED default may not be enabled before Gate L-J; the
        # runtime rejects it at startup.
        raise RuntimeRejected(
            "CERTIFIED_NOT_YET_AUTHORIZED",
            "CERTIFIED runtime mode requires Gate L-J authorization "
            "(reports/AEON-GREENFIELD-BUILD-REPORT.md)",
        )

    graph = build_from_config(cfg)
    ir = compile_to_ir(cfg, graph)

    sources = {}
    source_states = {}
    for s_cfg in cfg.sources:
        cls = _resolve_source(s_cfg.implementation)
        # Attention source accepts an optional history parameter; we
        # keep the default for REFERENCE mode.
        if cls is AttentionSource:
            src = cls(source_id=s_cfg.component_id, dimension=s_cfg.dimension)
        else:
            src = cls(source_id=s_cfg.component_id, dimension=s_cfg.dimension)
        sources[s_cfg.component_id] = src
        source_states[s_cfg.component_id] = src.initialize(
            {"dimension": s_cfg.dimension}, s_cfg.seed,
        )

    contract = Contractive(
        metric=Metric.LINF,
        requested_margin=cfg.recursion.contraction_margin,
        numerical_tolerance=1e-12,
        precision_policy=PrecisionPolicy(cfg.recursion.numerical_precision),
        certification_method=CertificationMethod.EXACT_RATIONAL_ARITHMETIC,
    )
    substrate = ApplicationContractiveRecursion(
        dimension=cfg.recursion.dimension,
        contract=contract,
        substrate_id="aeon_app.recursion.substrate/0.1.0",
        decay=cfg.recursion.decay,
        declared_input_radius=cfg.recursion.declared_input_radius or 10.0,
        declared_state_radius=cfg.recursion.declared_state_radius or 10.0,
        declared_projection_scale_upper=cfg.recursion.declared_projection_scale_upper or 1.0,
    )
    recursion_state = substrate.initialize({"dimension": cfg.recursion.dimension}, 0)

    projections = {}
    for p_cfg in cfg.projections:
        cls = resolve_projection(p_cfg.implementation)
        projections[p_cfg.component_id] = cls(
            ProjectionParameters(scale=p_cfg.scale_upper_bound),
        )

    session = ApplicationSession(
        config=cfg,
        graph_id=graph.graph_id,
        ir_module_id=ir.module_id,
        sources=sources,
        source_states=source_states,
        recursion_impl=substrate,
        recursion_state=recursion_state,
        projections=projections,
        event_log=EventLog(tracing_enabled=cfg.observability.tracing_enabled),
    )
    session.event_log.record(
        kind="ApplicationInitialized",
        body={"graph_id": graph.graph_id, "ir_module_id": ir.module_id,
              "runtime_mode": cfg.runtime_mode,
              "config_digest": cfg.digest()},
    )
    return session


def run(session: ApplicationSession, ticks: Optional[int] = None) -> List[AeonOutput]:
    """Run the session for ``ticks`` source-clock ticks (default:
    config.inference.ticks). Integration happens whenever a window
    closes.
    """
    ticks = ticks if ticks is not None else session.config.inference.ticks
    integration = next(c for c in session.config.clocks
                       if c.id == session.config.recursion.clock)
    window_size = integration.window_size or 1
    start_tick = session.clock_positions.get("source", 0) + 1
    outputs_before = list(session.outputs)
    for tick in range(start_tick, start_tick + ticks):
        session.step_tick(tick)
        if tick % window_size == 0:
            session.integrate_window()
    # Return only the outputs produced during this call.
    return session.outputs[len(outputs_before):]


def restore(config: ApplicationConfig,
            snap: ApplicationSnapshot) -> ApplicationSession:
    verify_language_lock()
    verify_snapshot_version(snap)
    if snap.config_digest != resolve(config).digest():
        raise RuntimeRejected(
            "SNAPSHOT_CONFIG_MISMATCH",
            f"snapshot config_digest {snap.config_digest!r} does not match "
            f"provided config digest {resolve(config).digest()!r}",
        )
    session = new_session(config)
    # Restore source and recursion states.
    for s_cfg in session.config.sources:
        src = session.sources[s_cfg.component_id]
        from aeon.port import SourceSnapshot
        snap_bytes = snap.source_snapshots[s_cfg.component_id]
        source_snap = SourceSnapshot(
            id=make_identity("aeon_app.source_snapshot",
                             {"digest": canonical_digest(snap_bytes.hex())}),
            canonical=snap_bytes,
            origin_source_id=s_cfg.component_id, version="0.1.0",
        )
        session.source_states[s_cfg.component_id] = src.restore(source_snap)
    from aeon.recursion import RecursionSnapshot
    rec_snap = RecursionSnapshot(
        id=make_identity("aeon_app.recursion_snapshot",
                         {"digest": canonical_digest(snap.recursion_snapshot.hex())}),
        canonical=snap.recursion_snapshot,
        dimension=session.config.recursion.dimension,
        version="0.1.0",
    )
    session.recursion_state = session.recursion_impl.restore(rec_snap)
    session.clock_positions = dict(snap.clock_positions)
    session.event_log.record(
        kind="SnapshotRestored",
        body={"snapshot_digest": snap.digest()},
    )
    return session


__all__ = [
    "AeonOutput",
    "ApplicationSession",
    "RuntimeRejected",
    "RuntimeFailure",
    "new_session",
    "run",
    "restore",
]
