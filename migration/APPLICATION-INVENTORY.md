# Application Inventory

**Baseline audit SHA:** `2763c913d75bced7fd96553316b951608891c214`
**Aeon Language SHA:** `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`
**Date:** 2026-07-29

Per mandate §5, this document inventories the current Aeon
application by executable responsibility. Every item is
determined mechanically, not inferred from filenames.

## Mechanical enumeration

```
$ git ls-tree -r HEAD --name-only \
    | grep -vE '^(aeon-language/|\.github/|\.gitignore|LICENSE|README\.md)'
$
```

Zero files match. Every file in the repository belongs to one of
three categories:

- **The Aeon Language subsystem** (`aeon-language/`) — the
  certified v0.1.0 release described in
  `aeon-language/AEON-LANGUAGE-v0.1.0-RELEASE-REPORT.md`. Under
  the constitution (`aeon-language/specification/00-CONSTITUTION.md`)
  this is a language, not an application.
- **CI infrastructure** (`.github/workflows/aeon-language.yml`).
- **Repository scaffolding** (`.gitignore`, `LICENSE`,
  `README.md`).

## Component-by-component inventory (mandate §5)

For each responsibility the mandate requires:

| Responsibility | Present in the repository? |
| -------------- | -------------------------- |
| application entry points | **No** |
| configuration loading | **No** |
| model construction | **No** |
| source implementations (application) | **No** — only reference dummies in `aeon.sources.dummy` |
| Recursion implementation (application) | **No** — only the reference `ReferenceContractiveRecursion` |
| source-to-Recursion projections (application) | **No** — only the reference `project_frame` |
| feedback paths | **No** — the ISA reserves `RECURSION_FEEDBACK` but no application uses it |
| clock and cadence behavior (application) | **No** — only the reference scheduler unrolling the illustrative example |
| state ownership (application) | **No** |
| state persistence (application) | **No** — snapshot mechanism exists in the language; no application uses it |
| snapshot and restore (application) | **No** |
| training paths | **No** |
| inference paths | **No** |
| generation paths | **No** |
| tokenization | **No** |
| numerical kernels (application) | **No** — the reference substrate is pure Python; a NumPy backend exists in the language |
| device placement | **No** |
| serialization (application) | **No** — the language ships canonical serialization; no application uses it |
| observability | **No** application observability |
| error handling (application) | **No** |
| tests (application) | **No** — the 223 tests all belong to Aeon Language |
| benchmarks | **No** |
| external dependencies (application) | **No** — the language itself declares only `pytest` (dev) and `numpy` (optional) |

## Interpretation

The repository has never contained an Aeon application. This
was documented explicitly in Phase 0 (`PHASE-0-REPORT.md` §1
"Repository state at Phase 0 start: **completely empty**"), and
every commit since has been Aeon Language development. Every
Phase 0.1 and v0.1 final closure commit is language work.

The Gate K mandate's foundational premise —
"The rewrite must preserve the current application as the
behavioral reference until each replacement tranche passes
parity" (§0 and §1) — cannot be honored, because there is no
current application to serve as behavioral reference.

## Consequence for the migration sequence

Every subsequent tranche (K1–K18) depends on this inventory:

- K1 captures the "legacy behavioral and state-transition
  baseline" — there is no legacy behavior to capture.
- K2 pins the certified language runtime — already done inside
  Aeon Language itself as `LANGUAGE_VERSION = "0.1.0"`; no
  application to pin it from.
- K3 introduces `LEGACY`, `AEON_SHADOW`, `AEON_ACTIVE` modes —
  there is no LEGACY execution to shadow.
- K4 encodes the application topology as a semantic graph —
  there is no application topology.
- K5–K13 migrate identity/state/clocks/ports/projections/
  Recursion/feedback/scheduler/snapshot/outputs — nothing to
  migrate.
- K14 certifies legacy-to-Aeon shadow parity — no legacy exists
  to compare against; §11.1 forbids classifying anything as
  parity in this state, and §6.3 forbids claiming parity from a
  single example (or none).
- K15 activates Aeon as authoritative — Aeon already is the
  only execution in this repository.
- K16/K17 audit and remove legacy — nothing to remove.
- K18 launch certification — no application to launch.

This is not a claim that migration is "mostly ready" or
"functionally complete"; it is a claim that the migration
mechanism has no legacy source. See
`AEON-APPLICATION-REWRITE-REPORT.md` for the mechanical launch
decision.
