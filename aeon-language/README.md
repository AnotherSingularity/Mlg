# Aeon Language

The Aeon Language subsystem: framework-neutral kernel, canonical
IR, reference compiler, reference runtime, two host backends, and
a versioned conformance suite.

See `specification/00-CONSTITUTION.md` for the governing document
and `PHASE-0-REPORT.md` + `PHASE-0-EVIDENCE-RECONCILIATION.md` +
`AEON-PHASE-0.1-CLOSURE-REPORT.md` for the release-candidate
assessment.

## Install

```bash
pip install .
# with numpy backend + differential parity tests:
pip install '.[numpy,dev]'
```

Console scripts installed by the package:

    aeonc aeonrun aeoncheck aeonfmt aeonir aeongraph aeontest aeonreplay

## Repository layout

- `specification/` — normative documents (14 files).
- `schemas/`      — JSON schemas (canonical IR).
- `compiler/`     — lexer, parser, formatter, static validator,
                    type analyzer, staged pipeline, CLI.
- `runtime/`      — reference interpreter, scheduler, replay.
- `standard_library/aeon/` — framework-neutral kernel modules.
- `backends/`     — `python` (reference) and `numpy` (differential).
- `conformance/`  — versioned profiles + JSON manifest + runner.
- `tests/`        — pytest suite (unit, property, golden, negative,
                    differential, fresh-process replay).
- `examples/`     — canonical Aeon programs.
