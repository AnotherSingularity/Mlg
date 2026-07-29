"""aeon.math — pure-Python numeric helpers used by the kernel.

This module is deliberately narrow. It provides only the
operations the framework-neutral kernel needs to describe and
verify Aeon transitions; it is not a general-purpose numerical
library.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence, Tuple


def l_inf(vector: Sequence[float]) -> float:
    return max((abs(x) for x in vector), default=0.0)


def l2(vector: Sequence[float]) -> float:
    return math.sqrt(sum(x * x for x in vector))


def is_finite(x: float) -> bool:
    return math.isfinite(x)


def all_finite(vector: Iterable[float]) -> bool:
    return all(math.isfinite(x) for x in vector)


def clamp(x: float, lo: float, hi: float) -> float:
    if hi < lo:
        raise ValueError("clamp: hi < lo")
    return max(lo, min(hi, x))


def dot(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"dot: length mismatch {len(a)} vs {len(b)}")
    return sum(x * y for x, y in zip(a, b))


__all__ = ["all_finite", "clamp", "dot", "is_finite", "l2", "l_inf"]
