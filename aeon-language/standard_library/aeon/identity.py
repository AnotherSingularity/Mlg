"""aeon.identity — the identity subsystem's public surface.

Re-exports identity constructors from :mod:`aeon.provenance` under
the module name required by mandate §17. New code SHOULD import
from ``aeon.identity`` rather than from ``aeon.provenance``; both
resolve to the same underlying implementation.
"""

from __future__ import annotations

from .core import Identity
from .provenance import (
    graph_id,
    make_identity,
    node_id,
    signal_id,
    snapshot_id,
    state_id,
    transition_id,
    window_id,
)
from .serialization import DEFAULT_DIGEST_METHOD, digest, digest_bytes

__all__ = [
    "DEFAULT_DIGEST_METHOD",
    "Identity",
    "digest",
    "digest_bytes",
    "graph_id",
    "make_identity",
    "node_id",
    "signal_id",
    "snapshot_id",
    "state_id",
    "transition_id",
    "window_id",
]
