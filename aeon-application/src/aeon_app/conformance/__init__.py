"""aeon_app.conformance — versioned conformance suite + runner.

The conformance suite is the mechanical evidence body for
Gate L-A through L-J (see
``aeon-application/specification/03-GATES.md``).

The suite reads its structure from
``aeon_app.evaluation.PROFILES`` and adds a small amount of
governance metadata (REQUIRED vs OPTIONAL, mandate section, etc)
so a conformance report can be emitted independently of any test
runner state.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from aeon.serialization import canonical_bytes, canonical_value, digest

from .. import APPLICATION_VERSION, AEON_LANGUAGE_CERTIFIED_COMMIT
from ..evaluation import (
    CATEGORIES,
    EVALUATION_SCHEMA_VERSION,
    PROFILES,
    profile_manifest,
    run_profile,
)


CONFORMANCE_SCHEMA_VERSION = "0.1.0"


# Which profiles are REQUIRED for launch certification. Every
# profile named here must report passed=True for the suite to
# be considered green.
REQUIRED_PROFILES: Tuple[str, ...] = (
    "CONFIG",
    "SOURCE",
    "PROJECTION",
    "RECURSION",
    "SCHEDULER",
    "FEEDBACK",
    "PERSISTENCE",
    "TRAINING",
)


# Which mandate gate each profile category satisfies. Used only
# for reporting — the actual gate decision is made in the release
# report by human review of this table.
GATE_MAP: Mapping[str, str] = {
    "language_conformance":       "Gate L-A",
    "source_conformance":         "Gate L-B",
    "boundedness":                "Gate L-C",
    "contraction_status":         "Gate L-D",
    "runtime_determinism":        "Gate L-E",
    "snapshot_fidelity":          "Gate L-F",
    "feedback_neutrality":        "Gate L-G",
    "training_reproducibility":   "Gate L-H",
    "inference_consistency":      "Gate L-I",
    "performance":                "Gate L-J",
}


def build_manifest() -> dict:
    """Emit the canonical, versioned conformance manifest.

    The manifest is a pure derivation of PROFILES + the governance
    metadata above; running it is deterministic under
    PYTHONHASHSEED because canonical_bytes sorts every mapping.
    """
    profile_specs = {p.name: p.to_canonical() for p in PROFILES}
    entries = {}
    for name, spec in sorted(profile_specs.items()):
        entries[name] = {
            **spec,
            "required": name in REQUIRED_PROFILES,
            "gate": GATE_MAP.get(spec["category"], "unassigned"),
        }
    return canonical_value({
        "schema_version": CONFORMANCE_SCHEMA_VERSION,
        "application_version": APPLICATION_VERSION,
        "language_certified_commit": AEON_LANGUAGE_CERTIFIED_COMMIT,
        "evaluation_schema_version": EVALUATION_SCHEMA_VERSION,
        "categories": list(CATEGORIES),
        "required_profiles": list(REQUIRED_PROFILES),
        "profiles": entries,
    })


def manifest_digest() -> str:
    return digest(build_manifest())


@dataclass
class ProfileOutcome:
    name: str
    category: str
    required: bool
    gate: str
    passed: bool
    pass_count: int
    fail_count: int
    skip_count: int


def run_suite(select: Optional[Iterable[str]] = None) -> dict:
    """Run every profile (or the given subset) and emit a
    canonical, decision-bearing report.

    ``select`` may be used to restrict the run to a subset of
    profile names; ``None`` runs every profile in PROFILES.

    Returns a dict with keys: ``manifest_digest``, ``profiles``
    (list of per-profile outcomes), ``aggregate`` (rollup of
    counts), and ``decision`` (``"PASS"`` / ``"FAIL"``).
    """
    names = set(select) if select else {p.name for p in PROFILES}
    outcomes: List[ProfileOutcome] = []
    for p in PROFILES:
        if p.name not in names:
            continue
        result = run_profile(p.name)
        outcomes.append(ProfileOutcome(
            name=p.name,
            category=p.category,
            required=p.name in REQUIRED_PROFILES,
            gate=GATE_MAP.get(p.category, "unassigned"),
            passed=bool(result["passed"]),
            pass_count=int(result["pass_count"]),
            fail_count=int(result["fail_count"]),
            skip_count=int(result["skip_count"]),
        ))
    required_failed = [o.name for o in outcomes
                       if o.required and not o.passed]
    decision = "PASS" if not required_failed else "FAIL"
    aggregate = {
        "profiles_run": len(outcomes),
        "profiles_passed": sum(1 for o in outcomes if o.passed),
        "profiles_failed": sum(1 for o in outcomes if not o.passed),
        "required_failed": required_failed,
        "total_pass_count": sum(o.pass_count for o in outcomes),
        "total_fail_count": sum(o.fail_count for o in outcomes),
        "total_skip_count": sum(o.skip_count for o in outcomes),
    }
    return canonical_value({
        "schema_version": CONFORMANCE_SCHEMA_VERSION,
        "application_version": APPLICATION_VERSION,
        "language_certified_commit": AEON_LANGUAGE_CERTIFIED_COMMIT,
        "manifest_digest": manifest_digest(),
        "profiles": [
            {
                "name": o.name,
                "category": o.category,
                "required": o.required,
                "gate": o.gate,
                "passed": o.passed,
                "pass_count": o.pass_count,
                "fail_count": o.fail_count,
                "skip_count": o.skip_count,
            }
            for o in outcomes
        ],
        "aggregate": aggregate,
        "decision": decision,
    })


def _main(argv: Optional[list] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        prog="python -m aeon_app.conformance",
        description="Run the aeon-application conformance suite.",
    )
    ap.add_argument("--profile", action="append", default=None,
                    help="run only the named profile (repeatable)")
    ap.add_argument("--manifest-only", action="store_true",
                    help="print the manifest without running any tests")
    args = ap.parse_args(argv)
    if args.manifest_only:
        json.dump(build_manifest(), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0
    report = run_suite(select=args.profile)
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(_main())


__all__ = [
    "CONFORMANCE_SCHEMA_VERSION",
    "REQUIRED_PROFILES",
    "GATE_MAP",
    "build_manifest",
    "manifest_digest",
    "run_suite",
]
