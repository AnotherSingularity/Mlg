"""aeon_app.certified — authoritative certified-execution surface.

L15 makes ``CERTIFIED`` the application's default runtime mode.
This module owns everything that distinguishes certified execution
from REFERENCE / DEVELOPMENT:

- the frozen certified configuration digest, semantic-graph digest,
  and canonical-IR digest — computed at freeze time and checked
  at every certified startup;
- ``CertifiedStartupResult`` — the structured, canonical result
  of certified startup verification;
- ``verify_certified_startup(config)`` — the single startup gate;
  raises ``CertifiedStartupError`` on any mismatch and MUST NOT be
  caught to downgrade to another mode;
- ``certified_config()`` — the authoritative factory for the
  CERTIFIED runtime-mode config.

No source or Recursion state may be initialized before this
module reports valid=True (mandate §L15.2.4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

from aeon.serialization import canonical_value, digest

from .. import (
    AEON_LANGUAGE_CERTIFIED_COMMIT,
    AEON_LANGUAGE_REQUIRED_VERSION,
    APPLICATION_SNAPSHOT_SCHEMA_VERSION,
    APPLICATION_VERSION,
)


DEFAULT_RUNTIME_MODE = "CERTIFIED"
CERTIFIED_ACTIVATION_VERSION = "0.1.0"


# ---------------------------------------------------------------------------
# Frozen certified identities.
# These values are computed at freeze time from the certified config /
# semantic graph / canonical IR of the certified activation head, and
# are re-checked on every certified startup. Any drift means either
# the frozen values need re-freezing (semantic change, not permitted
# outside a versioned activation revision) or the runtime code has
# been tampered with.
# ---------------------------------------------------------------------------


CERTIFIED_CONFIG_DIGEST = (
    "5cd0371f157fe9dd921c45b888ece3228aee7f9b3a247968e6c7714fdb88753d"
)
CERTIFIED_SEMANTIC_DIGEST = (
    "4c4fae2b986bf3ba710e2c22ee0573c0b41fa35d15eb86fcacd7e4db7984d05c"
)
CERTIFIED_GRAPH_ID = (
    "dbbb6c3bb2a7ee1e6d4945b6509cefaee2a77c92918237fa8098d66c05dac565"
)
CERTIFIED_IR_MODULE_ID = (
    "9cf9ce5377d7f81e6382cc6aa4d647f2ee585818417cfefdb02b608e26f5ad76"
)
CERTIFIED_INSTRUCTION_COUNT = 21
CERTIFIED_BACKEND_ID = "python"


# ---------------------------------------------------------------------------
# Startup result and error
# ---------------------------------------------------------------------------


class CertifiedStartupError(Exception):
    """Raised when certified startup verification fails.

    CATCHING this exception to run the application under a different
    runtime mode is expressly forbidden by mandate §L15.2.3. If a
    caller wants to run under REFERENCE or DEVELOPMENT after a
    certified startup failure, that caller MUST issue a brand new
    startup, chosen explicitly, in a fresh process invocation.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code


@dataclass(frozen=True)
class CertifiedStartupResult:
    valid: bool
    application_version: str
    language_version: str
    language_commit: str
    graph_digest: str
    ir_digest: str
    configuration_digest: str
    backend: str
    checks: Mapping[str, bool]
    failure_reason: Optional[str] = None

    def to_canonical(self) -> dict:
        return canonical_value({
            "valid": self.valid,
            "application_version": self.application_version,
            "language_version": self.language_version,
            "language_commit": self.language_commit,
            "graph_digest": self.graph_digest,
            "ir_digest": self.ir_digest,
            "configuration_digest": self.configuration_digest,
            "backend": self.backend,
            "checks": dict(sorted(self.checks.items())),
            "failure_reason": self.failure_reason,
        })

    def digest(self) -> str:
        return digest(self.to_canonical())


# ---------------------------------------------------------------------------
# Certified configuration factory
# ---------------------------------------------------------------------------


def certified_config():
    """Return the frozen certified ApplicationConfig.

    This is the single authoritative certified configuration.
    It is derived from the reference topology (same components,
    same clocks, same feedback gates — feedback remains at the
    approved zero-gate value per mandate §L15.2.5) with
    ``runtime_mode='CERTIFIED'`` and the certified backend pin.

    Import is deferred to avoid a cycle between the config
    package and this module.
    """
    from dataclasses import replace
    from ..config import reference_config
    base = reference_config()
    return replace(base,
                   runtime_mode="CERTIFIED",
                   backend=replace(base.backend, id=CERTIFIED_BACKEND_ID))


def default_config():
    """The application-wide default configuration.

    Every entry point that does not explicitly specify a runtime
    mode reaches for this. It is the single authoritative source
    of the DEFAULT_RUNTIME_MODE choice.
    """
    return certified_config()


# ---------------------------------------------------------------------------
# Runtime-mode parsing
# ---------------------------------------------------------------------------


SUPPORTED_RUNTIME_MODES: Tuple[str, ...] = ("REFERENCE", "DEVELOPMENT", "CERTIFIED")


def parse_runtime_mode(value: Optional[str]) -> str:
    """Return the exact runtime mode identifier or raise.

    ``None`` resolves to ``DEFAULT_RUNTIME_MODE``. Unknown strings
    raise ``CertifiedStartupError`` — the mandate forbids ambiguous
    prefixes and spelling corrections.
    """
    if value is None:
        return DEFAULT_RUNTIME_MODE
    if value not in SUPPORTED_RUNTIME_MODES:
        raise CertifiedStartupError(
            "UNKNOWN_RUNTIME_MODE",
            f"unsupported runtime mode {value!r}; "
            f"choose one of {SUPPORTED_RUNTIME_MODES}",
        )
    return value


# ---------------------------------------------------------------------------
# Startup verification
# ---------------------------------------------------------------------------


def verify_certified_startup(config) -> CertifiedStartupResult:
    """Perform the L15 startup-verification gate.

    Runs the strict certified-startup checks demanded by mandate
    §L15.2.4. On success returns a ``CertifiedStartupResult`` with
    ``valid=True`` and per-check flags. On failure raises
    ``CertifiedStartupError`` — callers MUST NOT catch this to
    downgrade to another mode.

    This function initializes NO source or Recursion state. It is
    a pre-flight gate.
    """
    from aeon import LANGUAGE_VERSION
    from ..config import ConfigError, resolve
    from ..config.language_lock import LanguageLockError, verify_language_lock
    from ..graph import build_from_config, compile_to_ir

    checks = {}
    failure_reason = None

    def fail(code, message):
        raise CertifiedStartupError(code, message)

    if config.runtime_mode != "CERTIFIED":
        fail("STARTUP_NON_CERTIFIED_MODE",
             f"verify_certified_startup requires runtime_mode='CERTIFIED', "
             f"got {config.runtime_mode!r}")
    checks["runtime_mode_is_certified"] = True

    # Reject unknown modes / unknown required fields via config resolver.
    try:
        config = resolve(config)
    except ConfigError as e:
        fail("STARTUP_CONFIG_INVALID", f"{e}")
    checks["configuration_resolves"] = True

    # Reject experimental / development-only backend identities from
    # certified execution.
    if config.backend.id != CERTIFIED_BACKEND_ID:
        fail("STARTUP_BACKEND_MISMATCH",
             f"certified backend must be {CERTIFIED_BACKEND_ID!r}; "
             f"got {config.backend.id!r}")
    checks["backend_matches"] = True

    # Language lock must load and verify against the loaded aeon
    # package identity.
    try:
        lock = verify_language_lock()
    except LanguageLockError as e:
        fail("STARTUP_LANGUAGE_LOCK_FAILED", f"{e}")
    checks["language_lock_verified"] = True

    if lock.language_version != AEON_LANGUAGE_REQUIRED_VERSION:
        fail("STARTUP_LANGUAGE_VERSION_MISMATCH",
             f"lock={lock.language_version!r}, "
             f"pin={AEON_LANGUAGE_REQUIRED_VERSION!r}")
    if lock.certified_commit != AEON_LANGUAGE_CERTIFIED_COMMIT:
        fail("STARTUP_LANGUAGE_COMMIT_MISMATCH",
             f"lock={lock.certified_commit!r}, "
             f"pin={AEON_LANGUAGE_CERTIFIED_COMMIT!r}")
    if LANGUAGE_VERSION != AEON_LANGUAGE_REQUIRED_VERSION:
        fail("STARTUP_LOADED_LANGUAGE_MISMATCH",
             f"loaded aeon.LANGUAGE_VERSION={LANGUAGE_VERSION!r}, "
             f"application pin={AEON_LANGUAGE_REQUIRED_VERSION!r}")
    checks["language_identity_matches"] = True

    # Configuration digest must equal the frozen certified value.
    cfg_digest = config.digest()
    if cfg_digest != CERTIFIED_CONFIG_DIGEST:
        fail("STARTUP_CONFIG_DIGEST_MISMATCH",
             f"live={cfg_digest!r}, frozen={CERTIFIED_CONFIG_DIGEST!r}")
    checks["configuration_digest_matches"] = True

    # Build the semantic graph deterministically and compare.
    graph = build_from_config(config)
    if graph.graph_id != CERTIFIED_GRAPH_ID:
        fail("STARTUP_GRAPH_DIGEST_MISMATCH",
             f"live={graph.graph_id!r}, frozen={CERTIFIED_GRAPH_ID!r}")
    checks["graph_digest_matches"] = True

    # Compile the canonical IR deterministically and compare.
    ir = compile_to_ir(config, graph)
    if ir.module_id != CERTIFIED_IR_MODULE_ID:
        fail("STARTUP_IR_DIGEST_MISMATCH",
             f"live={ir.module_id!r}, frozen={CERTIFIED_IR_MODULE_ID!r}")
    if len(ir.instructions) != CERTIFIED_INSTRUCTION_COUNT:
        fail("STARTUP_IR_INSTRUCTION_COUNT_MISMATCH",
             f"live={len(ir.instructions)}, "
             f"frozen={CERTIFIED_INSTRUCTION_COUNT}")
    checks["ir_digest_matches"] = True

    # Snapshot + certificate schema versions.
    if APPLICATION_SNAPSHOT_SCHEMA_VERSION != "0.1.0":
        fail("STARTUP_SNAPSHOT_SCHEMA_MISMATCH",
             f"expected 0.1.0, got {APPLICATION_SNAPSHOT_SCHEMA_VERSION!r}")
    if lock.certificate_schema != "0.1.0":
        fail("STARTUP_CERTIFICATE_SCHEMA_MISMATCH",
             f"expected 0.1.0, got {lock.certificate_schema!r}")
    checks["snapshot_and_certificate_schema_ok"] = True

    # Reject any REQUIRED capability that would not be satisfied.
    # (Full negotiation happens inside new_session; here we ensure
    # every declared source implementation is one of the certified
    # implementations. Experimental / unknown implementations are
    # rejected fail-closed.)
    for s in config.sources:
        if s.implementation not in _CERTIFIED_SOURCE_IMPLEMENTATIONS:
            fail("STARTUP_EXPERIMENTAL_SOURCE_REJECTED",
                 f"source {s.component_id}: implementation "
                 f"{s.implementation!r} is not certified")
    for p in config.projections:
        if p.implementation not in _CERTIFIED_PROJECTION_IMPLEMENTATIONS:
            fail("STARTUP_EXPERIMENTAL_PROJECTION_REJECTED",
                 f"projection {p.component_id}: implementation "
                 f"{p.implementation!r} is not certified")
    checks["no_experimental_components"] = True

    return CertifiedStartupResult(
        valid=True,
        application_version=APPLICATION_VERSION,
        language_version=lock.language_version,
        language_commit=lock.certified_commit,
        graph_digest=graph.graph_id,
        ir_digest=ir.module_id,
        configuration_digest=cfg_digest,
        backend=config.backend.id,
        checks=dict(checks),
        failure_reason=None,
    )


# ---------------------------------------------------------------------------
# Certified component allow-lists.
#
# Certified execution refuses any source or projection implementation
# not on this list. This is the mandate §L15.2.2 "reject experimental
# components" gate.
# ---------------------------------------------------------------------------


_CERTIFIED_SOURCE_IMPLEMENTATIONS = frozenset({
    "aeon_app.sources.attention:AttentionSource",
    "aeon_app.sources.recurrent:PersistentRecurrentSource",
})


_CERTIFIED_PROJECTION_IMPLEMENTATIONS = frozenset({
    "aeon_app.projections.attention_to_recursion:AttentionToRecursion",
    "aeon_app.projections.recurrent_to_recursion:RecurrentToRecursion",
    "aeon_app.projections.feedback:RecursionToAttentionFeedback",
    "aeon_app.projections.feedback:RecursionToRecurrentFeedback",
})


__all__ = [
    "DEFAULT_RUNTIME_MODE",
    "CERTIFIED_ACTIVATION_VERSION",
    "CERTIFIED_CONFIG_DIGEST",
    "CERTIFIED_SEMANTIC_DIGEST",
    "CERTIFIED_GRAPH_ID",
    "CERTIFIED_IR_MODULE_ID",
    "CERTIFIED_INSTRUCTION_COUNT",
    "CERTIFIED_BACKEND_ID",
    "SUPPORTED_RUNTIME_MODES",
    "CertifiedStartupError",
    "CertifiedStartupResult",
    "certified_config",
    "default_config",
    "parse_runtime_mode",
    "verify_certified_startup",
]
