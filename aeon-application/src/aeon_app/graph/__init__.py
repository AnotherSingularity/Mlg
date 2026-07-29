"""aeon_app.graph — typed application graph + canonical IR compile."""

from .builder import (
    ApplicationEdge,
    ApplicationGraph,
    ApplicationNode,
    build_from_config,
    compile_to_ir,
)

__all__ = [
    "ApplicationGraph",
    "ApplicationNode",
    "ApplicationEdge",
    "build_from_config",
    "compile_to_ir",
]
