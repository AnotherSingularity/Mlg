"""Configuration schemas + language lock verification."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aeon_app import (
    AEON_LANGUAGE_CERTIFIED_COMMIT,
    AEON_LANGUAGE_REQUIRED_VERSION,
    APPLICATION_CONFIG_SCHEMA_VERSION,
    APPLICATION_VERSION,
)
from aeon_app.config import (
    ApplicationConfig,
    ConfigError,
    LanguageLockError,
    LanguageLockRecord,
    load_lock,
    reference_config,
    resolve,
    verify_language_lock,
)
from aeon_app.config.schemas import (
    BackendConfig,
    ClockConfig,
    FeedbackConfig,
    ProjectionConfig,
    RecursionConfig,
    SourceConfig,
)


# ---------------------------------------------------------------------------
# Reference config resolves
# ---------------------------------------------------------------------------


def test_reference_config_resolves_cleanly():
    cfg = resolve(reference_config())
    assert cfg.runtime_mode == "REFERENCE"
    assert cfg.application_version == APPLICATION_VERSION
    assert cfg.schema_version == APPLICATION_CONFIG_SCHEMA_VERSION
    assert len(cfg.sources) == 2
    assert cfg.recursion.contraction_margin == 0.9


def test_reference_config_digest_is_deterministic():
    a = reference_config().digest()
    b = reference_config().digest()
    assert a == b


def test_reference_config_digest_changes_with_seed():
    from dataclasses import replace
    base = reference_config()
    a = base
    b = replace(base, sources=tuple(
        replace(s, seed=s.seed + 100) for s in base.sources
    ))
    assert a.digest() != b.digest()


# ---------------------------------------------------------------------------
# Negative validations (fail-closed)
# ---------------------------------------------------------------------------


def test_unknown_runtime_mode_rejected():
    from dataclasses import replace
    bad = replace(reference_config(), runtime_mode="MAGIC")
    with pytest.raises(ConfigError) as exc:
        resolve(bad)
    assert exc.value.code == "UNKNOWN_RUNTIME_MODE"


def test_unsupported_backend_rejected():
    from dataclasses import replace
    base = reference_config()
    bad = replace(base, backend=replace(base.backend, id="cuda"))
    with pytest.raises(ConfigError) as exc:
        resolve(bad)
    assert exc.value.code == "UNSUPPORTED_BACKEND"


def test_missing_required_capability_rejected():
    from dataclasses import replace
    base = reference_config()
    weak_source = replace(base.sources[0],
                          offered_capabilities=("VectorRead",))
    bad = replace(base, sources=(weak_source,) + base.sources[1:])
    with pytest.raises(ConfigError) as exc:
        resolve(bad)
    assert exc.value.code == "MISSING_REQUIRED_CAPABILITY"


def test_invalid_contraction_margin_rejected():
    from dataclasses import replace
    base = reference_config()
    bad = replace(base, recursion=replace(base.recursion, contraction_margin=1.5))
    with pytest.raises(ConfigError) as exc:
        resolve(bad)
    assert exc.value.code == "INVALID_CONTRACTION_MARGIN"


def test_duplicate_component_id_rejected():
    from dataclasses import replace
    base = reference_config()
    dup = replace(base.sources[0], component_id="recurrent")  # collides with second source
    bad = replace(base, sources=(dup, base.sources[1]))
    with pytest.raises(ConfigError) as exc:
        resolve(bad)
    assert exc.value.code == "DUPLICATE_COMPONENT_ID"


def test_undeclared_clock_crossing_rejected():
    from dataclasses import replace
    base = reference_config()
    # Break the aggregates_from link: integration no longer aggregates from source.
    broken_clocks = (
        base.clocks[0],
        replace(base.clocks[1], aggregates_from=None, window_size=None),
    )
    bad = replace(base, clocks=broken_clocks)
    with pytest.raises(ConfigError) as exc:
        resolve(bad)
    assert exc.value.code == "UNDECLARED_CLOCK_CROSSING"


def test_feedback_capability_required_when_gate_nonzero():
    from dataclasses import replace
    base = reference_config()
    activated = tuple(
        replace(f, gate=0.5, required_capability=None) for f in base.feedback
    )
    bad = replace(base, feedback=activated)
    with pytest.raises(ConfigError) as exc:
        resolve(bad)
    assert exc.value.code == "FEEDBACK_CAPABILITY_MISSING"


def test_invalid_projection_scale_rejected():
    from dataclasses import replace
    base = reference_config()
    bad_proj = replace(base.projections[0], scale_upper_bound=2.0)
    bad = replace(base, projections=(bad_proj,) + base.projections[1:])
    with pytest.raises(ConfigError) as exc:
        resolve(bad)
    assert exc.value.code == "INVALID_PROJECTION_SCALE"


# ---------------------------------------------------------------------------
# Language lock
# ---------------------------------------------------------------------------


def test_language_lock_loads_and_verifies():
    lock = load_lock()
    assert lock.language_version == AEON_LANGUAGE_REQUIRED_VERSION
    assert lock.certified_commit == AEON_LANGUAGE_CERTIFIED_COMMIT
    assert verify_language_lock(lock) is lock


def test_language_lock_missing_file_rejected(tmp_path: Path):
    with pytest.raises(LanguageLockError) as exc:
        load_lock(tmp_path / "nope.json")
    assert exc.value.code == "LOCK_MISSING"


def test_language_lock_mismatch_rejected(tmp_path: Path):
    original = load_lock()
    # Write a lock with a wrong certified commit.
    p = tmp_path / "bad.json"
    payload = {
        "language_version": original.language_version,
        "certified_commit": "0" * 40,  # not the certified SHA
        "ir_version": original.ir_version,
        "instruction_set_version": original.instruction_set_version,
        "stdlib_version": original.stdlib_version,
        "source_grammar_version": original.source_grammar_version,
        "certificate_schema": original.certificate_schema,
        "snapshot_schema": original.snapshot_schema,
        "conformance_profile": original.conformance_profile,
        "backend_contract": original.backend_contract,
        "migration_framework": original.migration_framework,
        "certified_ci_run": original.certified_ci_run,
        "lock_generator": original.lock_generator,
    }
    p.write_text(json.dumps(payload), encoding="utf-8")
    bad = load_lock(p)
    with pytest.raises(LanguageLockError) as exc:
        verify_language_lock(bad)
    assert exc.value.code == "APPLICATION_PIN_MISMATCH"


def test_language_lock_field_missing_rejected(tmp_path: Path):
    p = tmp_path / "partial.json"
    p.write_text(json.dumps({"language_version": "0.1.0"}), encoding="utf-8")
    with pytest.raises(LanguageLockError) as exc:
        load_lock(p)
    assert exc.value.code == "LOCK_FIELD_MISSING"
