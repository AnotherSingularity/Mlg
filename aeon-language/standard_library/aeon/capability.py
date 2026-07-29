"""aeon.capability — capabilities, tiers, and deterministic negotiation.

Implements the negotiation model from ``05-PORTS-AND-CAPABILITIES.md``.
Every step is pure: given the same offered and required capability
sets, ``negotiate`` returns the same :class:`NegotiationResult` in
byte-identical canonical form.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping, Optional, Sequence, Tuple

from .core import SemVer
from .serialization import canonical_value


class CapabilityTier(Enum):
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"


@dataclass(frozen=True)
class CapabilityRef:
    """A reference to a named, versioned capability contract."""

    name: str
    version: SemVer
    tier: CapabilityTier = CapabilityTier.OPTIONAL

    def sort_key(self) -> Tuple[str, str]:
        # Canonical sort by (name, str(version)).
        return (self.name, str(self.version))


@dataclass(frozen=True)
class VersionConstraint:
    """A caret-style constraint: same major, minor/patch >= min."""

    name: str
    min_version: SemVer

    def accepts(self, offered: SemVer) -> bool:
        if offered.major != self.min_version.major:
            return False
        if offered.minor < self.min_version.minor:
            return False
        if offered.minor == self.min_version.minor and offered.patch < self.min_version.patch:
            return False
        return True


@dataclass(frozen=True)
class Incompatibility:
    capability_name: str
    reason: str


@dataclass(frozen=True)
class NegotiationResult:
    compatible: bool
    selected_versions: Tuple[Tuple[str, str], ...]  # sorted (name, str(version))
    required_path: Tuple[str, ...]                  # sorted names
    optional_paths: Tuple[str, ...]                 # sorted names
    fallback_path: Tuple[str, ...]                  # sorted names
    incompatibilities: Tuple[Incompatibility, ...]  # sorted by (name, reason)

    def to_canonical(self) -> dict:
        return canonical_value({
            "compatible": self.compatible,
            "selected_versions": [list(pair) for pair in self.selected_versions],
            "required_path": list(self.required_path),
            "optional_paths": list(self.optional_paths),
            "fallback_path": list(self.fallback_path),
            "incompatibilities": [
                {"capability_name": i.capability_name, "reason": i.reason}
                for i in self.incompatibilities
            ],
        })


# ---------------------------------------------------------------------------
# Reserved capability names (see ontology and 05-PORTS-AND-CAPABILITIES §3)
# ---------------------------------------------------------------------------

REQUIRED_CAPABILITY_NAMES: Tuple[str, ...] = (
    "VectorDrive",
    "VectorRead",
    "PerTokenStep",
)

PROVISIONAL_CAPABILITY_NAMES: Tuple[str, ...] = (
    "AssociationWrite",
    "ConfigurableCadence",
    "DecayControl",
    "LayerRead",
    "MatrixRead",
)


# ---------------------------------------------------------------------------
# Negotiation
# ---------------------------------------------------------------------------


def negotiate(
    offered: Iterable[CapabilityRef],
    required: Iterable[VersionConstraint],
    optional: Iterable[VersionConstraint] = (),
    fallback: Iterable[str] = (),
) -> NegotiationResult:
    """Compute a deterministic capability negotiation.

    Inputs are iterables of any order. Outputs are sorted by
    capability name (and by (name, reason) for incompatibilities)
    so that the canonical form is independent of input ordering.

    Rules (spec 05 §4):
    - ``compatible = False`` iff any REQUIRED name has no offered
      version satisfying its constraint.
    - Version selection picks the highest offered version satisfying
      the constraint.
    - Capability absence is an explicit ``Incompatibility``, never a
      silent absence.
    """

    offered_by_name: dict[str, list[SemVer]] = {}
    for cap in offered:
        offered_by_name.setdefault(cap.name, []).append(cap.version)

    selected: dict[str, SemVer] = {}
    required_names: list[str] = []
    optional_names: list[str] = []
    incompats: list[Incompatibility] = []

    def _select(constraint: VersionConstraint) -> Optional[SemVer]:
        candidates = [v for v in offered_by_name.get(constraint.name, [])
                      if constraint.accepts(v)]
        if not candidates:
            return None
        # Deterministic "highest": lexicographic on tuple (major, minor, patch).
        return max(candidates, key=lambda v: (v.major, v.minor, v.patch))

    for constraint in sorted(required, key=lambda c: c.name):
        required_names.append(constraint.name)
        chosen = _select(constraint)
        if chosen is None:
            incompats.append(
                Incompatibility(
                    capability_name=constraint.name,
                    reason=f"no offered version satisfies >= {constraint.min_version}",
                )
            )
        else:
            selected[constraint.name] = chosen

    for constraint in sorted(optional, key=lambda c: c.name):
        chosen = _select(constraint)
        if chosen is not None:
            optional_names.append(constraint.name)
            selected[constraint.name] = chosen
        # Absent optional capabilities are simply not selected — not
        # an incompatibility.

    compatible = all(name in selected for name in required_names)

    selected_versions_sorted = tuple(
        (name, str(selected[name])) for name in sorted(selected.keys())
    )
    incompats.sort(key=lambda i: (i.capability_name, i.reason))

    return NegotiationResult(
        compatible=compatible,
        selected_versions=selected_versions_sorted,
        required_path=tuple(sorted(required_names)),
        optional_paths=tuple(sorted(optional_names)),
        fallback_path=tuple(sorted(fallback)),
        incompatibilities=tuple(incompats),
    )
