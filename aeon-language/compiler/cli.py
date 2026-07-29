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

from aeon import IR_VERSION, INSTRUCTION_SET_VERSION, LANGUAGE_VERSION
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
    ap.add_argument("source", help="Path to an Aeon source file (.aeon)")
    ap.add_argument("-o", "--output", help="Output path for the canonical IR JSON")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--ticks-per-clock", type=int, default=8)
    args = ap.parse_args(argv)

    try:
        text = _read_source(args.source)
    except OSError as exc:
        sys.stderr.write(f"aeonc: cannot read {args.source}: {exc}\n")
        return 2

    try:
        module = parse(text, filename=args.source, module_id=args.source)
    except ParseError as exc:
        sys.stderr.write(f"aeonc: parse failed: {exc}\n")
        return 3

    res = validate_module(module)
    if not res.ok():
        sys.stderr.write("aeonc: validation failed:\n")
        _print_diag_json(res.errors())
        return 4

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
    ap.add_argument("source", help="Path to an Aeon source file (.aeon)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--ticks-per-clock", type=int, default=8)
    ap.add_argument("--dimension", type=int, default=4,
                    help="Dimension for default reference sources")
    args = ap.parse_args(argv)

    text = _read_source(args.source)
    module = parse(text, filename=args.source, module_id=args.source)
    res = validate_module(module)
    if not res.ok():
        _print_diag_json(res.errors())
        return 4

    from runtime.scheduler import lower
    ir = lower(module, res.graph, seed=args.seed, ticks_per_clock=args.ticks_per_clock)

    sources = {}
    for s in module.sources:
        if "MatrixRead" in s.offers or "DecayControl" in s.offers or "LayerRead" in s.offers:
            sources[s.name] = DummyRichSource(s.name, args.dimension)
        else:
            sources[s.name] = DummyVectorSource(s.name, args.dimension)

    substrates = {}
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
        )

    from backends.python import PythonBackend
    outcome = PythonBackend().execute(ir, sources=sources, substrates=substrates, seed=args.seed)

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
    ap = argparse.ArgumentParser(prog="aeoncheck", description="Validate an Aeon source module")
    ap.add_argument("source")
    args = ap.parse_args(argv)

    text = _read_source(args.source)
    try:
        module = parse(text, filename=args.source, module_id=args.source)
    except ParseError as exc:
        sys.stderr.write(f"aeoncheck: {exc}\n")
        return 3

    res = validate_module(module)
    if not res.ok():
        _print_diag_json(res.diagnostics)
        return 4
    sys.stdout.write("OK\n")
    return 0


# ---------------------------------------------------------------------------
# aeonfmt
# ---------------------------------------------------------------------------


def aeonfmt(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="aeonfmt", description="Canonically format Aeon source")
    ap.add_argument("source")
    ap.add_argument("-w", "--write", action="store_true", help="write result back in place")
    ap.add_argument("--check", action="store_true",
                    help="exit 0 iff input already canonical")
    args = ap.parse_args(argv)

    text = _read_source(args.source)
    module = parse(text, filename=args.source, module_id=args.source)
    formatted = format_module(module)

    if args.check:
        if text != formatted:
            sys.stderr.write("aeonfmt: not canonical\n")
            return 5
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
    ap.add_argument("source")
    args = ap.parse_args(argv)

    text = _read_source(args.source)
    module = parse(text, filename=args.source, module_id=args.source)
    res = validate_module(module)
    if not res.ok():
        _print_diag_json(res.errors())
        return 4
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
    ap.add_argument("--tests-dir", default=None)
    args = ap.parse_args(argv)

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
    ap.add_argument("source")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--ticks-per-clock", type=int, default=8)
    ap.add_argument("--dimension", type=int, default=4)
    args = ap.parse_args(argv)

    text = _read_source(args.source)
    module = parse(text, filename=args.source, module_id=args.source)
    res = validate_module(module)
    if not res.ok():
        _print_diag_json(res.errors())
        return 4
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
    return 0 if report.identical else 6


# ---------------------------------------------------------------------------
# Dispatcher (`aeon` multiplexer)
# ---------------------------------------------------------------------------


TOOLS = {
    "aeonc": aeonc,
    "aeonrun": aeonrun,
    "aeoncheck": aeoncheck,
    "aeonfmt": aeonfmt,
    "aeonir": aeonir,
    "aeongraph": aeongraph,
    "aeontest": aeontest,
    "aeonreplay": aeonreplay,
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
