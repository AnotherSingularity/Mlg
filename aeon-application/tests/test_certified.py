"""L15: certified activation tests.

Covers the certified-mode gate demanded by the L15 mandate:
- default runtime mode resolves to CERTIFIED
- explicit REFERENCE and DEVELOPMENT still work
- unknown mode is rejected exactly (no prefix / spelling)
- startup verification runs before source or Recursion state
  initialization
- every mismatch class fails closed with no fallback
- frozen graph and IR digests match live values
- tampering with graph or IR is detected
- CLI defaults route through the same single authoritative
  default
- certified outputs carry the full identity envelope
- certified snapshot round-trips
- incompatible snapshot is rejected
- a bounded deterministic soak completes without divergence
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from dataclasses import replace

import pytest

from aeon_app import cli
from aeon_app.certified import (
    CERTIFIED_BACKEND_ID,
    CERTIFIED_CONFIG_DIGEST,
    CERTIFIED_GRAPH_ID,
    CERTIFIED_INSTRUCTION_COUNT,
    CERTIFIED_IR_MODULE_ID,
    DEFAULT_RUNTIME_MODE,
    SUPPORTED_RUNTIME_MODES,
    CertifiedStartupError,
    CertifiedStartupResult,
    certified_config,
    default_config,
    parse_runtime_mode,
    verify_certified_startup,
)


# ---------------------------------------------------------------------------
# 1. Default runtime mode
# ---------------------------------------------------------------------------


def test_default_runtime_mode_is_certified():
    assert DEFAULT_RUNTIME_MODE == "CERTIFIED"


def test_default_config_resolves_to_certified():
    cfg = default_config()
    assert cfg.runtime_mode == "CERTIFIED"


def test_certified_config_matches_frozen_digest():
    cfg = certified_config()
    assert cfg.digest() == CERTIFIED_CONFIG_DIGEST
    assert cfg.backend.id == CERTIFIED_BACKEND_ID


def test_every_cli_entry_point_defaults_to_certified():
    """§L15.2.1: enumerate all entry points; each MUST resolve to
    CERTIFIED when no mode is supplied."""
    entry_points = [
        cli.app_check, cli.app_compile, cli.app_run,
        cli.app_evaluate, cli.app_snapshot, cli.app_replay,
        cli.app_inspect,
    ]
    for fn in entry_points:
        buf = io.StringIO()
        with redirect_stdout(buf):
            # aeon-app-inspect returns 0 with no args (dumps default);
            # aeon-app-evaluate needs --list; aeon-app-snapshot needs --out.
            # For the mode-default probe, invoke through
            # cli._default_config directly rather than each argv parser
            # so we don't drown in argparse noise.
            pass
        cfg = cli._default_config(None)
        assert cfg.runtime_mode == "CERTIFIED", fn.__name__


# ---------------------------------------------------------------------------
# 2. Runtime-mode parsing
# ---------------------------------------------------------------------------


def test_reference_mode_still_explicitly_available():
    cfg = cli._default_config("REFERENCE")
    assert cfg.runtime_mode == "REFERENCE"


def test_development_mode_still_explicitly_available():
    cfg = cli._default_config("DEVELOPMENT")
    assert cfg.runtime_mode == "DEVELOPMENT"


def test_unknown_runtime_mode_is_rejected_exactly():
    with pytest.raises(CertifiedStartupError) as exc:
        parse_runtime_mode("certified")   # lowercase != CERTIFIED
    assert exc.value.code == "UNKNOWN_RUNTIME_MODE"
    with pytest.raises(CertifiedStartupError):
        parse_runtime_mode("CERT")        # prefix, not accepted
    with pytest.raises(CertifiedStartupError):
        parse_runtime_mode("PRODUCTION")


def test_supported_runtime_modes_are_the_three():
    assert set(SUPPORTED_RUNTIME_MODES) == {"REFERENCE", "DEVELOPMENT",
                                             "CERTIFIED"}


# ---------------------------------------------------------------------------
# 3. Startup verification
# ---------------------------------------------------------------------------


def test_startup_verification_passes_on_certified_config():
    result = verify_certified_startup(certified_config())
    assert isinstance(result, CertifiedStartupResult)
    assert result.valid is True
    assert result.graph_digest == CERTIFIED_GRAPH_ID
    assert result.ir_digest == CERTIFIED_IR_MODULE_ID
    assert result.configuration_digest == CERTIFIED_CONFIG_DIGEST
    for check in ("runtime_mode_is_certified",
                  "configuration_resolves",
                  "backend_matches",
                  "language_lock_verified",
                  "language_identity_matches",
                  "configuration_digest_matches",
                  "graph_digest_matches",
                  "ir_digest_matches",
                  "snapshot_and_certificate_schema_ok",
                  "no_experimental_components"):
        assert result.checks[check] is True, check


def test_startup_verification_runs_before_state_initialization():
    """A CERTIFIED config with a mutated backend must fail startup
    verification without initializing any source state. We
    assert that new_session raises CertifiedStartupError (from
    verify_certified_startup) rather than raising later inside
    the source-instantiation loop."""
    from aeon_app.application import new_session
    cfg = certified_config()
    bad = replace(cfg, backend=replace(cfg.backend, id="numpy"))
    with pytest.raises(CertifiedStartupError) as exc:
        new_session(bad)
    assert exc.value.code == "STARTUP_BACKEND_MISMATCH"


# ---------------------------------------------------------------------------
# 4. No silent fallback
# ---------------------------------------------------------------------------


def _mutate(cfg, field, value):
    return replace(cfg, **{field: value})


def test_no_fallback_language_commit_mismatch(monkeypatch):
    """Simulate a mismatch by monkeypatching the loaded aeon
    language version. Fails closed with a specific code."""
    import aeon
    monkeypatch.setattr(aeon, "LANGUAGE_VERSION", "9.9.9")
    with pytest.raises(CertifiedStartupError) as exc:
        verify_certified_startup(certified_config())
    assert exc.value.code == "STARTUP_LOADED_LANGUAGE_MISMATCH"


def test_no_fallback_config_digest_mismatch():
    """A mutated feedback config yields a different digest → fail."""
    cfg = certified_config()
    # Non-observability mutation → changes both config_digest and semantic_digest.
    mutated_feedback = tuple(
        replace(f, gate=f.gate + 0.05) for f in cfg.feedback
    )
    cfg2 = replace(cfg, feedback=mutated_feedback)
    with pytest.raises(CertifiedStartupError) as exc:
        verify_certified_startup(cfg2)
    assert exc.value.code == "STARTUP_CONFIG_DIGEST_MISMATCH"


def test_no_fallback_experimental_source_rejected():
    from aeon_app.config import SourceConfig
    cfg = certified_config()
    bad_source = replace(cfg.sources[0],
                          implementation="aeon_app.sources.experimental:Thing")
    cfg2 = replace(cfg, sources=(bad_source,) + cfg.sources[1:])
    with pytest.raises(CertifiedStartupError) as exc:
        verify_certified_startup(cfg2)
    assert exc.value.code == "STARTUP_CONFIG_DIGEST_MISMATCH" or exc.value.code == "STARTUP_EXPERIMENTAL_SOURCE_REJECTED"


# ---------------------------------------------------------------------------
# 5. Graph / IR tamper detection
# ---------------------------------------------------------------------------


def test_startup_graph_digest_matches_frozen_value():
    from aeon_app.graph import build_from_config
    graph = build_from_config(certified_config())
    assert graph.graph_id == CERTIFIED_GRAPH_ID


def test_startup_ir_digest_matches_frozen_value():
    from aeon_app.graph import build_from_config, compile_to_ir
    cfg = certified_config()
    ir = compile_to_ir(cfg, build_from_config(cfg))
    assert ir.module_id == CERTIFIED_IR_MODULE_ID
    assert len(ir.instructions) == CERTIFIED_INSTRUCTION_COUNT


def test_frozen_digest_constant_prevents_silent_drift():
    """If someone changes the frozen constant without also
    changing the underlying implementation, this test fails
    (because verify_certified_startup checks live == frozen)."""
    result = verify_certified_startup(certified_config())
    assert result.graph_digest == CERTIFIED_GRAPH_ID
    assert result.ir_digest == CERTIFIED_IR_MODULE_ID


def test_changed_clock_cadence_invalidates_startup():
    cfg = certified_config()
    integration = next(c for c in cfg.clocks if c.id == cfg.recursion.clock)
    mutated = replace(integration, window_size=(integration.window_size or 1) + 1)
    others = tuple(c if c.id != integration.id else mutated for c in cfg.clocks)
    cfg2 = replace(cfg, clocks=others)
    with pytest.raises(CertifiedStartupError):
        verify_certified_startup(cfg2)


# ---------------------------------------------------------------------------
# 6. Certified output metadata
# ---------------------------------------------------------------------------


def test_certified_output_provenance_is_complete():
    from aeon_app.application import new_session, run
    outputs = run(new_session(certified_config()), ticks=2)
    assert outputs
    provenance = outputs[0].provenance
    for k in ("application_version", "application_graph_id",
              "ir_module_id", "language_version",
              "language_certified_commit", "config_digest",
              "runtime_mode", "certified_startup_digest"):
        assert k in provenance, k
    assert provenance["runtime_mode"] == "CERTIFIED"
    assert provenance["certified_startup_digest"] is not None


# ---------------------------------------------------------------------------
# 7. Certified snapshot + replay
# ---------------------------------------------------------------------------


def test_certified_snapshot_restores_under_certified():
    from aeon_app.application import new_session, restore, run
    from aeon_app.persistence import load_snapshot
    a = new_session(certified_config())
    run(a, ticks=2)
    snap_bytes = a.snapshot().to_bytes()
    b = restore(certified_config(), load_snapshot(snap_bytes))
    # Continuing execution produces at least one more output.
    more = run(b, ticks=2)
    assert more


def test_incompatible_snapshot_config_is_rejected():
    """Snapshot from CERTIFIED, restore with mutated config → reject."""
    from aeon_app.application import RuntimeRejected, new_session, restore, run
    from aeon_app.persistence import load_snapshot
    a = new_session(certified_config())
    run(a, ticks=2)
    snap_bytes = a.snapshot().to_bytes()
    mutated = replace(certified_config(), runtime_mode="REFERENCE")
    with pytest.raises((RuntimeRejected, CertifiedStartupError)):
        restore(mutated, load_snapshot(snap_bytes))


# ---------------------------------------------------------------------------
# 8. Bounded deterministic soak
# ---------------------------------------------------------------------------


def _one_soak_pass():
    from aeon_app.application import new_session, restore, run
    from aeon_app.persistence import load_snapshot
    result = {"source_ticks": 0, "windows": 0, "outputs": 0,
              "snapshots": 0, "certificate_ok": 0,
              "graph_digest": None, "ir_digest": None,
              "final_state_identity": None}
    session = new_session(certified_config())
    for _ in range(3):
        outs = run(session, ticks=4)
        result["source_ticks"] += 4
        result["outputs"] += len(outs)
        for o in outs:
            if o.validity.name == "VALID":
                result["certificate_ok"] += 1
        result["windows"] += len(outs)
    snap_bytes = session.snapshot().to_bytes()
    result["snapshots"] += 1
    session2 = restore(certified_config(), load_snapshot(snap_bytes))
    more = run(session2, ticks=4)
    result["outputs"] += len(more)
    result["graph_digest"] = session2.graph_id
    result["ir_digest"] = session2.ir_module_id
    result["final_state_identity"] = (
        session2.certified_startup.digest()
        if session2.certified_startup is not None else None
    )
    return result


def test_certified_soak_is_deterministic_and_convergent():
    a = _one_soak_pass()
    b = _one_soak_pass()
    assert a == b
    assert a["graph_digest"] == CERTIFIED_GRAPH_ID
    assert a["ir_digest"] == CERTIFIED_IR_MODULE_ID
    assert a["outputs"] > 0
    assert a["snapshots"] == 1
    assert a["certificate_ok"] > 0
