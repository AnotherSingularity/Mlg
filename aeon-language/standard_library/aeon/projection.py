"""aeon.projection — projection contracts and the reference projection.

Public surface for the projection subsystem, distinct from
:mod:`aeon.recursion` where the reference substrate lives.
"""

from __future__ import annotations

from .recursion import ManifoldInput, ProjectionContract, project_frame

__all__ = ["ManifoldInput", "ProjectionContract", "project_frame"]
