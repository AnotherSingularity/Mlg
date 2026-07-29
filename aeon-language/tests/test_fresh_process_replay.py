"""Fresh-process determinism (Phase 0.1 §12 + §2.4 Gate H).

Spawns a fresh Python subprocess for each of two runs, compares
their canonical byte outputs. This is stronger than same-process
replay because it defeats any hidden module-level state that would
otherwise cache across runs.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "two_sources.aeon"

RUN_SCRIPT = r'''
import json, sys
from compiler.parser import parse
from compiler.validator import validate
from runtime.scheduler import lower
from runtime.interpreter import Interpreter
from aeon.sources.dummy import DummyRichSource, DummyVectorSource
from aeon.contraction import Contractive, Metric, PrecisionPolicy, CertificationMethod
from aeon.recursion import ReferenceContractiveRecursion

with open(sys.argv[1]) as f:
    text = f.read()
m = parse(text, "e.aeon", module_id="e")
res = validate(m)
assert res.ok(), [d.code for d in res.errors()]
ir = lower(m, res.graph, seed=1, ticks_per_clock=4)

contract = Contractive(
    metric=Metric.LINF, requested_margin=0.9,
    numerical_tolerance=1e-12,
    precision_policy=PrecisionPolicy("float64"),
    certification_method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
)
sources = {}
for s in m.sources:
    if "MatrixRead" in s.offers or "DecayControl" in s.offers:
        sources[s.name] = DummyRichSource(s.name, 4)
    else:
        sources[s.name] = DummyVectorSource(s.name, 4)
substrates = {}
for r in m.recursions:
    substrates[r.name] = ReferenceContractiveRecursion(
        4, contract, r.name, 0.5,
        declared_input_radius=10.0,
        declared_state_radius=10.0,
        declared_projection_scale_upper=1.0,
    )

outcome = Interpreter(ir, sources=sources, substrates=substrates, seed=1).run()
summary = {
    "module_id": ir.module_id,
    "halt_reason": outcome.halt_reason,
    "outputs": [
        {"id": f.id.digest, "payload_digest": f.payload_digest()}
        for f in outcome.outputs
    ],
    "certificates": [
        {"result": c.result.value,
         "measured_upper_bound": c.measured_upper_bound,
         "consumed_inputs_sorted": list(c.consumed_inputs)}
        for c in outcome.contraction_certificates
    ],
    "trace_opcodes": [t.opcode for t in outcome.trace],
}
sys.stdout.write(json.dumps(summary, sort_keys=True))
'''


def _spawn(hashseed: str) -> str:
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = hashseed
    env["PYTHONPATH"] = f"{ROOT/'standard_library'}:{ROOT}"
    proc = subprocess.run(
        [sys.executable, "-c", RUN_SCRIPT, str(EXAMPLE)],
        env=env, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(f"subprocess failed: {proc.stderr}")
    return proc.stdout


def test_fresh_process_replay_hashseed_0_and_1():
    a = _spawn("0")
    b = _spawn("1")
    assert a == b, "fresh-process replay diverged across PYTHONHASHSEEDs"


def test_fresh_process_replay_hashseed_42_and_random():
    a = _spawn("42")
    b = _spawn("random")
    assert a == b, "fresh-process replay diverged (seed 42 vs random)"


def test_fresh_process_replay_across_all_seeds():
    seeds = ["0", "1", "42", "random"]
    outputs = [_spawn(s) for s in seeds]
    for i in range(1, len(outputs)):
        assert outputs[0] == outputs[i], f"seed {seeds[i]} diverged from seed {seeds[0]}"
