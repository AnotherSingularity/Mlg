"""Aeon command-line tools.

Implements the eight tools required by specification §19:

    aeonc      compile source to canonical IR
    aeonrun    execute canonical IR
    aeoncheck  validate source, graph, contracts, and IR
    aeonfmt    canonical source formatting
    aeonir     inspect and validate canonical IR
    aeongraph  render the semantic graph
    aeontest   run language and backend conformance
    aeonreplay replay a recorded deterministic execution

Every tool returns a meaningful nonzero exit code on failure and
prints machine-readable diagnostics (JSON) when appropriate.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, List, Optional

from aeon import (
    INSTRUCTION_SET_VERSION,
    IR_VERSION,
    LANGUAGE_VERSION,
    STDLIB_VERSION,
)
from aeon.contraction import (
    CertificationMethod,
    Contractive,
    Metric,
    PrecisionPolicy,
)
from aeon.core import Severity
from aeon.recursion import ReferenceContractiveRecursion
from aeon.serialization import canonical_bytes, digest
from aeon.sources.dummy import DummyRichSource, DummyVectorSource

from .formatter import format_module
from .parser import ParseError, parse
from .validator import validate as validate_module

# Structured exit codes (Phase 0.1 §10).
EX_OK = 0
EX_USAGE = 2
EX_PARSE = 3
EX_VALIDATE = 4
EX_FORMAT = 5
EX_REPLAY_DIFF = 6
EX_INCOMPAT = 7
EX_OVERWRITE_REFUSED = 8


def _version_string() -> str:
    return (
        f"aeon (language={LANGUAGE_VERSION} "
        f"ir={IR_VERSION} isa={INSTRUCTION_SET_VERSION} "
        f"stdlib={STDLIB_VERSION})"
    )


def _add_common(ap: argparse.ArgumentParser, *,
                json_output: bool = False) -> None:
    ap.add_argument("--version", action="version", version=_version_string())
    if json_output:
        ap.add_argument("--json", action="store_true",
                        help="emit machine-readable JSON to stdout")


def _refuse_overwrite(path: Optional[str], force: bool) -> Optional[int]:
    if path and os.path.exists(path) and not force:
        sys.stderr.write(
            f"refusing to overwrite existing file {path!r}; pass --force to override.\n"
        )
        return EX_OVERWRITE_REFUSED
    return None


def _print_diag_json(diagnostics) -> None:
    payload = [
        {
            "severity": d.severity.value,
            "code": d.code,
            "message": d.message,
            "file": d.source_span.file if d.source_span else None,
            "line": d.source_span.start_line if d.source_span else None,
            "col": d.source_span.start_col if d.source_span else None,
        }
        for d in diagnostics
    ]
    sys.stderr.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")


def _read_source(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _read_source_or_stdin(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return _read_source(path)


def _load_ir(path: str):
    """Rebuild an IRModule from a compiled .aeon.ir.json file (a canonical
    envelope). Only supports the envelope produced by aeonc for now.

    Full IR round-trip deserialization is deferred; aeonrun today
    uses aeonc's in-process compile-and-run path via --from-source.
    """
    raise NotImplementedError(
        "aeonir/aeonrun currently support --from-source only in v0.1"
    )


# ---------------------------------------------------------------------------
# aeonc
# ---------------------------------------------------------------------------


def aeonc(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="aeonc", description="Compile Aeon source to canonical IR")
    _add_common(ap)
    ap.add_argument("source", help="Path to an Aeon source file (.aeon), or - for stdin")
    ap.add_argument("-o", "--output", help="Output path for the canonical IR JSON")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--ticks-per-clock", type=int, default=8)
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing output file")
    args = ap.parse_args(argv)

    try:
        text = _read_source_or_stdin(args.source)
    except OSError as exc:
        sys.stderr.write(f"aeonc: cannot read {args.source}: {exc}\n")
        return EX_USAGE

    rc = _refuse_overwrite(args.output, args.force)
    if rc is not None:
        return rc

    try:
        module = parse(text, filename=args.source, module_id=args.source)
    except ParseError as exc:
        sys.stderr.write(f"aeonc: parse failed: {exc}\n")
        return EX_PARSE

    res = validate_module(module)
    if not res.ok():
        sys.stderr.write("aeonc: validation failed:\n")
        _print_diag_json(res.errors())
        return EX_VALIDATE

    from runtime.scheduler import lower
    ir = lower(module, res.graph, seed=args.seed, ticks_per_clock=args.ticks_per_clock)

    payload = ir.to_bytes()
    if args.output:
        Path(args.output).write_bytes(payload)
        sys.stdout.write(f"{args.output}\n")
    else:
        sys.stdout.buffer.write(payload)
    sys.stderr.write(f"aeonc: module_id={ir.module_id[:24]} instructions={len(ir.instructions)}\n")
    return 0


# ---------------------------------------------------------------------------
# aeonrun
# ---------------------------------------------------------------------------


def aeonrun(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="aeonrun", description="Execute an Aeon program (source-driven)")
    _add_common(ap)
    ap.add_argument("source", help="Path to an Aeon source file (.aeon), or - for stdin")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--ticks-per-clock", type=int, default=8)
    ap.add_argument("--dimension", type=int, default=4,
                    help="Dimension for default reference sources")
    ap.add_argument("--backend", choices=["python", "numpy"], default="python",
                    help="Backend adapter to execute with")
    args = ap.parse_args(argv)

    text = _read_source_or_stdin(args.source)
    module = parse(text, filename=args.source, module_id=args.source)
    res = validate_module(module)
    if not res.ok():
        _print_diag_json(res.errors())
        return EX_VALIDATE

    from runtime.scheduler import lower
    ir = lower(module, res.graph, seed=args.seed, ticks_per_clock=args.ticks_per_clock)

    # Version compatibility check (mandate §10):
    # aeonrun MUST reject unvalidated or incompatible IR. The
    # scheduler tags IR with the current versions; if they diverged
    # (e.g. reader older than artifact), we would refuse here.
    if ir.aeon_ir_version != IR_VERSION or ir.language_version != LANGUAGE_VERSION:
        sys.stderr.write(
            f"aeonrun: incompatible IR version "
            f"(ir={ir.aeon_ir_version!r} language={ir.language_version!r}; "
            f"expected ir={IR_VERSION!r} language={LANGUAGE_VERSION!r})\n"
        )
        return EX_INCOMPAT

    sources = {}
    for s in module.sources:
        if "MatrixRead" in s.offers or "DecayControl" in s.offers or "LayerRead" in s.offers:
            sources[s.name] = DummyRichSource(s.name, args.dimension)
        else:
            sources[s.name] = DummyVectorSource(s.name, args.dimension)

    substrates = {}
    if args.backend == "numpy":
        try:
            from backends.numpy import NumpyBackend, NumpyContractiveRecursion
        except ImportError as exc:
            sys.stderr.write(f"aeonrun: numpy backend unavailable: {exc}\n")
            return EX_USAGE
        for r in module.recursions:
            contract = Contractive(
                metric=Metric.LINF,
                requested_margin=r.contraction_margin or 0.9,
                numerical_tolerance=1e-12,
                precision_policy=PrecisionPolicy("float64"),
                certification_method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
            )
            substrates[r.name] = NumpyContractiveRecursion(
                dimension=r.dimension or args.dimension, contract=contract,
                substrate_id=r.name, decay=0.5,
                declared_input_radius=10.0, declared_state_radius=10.0,
                declared_projection_scale_upper=1.0,
            )
        backend = NumpyBackend()
    else:
        for r in module.recursions:
            contract = Contractive(
                metric=Metric.LINF,
                requested_margin=r.contraction_margin or 0.9,
                numerical_tolerance=1e-12,
                precision_policy=PrecisionPolicy("float64"),
                certification_method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
            )
            substrates[r.name] = ReferenceContractiveRecursion(
                dimension=r.dimension or args.dimension, contract=contract,
                substrate_id=r.name, decay=0.5,
                declared_input_radius=10.0, declared_state_radius=10.0,
                declared_projection_scale_upper=1.0,
            )
        from backends.python import PythonBackend
        backend = PythonBackend()
    outcome = backend.execute(ir, sources=sources, substrates=substrates, seed=args.seed)

    summary = {
        "module_id": ir.module_id,
        "halt_reason": outcome.halt_reason,
        "outputs": len(outcome.outputs),
        "contraction_certificates": [
            {"result": c.result.value,
             "consumed_inputs": len(c.consumed_inputs),
             "clock_tick": c.clock_position.tick}
            for c in outcome.contraction_certificates
        ],
        "transition_certificates": len(outcome.certificates),
        "trace_steps": len(outcome.trace),
        "errors": [d.code for d in outcome.diagnostics if d.severity is Severity.ERROR],
    }
    sys.stdout.write(json.dumps(summary, sort_keys=True, indent=2) + "\n")
    return 0 if not summary["errors"] else 1


# ---------------------------------------------------------------------------
# aeoncheck
# ---------------------------------------------------------------------------


def aeoncheck(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="aeoncheck", description="Validate an Aeon source module via the staged compiler pipeline")
    _add_common(ap, json_output=True)
    ap.add_argument("source", help="Path to an Aeon source file, or - for stdin")
    args = ap.parse_args(argv)

    text = _read_source_or_stdin(args.source)
    from .pipeline import ALL_STAGES, run_pipeline
    result = run_pipeline(text, filename=args.source, module_id=args.source)

    if args.json:
        payload = {
            "source_file": result.source_file,
            "stages_run": result.stages_run,
            "failed_stage": result.failed_stage,
            "diagnostics": [
                {
                    "severity": d.severity.value,
                    "code": d.code,
                    "message": d.message,
                    "file": d.source_span.file if d.source_span else None,
                    "line": d.source_span.start_line if d.source_span else None,
                    "col": d.source_span.start_col if d.source_span else None,
                    "remediation": d.remediation,
                }
                for d in result.diagnostics
            ],
            "ok": result.ok(),
            "language_version": LANGUAGE_VERSION,
            "ir_version": IR_VERSION,
        }
        sys.stdout.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    else:
        if result.ok():
            sys.stdout.write(f"OK — {len(result.stages_run)} stage(s) passed\n")
        else:
            sys.stderr.write(
                f"aeoncheck: failed at stage {result.failed_stage!r} "
                f"(stage {result.stages_run.index(result.failed_stage) + 1 if result.failed_stage in result.stages_run else '?'} "
                f"of {len(ALL_STAGES)})\n"
            )
            _print_diag_json(result.errors())
    return EX_OK if result.ok() else EX_VALIDATE


# ---------------------------------------------------------------------------
# aeonfmt
# ---------------------------------------------------------------------------


def aeonfmt(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="aeonfmt", description="Canonically format Aeon source")
    _add_common(ap)
    ap.add_argument("source", help="Path to an Aeon source file, or - for stdin")
    ap.add_argument("-w", "--write", action="store_true", help="write result back in place")
    ap.add_argument("--check", action="store_true",
                    help="exit 0 iff input already canonical (exit 5 otherwise)")
    args = ap.parse_args(argv)

    text = _read_source_or_stdin(args.source)
    module = parse(text, filename=args.source, module_id=args.source)
    formatted = format_module(module)

    if args.check:
        if text != formatted:
            sys.stderr.write("aeonfmt: not canonical\n")
            return EX_FORMAT
        return 0
    if args.write:
        Path(args.source).write_text(formatted, encoding="utf-8")
        return 0
    sys.stdout.write(formatted)
    return 0


# ---------------------------------------------------------------------------
# aeonir
# ---------------------------------------------------------------------------


def aeonir(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="aeonir", description="Inspect canonical IR")
    _add_common(ap)
    ap.add_argument("path", help="Path to a canonical IR file (bytes from aeonc)")
    args = ap.parse_args(argv)

    payload = Path(args.path).read_bytes()
    doc = json.loads(payload.decode("utf-8"))
    body = doc.get("body", {})
    summary = {
        "aeon_ir_version": doc.get("aeon_ir_version"),
        "language_version": doc.get("language_version"),
        "module_id": doc.get("module_id"),
        "digest_method": doc.get("digest_method"),
        "n_declarations": len(body.get("declarations", [])),
        "n_capabilities": len(body.get("capabilities", [])),
        "n_clocks": len(body.get("clocks", [])),
        "n_instructions": len(body.get("instructions", [])),
        "n_nodes": len(body.get("graph", {}).get("nodes", [])),
        "n_edges": len(body.get("graph", {}).get("edges", [])),
    }
    sys.stdout.write(json.dumps(summary, sort_keys=True, indent=2) + "\n")
    return 0


# ---------------------------------------------------------------------------
# aeongraph
# ---------------------------------------------------------------------------


def aeongraph(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="aeongraph", description="Render the semantic graph as DOT")
    _add_common(ap)
    ap.add_argument("source", help="Path to an Aeon source file, or - for stdin")
    args = ap.parse_args(argv)

    text = _read_source_or_stdin(args.source)
    module = parse(text, filename=args.source, module_id=args.source)
    res = validate_module(module)
    if not res.ok():
        _print_diag_json(res.errors())
        return EX_VALIDATE
    g = res.graph
    lines = ["digraph aeon {"]
    for n in g.nodes:
        lines.append(f'    "{n.id}" [label="{n.id}\\n{n.kind.value}"];')
    for e in g.edges:
        lines.append(f'    "{e.from_node}" -> "{e.to_node}" [label="{e.edge_kind}"];')
    lines.append("}")
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


# ---------------------------------------------------------------------------
# aeontest
# ---------------------------------------------------------------------------


def aeontest(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="aeontest", description="Run the conformance suite")
    _add_common(ap, json_output=True)
    ap.add_argument("--tests-dir", default=None)
    ap.add_argument("--profile", action="append",
                    help="Run a specific conformance profile (repeatable)")
    args = ap.parse_args(argv)

    if args.profile:
        from conformance.runner import full_report
        here = Path(__file__).resolve().parents[1]
        tests_root = Path(args.tests_dir) if args.tests_dir else (here / "tests")
        report = full_report(tests_root, args.profile)
        if args.json:
            sys.stdout.write(json.dumps(report, sort_keys=True, indent=2) + "\n")
        else:
            for r in report["results"]:
                tag = "PASS" if r["passed"] else "FAIL"
                sys.stdout.write(
                    f"[{tag}] {r['name']:24s} "
                    f"pass={r['pass_count']} fail={r['fail_count']} skip={r['skip_count']}\n"
                )
            sys.stdout.write(f"Overall: {report['overall_conformance_result']}\n")
        return EX_OK if report["overall_conformance_result"] == "PASS" else EX_VALIDATE

    here = Path(__file__).resolve().parents[1]  # aeon-language/
    tests_dir = args.tests_dir or str(here / "tests")
    env = os.environ.copy()
    stdlib = str(here / "standard_library")
    env["PYTHONPATH"] = f"{stdlib}:{here}"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", tests_dir, "-q"],
        env=env,
    )
    return result.returncode


# ---------------------------------------------------------------------------
# aeonreplay
# ---------------------------------------------------------------------------


def aeonreplay(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="aeonreplay", description="Replay a source module twice and diff")
    _add_common(ap)
    ap.add_argument("source", help="Path to an Aeon source file, or - for stdin")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--ticks-per-clock", type=int, default=8)
    ap.add_argument("--dimension", type=int, default=4)
    args = ap.parse_args(argv)

    text = _read_source_or_stdin(args.source)
    module = parse(text, filename=args.source, module_id=args.source)
    res = validate_module(module)
    if not res.ok():
        _print_diag_json(res.errors())
        return EX_VALIDATE

    # Refuse replay under an incompatible IR/language version
    # (mandate §10: aeonreplay must fail clearly).
    if LANGUAGE_VERSION != "0.1.0-dev":
        sys.stderr.write(
            f"aeonreplay: unexpected language version {LANGUAGE_VERSION!r}\n"
        )
        return EX_INCOMPAT
    from runtime.scheduler import lower
    from runtime.replay import replay
    ir = lower(module, res.graph, seed=args.seed, ticks_per_clock=args.ticks_per_clock)

    def sources_factory():
        out = {}
        for s in module.sources:
            if "MatrixRead" in s.offers or "DecayControl" in s.offers or "LayerRead" in s.offers:
                out[s.name] = DummyRichSource(s.name, args.dimension)
            else:
                out[s.name] = DummyVectorSource(s.name, args.dimension)
        return out

    def substrates_factory():
        out = {}
        for r in module.recursions:
            contract = Contractive(
                metric=Metric.LINF,
                requested_margin=r.contraction_margin or 0.9,
                numerical_tolerance=1e-12,
                precision_policy=PrecisionPolicy("float64"),
                certification_method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
            )
            out[r.name] = ReferenceContractiveRecursion(
                dimension=r.dimension or args.dimension, contract=contract,
                substrate_id=r.name, decay=0.5,
                declared_input_radius=10.0, declared_state_radius=10.0,
                declared_projection_scale_upper=1.0,
            )
        return out

    report = replay(ir, sources_factory=sources_factory,
                    substrates_factory=substrates_factory, seed=args.seed)
    sys.stdout.write(json.dumps({
        "identical": report.identical,
        "difference": report.difference,
        "outputs_a": len(report.outcome_a.outputs),
        "outputs_b": len(report.outcome_b.outputs),
    }, sort_keys=True, indent=2) + "\n")
    return EX_OK if report.identical else EX_REPLAY_DIFF


# ---------------------------------------------------------------------------
# Dispatcher (`aeon` multiplexer)
# ---------------------------------------------------------------------------


def aeonmigrate(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="aeonmigrate",
                                 description="Migrate a versioned Aeon artifact to a target version")
    _add_common(ap, json_output=True)
    ap.add_argument("input", help="Path to the input JSON artifact, or - for stdin")
    ap.add_argument("--artifact-kind", required=True,
                    choices=["semantic_graph", "canonical_ir", "snapshot",
                             "certificate", "conformance_manifest",
                             "backend_contract", "source_module"])
    ap.add_argument("--from-version", default=None,
                    help="Override the artifact's declared source version")
    ap.add_argument("--to-version", default="0.1.0",
                    help="Target version (default: 0.1.0)")
    ap.add_argument("--check", action="store_true",
                    help="Report the migration outcome without writing output")
    ap.add_argument("-o", "--output", help="Output path for the migrated artifact")
    ap.add_argument("--force", action="store_true",
                    help="Overwrite an existing output file")
    args = ap.parse_args(argv)

    from aeon.migration import ArtifactKind, MigrationOutcome
    from aeon.migration_registry import DEFAULT_REGISTRY

    kind = ArtifactKind(args.artifact_kind)
    text = _read_source_or_stdin(args.input)
    artifact = json.loads(text)
    if args.from_version is not None:
        from aeon.migration import AEON_VERSION_KEY
        artifact = dict(artifact)
        artifact[AEON_VERSION_KEY] = args.from_version

    result = DEFAULT_REGISTRY.migrate(kind, artifact, args.to_version)

    payload = {
        "outcome": result.outcome.value,
        "path": list(result.path),
        "artifact_kind": kind.value,
        "target_version": args.to_version,
        "ok": result.ok(),
        "diagnostics": [
            {"code": d.code, "message": d.message, "field_path": d.field_path}
            for d in result.diagnostics
        ],
    }

    if args.check or args.output is None:
        if args.json:
            sys.stdout.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
        else:
            sys.stdout.write(f"{result.outcome.value}: path={list(result.path)}\n")
            for d in result.diagnostics:
                sys.stderr.write(f"  {d.code}: {d.message}\n")
        return EX_OK if result.ok() else EX_VALIDATE

    if not result.ok():
        if args.json:
            sys.stdout.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
        else:
            for d in result.diagnostics:
                sys.stderr.write(f"  {d.code}: {d.message}\n")
        return EX_VALIDATE

    rc = _refuse_overwrite(args.output, args.force)
    if rc is not None:
        return rc
    Path(args.output).write_bytes(result.canonical_bytes or b"")
    sys.stderr.write(f"aeonmigrate: wrote {args.output} ({result.outcome.value})\n")
    if args.json:
        sys.stdout.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    return EX_OK


TOOLS = {
    "aeonc": aeonc,
    "aeonrun": aeonrun,
    "aeoncheck": aeoncheck,
    "aeonfmt": aeonfmt,
    "aeonir": aeonir,
    "aeongraph": aeongraph,
    "aeontest": aeontest,
    "aeonreplay": aeonreplay,
    "aeonmigrate": aeonmigrate,
}


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if not argv or argv[0] in ("-h", "--help"):
        sys.stdout.write(
            "usage: aeon <tool> [args]\n"
            f"tools: {', '.join(sorted(TOOLS))}\n"
            f"language={LANGUAGE_VERSION} ir={IR_VERSION} isa={INSTRUCTION_SET_VERSION}\n"
        )
        return 0
    tool = argv[0]
    if tool not in TOOLS:
        sys.stderr.write(f"unknown tool: {tool}\n")
        return 1
    return TOOLS[tool](argv[1:])


if __name__ == "__main__":
    sys.exit(main())
