"""L11: evaluation profiles."""

from __future__ import annotations

from aeon_app.evaluation import (
    CATEGORIES,
    EVALUATION_SCHEMA_VERSION,
    PROFILES,
    Profile,
    profile_manifest,
)


def test_evaluation_schema_version():
    assert EVALUATION_SCHEMA_VERSION == "0.1.0"


def test_mandatory_categories_present():
    for c in (
        "language_conformance", "source_conformance", "runtime_determinism",
        "snapshot_fidelity", "contraction_status", "boundedness",
        "training_reproducibility", "inference_consistency",
        "feedback_neutrality", "performance",
    ):
        assert c in CATEGORIES


def test_all_expected_profiles_present():
    names = {p.name for p in PROFILES}
    for expected in ("CONFIG", "SOURCE", "PROJECTION", "RECURSION",
                     "SCHEDULER", "FEEDBACK", "PERSISTENCE", "TRAINING",
                     "FULL_APPLICATION"):
        assert expected in names


def test_profile_manifest_shape():
    m = profile_manifest()
    assert m["schema_version"] == "0.1.0"
    assert m["application_version"] == "0.1.0"
    assert set(m["profiles"]) >= {"CONFIG", "SOURCE", "RECURSION",
                                    "SCHEDULER", "FEEDBACK",
                                    "PERSISTENCE", "TRAINING",
                                    "FULL_APPLICATION"}
    for name, spec in m["profiles"].items():
        for k in ("name", "description", "fixtures", "category"):
            assert k in spec
