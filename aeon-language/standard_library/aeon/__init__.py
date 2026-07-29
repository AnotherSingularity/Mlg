"""Aeon framework-neutral standard library.

This package is the framework-neutral semantic kernel of the Aeon
Language. It MUST NOT import PyTorch, NumPy, CUDA bindings, or any
other numerical framework. Backend integrations belong under
``aeon.backends``.

The kernel's semantics are governed by the documents in
``aeon-language/specification/``. This code is one reference
implementation; it does not define the language.
"""

__all__ = [
    "LANGUAGE_VERSION",
    "IR_VERSION",
    "INSTRUCTION_SET_VERSION",
    "STDLIB_VERSION",
]

LANGUAGE_VERSION = "0.1.0-dev"
IR_VERSION = "0.1.0-dev"
INSTRUCTION_SET_VERSION = "0.1.0-dev"
STDLIB_VERSION = "0.1.0-dev"
