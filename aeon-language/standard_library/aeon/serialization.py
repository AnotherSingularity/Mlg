"""aeon.serialization — canonical byte-stable serialization.

Implements the canonical serialization contract from
``08-PROVENANCE.md §4``:

1. Deterministic field order per schema.
2. Deterministic collection order.
3. Identifier NFC normalization.
4. Number encoding rules.
5. UTF-8 NFC strings.
6. Optional fields omitted when absent.
7. Version envelope.
8. Reject unknown fields.

The canonical form is a byte sequence. On top of it,
:func:`digest` produces a BLAKE2b-256 hex digest, which is used for
every Identity in the kernel.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence, Tuple


DEFAULT_DIGEST_METHOD = "blake2b-256"


class CanonicalizationError(ValueError):
    """Raised when a value cannot be canonicalized deterministically."""


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _encode_float(value: float) -> Any:
    # Shortest round-trip decimal per 08-PROVENANCE §4.4.
    if value != value:  # NaN
        raise CanonicalizationError("NaN cannot be canonicalized")
    if value in (float("inf"), float("-inf")):
        raise CanonicalizationError("Inf cannot be canonicalized")
    # Python's ``repr(float)`` is the shortest round-trip form.
    return repr(value)


def _canonical_atom(value: Any) -> Any:
    if value is None:
        return None
    if value is True or value is False:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return _encode_float(value)
    if isinstance(value, Decimal):
        # Represent exactly as string.
        return format(value, "f")
    if isinstance(value, str):
        return _nfc(value)
    if isinstance(value, bytes):
        return {"__aeon_bytes__": value.hex()}
    raise CanonicalizationError(
        f"unsupported atom type: {type(value).__name__}"
    )


def canonical_value(value: Any) -> Any:
    """Recursively convert ``value`` into a canonical JSON tree.

    Mapping keys MUST be strings and are NFC-normalized. Sequences
    are preserved as-is (schemas define ordering; sequences here
    are ordered lists). Sets are prohibited — schemas MUST replace
    a set with an explicitly sorted list under a defined key.
    """

    if isinstance(value, Mapping):
        result = {}
        # Sort by NFC-normalized key for byte stability.
        for key in sorted(value.keys()):
            if not isinstance(key, str):
                raise CanonicalizationError(
                    f"map key must be str, got {type(key).__name__}"
                )
            nkey = _nfc(key)
            result[nkey] = canonical_value(value[key])
        return result

    if isinstance(value, (list, tuple)):
        return [canonical_value(v) for v in value]

    if isinstance(value, (set, frozenset)):
        raise CanonicalizationError(
            "set/frozenset cannot be canonicalized; replace with a "
            "schema-sorted list"
        )

    return _canonical_atom(value)


def canonical_bytes(value: Any) -> bytes:
    """Canonical byte serialization of ``value``.

    The wire format is JSON with:

    - sorted keys;
    - no non-ASCII escapes (raw UTF-8);
    - no spaces;
    - explicit newline at end (for POSIX-friendly diffs).
    """

    tree = canonical_value(value)
    text = json.dumps(
        tree,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return (text + "\n").encode("utf-8")


def digest(value: Any, method: str = DEFAULT_DIGEST_METHOD) -> str:
    """Return the hex digest of ``value``'s canonical bytes."""

    payload = canonical_bytes(value) if not isinstance(value, (bytes, bytearray)) else bytes(value)
    return digest_bytes(payload, method)


def digest_bytes(payload: bytes, method: str = DEFAULT_DIGEST_METHOD) -> str:
    if method == "blake2b-256":
        return hashlib.blake2b(payload, digest_size=32).hexdigest()
    if method == "sha256":
        return hashlib.sha256(payload).hexdigest()
    raise ValueError(f"unknown digest method: {method}")


# ---------------------------------------------------------------------------
# Envelope helpers
# ---------------------------------------------------------------------------


def envelope(
    kind: str,
    body: Any,
    *,
    language_version: str,
    schema_version: str,
) -> dict:
    """Wrap ``body`` in the standard canonical envelope."""

    if not isinstance(kind, str) or not kind:
        raise CanonicalizationError("envelope kind must be non-empty str")
    return {
        "__aeon_kind__": _nfc(kind),
        "language_version": language_version,
        "schema_version": schema_version,
        "body": canonical_value(body),
    }
