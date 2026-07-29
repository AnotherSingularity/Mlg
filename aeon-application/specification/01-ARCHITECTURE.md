# Aeon Application Architecture

**Status:** REQUIRED — Gate L
**Depends on:** `00-APPLICATION-CONSTITUTION.md`

## 1. Layers

    ┌──────────────────────────────────────────────────┐
    │  aeon_app.application                            │
    │      startup, mode selection, output emission    │
    ├──────────────────────────────────────────────────┤
    │  aeon_app.runtime                                │
    │      canonical IR execution, backend selection   │
    ├──────────────────────────────────────────────────┤
    │  aeon_app.scheduler                              │
    │      clock ticks, window open/close, cadence     │
    ├──────────────────────────────────────────────────┤
    │  aeon_app.graph                                  │
    │      typed nodes, typed edges, canonical IR      │
    ├─────────────┬──────────────────┬─────────────────┤
    │  sources    │  projections     │  recursion      │
    │             │                  │                 │
    │ Attention   │ Attention→Rec.   │ Contractive     │
    │ Recurrent   │ Recurrent→Rec.   │ substrate       │
    │             │ Rec→Att fb       │                 │
    │             │ Rec→Rec fb       │                 │
    ├─────────────┴──────────────────┴─────────────────┤
    │  aeon_app.identity / clocks / persistence / obs. │
    ├──────────────────────────────────────────────────┤
    │  Aeon Language v0.1.0 (pinned certified SHA)     │
    └──────────────────────────────────────────────────┘

## 2. Package layout (Gate L mandate §3)

`aeon-application/src/aeon_app/`:

- `application/` — top-level session, mode selection, output
  contract.
- `config/` — configuration schemas + resolver + digests.
- `identity/` — application-scoped identity primitives; wraps
  `aeon.identity`.
- `graph/` — application node/edge builders, canonical IR
  compilation, golden graph digest.
- `sources/` — `AttentionSource`, `PersistentRecurrentSource`,
  and their state records.
- `projections/` — four typed projections
  (attention→recursion, recurrent→recursion, recursion→attention
  feedback, recursion→recurrent feedback).
- `recursion/` — application-scoped substrate wrapping the
  certified `ReferenceContractiveRecursion` with an application
  certificate.
- `feedback/` — feedback gates + capability-negotiated
  activation + zero-gate neutrality proof.
- `clocks/` — input/source/integration/training/checkpoint
  clocks + explicit relations.
- `scheduler/` — deterministic multi-clock scheduler.
- `runtime/` — canonical IR execution driver.
- `training/` — deterministic training surface (added at L10).
- `inference/` — inference driver (part of runtime after L8).
- `evaluation/` — evaluation profiles.
- `persistence/` — snapshot envelope, restore, replay.
- `observability/` — non-invasive traces + metrics.
- `cli/` — eight `aeon-app-*` commands.
- `backends/` — declared backend adapters (Python + NumPy
  initially).

## 3. Data flow

1. Configuration resolves to a canonical digest.
2. The application constructs a semantic graph from the config.
3. The certified Aeon compiler lowers the graph to canonical IR.
4. The application runtime schedules IR execution.
5. Sources step on their local clocks.
6. Frames land in aggregation windows.
7. Windows close on the integration clock.
8. Projections convert frames to manifold inputs.
9. Recursion integrates and emits certificates.
10. Feedback (if gated on) projects Recursion into sources.
11. Output emits a structured `AeonOutput` value.
12. Every step appends to the append-only event log.

## 4. Explicit non-goals for v0.1

The following are deliberately out of scope for v0.1 and will
be recorded as known limitations in the final report:

- GPU / CUDA execution.
- Learned tokenization (integer token IDs and small feature
  vectors only).
- Multi-node distributed execution.
- Closed-loop feedback contraction proofs (Aeon Language v0.1
  reserves `ContractionScope.CLOSED_LOOP_TRANSITION` but does
  not implement its verifier; feedback nonzero cases can only
  emit BOUNDED_CONTRACTIVE).
- Application-level PyTorch backend (may be added later behind
  the source port).
- Signed Windows executable (Gate L §29; only allowed after
  Gate L-J).
