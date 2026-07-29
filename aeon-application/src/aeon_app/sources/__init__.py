"""aeon_app.sources — application-scoped signal sources."""

from .attention import AttentionSource, AttentionSourceState
from .recurrent import PersistentRecurrentSource, RecurrentSourceState

__all__ = [
    "AttentionSource",
    "AttentionSourceState",
    "PersistentRecurrentSource",
    "RecurrentSourceState",
]
