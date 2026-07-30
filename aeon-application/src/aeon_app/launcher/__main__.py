"""Entry point for ``python -m aeon_app.launcher``."""

from __future__ import annotations

import sys

from . import main


if __name__ == "__main__":
    sys.exit(main())
