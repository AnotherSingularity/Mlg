"""Entry point for ``python -m aeon_app.launcher`` and for the
PyInstaller-packaged ``aeon-launcher.exe``.

Uses an absolute import so PyInstaller's frozen entry (which
executes this file as a script without a parent package) works
the same as ``python -m aeon_app.launcher``.
"""

from __future__ import annotations

import sys

from aeon_app.launcher import main


if __name__ == "__main__":
    sys.exit(main())

