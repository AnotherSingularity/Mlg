"""Pytest bootstrap for the aeon-application test suite.

Puts both the application source tree and the Aeon Language
subsystem on sys.path so tests can import `aeon_app.*` and
`aeon.*` without an installed package.
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.abspath(os.path.join(HERE, ".."))
REPO_ROOT = os.path.abspath(os.path.join(APP_ROOT, ".."))
LANG_ROOT = os.path.join(REPO_ROOT, "aeon-language")

for p in (
    os.path.join(APP_ROOT, "src"),                   # aeon_app package
    os.path.join(LANG_ROOT, "standard_library"),     # aeon package
    LANG_ROOT,                                       # compiler / runtime / backends
):
    if p not in sys.path:
        sys.path.insert(0, p)
