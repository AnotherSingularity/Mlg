# Behavioral Baseline

**Baseline audit SHA:** `2763c913d75bced7fd96553316b951608891c214`
**Aeon Language SHA:** `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`

Per mandate §6, this document records the reproducible legacy
behavioral baseline to be used as the parity reference through
K14.

## Baseline status

The application inventory (`APPLICATION-INVENTORY.md`) records
zero application entry points, zero application source
implementations, zero application Recursion implementations,
zero application clocks / projections / feedback / snapshots /
training / inference / generation / tokenization / numerical
kernels / serialization / observability / error paths / tests /
benchmarks.

**Therefore no baseline behavior exists to capture.**

## Fixture matrix (mandate §6.1)

| Required fixture class | Legacy behavior available? |
| ---------------------- | -------------------------- |
| minimal initialization | No |
| single-source execution | No |
| multi-source execution | No |
| single transition | No |
| multi-transition sequence | No |
| Recursion integration | No |
| feedback-enabled execution | No |
| feedback-disabled execution | No |
| snapshot and restore | No |
| deterministic replay | No |
| empty or unavailable source input | No |
| invalid source input | No |
| clock boundary | No |
| aggregation-window boundary | No |
| numerical boundary | No |
| error path | No |
| forward pass (training) | No |
| loss calculation (training) | No |
| backward pass (training) | No |
| optimizer step (training) | No |
| checkpoint save (training) | No |
| checkpoint restore (training) | No |

## Golden evidence (mandate §6.2)

Golden evidence requires an implementation to observe. No
application implementation exists; no golden evidence can be
captured.

## Determinism (mandate §6.3)

Determinism testing requires a program to run. The Aeon Language
subsystem has its own PYTHONHASHSEED matrix (verified across
`{0, 1, 42, random}` by CI job `determinism (seed *)`, run
`30472658596`); those results are language evidence, not
application-behavioral evidence.

## Comparison policy for intentional nondeterminism

Not applicable — no execution exists to be nondeterministic.

## Consequence

Mandate §6.3 states: "Do not claim parity from a single
successful example." A stronger form of the same rule applies
here: no parity claim of any kind is possible in either
direction, because there is no legacy execution to compare
against. Every subsequent tranche's parity gate (K14 Gates K-A
through K-E) is uncrossable in this state.
