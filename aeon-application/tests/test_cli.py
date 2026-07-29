"""L12: CLI smoke tests.

Verifies that each of the eight `aeon-app-*` entry points parses
arguments, runs, and emits a JSON payload with the expected shape.
The CLI is exercised in-process (each entry point returns an int
exit code) rather than via a subprocess so a broken import fails
loudly at collection time.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from aeon_app import cli


def _run(fn, argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = fn(argv)
    out = buf.getvalue().strip()
    payload = json.loads(out) if out else {}
    return rc, payload


def test_app_check_reference_config_passes():
    rc, payload = _run(cli.app_check, [])
    assert rc == 0
    assert payload["ok"] is True
    assert payload["application_version"] == "0.1.0"
    assert payload["config_digest"]
    assert payload["semantic_digest"]


def test_app_compile_reports_ir_identity():
    rc, payload = _run(cli.app_compile, [])
    assert rc == 0
    assert payload["graph_id"]
    assert payload["ir_module_id"]
    assert payload["instruction_count"] > 0


def test_app_run_produces_outputs():
    rc, payload = _run(cli.app_run, ["--ticks", "2"])
    assert rc == 0
    assert payload["ticks_executed"] >= 1
    assert payload["outputs"]
    for o in payload["outputs"]:
        assert "output_id" in o
        assert "payload" in o
        assert "clock_position" in o


def test_app_train_produces_certificates():
    rc, payload = _run(cli.app_train, ["--steps", "2", "--ticks", "4"])
    assert rc == 0
    assert payload["steps"] == 2
    assert len(payload["certificates"]) == 2
    for c in payload["certificates"]:
        for k in ("batch_digest", "loss_digest", "gradient_digest",
                  "updated_parameter_digest",
                  "certificate_recheck_required"):
            assert k in c


def test_app_evaluate_list_prints_profiles():
    rc, payload = _run(cli.app_evaluate, ["--list"])
    assert rc == 0
    assert "CONFIG" in payload["profiles"]
    assert "TRAINING" in payload["profiles"]
    assert payload["manifest"]["schema_version"] == "0.1.0"


def test_app_snapshot_and_replay_round_trip(tmp_path: Path):
    snap = tmp_path / "session.snap"
    rc, payload = _run(cli.app_snapshot,
                       ["--out", str(snap), "--ticks", "2"])
    assert rc == 0
    assert snap.exists()
    rc2, payload2 = _run(cli.app_replay,
                         ["--snapshot", str(snap), "--ticks", "2"])
    assert rc2 == 0
    assert payload2["snapshot_digest"] == payload["snapshot_digest"]
    assert payload2["graph_id"] == payload["graph_id"]
    # After closing the next window (window_size=2), replay yields
    # exactly one additional output.
    assert payload2["additional_ticks"] == 1


def test_app_inspect_dumps_identity():
    rc, payload = _run(cli.app_inspect, [])
    assert rc == 0
    assert payload["application_version"] == "0.1.0"
    assert payload["graph_id"]
    assert "recursion" in payload
    assert isinstance(payload["sources"], list)
