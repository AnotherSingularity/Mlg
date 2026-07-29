"""aeon.contraction — contraction contracts, results, certificates.

Implements ``07-CONTRACTION.md``. Every field of every certificate
is populated; the distinction between ``NOT_PROVEN`` and
``VIOLATED`` is preserved everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional, Tuple

from .clock import ClockPosition
from .core import SemVer
from .serialization import canonical_value


# ---------------------------------------------------------------------------
# Result vocabulary (spec 07 §2)
# ---------------------------------------------------------------------------


class ContractionResult(Enum):
    PROVEN_CONTRACTIVE = "PROVEN_CONTRACTIVE"
    BOUNDED_CONTRACTIVE = "BOUNDED_CONTRACTIVE"
    NOT_PROVEN = "NOT_PROVEN"
    VIOLATED = "VIOLATED"
    NUMERICALLY_INVALID = "NUMERICALLY_INVALID"


# ---------------------------------------------------------------------------
# Metric identifiers (initial)
# ---------------------------------------------------------------------------


class Metric(Enum):
    L2 = "L2"
    SPECTRAL_NORM = "SpectralNorm"
    LINF = "Linf"


# ---------------------------------------------------------------------------
# PrecisionPolicy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PrecisionPolicy:
    element_type: str        # e.g. "float64", "float32", "bf16"
    rounding_mode: str = "round_to_nearest_even"
    accumulation_bits: int = 64

    def to_canonical(self) -> dict:
        return canonical_value({
            "element_type": self.element_type,
            "rounding_mode": self.rounding_mode,
            "accumulation_bits": self.accumulation_bits,
        })


# ---------------------------------------------------------------------------
# Certification methods
# ---------------------------------------------------------------------------


class CertificationMethod(Enum):
    SPECTRAL_POWER_ITERATION = "SpectralPowerIteration"
    SINGULAR_VALUE_DECOMPOSITION = "SingularValueDecomposition"
    SYMBOLIC_PARAMETERIZATION = "SymbolicParameterization"
    EXACT_RATIONAL_ARITHMETIC = "ExactRationalArithmetic"


class ContractionScope(Enum):
    """The exact map for which a certificate claims a bound.

    Certifying a smaller scope does NOT imply anything about a
    larger scope. A RECURSION_CORE certificate does not cover
    projections, feedback, or the closed loop.
    """

    RECURSION_CORE = "RECURSION_CORE"
    PROJECTED_RECURSION = "PROJECTED_RECURSION"
    INTEGRATION_TRANSITION = "INTEGRATION_TRANSITION"
    CLOSED_LOOP_TRANSITION = "CLOSED_LOOP_TRANSITION"


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Contractive:
    metric: Metric
    requested_margin: float
    numerical_tolerance: float
    precision_policy: PrecisionPolicy
    certification_method: CertificationMethod
    method_params: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (0.0 < self.requested_margin <= 1.0):
            raise ValueError("requested_margin must satisfy 0 < m <= 1")
        if self.numerical_tolerance < 0.0:
            raise ValueError("numerical_tolerance must be >= 0")


# ---------------------------------------------------------------------------
# Certificate (spec 07 §3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContractionCertificate:
    contract_version: SemVer
    metric: Metric
    requested_margin: float
    measured_upper_bound: Optional[float]  # None => Unavailable
    numerical_tolerance: float
    arithmetic_precision: PrecisionPolicy
    certification_method: CertificationMethod
    result: ContractionResult
    consumed_inputs: Tuple[str, ...]  # sorted input digests
    clock_position: ClockPosition
    method_params: Mapping[str, Any] = field(default_factory=dict)
    certified_scope: ContractionScope = ContractionScope.RECURSION_CORE
    arithmetic_kind: str = "Float64"

    def to_canonical(self) -> dict:
        return canonical_value({
            "contract_version": str(self.contract_version),
            "metric": self.metric.value,
            "requested_margin": self.requested_margin,
            "measured_upper_bound":
                self.measured_upper_bound
                if self.measured_upper_bound is not None
                else {"__aeon_unavailable__": True},
            "numerical_tolerance": self.numerical_tolerance,
            "arithmetic_precision": self.arithmetic_precision.to_canonical(),
            "certification_method": self.certification_method.value,
            "result": self.result.value,
            "consumed_inputs": sorted(self.consumed_inputs),
            "clock_position": {
                "domain_id": self.clock_position.domain_id,
                "tick": self.clock_position.tick,
            },
            "method_params": dict(self.method_params),
            "certified_scope": self.certified_scope.value,
            "arithmetic_kind": self.arithmetic_kind,
        })


# ---------------------------------------------------------------------------
# Composition (spec 07 §6)
# ---------------------------------------------------------------------------


_SEVERITY = {
    ContractionResult.PROVEN_CONTRACTIVE: 0,
    ContractionResult.BOUNDED_CONTRACTIVE: 1,
    ContractionResult.NOT_PROVEN: 2,
    ContractionResult.VIOLATED: 3,
    ContractionResult.NUMERICALLY_INVALID: 4,
}


def compose_result(a: ContractionResult, b: ContractionResult) -> ContractionResult:
    """Return the least-favorable of two composed contraction results."""

    if _SEVERITY[a] >= _SEVERITY[b]:
        return a
    return b


def compose_margin(a: float, b: float) -> float:
    """Compose two PROVEN margins: m_a * m_b."""

    if not (0.0 < a <= 1.0 and 0.0 < b <= 1.0):
        raise ValueError("margins must lie in (0, 1]")
    return a * b
