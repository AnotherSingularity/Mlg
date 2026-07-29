"""Language-lock loader and verifier.

Reads ``aeon-application/AEON-LANGUAGE-LOCK.json`` and verifies
the loaded Aeon Language matches the pinned certified commit.
Every runtime invocation calls this. Failure is fail-closed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

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

from .. import (
    AEON_LANGUAGE_CERTIFIED_COMMIT,
    AEON_LANGUAGE_REQUIRED_VERSION,
)


class LanguageLockError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code


@dataclass(frozen=True)
class LanguageLockRecord:
    language_version: str
    certified_commit: str
    ir_version: str
    instruction_set_version: str
    stdlib_version: str
    source_grammar_version: str
    certificate_schema: str
    snapshot_schema: str
    conformance_profile: str
    backend_contract: str
    migration_framework: str
    certified_ci_run: str
    lock_generator: str


def _repo_root() -> Path:
    # aeon-application/src/aeon_app/config/language_lock.py -> repo root
    return Path(__file__).resolve().parents[4]


def _default_lock_path() -> Path:
    return _repo_root() / "aeon-application" / "AEON-LANGUAGE-LOCK.json"


def load_lock(path: Optional[Path] = None) -> LanguageLockRecord:
    p = Path(path) if path is not None else _default_lock_path()
    if not p.exists():
        raise LanguageLockError("LOCK_MISSING",
                                f"language lock file not found at {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    try:
        return LanguageLockRecord(
            language_version=data["language_version"],
            certified_commit=data["certified_commit"],
            ir_version=data["ir_version"],
            instruction_set_version=data["instruction_set_version"],
            stdlib_version=data["stdlib_version"],
            source_grammar_version=data["source_grammar_version"],
            certificate_schema=data["certificate_schema"],
            snapshot_schema=data["snapshot_schema"],
            conformance_profile=data["conformance_profile"],
            backend_contract=data["backend_contract"],
            migration_framework=data["migration_framework"],
            certified_ci_run=data["certified_ci_run"],
            lock_generator=data["lock_generator"],
        )
    except KeyError as exc:
        raise LanguageLockError("LOCK_FIELD_MISSING",
                                f"lock file missing field: {exc.args[0]!r}")


def verify_language_lock(lock: Optional[LanguageLockRecord] = None) -> LanguageLockRecord:
    """Compare a lock record against the loaded aeon package.

    Raises LanguageLockError on any mismatch. Returns the record.
    """
    if lock is None:
        lock = load_lock()

    expected = {
        "language_version": (lock.language_version, LANGUAGE_VERSION),
        "ir_version": (lock.ir_version, IR_VERSION),
        "instruction_set_version": (lock.instruction_set_version, INSTRUCTION_SET_VERSION),
        "stdlib_version": (lock.stdlib_version, STDLIB_VERSION),
        "source_grammar_version": (lock.source_grammar_version, SOURCE_GRAMMAR_VERSION),
        "certificate_schema": (lock.certificate_schema, CERTIFICATE_SCHEMA_VERSION),
        "snapshot_schema": (lock.snapshot_schema, SNAPSHOT_SCHEMA_VERSION),
        "conformance_profile": (lock.conformance_profile, CONFORMANCE_PROFILE_VERSION),
        "backend_contract": (lock.backend_contract, BACKEND_CONTRACT_VERSION),
        "migration_framework": (lock.migration_framework, MIGRATION_FRAMEWORK_VERSION),
    }
    for name, (locked, loaded) in expected.items():
        if locked != loaded:
            raise LanguageLockError(
                "LANGUAGE_VERSION_MISMATCH",
                f"{name}: locked={locked!r}, loaded={loaded!r}",
            )

    # The application-level constants must also agree with the lock.
    if lock.language_version != AEON_LANGUAGE_REQUIRED_VERSION:
        raise LanguageLockError(
            "APPLICATION_PIN_MISMATCH",
            f"lock language_version {lock.language_version!r} does not match "
            f"application AEON_LANGUAGE_REQUIRED_VERSION {AEON_LANGUAGE_REQUIRED_VERSION!r}",
        )
    if lock.certified_commit != AEON_LANGUAGE_CERTIFIED_COMMIT:
        raise LanguageLockError(
            "APPLICATION_PIN_MISMATCH",
            f"lock certified_commit {lock.certified_commit!r} does not match "
            f"application AEON_LANGUAGE_CERTIFIED_COMMIT {AEON_LANGUAGE_CERTIFIED_COMMIT!r}",
        )
    return lock
