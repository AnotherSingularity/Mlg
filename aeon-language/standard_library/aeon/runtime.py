"""aeon.runtime — public runtime surface.

Re-exports the reference interpreter, scheduler, and replay driver
from the ``runtime`` package (top-level in the repo) under the
mandate §17 module name. Backend adapters use this module rather
than reaching into the repo-relative ``runtime.`` package.
"""

from __future__ import annotations

# Deferred import so the framework-neutral kernel can be imported
# even if the runtime package is not on sys.path (backends and CLI
# tools always add it).

def load():
    """Return a small dict of the runtime entry points."""
    from runtime.interpreter import ExecutionOutcome, Interpreter, TraceEntry
    from runtime.replay import ReplayReport, replay
    from runtime.scheduler import lower
    return {
        "Interpreter": Interpreter,
        "ExecutionOutcome": ExecutionOutcome,
        "TraceEntry": TraceEntry,
        "lower": lower,
        "replay": replay,
        "ReplayReport": ReplayReport,
    }


__all__ = ["load"]
