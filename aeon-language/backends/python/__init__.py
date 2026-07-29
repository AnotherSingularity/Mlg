"""Aeon Python host backend.

The Python backend is a thin adapter that runs the reference
interpreter directly on pure Python values. It is the smallest
possible backend and serves as the parity reference against which
other backends (PyTorch, CUDA, ...) are compared.

Public surface:

- :class:`PythonBackend` wraps :class:`runtime.interpreter.Interpreter`
  and exposes ``execute(module, sources, substrates, seed)``.
- :class:`PythonBackendInfo` describes this backend for the
  `aeontest` CLI's backend-parity harness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from aeon.ir import IRModule
from aeon.port import SignalSourcePort
from aeon.recursion import RecursionSubstrate
from runtime.interpreter import ExecutionOutcome, Interpreter


@dataclass(frozen=True)
class PythonBackendInfo:
    name: str = "aeon.backends.python"
    version: str = "0.1.0-dev"
    numerical_tolerance: float = 0.0  # bit-exact per element on Python floats


class PythonBackend:
    info = PythonBackendInfo()

    def execute(
        self,
        module: IRModule,
        *,
        sources: Mapping[str, SignalSourcePort[Any]],
        substrates: Mapping[str, RecursionSubstrate],
        seed: int = 0,
    ) -> ExecutionOutcome:
        return Interpreter(module, sources=sources, substrates=substrates, seed=seed).run()
