"""Pytest configuration for the Aeon test suite.

Adds the standard_library and repo-relative compiler/runtime paths
to sys.path so tests can import ``aeon.*`` and ``compiler.*`` /
``runtime.*`` directly without an installed package.
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))

for p in (
    os.path.join(ROOT, "standard_library"),
    ROOT,
):
    if p not in sys.path:
        sys.path.insert(0, p)
