"""Entry point for ``python -m aeon_app.conformance``."""

from __future__ import annotations

import sys

from . import _main


if __name__ == "__main__":
    sys.exit(_main())
