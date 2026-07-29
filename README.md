# Mlg — Aeon

This repository hosts the Aeon system.

## Current state

At the start of the Phase 0 Language Mandate, this repository contained
no prior work: no application code, no research documents, no
configuration. The Phase 0 preservation checkpoint therefore records an
empty starting state.

## Aeon Language (Phase 0)

The `aeon-language/` subsystem is under active development. It defines:

- The Aeon Source Language.
- The Typed Semantic Graph.
- The Canonical Aeon IR.
- The Aeon Semantic Machine Instruction Set.
- The Reference Interpreter and host backends.
- The framework-neutral Standard Library.
- The Conformance Suite.

Until Aeon Language v0.1 is frozen (Gate J) and an application rewrite
is authorized (Gate K), no application-layer code depends on the
language kernel.

See `aeon-language/specification/00-CONSTITUTION.md` for the governing
document.

## Layout

```
aeon-language/
├── specification/       Normative language specification
├── schemas/             JSON schemas for canonical IR + graph
├── compiler/            Parser, formatter, static validator, IR lowerer
├── ir/                  Canonical IR data model + serialization
├── runtime/             Reference interpreter, scheduler, snapshots
├── standard_library/    Framework-neutral kernel (aeon.core, aeon.state, ...)
├── backends/            Host backends (Python reference; others later)
├── conformance/         Conformance fixtures + runner
├── examples/            Reference Aeon programs
├── tests/               Test suite (unit, property, golden, negative)
└── research/            Preserved research notes (RWKV-class study, etc.)
```

## Command-line tools

Installed by the Phase 0 subsystem (see `aeon-language/compiler/cli.py`):

- `aeonc`     — compile source to canonical IR
- `aeonrun`   — execute canonical IR
- `aeoncheck` — validate source, graph, contracts, and IR
- `aeonfmt`   — canonical source formatting
- `aeonir`    — inspect and validate canonical IR
- `aeongraph` — render the semantic graph
- `aeontest`  — run language and backend conformance
- `aeonreplay` — replay a recorded deterministic execution

## Prohibitions

The Aeon application rewrite is prohibited until Gate J passes and
Gate K authorization is issued. See
`aeon-language/specification/00-CONSTITUTION.md` §Prohibitions.
