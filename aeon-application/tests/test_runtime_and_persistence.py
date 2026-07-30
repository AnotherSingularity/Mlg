"""L6+L7+L8+L9: scheduler, feedback, runtime, snapshot/replay."""

from __future__ import annotations

from dataclasses import replace

import pytest

from aeon.contraction import ContractionResult
from aeon.core import Validity

from aeon_app.application import (
    ApplicationSession,
    RuntimeRejected,
    new_session,
    restore,
    run,
)
from aeon_app.config import reference_config, resolve
from aeon_app.observability import EventLog
from aeon_app.persistence import (
    APPLICATION_SNAPSHOT_KIND,
    ApplicationSnapshot,
    SnapshotError,
    load_snapshot,
    verify_snapshot_version,
)


def _session():
    return new_session(reference_config())


# ---------------------------------------------------------------------------
# Runtime and event log
# ---------------------------------------------------------------------------


def test_run_reference_produces_outputs_and_events():
    session = _session()
    outputs = run(session, ticks=4)
    # window_size = 2 → 2 outputs.
    assert len(outputs) == 2
    for out in outputs:
        assert out.validity is Validity.VALID
        assert out.contraction_certificate["result"] == "PROVEN_CONTRACTIVE"
        assert out.contraction_certificate["certified_scope"] == "PROJECTED_RECURSION"
        assert out.provenance["language_certified_commit"] == \
            "b5e27a9bbc836897d9ac20d92c7d2fb786335f8f"
    kinds = [e.kind for e in session.event_log.events()]
    for k in ("ApplicationInitialized", "SourceStepped",
              "WindowOpened", "RecursionIntegrated",
              "CertificateIssued", "OutputEmitted", "FeedbackApplied"):
        assert k in kinds


def test_run_is_deterministic():
    a = run(_session(), ticks=4)
    b = run(_session(), ticks=4)
    assert [o.output_id for o in a] == [o.output_id for o in b]
    assert [o.payload for o in a] == [o.payload for o in b]


def test_certified_mode_startup_succeeds_on_frozen_config():
    """L15 activated CERTIFIED as the default runtime. The frozen
    certified config must construct a session cleanly; the session
    exposes a valid CertifiedStartupResult."""
    from aeon_app.certified import certified_config
    session = new_session(certified_config())
    assert session.certified_startup is not None
    assert session.certified_startup.valid is True
    assert session.certified_startup.checks["graph_digest_matches"] is True
    assert session.certified_startup.checks["ir_digest_matches"] is True


def test_unknown_source_implementation_rejected_at_new_session():
    from dataclasses import replace
    base = reference_config()
    bad = replace(base, sources=(replace(base.sources[0],
                                         implementation="aeon_app.sources.nope:Nope"),) + base.sources[1:])
    # New session goes through resolve+build, which raises inside graph
    # build; here we assert the top-level RuntimeRejected or a
    # graph-build error surfaces at session construction.
    with pytest.raises(Exception) as exc:
        new_session(bad)
    # The error may come from graph or from source resolution.
    assert exc.type.__name__ in {"RuntimeRejected", "GraphBuildError"}


# ---------------------------------------------------------------------------
# Feedback zero-gate neutrality (mandate §12)
# ---------------------------------------------------------------------------


def test_zero_gate_feedback_is_neutral():
    # Baseline session runs with gate=0 by default. Change gate → check
    # that outputs match a session with feedback config removed entirely.
    baseline = run(_session(), ticks=4)
    from dataclasses import replace
    no_feedback = replace(reference_config(), feedback=())
    other = run(new_session(no_feedback), ticks=4)
    # The two runs may differ because "no feedback" also removes the
    # feedback config entries themselves; the semantic-neutrality
    # guarantee is that a zero-gate feedback does not affect source
    # state or recursion output. So we compare state trajectories via
    # the output payload sequence.
    assert [o.payload for o in baseline] == [o.payload for o in other]


def test_nonzero_gate_requires_capability_negotiation():
    """A nonzero feedback gate whose required_capability the destination
    does not offer must be rejected at execution time (fail-closed)."""
    from dataclasses import replace
    base = reference_config()
    active_feedback = tuple(
        replace(f, gate=0.5, required_capability="MadeUpCapability")
        for f in base.feedback
    )
    cfg = replace(base, feedback=active_feedback)
    session = new_session(cfg)
    with pytest.raises(RuntimeRejected) as exc:
        run(session, ticks=2)
    assert exc.value.code in {"CAPABILITY_NOT_OFFERED", "MISSING_REQUIRED_CAPABILITY"}


def test_nonzero_gate_with_negotiated_capability_alters_outputs():
    """A nonzero gate with a valid capability changes the source
    trajectory (bounded change; still deterministic)."""
    from dataclasses import replace
    baseline_outputs = run(_session(), ticks=4)
    base = reference_config()
    active = tuple(replace(f, gate=0.25) for f in base.feedback)
    session = new_session(replace(base, feedback=active))
    outputs = run(session, ticks=4)
    # Non-neutral: at least one payload differs.
    assert [o.payload for o in outputs] != [o.payload for o in baseline_outputs]
    # Still deterministic across two runs.
    other = run(new_session(replace(base, feedback=active)), ticks=4)
    assert [o.payload for o in outputs] == [o.payload for o in other]


# ---------------------------------------------------------------------------
# Snapshot / restore / replay
# ---------------------------------------------------------------------------


def test_snapshot_contains_every_required_field():
    session = _session()
    run(session, ticks=4)
    snap = session.snapshot()
    assert snap.application_version == "0.1.0"
    assert snap.language_version == "0.1.0"
    assert snap.language_certified_commit == "b5e27a9bbc836897d9ac20d92c7d2fb786335f8f"
    assert snap.graph_id and snap.ir_module_id
    assert snap.runtime_mode == "REFERENCE"
    assert snap.backend_id == "python"
    assert snap.config_digest == session.config.digest()
    assert set(snap.source_snapshots) == {"attention", "recurrent"}
    assert snap.recursion_snapshot
    assert snap.clock_positions.get("source") == 4
    assert snap.clock_positions.get("integration") == 2
    assert snap.event_log_digest


def test_snapshot_round_trip_reproduces_next_transition():
    session = _session()
    run(session, ticks=4)
    snap = session.snapshot()
    # Serialize + deserialize.
    raw = snap.to_bytes()
    parsed = load_snapshot(raw)
    verify_snapshot_version(parsed)
    # Restore and run one more tick + integration.
    restored = restore(reference_config(), parsed)
    baseline = new_session(reference_config())
    run(baseline, ticks=6)   # 4 ticks + 2 more
    # Restore and step 2 more ticks; then integrate.
    from aeon_app.application import run as run_more
    more = run_more(restored, ticks=2)
    assert baseline.outputs[-1].payload == more[-1].payload


def test_snapshot_schema_mismatch_rejected(tmp_path):
    session = _session()
    run(session, ticks=4)
    snap = session.snapshot()
    raw = snap.to_bytes()
    import json
    obj = json.loads(raw.decode("utf-8"))
    obj["schema_version"] = "9.9.9"
    with pytest.raises(SnapshotError) as exc:
        verify_snapshot_version(load_snapshot(json.dumps(obj).encode("utf-8")))
    assert exc.value.code == "SNAPSHOT_SCHEMA_MISMATCH"


def test_snapshot_corrupt_bytes_rejected():
    with pytest.raises(SnapshotError) as exc:
        load_snapshot(b"not-json")
    assert exc.value.code == "SNAPSHOT_CORRUPT"


def test_snapshot_config_mismatch_rejected():
    """Restoring a snapshot with a different config must fail closed."""
    session = _session()
    run(session, ticks=4)
    snap = session.snapshot()
    from dataclasses import replace
    other = replace(reference_config(), graph_name="different-name")
    with pytest.raises(RuntimeRejected) as exc:
        restore(other, snap)
    assert exc.value.code == "SNAPSHOT_CONFIG_MISMATCH"


# ---------------------------------------------------------------------------
# Observability neutrality (mandate §20)
# ---------------------------------------------------------------------------


def test_tracing_off_produces_same_outputs():
    from dataclasses import replace
    base = reference_config()
    off_cfg = replace(base, observability=replace(base.observability, tracing_enabled=False))
    on_outputs = run(_session(), ticks=4)
    off_outputs = run(new_session(off_cfg), ticks=4)
    assert [o.payload for o in on_outputs] == [o.payload for o in off_outputs]
    assert [o.output_id for o in on_outputs] == [o.output_id for o in off_outputs]
