"""aeon.types — the Aeon static type surface.

Implements the type categories from ``02-TYPE-SYSTEM.md`` and the
Phase 0.1 §4.1 required list. The types here are pure value
descriptors; the compiler and runtime consult them via
:mod:`aeon.types` rather than via Python's built-in ``isinstance``.

The types are:

- Kind marker: :class:`Kind` (VALUE, STATE, SIGNAL, PORT,
  CAPABILITY, CONTRACT, CERTIFICATE, CLOCK, SHAPE).
- Category atoms: Bool, Integer, Float, Fixed, ExactRational,
  Probability.
- Bounded / interval qualifiers.
- Vector, Matrix, Tensor.
- Compound types: State<T, Owner, Clock>, Signal<T, Clock>,
  Frame<T, Clock>, Port<In, Out>, Capability<Version>,
  Contract<T>, Certificate<T>, Result<T, E>, Window<Src, Tgt>.
- Clock aliases.

Every type provides:

- ``name``: the nominal identifier;
- ``kind``: the Kind marker;
- ``params``: any type parameters;
- ``matches``: structural compatibility test;
- ``to_canonical``: canonical dict form for the IR.

Convertibility rules (Phase 0.1 §4.3) are exposed through
:func:`can_convert` / :func:`convert_kind`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional, Sequence, Tuple


class Kind(Enum):
    VALUE = "*"
    STATE = "State"
    SIGNAL = "Signal"
    PORT = "Port"
    CAPABILITY = "Capability"
    CONTRACT = "Contract"
    CERTIFICATE = "Certificate"
    CLOCK = "Clock"
    SHAPE = "Shape"


@dataclass(frozen=True)
class AeonType:
    name: str
    kind: Kind = Kind.VALUE
    params: Tuple[Any, ...] = ()

    def to_canonical(self) -> dict:
        return {"name": self.name, "kind": self.kind.value,
                "params": [_param_canonical(p) for p in self.params]}

    def matches(self, other: "AeonType") -> bool:
        """Structural type equivalence (nominal + params)."""
        return (self.name == other.name
                and self.kind is other.kind
                and _params_match(self.params, other.params))


def _param_canonical(p: Any) -> Any:
    if isinstance(p, AeonType):
        return p.to_canonical()
    if isinstance(p, (list, tuple)):
        return [_param_canonical(x) for x in p]
    if isinstance(p, dict):
        return {k: _param_canonical(v) for k, v in p.items()}
    return p


def _params_match(a: Tuple[Any, ...], b: Tuple[Any, ...]) -> bool:
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if isinstance(x, AeonType) and isinstance(y, AeonType):
            if not x.matches(y):
                return False
        elif x != y:
            return False
    return True


# ---------------------------------------------------------------------------
# Atoms
# ---------------------------------------------------------------------------


BOOL = AeonType("Bool")
INTEGER = AeonType("Integer")
EXACT_RATIONAL = AeonType("ExactRational")
PROBABILITY = AeonType("Probability")


def Float(precision: str = "f64") -> AeonType:
    return AeonType("Float", params=(precision,))


def Fixed(scale: int, width: int) -> AeonType:
    return AeonType("Fixed", params=(int(scale), int(width)))


# ---------------------------------------------------------------------------
# Qualifiers
# ---------------------------------------------------------------------------


def Interval(bound_type: AeonType) -> AeonType:
    return AeonType("Interval", params=(bound_type,))


def Bounded(lo: float, hi: float, element: AeonType) -> AeonType:
    if hi <= lo:
        raise ValueError("Bounded requires lo < hi")
    return AeonType("Bounded", params=(float(lo), float(hi), element))


# ---------------------------------------------------------------------------
# Tensor family
# ---------------------------------------------------------------------------


def Vector(element: AeonType, n) -> AeonType:
    return AeonType("Vector", params=(element, n))


def Matrix(element: AeonType, rows, cols) -> AeonType:
    return AeonType("Matrix", params=(element, rows, cols))


def Tensor(element: AeonType, shape: Sequence[Any]) -> AeonType:
    return AeonType("Tensor", params=(element, tuple(shape)))


# ---------------------------------------------------------------------------
# Compound types
# ---------------------------------------------------------------------------


def State(payload: AeonType, owner: str, clock: str) -> AeonType:
    return AeonType("State", kind=Kind.STATE, params=(payload, owner, clock))


def Signal(payload: AeonType, clock: str) -> AeonType:
    return AeonType("Signal", kind=Kind.SIGNAL, params=(payload, clock))


def Frame(payload: AeonType, clock: str) -> AeonType:
    return AeonType("Frame", kind=Kind.SIGNAL, params=(payload, clock))


def Port(input: AeonType, output: AeonType) -> AeonType:
    return AeonType("Port", kind=Kind.PORT, params=(input, output))


def Capability(version: str) -> AeonType:
    return AeonType("Capability", kind=Kind.CAPABILITY, params=(version,))


def Contract(subject: AeonType) -> AeonType:
    return AeonType("Contract", kind=Kind.CONTRACT, params=(subject,))


def Certificate(subject: AeonType) -> AeonType:
    return AeonType("Certificate", kind=Kind.CERTIFICATE, params=(subject,))


def Result(ok: AeonType, err: AeonType) -> AeonType:
    return AeonType("Result", params=(ok, err))


def Window(src_clock: str, tgt_clock: str) -> AeonType:
    return AeonType("Window", kind=Kind.CLOCK, params=(src_clock, tgt_clock))


IDENTITY = AeonType("Identity")
CLOCK_DOMAIN = AeonType("ClockDomain", kind=Kind.CLOCK)
CLOCK_POSITION = AeonType("ClockPosition", kind=Kind.CLOCK)


# ---------------------------------------------------------------------------
# Convertibility
# ---------------------------------------------------------------------------


class Convertibility(Enum):
    LOSSLESS = "lossless"      # implicit
    LOSSY = "lossy"            # explicit
    PROHIBITED = "prohibited"  # not permitted implicitly or explicitly


_FLOAT_ORDER = {"f16": 0, "bf16": 0, "f32": 1, "f64": 2}


def can_convert(src: AeonType, dst: AeonType) -> Convertibility:
    """Return the convertibility of ``src`` to ``dst``.

    Rules encode Phase 0.1 §4.3:
    - lossless: widen precision.
    - lossy: narrow precision, integer -> float f32, float -> integer, etc.
    - prohibited: kind mismatches, state/signal cross-type.
    """

    # Identical types are trivially lossless.
    if src.matches(dst):
        return Convertibility.LOSSLESS

    # Kind mismatch is prohibited.
    if src.kind is not dst.kind:
        return Convertibility.PROHIBITED

    # Vector shape unification: a ``None`` dim on either side is a
    # shape variable and matches any concrete dim losslessly.
    if src.name == "Vector" and dst.name == "Vector":
        # element must match
        se, sd = src.params[0], dst.params[0]
        if isinstance(se, AeonType) and isinstance(sd, AeonType) and not se.matches(sd):
            return Convertibility.PROHIBITED
        s_dim, d_dim = src.params[1], dst.params[1]
        if s_dim is None or d_dim is None or s_dim == d_dim:
            return Convertibility.LOSSLESS
        return Convertibility.PROHIBITED

    # Float precision widening/narrowing.
    if src.name == "Float" and dst.name == "Float":
        sp = _FLOAT_ORDER.get(str(src.params[0]) if src.params else "f64", 2)
        dp = _FLOAT_ORDER.get(str(dst.params[0]) if dst.params else "f64", 2)
        if dp > sp:
            return Convertibility.LOSSLESS
        if dp < sp:
            return Convertibility.LOSSY
        return Convertibility.LOSSLESS

    # Integer -> Float is lossy (rounding possible past 2^53).
    if src.name == "Integer" and dst.name == "Float":
        return Convertibility.LOSSY

    # Integer -> ExactRational is lossless.
    if src.name == "Integer" and dst.name == "ExactRational":
        return Convertibility.LOSSLESS

    # Float -> Integer is lossy (truncation).
    if src.name == "Float" and dst.name == "Integer":
        return Convertibility.LOSSY

    # Probability -> Float is lossless (Probability is a Float-valued
    # bounded [0,1] type).
    if src.name == "Probability" and dst.name == "Float":
        return Convertibility.LOSSLESS

    # Float -> Probability is lossy (must runtime-check bounds).
    if src.name == "Float" and dst.name == "Probability":
        return Convertibility.LOSSY

    # Bounded<T> -> T is lossless.
    if src.name == "Bounded" and len(src.params) == 3 and src.params[2].matches(dst):
        return Convertibility.LOSSLESS

    # Everything else across nominal boundaries is prohibited.
    return Convertibility.PROHIBITED
