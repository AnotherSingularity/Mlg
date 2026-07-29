"""aeon.tensor — pure-Python tensor value type.

Backend-neutral. Not a NumPy or PyTorch tensor. Backends may
translate an :class:`AeonTensor` into their native representation
before executing an instruction; the kernel itself operates on
this value type only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence, Tuple

from .state import Shape


@dataclass(frozen=True)
class AeonTensor:
    """A shape-typed vector of floats stored as a Python tuple.

    Higher-rank tensors are represented as nested tuples of floats.
    The rank is fixed by ``shape``; construction validates the
    payload matches the shape.
    """

    shape: Shape
    payload: Tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.shape.is_concrete():
            raise ValueError("AeonTensor.shape must be concrete (no symbolic or variable dims)")
        expected = 1
        for d in self.shape.dims:
            expected *= int(d)
        if len(self.payload) != expected:
            raise ValueError(
                f"AeonTensor payload length {len(self.payload)} does not match "
                f"shape product {expected}"
            )
        for v in self.payload:
            if not isinstance(v, (int, float)):
                raise TypeError(f"AeonTensor payload must be numeric, got {type(v).__name__}")

    @classmethod
    def from_iterable(cls, iterable: Sequence[float], shape: Shape) -> "AeonTensor":
        return cls(shape=shape, payload=tuple(float(v) for v in iterable))


__all__ = ["AeonTensor"]
