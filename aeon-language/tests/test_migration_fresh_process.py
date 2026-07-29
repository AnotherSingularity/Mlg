"""Migration byte-identity across PYTHONHASHSEED (mandate §2.5)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "conformance" / "fixtures" / "migration" / "v0_0"


RUN_SCRIPT = r'''
import json, sys
from aeon.migration import ArtifactKind
from aeon.migration_registry import DEFAULT_REGISTRY, V0_1

kind = ArtifactKind(sys.argv[1])
with open(sys.argv[2]) as f:
    artifact = json.load(f)
result = DEFAULT_REGISTRY.migrate(kind, artifact, V0_1)
sys.stdout.buffer.write(result.canonical_bytes or b"")
'''


def _spawn(hashseed: str, kind: str, fixture_name: str) -> bytes:
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = hashseed
    env["PYTHONPATH"] = f"{ROOT/'standard_library'}:{ROOT}"
    proc = subprocess.run(
        [sys.executable, "-c", RUN_SCRIPT, kind, str(FIXTURE / f"{fixture_name}.json")],
        env=env, capture_output=True,
    )
    assert proc.returncode == 0, proc.stderr.decode()
    return proc.stdout


@pytest.mark.parametrize("kind,name", [
    ("semantic_graph", "graph"),
    ("canonical_ir", "ir"),
    ("snapshot", "snapshot"),
    ("certificate", "certificate"),
])
def test_migration_byte_identical_across_hashseeds(kind: str, name: str):
    seeds = ["0", "1", "42", "random"]
    outputs = [_spawn(s, kind, name) for s in seeds]
    for i in range(1, len(outputs)):
        assert outputs[0] == outputs[i], (
            f"{kind}/{name}: seed {seeds[i]} produced different canonical bytes"
        )
