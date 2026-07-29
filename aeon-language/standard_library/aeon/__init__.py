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
    "SOURCE_GRAMMAR_VERSION",
    "CERTIFICATE_SCHEMA_VERSION",
    "SNAPSHOT_SCHEMA_VERSION",
    "CONFORMANCE_PROFILE_VERSION",
    "BACKEND_CONTRACT_VERSION",
    "MIGRATION_FRAMEWORK_VERSION",
]

# --- Aeon Language v0.1.0 ---
# Single authoritative version constants. Every artifact envelope,
# every schema, every backend, and the migration framework MUST
# derive its version tag from here.
LANGUAGE_VERSION = "0.1.0"
IR_VERSION = "0.1.0"
INSTRUCTION_SET_VERSION = "0.1.0"
STDLIB_VERSION = "0.1.0"
SOURCE_GRAMMAR_VERSION = "0.1.0"
CERTIFICATE_SCHEMA_VERSION = "0.1.0"
SNAPSHOT_SCHEMA_VERSION = "0.1.0"
CONFORMANCE_PROFILE_VERSION = "0.1.0"
BACKEND_CONTRACT_VERSION = "0.1.0"
MIGRATION_FRAMEWORK_VERSION = "0.1.0"
