"""aeon_app.cli — command-line surface for the Aeon Application.

Eight entry points, each corresponding to a single verb in the
launch-plan matrix:

- ``aeon-app-check``    validate the application config
- ``aeon-app-compile``  compile the config to canonical IR
- ``aeon-app-run``      execute deterministic inference for N ticks
- ``aeon-app-train``    run one or more deterministic training steps
- ``aeon-app-evaluate`` execute an evaluation profile
- ``aeon-app-snapshot`` write a snapshot to disk
- ``aeon-app-replay``   restore a snapshot and continue for N more ticks
- ``aeon-app-inspect``  dump the resolved config / graph identity

All commands operate on the reference application config by default.
A future release may add ``--config PATH`` loading of external
JSON configs; today the reference is the only shipped configuration
and the CLI is honest about that.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Callable, Optional, Sequence

from . import APPLICATION_VERSION


# ---------------------------------------------------------------------------
# Small formatting helpers
# ---------------------------------------------------------------------------


def _emit(obj) -> None:
    json.dump(obj, sys.stdout, indent=2, sort_keys=True, default=str)
    sys.stdout.write("\n")


def _reference_config(mode: Optional[str] = None):
    from .config import reference_config
    cfg = reference_config()
    if mode:
        cfg = replace(cfg, runtime_mode=mode)
    return cfg


def _add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--mode",
                   choices=("REFERENCE", "DEVELOPMENT", "CERTIFIED"),
                   default=None,
                   help="override runtime mode (default: config value)")


# ---------------------------------------------------------------------------
# aeon-app-check
# ---------------------------------------------------------------------------


def _cmd_check(args: argparse.Namespace) -> int:
    from .config import resolve, ConfigError
    from .config.language_lock import verify_language_lock
    cfg = _reference_config(args.mode)
    try:
        cfg = resolve(cfg)
    except ConfigError as e:
        _emit({"ok": False, "stage": "config",
               "code": e.code, "message": str(e)})
        return 2
    try:
        verify_language_lock()
    except Exception as e:
        _emit({"ok": False, "stage": "language_lock",
               "message": str(e)})
        return 3
    _emit({"ok": True,
           "application_version": APPLICATION_VERSION,
           "runtime_mode": cfg.runtime_mode,
           "config_digest": cfg.digest(),
           "semantic_digest": cfg.semantic_digest()})
    return 0


def app_check(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="aeon-app-check",
        description="Validate the application config + language lock.")
    _add_common_args(p)
    return _cmd_check(p.parse_args(argv))


# ---------------------------------------------------------------------------
# aeon-app-compile
# ---------------------------------------------------------------------------


def _cmd_compile(args: argparse.Namespace) -> int:
    from .config import resolve
    from .graph import build_from_config, compile_to_ir
    cfg = resolve(_reference_config(args.mode))
    graph = build_from_config(cfg)
    ir = compile_to_ir(cfg, graph)
    payload = {
        "graph_id": graph.graph_id,
        "ir_module_id": ir.module_id,
        "instruction_count": len(ir.instructions),
    }
    if args.out:
        Path(args.out).write_bytes(ir.to_bytes())
        payload["written"] = args.out
    _emit(payload)
    return 0


def app_compile(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="aeon-app-compile",
        description="Compile the application config to canonical IR.")
    _add_common_args(p)
    p.add_argument("--out", help="write the IR module bytes to PATH")
    return _cmd_compile(p.parse_args(argv))


# ---------------------------------------------------------------------------
# aeon-app-run
# ---------------------------------------------------------------------------


def _cmd_run(args: argparse.Namespace) -> int:
    from .application import new_session, run
    from .config import resolve
    cfg = resolve(_reference_config(args.mode))
    session = new_session(cfg)
    outputs = run(session, ticks=args.ticks)
    payload = {
        "graph_id": session.graph_id,
        "runtime_mode": cfg.runtime_mode,
        "ticks_executed": len(outputs),
        "outputs": [
            {
                "output_id": o.output_id,
                "clock_position": list(o.clock_position),
                "payload": list(o.payload),
                "validity": o.validity.name,
            }
            for o in outputs
        ],
    }
    _emit(payload)
    return 0


def app_run(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="aeon-app-run",
        description="Run deterministic inference for N ticks.")
    _add_common_args(p)
    p.add_argument("--ticks", type=int, default=None,
                   help="ticks to run (default: config.inference.ticks)")
    return _cmd_run(p.parse_args(argv))


# ---------------------------------------------------------------------------
# aeon-app-train
# ---------------------------------------------------------------------------


def _cmd_train(args: argparse.Namespace) -> int:
    from .training import make_reference_batch, make_training_session
    session = make_training_session(learning_rate=args.learning_rate)
    certs = []
    for i in range(args.steps):
        batch = make_reference_batch(seed=args.seed + i, ticks=args.ticks)
        certs.append(session.step(batch))
    _emit({
        "steps": len(certs),
        "final_optimizer_digest": session.optimizer.digest(),
        "certificates": [
            {
                "batch_digest": c.batch_digest,
                "loss_digest": c.loss_digest,
                "gradient_digest": c.gradient_digest,
                "updated_parameter_digest": c.updated_parameter_digest,
                "certificate_recheck_required": c.certificate_recheck_required,
            }
            for c in certs
        ],
    })
    return 0


def app_train(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="aeon-app-train",
        description="Run N deterministic training steps.")
    p.add_argument("--steps", type=int, default=1)
    p.add_argument("--ticks", type=int, default=4)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--learning-rate", type=float, default=1e-3)
    return _cmd_train(p.parse_args(argv))


# ---------------------------------------------------------------------------
# aeon-app-evaluate
# ---------------------------------------------------------------------------


def _cmd_evaluate(args: argparse.Namespace) -> int:
    from .evaluation import PROFILES, profile_manifest, run_profile
    if args.list:
        _emit({"profiles": [p.name for p in PROFILES],
               "manifest": profile_manifest()})
        return 0
    if not args.profile:
        _emit({"ok": False, "message": "--profile required (or use --list)"})
        return 2
    result = run_profile(args.profile)
    _emit(result)
    return 0 if result["passed"] else 1


def app_evaluate(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="aeon-app-evaluate",
        description="Run a named evaluation profile.")
    p.add_argument("--profile", help="profile name (see --list)")
    p.add_argument("--list", action="store_true",
                   help="list all profiles and print the manifest")
    return _cmd_evaluate(p.parse_args(argv))


# ---------------------------------------------------------------------------
# aeon-app-snapshot
# ---------------------------------------------------------------------------


def _cmd_snapshot(args: argparse.Namespace) -> int:
    from .application import new_session, run
    from .config import resolve
    cfg = resolve(_reference_config(args.mode))
    session = new_session(cfg)
    run(session, ticks=args.ticks)
    snap = session.snapshot()
    Path(args.out).write_bytes(snap.to_bytes())
    _emit({
        "written": args.out,
        "ticks_executed": args.ticks or cfg.inference.ticks,
        "snapshot_digest": snap.digest(),
        "graph_id": snap.graph_id,
        "config_digest": snap.config_digest,
    })
    return 0


def app_snapshot(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="aeon-app-snapshot",
        description="Run the application then write a snapshot to disk.")
    _add_common_args(p)
    p.add_argument("--out", required=True, help="snapshot output path")
    p.add_argument("--ticks", type=int, default=None,
                   help="ticks to run before snapshotting")
    return _cmd_snapshot(p.parse_args(argv))


# ---------------------------------------------------------------------------
# aeon-app-replay
# ---------------------------------------------------------------------------


def _cmd_replay(args: argparse.Namespace) -> int:
    from .application import restore, run
    from .config import resolve
    from .persistence import load_snapshot
    raw = Path(args.snapshot).read_bytes()
    snap = load_snapshot(raw)
    cfg = resolve(_reference_config(args.mode))
    session = restore(cfg, snap)
    outputs = run(session, ticks=args.ticks)
    _emit({
        "snapshot_digest": snap.digest(),
        "graph_id": session.graph_id,
        "resumed_at_tick": snap.clock_positions.get("source", 0),
        "additional_ticks": len(outputs),
        "outputs": [
            {
                "output_id": o.output_id,
                "clock_position": list(o.clock_position),
                "payload": list(o.payload),
            }
            for o in outputs
        ],
    })
    return 0


def app_replay(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="aeon-app-replay",
        description="Restore a snapshot and run additional ticks.")
    _add_common_args(p)
    p.add_argument("--snapshot", required=True, help="snapshot input path")
    p.add_argument("--ticks", type=int, default=None,
                   help="additional ticks to run (default: config.inference.ticks)")
    return _cmd_replay(p.parse_args(argv))


# ---------------------------------------------------------------------------
# aeon-app-inspect
# ---------------------------------------------------------------------------


def _cmd_inspect(args: argparse.Namespace) -> int:
    from .config import resolve
    from .graph import build_from_config, compile_to_ir
    cfg = resolve(_reference_config(args.mode))
    graph = build_from_config(cfg)
    ir = compile_to_ir(cfg, graph)
    payload = {
        "application_version": APPLICATION_VERSION,
        "runtime_mode": cfg.runtime_mode,
        "config_digest": cfg.digest(),
        "semantic_digest": cfg.semantic_digest(),
        "graph_id": graph.graph_id,
        "ir_module_id": ir.module_id,
        "instruction_count": len(ir.instructions),
        "sources": [s.component_id for s in cfg.sources],
        "projections": [p.component_id for p in cfg.projections],
        "recursion": cfg.recursion.component_id,
        "feedback": [f.id for f in cfg.feedback],
        "clocks": [c.id for c in cfg.clocks],
    }
    if args.canonical:
        payload["config_canonical"] = cfg.to_canonical()
    _emit(payload)
    return 0


def app_inspect(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="aeon-app-inspect",
        description="Dump the resolved configuration and identity digests.")
    _add_common_args(p)
    p.add_argument("--canonical", action="store_true",
                   help="also include the full canonical config payload")
    return _cmd_inspect(p.parse_args(argv))


__all__ = [
    "app_check", "app_compile", "app_run", "app_train",
    "app_evaluate", "app_snapshot", "app_replay", "app_inspect",
]
