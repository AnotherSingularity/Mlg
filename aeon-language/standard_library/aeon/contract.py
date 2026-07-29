"""aeon.contract — the contract subsystem's public surface.

A contract is a machine-checkable specification bound to a
transition, projection, port, or capability (spec 01-ONTOLOGY.md).
The Contractive contract lives in :mod:`aeon.contraction`; other
contract kinds are declared here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .contraction import Contractive
from .serialization import canonical_value


@dataclass(frozen=True)
class ContractRef:
    id: str
    kind: str
    version: str = "0.1.0-dev"


@dataclass(frozen=True)
class ContractBinding:
    """Binds a contract to a target (transition or projection id)."""

    contract: ContractRef
    target_id: str


@dataclass(frozen=True)
class RecoveryContract:
    """Declares a recovery handler for a specific ContractViolation code."""

    violation_code: str
    recovery_transition_id: str


def to_canonical_binding(b: ContractBinding) -> dict:
    return canonical_value({
        "contract_id": b.contract.id,
        "contract_kind": b.contract.kind,
        "contract_version": b.contract.version,
        "target_id": b.target_id,
    })


__all__ = [
    "ContractRef",
    "ContractBinding",
    "RecoveryContract",
    "Contractive",
    "to_canonical_binding",
]
