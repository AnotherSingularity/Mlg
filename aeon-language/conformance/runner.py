"""Conformance runner.

Loads ``manifest.json`` and executes each profile via pytest. Emits
both human-readable text and machine-readable JSON per Phase 0.1
§8.4.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from aeon import (
    INSTRUCTION_SET_VERSION,
    IR_VERSION,
    LANGUAGE_VERSION,
    STDLIB_VERSION,
)


@dataclass
class ProfileResult:
    name: str
    description: str
    required_fixtures: List[str]
    required_capabilities: List[str]
    pass_count: int = 0
    fail_count: int = 0
    skip_count: int = 0
    total: int = 0
    passed: bool = False
    failure_diagnostics: List[str] = field(default_factory=list)


def load_manifest(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _run_pytest(fixture_paths: List[str], tests_root: Path) -> tuple[int, str]:
    args = [sys.executable, "-m", "pytest", "-q", "--tb=short"]
    for p in fixture_paths:
        args.append(str(tests_root.parent / p))
    env = os.environ.copy()
    root = tests_root.parent
    env["PYTHONPATH"] = f"{root / 'standard_library'}:{root}"
    proc = subprocess.run(args, env=env, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def _parse_pytest_summary(output: str) -> tuple[int, int, int]:
    passed = failed = skipped = 0
    for line in output.splitlines():
        line = line.strip()
        if " passed" in line or " failed" in line or " skipped" in line:
            for token in line.split(","):
                token = token.strip().lstrip("=").rstrip("=").strip()
                if " passed" in token:
                    try:
                        passed = int(token.split(" passed", 1)[0].split()[-1])
                    except ValueError:
                        pass
                if " failed" in token:
                    try:
                        failed = int(token.split(" failed", 1)[0].split()[-1])
                    except ValueError:
                        pass
                if " skipped" in token:
                    try:
                        skipped = int(token.split(" skipped", 1)[0].split()[-1])
                    except ValueError:
                        pass
    return passed, failed, skipped


def run(profile_name: str, tests_root: Path) -> ProfileResult:
    manifest_path = Path(__file__).parent / "manifest.json"
    manifest = load_manifest(manifest_path)
    profiles = manifest["profiles"]
    if profile_name not in profiles:
        raise KeyError(f"unknown profile: {profile_name!r}")
    spec = profiles[profile_name]
    result = ProfileResult(
        name=profile_name,
        description=spec["description"],
        required_fixtures=list(spec["required_fixtures"]),
        required_capabilities=list(spec.get("required_capabilities", [])),
    )
    rc, output = _run_pytest(result.required_fixtures, tests_root)
    passed, failed, skipped = _parse_pytest_summary(output)
    result.pass_count = passed
    result.fail_count = failed
    result.skip_count = skipped
    result.total = passed + failed + skipped
    result.passed = (rc == 0 and failed == 0)
    if not result.passed:
        # Trim large output to a reasonable head; the manifest §8.5
        # rule says a profile cannot pass silently on skipped
        # required fixtures, so failure diagnostics must be present.
        result.failure_diagnostics = output.splitlines()[-30:]
    # Vacuous-pass guard: a profile with a required fixture that was
    # skipped MUST NOT be marked passed (§8.5).
    if skipped > 0 and result.passed:
        result.passed = False
        result.failure_diagnostics.append(
            f"[vacuous-pass guard] {skipped} required fixture(s) skipped"
        )
    return result


def full_report(tests_root: Path,
                profiles: Optional[List[str]] = None) -> dict:
    manifest_path = Path(__file__).parent / "manifest.json"
    manifest = load_manifest(manifest_path)
    if profiles is None:
        profiles = list(manifest["profiles"].keys())
    results = [run(p, tests_root) for p in profiles]
    overall = all(r.passed for r in results)
    return {
        "implementation_identity": "aeon.reference/0.1.0-dev",
        "language_version": LANGUAGE_VERSION,
        "ir_version": IR_VERSION,
        "instruction_set_version": INSTRUCTION_SET_VERSION,
        "stdlib_version": STDLIB_VERSION,
        "manifest_version": manifest.get("schema_version"),
        "profiles_executed": [r.name for r in results],
        "results": [{
            "name": r.name,
            "description": r.description,
            "pass_count": r.pass_count,
            "fail_count": r.fail_count,
            "skip_count": r.skip_count,
            "total": r.total,
            "passed": r.passed,
            "failure_diagnostics": r.failure_diagnostics,
        } for r in results],
        "overall_conformance_result": "PASS" if overall else "FAIL",
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="aeontest-conformance",
                                 description="Run Aeon conformance profiles")
    ap.add_argument("--profile", action="append",
                    help="Run one or more profiles by name (repeatable)")
    ap.add_argument("--json", action="store_true",
                    help="Emit machine-readable JSON to stdout")
    ap.add_argument("--tests-root", default=None,
                    help="Path to the tests/ directory (default: sibling)")
    args = ap.parse_args(argv)

    here = Path(__file__).resolve().parents[1]  # aeon-language/
    tests_root = Path(args.tests_root) if args.tests_root else (here / "tests")

    report = full_report(tests_root, args.profile)

    if args.json:
        sys.stdout.write(json.dumps(report, sort_keys=True, indent=2) + "\n")
    else:
        sys.stdout.write(f"Aeon conformance report\n")
        sys.stdout.write(f"  language={report['language_version']} ir={report['ir_version']}\n")
        for r in report["results"]:
            tag = "PASS" if r["passed"] else "FAIL"
            sys.stdout.write(
                f"  [{tag}] {r['name']:24s} "
                f"pass={r['pass_count']} fail={r['fail_count']} skip={r['skip_count']}\n"
            )
        sys.stdout.write(f"Overall: {report['overall_conformance_result']}\n")

    return 0 if report["overall_conformance_result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
