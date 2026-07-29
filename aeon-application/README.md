# Aeon Application v0.1

A greenfield Aeon-native application built on Aeon Language
v0.1.0 (certified commit
`b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`, CI run
`30472658596`).

See `specification/00-APPLICATION-CONSTITUTION.md` for the
governing document, and `reports/AEON-GREENFIELD-BUILD-REPORT.md`
for the final Gate L outcome (published at L14).

## Layout

- `specification/` — normative documents (constitution,
  architecture, runtime modes, gates, ontology).
- `schemas/` — JSON schemas.
- `src/aeon_app/` — Python package.
- `configs/` — application configurations.
- `examples/` — reference programs (see
  `examples/two_source_reference/`).
- `tests/` — pytest suite.
- `conformance/` — versioned conformance profiles.
- `evaluation/` — evaluation profiles.
- `benchmarks/`, `packaging/`, `scripts/`, `reports/` — see mandate.

## Language dependency

The application MUST be executed against the Aeon Language
certified at `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`. The
machine-readable pin is `AEON-LANGUAGE-LOCK.json`. Every
runtime invocation verifies the pin and fails closed on
mismatch (see `src/aeon_app/config/language_lock.py`).

## Runtime modes

The application supports three modes with these defaults:

- `REFERENCE` — default until Gate L-J passes.
- `DEVELOPMENT` — for iteration.
- `CERTIFIED` — the launched application; only becomes the
  default after Gate L-J passes.
