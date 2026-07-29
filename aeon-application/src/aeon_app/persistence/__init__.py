"""aeon_app.persistence — application snapshot envelope + restore + replay."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Tuple

from aeon.serialization import canonical_bytes, canonical_value, digest

from .. import (
    APPLICATION_SNAPSHOT_SCHEMA_VERSION,
    APPLICATION_VERSION,
    AEON_LANGUAGE_CERTIFIED_COMMIT,
    AEON_LANGUAGE_REQUIRED_VERSION,
)


APPLICATION_SNAPSHOT_KIND = "aeon_app.snapshot"


class SnapshotError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code


@dataclass(frozen=True)
class ApplicationSnapshot:
    schema_version: str
    application_version: str
    language_version: str
    language_certified_commit: str
    ir_version: str
    graph_id: str
    ir_module_id: str
    runtime_mode: str
    backend_id: str
    config_digest: str
    source_snapshots: Mapping[str, bytes]        # component_id -> canonical bytes
    recursion_snapshot: bytes
    scheduler_state: Mapping[str, Any]
    clock_positions: Mapping[str, int]
    active_windows: Tuple[Mapping[str, Any], ...]
    negotiation_result: Optional[Mapping[str, Any]]
    active_contracts: Tuple[str, ...]
    random_state: Optional[Mapping[str, Any]]
    event_log_digest: str

    def to_canonical(self) -> dict:
        return canonical_value({
            "schema_version": self.schema_version,
            "application_version": self.application_version,
            "language_version": self.language_version,
            "language_certified_commit": self.language_certified_commit,
            "ir_version": self.ir_version,
            "graph_id": self.graph_id,
            "ir_module_id": self.ir_module_id,
            "runtime_mode": self.runtime_mode,
            "backend_id": self.backend_id,
            "config_digest": self.config_digest,
            "source_snapshots": {
                k: {"__aeon_bytes__": v.hex()} for k, v in sorted(self.source_snapshots.items())
            },
            "recursion_snapshot": {"__aeon_bytes__": self.recursion_snapshot.hex()},
            "scheduler_state": dict(self.scheduler_state),
            "clock_positions": dict(self.clock_positions),
            "active_windows": [dict(w) for w in self.active_windows],
            "negotiation_result": dict(self.negotiation_result) if self.negotiation_result else None,
            "active_contracts": sorted(self.active_contracts),
            "random_state": dict(self.random_state) if self.random_state else None,
            "event_log_digest": self.event_log_digest,
        })

    def to_bytes(self) -> bytes:
        return canonical_bytes(self.to_canonical())

    def digest(self) -> str:
        return digest(self.to_canonical())


def load_snapshot(raw: bytes) -> ApplicationSnapshot:
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise SnapshotError("SNAPSHOT_CORRUPT",
                            f"unable to parse snapshot: {exc}")
    try:
        return ApplicationSnapshot(
            schema_version=data["schema_version"],
            application_version=data["application_version"],
            language_version=data["language_version"],
            language_certified_commit=data["language_certified_commit"],
            ir_version=data["ir_version"],
            graph_id=data["graph_id"],
            ir_module_id=data["ir_module_id"],
            runtime_mode=data["runtime_mode"],
            backend_id=data["backend_id"],
            config_digest=data["config_digest"],
            source_snapshots={k: bytes.fromhex(v["__aeon_bytes__"])
                              for k, v in data["source_snapshots"].items()},
            recursion_snapshot=bytes.fromhex(data["recursion_snapshot"]["__aeon_bytes__"]),
            scheduler_state=data["scheduler_state"],
            clock_positions=data["clock_positions"],
            active_windows=tuple(data["active_windows"]),
            negotiation_result=data.get("negotiation_result"),
            active_contracts=tuple(data["active_contracts"]),
            random_state=data.get("random_state"),
            event_log_digest=data["event_log_digest"],
        )
    except (KeyError, ValueError) as exc:
        raise SnapshotError("SNAPSHOT_MISSING_FIELD",
                            f"snapshot missing field: {exc}")


def verify_snapshot_version(snap: ApplicationSnapshot) -> None:
    if snap.schema_version != APPLICATION_SNAPSHOT_SCHEMA_VERSION:
        raise SnapshotError("SNAPSHOT_SCHEMA_MISMATCH",
                            f"expected {APPLICATION_SNAPSHOT_SCHEMA_VERSION!r}, "
                            f"got {snap.schema_version!r}")
    if snap.application_version != APPLICATION_VERSION:
        raise SnapshotError("SNAPSHOT_APP_VERSION_MISMATCH",
                            f"expected {APPLICATION_VERSION!r}, "
                            f"got {snap.application_version!r}")
    if snap.language_version != AEON_LANGUAGE_REQUIRED_VERSION:
        raise SnapshotError("SNAPSHOT_LANGUAGE_VERSION_MISMATCH",
                            f"expected {AEON_LANGUAGE_REQUIRED_VERSION!r}, "
                            f"got {snap.language_version!r}")
    if snap.language_certified_commit != AEON_LANGUAGE_CERTIFIED_COMMIT:
        raise SnapshotError("SNAPSHOT_LANGUAGE_COMMIT_MISMATCH",
                            f"expected {AEON_LANGUAGE_CERTIFIED_COMMIT!r}, "
                            f"got {snap.language_certified_commit!r}")


__all__ = [
    "APPLICATION_SNAPSHOT_KIND",
    "ApplicationSnapshot",
    "SnapshotError",
    "load_snapshot",
    "verify_snapshot_version",
]
