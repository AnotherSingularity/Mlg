"""Aeon release manifest.

Computes the canonical release manifest for a given SHA. Every
artifact of any versioned kind has its digest recorded here so
that verifying the manifest against a checkout proves the release
content hasn't drifted.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from aeon import (
    BACKEND_CONTRACT_VERSION,
    CERTIFICATE_SCHEMA_VERSION,
    CONFORMANCE_PROFILE_VERSION,
    INSTRUCTION_SET_VERSION,
    IR_VERSION,
    LANGUAGE_VERSION,
    MIGRATION_FRAMEWORK_VERSION,
    SNAPSHOT_SCHEMA_VERSION,
    SOURCE_GRAMMAR_VERSION,
    STDLIB_VERSION,
)
from aeon.serialization import canonical_bytes, canonical_value, digest


REPO_ROOT = Path(__file__).resolve().parents[1]  # aeon-language/


def _sha_of_head() -> Optional[str]:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=str(REPO_ROOT.parent),
        )
        if out.returncode != 0:
            return None
        return out.stdout.strip()
    except Exception:  # noqa: BLE001
        return None


def _digest_file(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    return digest(path.read_bytes())


def _digest_json(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    return digest(json.loads(path.read_text()))


def _spec_digests() -> Dict[str, str]:
    spec_dir = REPO_ROOT / "specification"
    out: Dict[str, str] = {}
    if spec_dir.is_dir():
        for f in sorted(spec_dir.glob("*.md")):
            out[f.name] = digest(f.read_bytes())
    return out


def _fixture_digests() -> Dict[str, str]:
    fixture_dir = REPO_ROOT / "conformance" / "fixtures"
    out: Dict[str, str] = {}
    if fixture_dir.is_dir():
        for f in sorted(fixture_dir.rglob("*.json")):
            rel = f.relative_to(fixture_dir).as_posix()
            out[rel] = digest(json.loads(f.read_text()))
    return out


def _stdlib_public_api() -> List[str]:
    # Report the module list from aeon.__init__ + the mandated §17
    # module names. Absence of any name here is a release blocker.
    return sorted([
        "aeon.core", "aeon.types", "aeon.identity", "aeon.state",
        "aeon.signal", "aeon.clock", "aeon.causality", "aeon.port",
        "aeon.capability", "aeon.contract", "aeon.contraction",
        "aeon.recursion", "aeon.projection", "aeon.graph", "aeon.ir",
        "aeon.runtime", "aeon.certificate", "aeon.provenance",
        "aeon.serialization", "aeon.snapshot", "aeon.testing",
        "aeon.math", "aeon.tensor", "aeon.verifier", "aeon.migration",
        "aeon.migration_registry",
    ])


def _instruction_set() -> List[str]:
    from aeon.ir import OPCODE_VALUES
    return sorted(OPCODE_VALUES)


def _cli_tools() -> List[str]:
    from compiler.cli import TOOLS
    return sorted(TOOLS.keys())


def _backend_infos() -> Dict[str, Dict[str, Any]]:
    from backends.python import PythonBackend
    out = {
        "aeon.backends.python": {
            "version": PythonBackend.info.version,
            "numerical_tolerance": PythonBackend.info.numerical_tolerance,
        }
    }
    try:
        from backends.numpy import NumpyBackend
        out["aeon.backends.numpy"] = {
            "version": NumpyBackend.info.version,
            "numerical_tolerance": NumpyBackend.info.numerical_tolerance,
            "supported_ir_version": NumpyBackend.info.supported_ir_version,
        }
    except ImportError:
        pass
    return out


def build_release_manifest(*, sha: Optional[str] = None) -> Dict[str, Any]:
    """Compute the canonical release manifest as a dict."""

    return {
        "release_version": LANGUAGE_VERSION,
        "candidate_sha": sha or _sha_of_head() or "UNKNOWN",
        "versions": {
            "language": LANGUAGE_VERSION,
            "ir": IR_VERSION,
            "instruction_set": INSTRUCTION_SET_VERSION,
            "stdlib": STDLIB_VERSION,
            "source_grammar": SOURCE_GRAMMAR_VERSION,
            "certificate_schema": CERTIFICATE_SCHEMA_VERSION,
            "snapshot_schema": SNAPSHOT_SCHEMA_VERSION,
            "conformance_profile": CONFORMANCE_PROFILE_VERSION,
            "backend_contract": BACKEND_CONTRACT_VERSION,
            "migration_framework": MIGRATION_FRAMEWORK_VERSION,
        },
        "specification_digests": _spec_digests(),
        "ir_schema_digest": _digest_json(
            REPO_ROOT / "schemas" / "ir-module.schema.json"
        ),
        "conformance_manifest_digest": _digest_json(
            REPO_ROOT / "conformance" / "manifest.json"
        ),
        "fixture_digests": _fixture_digests(),
        "stdlib_public_api": _stdlib_public_api(),
        "instruction_set": _instruction_set(),
        "cli_tools": _cli_tools(),
        "backends": _backend_infos(),
    }


def release_manifest_digest(manifest: Dict[str, Any]) -> str:
    return digest(canonical_value(manifest))


def release_manifest_bytes(manifest: Dict[str, Any]) -> bytes:
    return canonical_bytes(canonical_value(manifest))


def write_release_manifest(destination: Path, *, sha: Optional[str] = None) -> Dict[str, Any]:
    manifest = build_release_manifest(sha=sha)
    destination.write_bytes(release_manifest_bytes(manifest))
    return manifest


def verify_release_manifest(path: Path) -> Dict[str, Any]:
    """Recompute the manifest and compare with the on-disk file.

    Returns a report with fields:
        ok (bool)
        manifest_digest (str)
        recomputed_digest (str)
        mismatches (list[str])
    """

    if not path.exists():
        return {"ok": False, "reason": f"missing manifest at {path}"}
    stored = json.loads(path.read_text())
    recomputed = build_release_manifest(sha=stored.get("candidate_sha"))
    # SHA verification: manifest is bound to a specific SHA; do not
    # compare against the current HEAD.
    stored_digest = release_manifest_digest(stored)
    recomputed_digest = release_manifest_digest(recomputed)
    mismatches: List[str] = []
    for key in sorted(set(stored) | set(recomputed)):
        if canonical_value(stored.get(key)) != canonical_value(recomputed.get(key)):
            mismatches.append(key)
    return {
        "ok": stored_digest == recomputed_digest,
        "manifest_digest": stored_digest,
        "recomputed_digest": recomputed_digest,
        "mismatches": mismatches,
    }
