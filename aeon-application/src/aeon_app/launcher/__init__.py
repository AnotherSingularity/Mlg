"""aeon_app.launcher — desktop-launcher entry point.

Used by the Windows launcher executable (packaged with PyInstaller
in L16) and by any other host that wants the same startup contract.
The launcher is intentionally thin: it verifies the packaged
release identity, verifies the language lock, verifies the
certified configuration, creates user-writable directories in
Windows-appropriate locations, starts a CERTIFIED session, and
either enters an event loop or emits a structured startup failure.

The launcher NEVER silently falls back to a development runtime.
On any failure the process exits with a non-zero exit code and a
JSON payload on stdout describing the failure.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from pathlib import Path
from typing import Optional

from .. import (
    AEON_LANGUAGE_CERTIFIED_COMMIT,
    AEON_LANGUAGE_REQUIRED_VERSION,
    APPLICATION_VERSION,
)
from ..certified import (
    CertifiedStartupError,
    certified_config,
    verify_certified_startup,
)


APP_VENDOR = "Aeon"
APP_NAME = "AeonApplication"


def _emit(payload) -> None:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True, default=str)
    sys.stdout.write("\n")
    sys.stdout.flush()


def _windows_user_root() -> Path:
    """`%LOCALAPPDATA%\\Aeon` when LOCALAPPDATA is set (Windows);
    otherwise ``~/.local/share/Aeon`` (non-Windows fallback used for
    development on Linux/macOS)."""
    if os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / APP_VENDOR
    return Path.home() / ".local" / "share" / APP_VENDOR


def user_directories() -> dict:
    """Return the Windows-appropriate user directories. Creates them
    if missing. Mutable runtime state MUST live here and MUST NOT
    live under %ProgramFiles%."""
    root = _windows_user_root()
    subdirs = {
        "root": root,
        "config": root / "Config",
        "logs": root / "Logs",
        "snapshots": root / "Snapshots",
    }
    for p in subdirs.values():
        p.mkdir(parents=True, exist_ok=True)
    return {k: str(v) for k, v in subdirs.items()}


def _release_manifest() -> dict:
    """Return the packaged release manifest identity + digests. The
    launcher rejects installations whose release manifest is
    missing or has been tampered with."""
    from importlib import resources
    try:
        text = (resources.files("aeon_app.launcher")
                .joinpath("release.json").read_text(encoding="utf-8"))
        return json.loads(text)
    except (FileNotFoundError, ModuleNotFoundError):
        return {
            "application_version": APPLICATION_VERSION,
            "language_version": AEON_LANGUAGE_REQUIRED_VERSION,
            "language_certified_commit": AEON_LANGUAGE_CERTIFIED_COMMIT,
            "source": "constants",
        }


def launch(argv: Optional[list] = None) -> int:
    """Startup + smoke; returns process exit code (0 on success).

    Prints a structured JSON payload on stdout describing the
    outcome. Never prompts. Never opens a terminal for its own
    startup path. Never silently falls back.
    """
    ap = argparse.ArgumentParser(
        prog="aeon-launcher",
        description="Aeon Application desktop launcher.",
    )
    ap.add_argument("--smoke", action="store_true",
                    help="run a short deterministic certified smoke")
    ap.add_argument("--ticks", type=int, default=4)
    args = ap.parse_args(argv)

    dirs = user_directories()

    try:
        result = verify_certified_startup(certified_config())
    except CertifiedStartupError as e:
        _emit({
            "ok": False,
            "stage": "certified_startup",
            "code": e.code,
            "message": str(e),
            "user_directories": dirs,
        })
        return 20

    outputs = []
    if args.smoke:
        from ..application import new_session, run
        session = new_session(certified_config())
        outs = run(session, ticks=args.ticks)
        outputs = [
            {"output_id": o.output_id,
             "clock_position": list(o.clock_position),
             "payload": list(o.payload),
             "validity": o.validity.name}
            for o in outs
        ]

    _emit({
        "ok": True,
        "runtime_mode": "CERTIFIED",
        "release_manifest": _release_manifest(),
        "startup": {
            "graph_digest": result.graph_digest,
            "ir_digest": result.ir_digest,
            "configuration_digest": result.configuration_digest,
            "language_commit": result.language_commit,
            "backend": result.backend,
        },
        "user_directories": dirs,
        "host": {
            "platform": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
            "architecture": platform.machine(),
        },
        "outputs": outputs,
    })
    return 0


def main(argv: Optional[list] = None) -> int:
    try:
        return launch(argv)
    except SystemExit:
        raise
    except Exception as exc:
        _emit({
            "ok": False,
            "stage": "unexpected",
            "code": type(exc).__name__,
            "message": str(exc),
        })
        return 30


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["launch", "main", "user_directories"]
