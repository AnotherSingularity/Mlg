"""aeon_app.evaluation — structured evaluation profiles."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from aeon.serialization import canonical_value, digest

from .. import APPLICATION_VERSION


EVALUATION_SCHEMA_VERSION = "0.1.0"


CATEGORIES = (
    "language_conformance",
    "source_conformance",
    "runtime_determinism",
    "causal_correctness",
    "snapshot_fidelity",
    "replay_fidelity",
    "contraction_status",
    "boundedness",
    "numerical_stability",
    "training_reproducibility",
    "inference_consistency",
    "feedback_neutrality",
    "feedback_boundedness",
    "performance",
    "resource_use",
)


@dataclass(frozen=True)
class Profile:
    name: str
    description: str
    fixtures: Tuple[str, ...]
    category: str

    def to_canonical(self) -> dict:
        return canonical_value({
            "name": self.name,
            "description": self.description,
            "fixtures": list(self.fixtures),
            "category": self.category,
        })


PROFILES: Tuple[Profile, ...] = (
    Profile(
        name="CONFIG",
        description="Configuration schemas + language lock",
        fixtures=("tests/test_config_and_lock.py",),
        category="language_conformance",
    ),
    Profile(
        name="SOURCE",
        description="AttentionSource + PersistentRecurrentSource port conformance",
        fixtures=(
            "tests/test_sources_projections_recursion.py::test_attention_source_offers_required_and_attention_map",
            "tests/test_sources_projections_recursion.py::test_attention_source_step_deterministic",
            "tests/test_sources_projections_recursion.py::test_attention_source_reads_and_unavailable",
            "tests/test_sources_projections_recursion.py::test_attention_source_snapshot_restore_round_trip",
            "tests/test_sources_projections_recursion.py::test_attention_source_input_dim_mismatch_raises",
            "tests/test_sources_projections_recursion.py::test_recurrent_source_offers_required_plus_matrix_and_decay",
            "tests/test_sources_projections_recursion.py::test_recurrent_source_step_deterministic_and_bounded",
            "tests/test_sources_projections_recursion.py::test_recurrent_source_snapshot_restore_reproduces_next",
            "tests/test_sources_projections_recursion.py::test_recurrent_matrix_read_and_dimension_read",
            "tests/test_sources_projections_recursion.py::test_recurrent_source_capability_negotiation_passes_required",
        ),
        category="source_conformance",
    ),
    Profile(
        name="PROJECTION",
        description="Typed projections + bound enforcement",
        fixtures=(
            "tests/test_sources_projections_recursion.py::test_all_four_projections_registered",
            "tests/test_sources_projections_recursion.py::test_projection_apply_scales_within_bound",
            "tests/test_sources_projections_recursion.py::test_projection_scale_bound_enforced",
            "tests/test_sources_projections_recursion.py::test_projection_input_dim_mismatch_raises",
            "tests/test_sources_projections_recursion.py::test_projection_descriptor_is_stable_json",
        ),
        category="boundedness",
    ),
    Profile(
        name="RECURSION",
        description="Application contractive substrate + certificate scope",
        fixtures=(
            "tests/test_sources_projections_recursion.py::test_recursion_substrate_produces_proven_projected_scope",
            "tests/test_sources_projections_recursion.py::test_recursion_substrate_deterministic",
            "tests/test_sources_projections_recursion.py::test_recursion_source_disagreement_not_hidden",
        ),
        category="contraction_status",
    ),
    Profile(
        name="SCHEDULER",
        description="Multi-clock scheduler + window closure + event log",
        fixtures=(
            "tests/test_runtime_and_persistence.py::test_run_reference_produces_outputs_and_events",
            "tests/test_runtime_and_persistence.py::test_run_is_deterministic",
        ),
        category="runtime_determinism",
    ),
    Profile(
        name="FEEDBACK",
        description="Zero-gate neutrality + capability negotiation + bounded activation",
        fixtures=(
            "tests/test_runtime_and_persistence.py::test_zero_gate_feedback_is_neutral",
            "tests/test_runtime_and_persistence.py::test_nonzero_gate_requires_capability_negotiation",
            "tests/test_runtime_and_persistence.py::test_nonzero_gate_with_negotiated_capability_alters_outputs",
        ),
        category="feedback_neutrality",
    ),
    Profile(
        name="PERSISTENCE",
        description="Snapshot envelope + restore + config validation",
        fixtures=(
            "tests/test_runtime_and_persistence.py::test_snapshot_contains_every_required_field",
            "tests/test_runtime_and_persistence.py::test_snapshot_round_trip_reproduces_next_transition",
            "tests/test_runtime_and_persistence.py::test_snapshot_schema_mismatch_rejected",
            "tests/test_runtime_and_persistence.py::test_snapshot_corrupt_bytes_rejected",
            "tests/test_runtime_and_persistence.py::test_snapshot_config_mismatch_rejected",
        ),
        category="snapshot_fidelity",
    ),
    Profile(
        name="TRAINING",
        description="Deterministic training fixture + loss decomposition + optimizer transition",
        fixtures=("tests/test_training.py",),
        category="training_reproducibility",
    ),
    Profile(
        name="FULL_APPLICATION",
        description="Every test in the aeon-application test suite",
        fixtures=("tests/",),
        category="inference_consistency",
    ),
)


def profile_manifest() -> dict:
    return canonical_value({
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "application_version": APPLICATION_VERSION,
        "profiles": {p.name: p.to_canonical() for p in PROFILES},
        "categories": list(CATEGORIES),
    })


def run_profile(name: str, tests_root: Optional[Path] = None) -> dict:
    profile = next((p for p in PROFILES if p.name == name), None)
    if profile is None:
        raise KeyError(f"unknown profile: {name!r}")
    root = tests_root or Path(__file__).resolve().parents[3]
    env = os.environ.copy()
    args = [sys.executable, "-m", "pytest", "-q", "--tb=short"]
    for f in profile.fixtures:
        args.append(str(root / f))
    proc = subprocess.run(args, cwd=str(root), env=env,
                          capture_output=True, text=True)
    passed, failed, skipped = _parse_pytest_summary(proc.stdout + proc.stderr)
    return {
        "profile": name,
        "description": profile.description,
        "category": profile.category,
        "pass_count": passed,
        "fail_count": failed,
        "skip_count": skipped,
        "total": passed + failed + skipped,
        "passed": (proc.returncode == 0 and failed == 0 and skipped == 0),
    }


def _parse_pytest_summary(output: str) -> Tuple[int, int, int]:
    passed = failed = skipped = 0
    for line in output.splitlines():
        stripped = line.strip().lstrip("=").rstrip("=").strip()
        if any(t in stripped for t in (" passed", " failed", " skipped")):
            for token in stripped.split(","):
                token = token.strip()
                if " passed" in token:
                    try:
                        passed = int(token.split(" passed", 1)[0].split()[-1])
                    except (ValueError, IndexError):
                        pass
                if " failed" in token:
                    try:
                        failed = int(token.split(" failed", 1)[0].split()[-1])
                    except (ValueError, IndexError):
                        pass
                if " skipped" in token:
                    try:
                        skipped = int(token.split(" skipped", 1)[0].split()[-1])
                    except (ValueError, IndexError):
                        pass
    return passed, failed, skipped


__all__ = [
    "EVALUATION_SCHEMA_VERSION", "CATEGORIES", "PROFILES",
    "Profile", "profile_manifest", "run_profile",
]
