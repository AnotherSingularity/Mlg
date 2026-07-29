"""Conformance manifest + runner properties (Phase 0.1 §8)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


MANIFEST_PATH = Path(__file__).parent.parent / "conformance" / "manifest.json"


def _load():
    with MANIFEST_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_manifest_carries_language_and_ir_versions():
    m = _load()
    for k in ("language_version", "ir_version", "instruction_set_version",
              "schema_version"):
        assert k in m and m[k]


def test_all_required_profiles_present():
    m = _load()
    required = {
        "CORE", "SOURCE_REQUIRED", "SOURCE_RICH", "RECURSION_SUBSTRATE",
        "COMPILER", "RUNTIME", "BACKEND", "STDLIB", "FULL_IMPLEMENTATION",
    }
    assert set(m["profiles"]) >= required


def test_each_profile_has_required_fields():
    m = _load()
    for name, spec in m["profiles"].items():
        for f in ("description", "required_fixtures",
                  "required_capabilities", "permitted_variance"):
            assert f in spec, f"profile {name!r} missing field {f!r}"
        assert spec["required_fixtures"], f"profile {name!r} declares no fixtures"


def test_runner_full_report_shape():
    from conformance.runner import full_report
    # Only run a cheap profile to keep the test fast.
    report = full_report(Path(__file__).parent, profiles=["STDLIB"])
    assert report["overall_conformance_result"] in ("PASS", "FAIL")
    for k in ("language_version", "ir_version", "instruction_set_version",
              "profiles_executed", "results"):
        assert k in report
    assert report["profiles_executed"] == ["STDLIB"]
    stdlib = report["results"][0]
    for k in ("name", "pass_count", "fail_count", "skip_count", "total", "passed"):
        assert k in stdlib
