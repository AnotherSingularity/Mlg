# Aeon Application Constitution

**Status:** REQUIRED — Gate L
**Applies to:** Aeon Application v0.1 (built against Aeon Language v0.1.0)
**Aeon Language certified commit:** `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`
**Aeon Language CI evidence:** run `30472658596` (11/11 jobs green)

This document is the governing specification of the Aeon
Application. Every other document under
`aeon-application/specification/` derives its authority from this
constitution.

## 1. Definition

> **Aeon Application is a multi-source, multi-clock cognitive
> execution system whose independently evolving signal sources
> project through negotiated ports into a contractive Recursion
> substrate. Every state transition preserves ownership,
> causality, clock identity, lineage, provenance, validity, and
> certification status.**

## 2. Mandatory invariants

Every valid execution of the Aeon Application MUST honor:

1. No application state exists without identity and owner.
2. No source mutates another source's private state directly.
3. No source enters Recursion without a typed projection.
4. No clock-domain crossing occurs implicitly.
5. No integration omits the frames it consumed.
6. No feedback mutates a source without negotiated capability.
7. No unavailable signal is represented as zero.
8. No uncertified transition is represented as certified.
9. No certificate claims a wider scope than was verified.
10. No runtime backend defines application semantics.
11. No canonical graph depends on host memory identity.
12. No snapshot omits active clocks, contracts, or lineage.
13. No future frame may influence an earlier transition.
14. No production execution silently falls back to another path.
15. No external model implementation defines Aeon's architecture.

## 3. Greenfield rule

Because no legacy Aeon application preceded this repository, the
application specification IS the behavioral authority. There is
no "prior behavior" to preserve. All expected behavior is
established before or with the implementation that introduces
it. Do not fabricate legacy parity; do not describe new
behavior as preserved behavior (Gate L mandate §2).

## 4. Language dependency

The application binds to a specific certified Aeon Language
implementation:

- **Language version:** `0.1.0`
- **Certified commit:** `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`
- **Local tag:** `aeon-language-v0.1.0` (remote publication
  pending — see `aeon-language/AEON-LANGUAGE-v0.1.0-RELEASE-REPORT.md
  §21`)

Every runtime invocation MUST verify the loaded language
matches this pin, and MUST fail closed on any mismatch. The
authoritative machine-readable record is
`aeon-application/AEON-LANGUAGE-LOCK.json`.

Aeon Language semantics MUST NOT be modified from inside the
application (Gate L mandate §0 and §2 constraint).

## 5. Runtime modes

The application supports exactly three modes, checked at
startup:

- **`REFERENCE`** — default until Gate L-J passes. Deterministic
  reference sources, small fixed dimensions, CPU execution,
  fixed seeds, complete tracing, strict validation. Used for
  fixtures and conformance.
- **`DEVELOPMENT`** — real components under development.
  Configurable dimensions, training permitted, debug tracing,
  experimental capabilities marked explicitly.
- **`CERTIFIED`** — only approved graph + config + language +
  backend + snapshot schema + capability negotiation are
  admitted. Green conformance is required. Only becomes the
  default after Gate L-J.

Any unknown runtime-mode string fails closed.

## 6. Architecture

Initial topology:

```
AttentionSource ───────────┐
                           ├──> typed projections
PersistentRecurrentSource ─┘            │
                                        ▼
                            Contractive Recursion
                                 │            │
                                 │            ├──> certified output
                                 │
                                 └──> bounded feedback
                                      (disabled by default,
                                      capability-negotiated)
```

Names describe roles, not external model compatibility. Neither
source is a wrapper for an external framework's implementation.

## 7. State model

Every application transition produces an identified state. The
required state families are:

    ApplicationState, AttentionSourceState, RecurrentSourceState,
    RecursionState, ProjectionState, SchedulerState,
    TrainingState, SnapshotState.

Each state records: `state_id`, `owner`, `parent_state_ids`,
`transition_id`, `clock_position`, `payload_digest`, `validity`,
`active_contracts`, `implementation_version`. Payload identity
and semantic state identity are separate.

## 8. Feedback

Feedback is disabled by default (gates set to 0). At zero gate:

- Feedback is behaviorally neutral.
- No source-private state changes because of feedback.

Feedback activation requires: destination capability
negotiation, bounded projection, declared clock relation,
state-ownership authorization, certification scope, and a
fixture proving both zero-gate neutrality and bounded nonzero
behavior. Direct matrix mutation on a source is prohibited
unless the destination advertises a versioned capability
expressly permitting it.

## 9. Output contract

Application outputs are structured values, not bare tensors:

    AeonOutput {
        output_id
        payload
        originating_state_id
        application_graph_id
        clock_position
        source_contributions
        validity ∈ {VALID, PROVISIONALLY_VALID, UNCERTIFIED,
                    CONTRACT_VIOLATED, INVALID, UNAVAILABLE}
        transition_certificate
        contraction_certificate
        provenance
    }

Validity is never collapsed into a Boolean success flag.

## 10. Training boundary

Training is a distinct application surface, added only after
deterministic inference and replay pass. Training MUST NOT be
hidden inside runtime transitions. A parameter update that
affects a certificate's declared assumptions MUST re-evaluate
the affected certificates.

## 11. Prohibitions (Gate L §2, §26 lifecycle)

Until Gate L-J:

- MUST NOT enable `CERTIFIED` as the default runtime mode.
- MUST NOT begin Windows packaging (L16).
- MUST NOT publish a launch decision as `LAUNCH CERTIFIED`
  without every §27 gate passing on the exact candidate SHA.
- MUST NOT modify Aeon Language semantics from inside the
  application repository.
- MUST NOT vendor or import external model implementations as
  architectural authority.
- MUST NOT permit silent fallback from Aeon runtime to any
  other execution path.
- MUST NOT collapse the validity enum into a Boolean.

## 12. Normative terminology

- **REQUIRED**, **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**,
  **SHOULD**, **SHOULD NOT**, **MAY** carry RFC 2119 meanings.
- **PROVISIONAL**, **EXPERIMENTAL**, **DEPRECATED**, **REJECTED**
  carry the same meanings as in the Aeon Language constitution.
