"""aeon.migration_registry — the concrete v0.0 → v0.1 registrations.

Every migration here is documented against a specific synthetic
predecessor. Synthetic v0.0 IS NOT a real historical Aeon release;
it exists solely to prove the migration mechanism is real
(mandate §2.1). The differences between synthetic v0.0 and v0.1
are intentional and non-trivial.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from . import IR_VERSION, LANGUAGE_VERSION
from .migration import (
    AEON_VERSION_KEY,
    ArtifactKind,
    Migration,
    MigrationRegistry,
)


# ---------------------------------------------------------------------------
# Synthetic v0.0 differences (documented)
# ---------------------------------------------------------------------------
#
# semantic_graph v0.0 -> v0.1
#   * top-level uses "attrs" instead of "attributes" on every node
#   * edges are stored under key "directed_edges" instead of "edges"
#   * each node has "type" instead of "kind"
#
# canonical_ir v0.0 -> v0.1
#   * instructions are stored under key "ops" instead of "instructions"
#   * each op uses "op" instead of "opcode"
#   * each op uses "args" instead of "operands"
#   * top-level lacks "instruction_set_version"; v0.1 introduces it
#
# snapshot v0.0 -> v0.1
#   * top-level uses "versions" sub-object instead of top-level
#     language_version / ir_version / stdlib_version keys
#   * uses "state" (single dict) instead of "state_snapshots" (list)
#   * uses "contracts" instead of "active_contracts"
#
# certificate v0.0 -> v0.1
#   * uses "upper_bound" instead of "measured_upper_bound"
#   * uses "precision" (string) instead of "arithmetic_precision"
#     (object with element_type, rounding_mode, accumulation_bits)
#   * lacks "method_params" (v0.1 introduces the audit trail)
#   * lacks "consumed_inputs" as a required sorted list
# ---------------------------------------------------------------------------


V0_0 = "0.0.0"
V0_1 = "0.1.0"


# ---------------------------------------------------------------------------
# semantic_graph
# ---------------------------------------------------------------------------


def _migrate_graph_v0_0_to_v0_1(artifact: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(artifact)
    out[AEON_VERSION_KEY] = V0_1

    nodes_out = []
    for n in artifact.get("nodes", []):
        # rename type -> kind, attrs -> attributes
        m = dict(n)
        if "type" in m:
            m["kind"] = m.pop("type")
        if "attrs" in m:
            m["attributes"] = m.pop("attrs")
        nodes_out.append(m)
    out["nodes"] = nodes_out
    out["edges"] = list(artifact.get("directed_edges", []))
    out.pop("directed_edges", None)
    return out


# ---------------------------------------------------------------------------
# canonical_ir
# ---------------------------------------------------------------------------


def _migrate_ir_v0_0_to_v0_1(artifact: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(artifact)
    out[AEON_VERSION_KEY] = V0_1

    ops = artifact.get("ops", [])
    instructions = []
    for op in ops:
        m = dict(op)
        if "op" in m:
            m["opcode"] = m.pop("op")
        if "args" in m:
            m["operands"] = m.pop("args")
        instructions.append(m)
    out["instructions"] = instructions
    out.pop("ops", None)
    # v0.1 introduces instruction_set_version at the envelope level.
    out.setdefault("instruction_set_version", IR_VERSION)
    return out


# ---------------------------------------------------------------------------
# snapshot
# ---------------------------------------------------------------------------


def _migrate_snapshot_v0_0_to_v0_1(artifact: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(artifact)
    out[AEON_VERSION_KEY] = V0_1

    versions = artifact.get("versions", {}) or {}
    out["language_version"] = versions.get("language", LANGUAGE_VERSION)
    out["ir_version"] = versions.get("ir", IR_VERSION)
    out["stdlib_version"] = versions.get("stdlib", LANGUAGE_VERSION)
    out.pop("versions", None)
    # state (single dict) -> state_snapshots (list)
    if "state" in out:
        out["state_snapshots"] = [out.pop("state")]
    else:
        out.setdefault("state_snapshots", [])
    if "contracts" in out:
        out["active_contracts"] = list(out.pop("contracts"))
    else:
        out.setdefault("active_contracts", [])
    return out


# ---------------------------------------------------------------------------
# certificate
# ---------------------------------------------------------------------------


def _migrate_certificate_v0_0_to_v0_1(artifact: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(artifact)
    out[AEON_VERSION_KEY] = V0_1

    if "upper_bound" in out:
        out["measured_upper_bound"] = out.pop("upper_bound")
    if "precision" in out and isinstance(out["precision"], str):
        # promote string -> object with the fields v0.1 requires
        out["arithmetic_precision"] = {
            "element_type": out["precision"],
            "rounding_mode": "round_to_nearest_even",
            "accumulation_bits": 64,
        }
        out.pop("precision", None)
    out.setdefault("consumed_inputs", [])
    # method_params is a new v0.1 field; explicitly record the
    # provenance of this artifact.
    mp = dict(out.get("method_params", {}) or {})
    mp.setdefault("migrated_from", "certificate/v0.0.0")
    out["method_params"] = mp
    return out


# ---------------------------------------------------------------------------
# Default registry
# ---------------------------------------------------------------------------


def build_default_registry() -> MigrationRegistry:
    reg = MigrationRegistry()
    reg.register(Migration(
        artifact_kind=ArtifactKind.SEMANTIC_GRAPH,
        source_version=V0_0, target_version=V0_1,
        apply=_migrate_graph_v0_0_to_v0_1,
        description="synthetic graph v0.0 -> v0.1: rename type->kind, attrs->attributes, directed_edges->edges",
    ))
    reg.register(Migration(
        artifact_kind=ArtifactKind.CANONICAL_IR,
        source_version=V0_0, target_version=V0_1,
        apply=_migrate_ir_v0_0_to_v0_1,
        description="synthetic IR v0.0 -> v0.1: rename ops->instructions, op->opcode, args->operands; add instruction_set_version",
    ))
    reg.register(Migration(
        artifact_kind=ArtifactKind.SNAPSHOT,
        source_version=V0_0, target_version=V0_1,
        apply=_migrate_snapshot_v0_0_to_v0_1,
        description="synthetic snapshot v0.0 -> v0.1: hoist versions sub-object to top-level, state->state_snapshots list, contracts->active_contracts",
    ))
    reg.register(Migration(
        artifact_kind=ArtifactKind.CERTIFICATE,
        source_version=V0_0, target_version=V0_1,
        apply=_migrate_certificate_v0_0_to_v0_1,
        description="synthetic certificate v0.0 -> v0.1: rename upper_bound->measured_upper_bound, promote precision string to arithmetic_precision object, add method_params.migrated_from",
    ))
    return reg


DEFAULT_REGISTRY = build_default_registry()

# MIGRATION_FRAMEWORK_VERSION is re-exported from aeon.__init__ for
# the single-authoritative-source rule.
from . import MIGRATION_FRAMEWORK_VERSION  # noqa: F401,E402
