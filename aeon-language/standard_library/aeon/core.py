"""aeon.core — foundational value types shared by the kernel.

This module defines the primitive value types that every other
kernel module builds on:

- ``Identity``          — a typed, stable, digest-based identity.
- ``LanguageVersion``   — the version stream tag.
- ``Validity``          — the enumeration from spec §11.
- ``TransitionResult``  — the tagged union from spec §11 (§6.4 of
                          the constitution).
- ``Reason``, ``ContractViolation``, ``RuntimeError_`` — the
                          vocabulary from ``11-ERROR-MODEL.md``.

Everything here is a pure value. There are no host-object
identities and no mutable global state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, Mapping, Optional, Sequence, Tuple, TypeVar, Union

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SemVer:
    """A three-part semantic version tag, optionally with a prerelease."""

    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None

    def __post_init__(self) -> None:
        for name in ("major", "minor", "patch"):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"SemVer.{name} must be a non-negative int")

    def __str__(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        return f"{base}-{self.prerelease}" if self.prerelease else base

    @classmethod
    def parse(cls, text: str) -> "SemVer":
        if not isinstance(text, str) or not text:
            raise ValueError("SemVer.parse: text must be a non-empty str")
        core, _, prerelease = text.partition("-")
        parts = core.split(".")
        if len(parts) != 3:
            raise ValueError(f"SemVer.parse: {text!r} not major.minor.patch")
        try:
            major, minor, patch = (int(p) for p in parts)
        except ValueError as exc:
            raise ValueError(f"SemVer.parse: {text!r} not integer parts") from exc
        return cls(major, minor, patch, prerelease or None)


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Identity:
    """A typed, canonical identity backed by a digest.

    Identity MUST NOT be derived from host memory address or
    nondeterministic iteration order (see spec 08-PROVENANCE §1).
    Construction is centralized in :mod:`aeon.provenance`; callers
    receive already-computed ``Identity`` values.
    """

    kind: str
    digest_method: str
    digest: str  # hexadecimal

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or not self.kind:
            raise ValueError("Identity.kind must be non-empty str")
        if not isinstance(self.digest_method, str) or not self.digest_method:
            raise ValueError("Identity.digest_method must be non-empty str")
        if not isinstance(self.digest, str) or not self.digest:
            raise ValueError("Identity.digest must be non-empty str")
        # Hexadecimal digest check; keep it cheap.
        try:
            int(self.digest, 16)
        except ValueError as exc:
            raise ValueError("Identity.digest must be hexadecimal") from exc

    def short(self, n: int = 12) -> str:
        return f"{self.kind}:{self.digest[:n]}"

    def __repr__(self) -> str:
        return f"Identity({self.kind!r}, {self.digest_method!r}, {self.short()!r})"


# ---------------------------------------------------------------------------
# Validity states (spec 03-STATE-SEMANTICS §7 and 11-ERROR-MODEL §2)
# ---------------------------------------------------------------------------


class Validity(Enum):
    VALID = "VALID"
    PROVISIONALLY_VALID = "PROVISIONALLY_VALID"
    UNCERTIFIED = "UNCERTIFIED"
    CONTRACT_VIOLATED = "CONTRACT_VIOLATED"
    INVALID = "INVALID"
    UNAVAILABLE = "UNAVAILABLE"


# ---------------------------------------------------------------------------
# Reasons, contract violations, runtime errors
# ---------------------------------------------------------------------------


class Reason(Enum):
    NO_CONTRACT_BOUND = "NoContractBound"
    CERTIFICATION_INCONCLUSIVE = "CertificationInconclusive"
    METHOD_NOT_APPLICABLE = "MethodNotApplicable"
    POLICY_ALLOWS_UNCERTIFIED = "PolicyAllowsUncertified"


class ContractViolationCode(Enum):
    TYPE_MISMATCH = "TypeMismatch"
    SHAPE_MISMATCH = "ShapeMismatch"
    OWNERSHIP_VIOLATION = "OwnershipViolation"
    CAUSALITY_VIOLATION = "CausalityViolation"
    CLOCK_CROSSING_UNDECLARED = "ClockCrossingUndeclared"
    WINDOW_IDENTITY_MISSING = "WindowIdentityMissing"
    FUTURE_LEAKAGE = "FutureLeakage"
    DUPLICATE_CONSUMPTION = "DuplicateConsumption"
    CONTRACTION_VIOLATED = "ContractionViolated"
    NUMERICAL_INVALID = "NumericalInvalid"
    CAPABILITY_ABSENT = "CapabilityAbsent"
    NEGOTIATION_FAILURE = "NegotiationFailure"
    SNAPSHOT_MISMATCH = "SnapshotMismatch"


class RuntimeErrorCode(Enum):
    HOST_FRAMEWORK_ERROR = "HostFrameworkError"
    OUT_OF_MEMORY = "OutOfMemory"
    IO_ERROR = "IoError"
    INTERNAL_CONSISTENCY_ERROR = "InternalConsistencyError"


@dataclass(frozen=True)
class ContractViolation:
    code: ContractViolationCode
    detail: str = ""
    involved: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RuntimeError_:
    """Runtime error value.

    Named ``RuntimeError_`` to avoid shadowing the built-in
    exception; the value type is not an exception.
    """

    code: RuntimeErrorCode
    detail: str = ""


# ---------------------------------------------------------------------------
# TransitionResult (spec 11-ERROR-MODEL §1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Applied(Generic[T]):
    value: T
    certificate: "Certificate[T]"


@dataclass(frozen=True)
class AppliedUncertified(Generic[T]):
    value: T
    reason: Reason
    detail: str = ""


@dataclass(frozen=True)
class Rejected:
    violation: ContractViolation


@dataclass(frozen=True)
class Failed:
    error: RuntimeError_


TransitionResult = Union[Applied[T], AppliedUncertified[T], Rejected, Failed]


def is_applied(result: TransitionResult[T]) -> bool:
    return isinstance(result, Applied)


def is_uncertified(result: TransitionResult[T]) -> bool:
    return isinstance(result, AppliedUncertified)


def is_rejected(result: TransitionResult[T]) -> bool:
    return isinstance(result, Rejected)


def is_failed(result: TransitionResult[T]) -> bool:
    return isinstance(result, Failed)


# ---------------------------------------------------------------------------
# Certificate skeleton (concrete forms in aeon.certificate / aeon.contraction)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Certificate(Generic[T]):
    """Evidence that a contract was checked and its result.

    The fields here are the universal minimum; specific certificate
    kinds (e.g. contraction certificates) extend this record via
    the ``detail`` map. Detail values MUST be canonicalizable
    primitive values (see :mod:`aeon.serialization`).
    """

    contract_id: str
    contract_version: SemVer
    method: str
    subject_id: Identity
    inputs_ids: Tuple[Identity, ...]
    clock_position: "ClockPositionRef"
    result: str  # e.g. "Passed", "PROVEN_CONTRACTIVE"
    detail: Mapping[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Diagnostic (spec 11-ERROR-MODEL §4)
# ---------------------------------------------------------------------------


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class SourceSpan:
    file: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int


@dataclass(frozen=True)
class Diagnostic:
    severity: Severity
    code: str
    message: str
    source_span: Optional[SourceSpan] = None
    involved_ids: Tuple[str, ...] = ()
    remediation: Optional[str] = None


# ---------------------------------------------------------------------------
# Option / Availability (spec 02-TYPE-SYSTEM §8)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Some(Generic[T]):
    value: T


@dataclass(frozen=True)
class Unavailable:
    reason: str = ""


Option = Union[Some[T], Unavailable]


def unwrap_or_raise(opt: Option[T]) -> T:
    """Extract ``T`` from ``Some[T]`` or raise.

    ``Unavailable`` MUST NOT be silently coerced (constitution §6).
    This helper raises rather than returning a default; callers who
    want a default MUST provide it explicitly.
    """

    if isinstance(opt, Some):
        return opt.value
    raise ValueError(f"unwrap on Unavailable: {opt.reason!r}")


# ---------------------------------------------------------------------------
# Placeholder references
# ---------------------------------------------------------------------------
# ``ClockPositionRef`` is imported lazily by consumers to avoid an
# import cycle with ``aeon.clock``. We provide a lightweight alias
# here to make ``Certificate`` self-contained at import time.
ClockPositionRef = Tuple[str, int]
