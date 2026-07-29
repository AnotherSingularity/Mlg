# Recursion Substrate

**Status:** REQUIRED — Phase 0
**Depends on:** `05-PORTS-AND-CAPABILITIES.md`, `07-CONTRACTION.md`

## 1. Non-source status

The Recursion substrate is not a source port. It is a distinct
subsystem with its own contract. The compiler MUST NOT allow a
Recursion substrate to be substituted for a source or vice versa,
even if their structural signatures resemble each other.

## 2. Substrate interface

```
RecursionSubstrate {
    initialize(config, seed) -> RecursionState

    project(source_frame       : SignalFrame,
            projection_contract : ProjectionContract)
        -> ManifoldInput

    integrate(inputs         : List<ManifoldInput>,
              state          : RecursionState,   // owned
              clock_position : ClockPosition in Integration)
        -> RecursionStepResult

    read(state   : RecursionState,   // borrowed
         request : ReadRequest)
        -> RecursionReadResult

    snapshot(state : RecursionState) -> RecursionSnapshot
    restore(snapshot : RecursionSnapshot) -> RecursionState
}
```

`RecursionStepResult` MUST have the shape:

```
RecursionStepResult {
    next_state              : RecursionState        // owned
    outputs                 : List<Emission>
    source_contributions    : Map<SourceId, Contribution>
    unresolved_inputs       : List<UnresolvedInput>
    contraction_certificate : ContractionCertificate
    transition_certificate  : Certificate<RecursionState>
}
```

`source_contributions` MUST identify every source whose projection
was integrated in this step, and MUST record the frame-range
identifier consumed for each.

## 3. Source-agnosticism

The integrator MUST NOT branch on:

- The source's implementation class.
- The source's host type or framework.
- The source's presence/absence of a specific optional capability
  identifier, except as returned by the negotiation result.

The integrator MAY branch on:

- Negotiated semantic capabilities from `NegotiationResult`.
- The projection contract selected for a specific `ManifoldInput`.
- The Recursion substrate's own configuration.

Prohibited constructs in the integrator (constitution §6):

```
if source_is_rwkv
if source_is_transformer
if source_class_name == "..."
if isinstance(source, TransformerSource)
if isinstance(source, RecurrentSource)
```

Such tests are Gate-B failures.

## 4. Projection adapters

A source-specific optimization MAY exist behind a projection
adapter. An adapter is a function:

```
adapter : (SourceFrame_source_specific, ProjectionContract)
       -> ManifoldInput
```

The adapter's specialization is invisible to the integrator: the
integrator sees only `ManifoldInput` values.

## 5. Feedback

If the Recursion substrate is permitted to feed back into a source
under the graph's declared feedback contract, the feedback path
MUST:

- Cross a clock boundary via a declared relationship (typically
  `Integration -> Token` via a declared mapping).
- Carry a `Feedback` capability negotiation result.
- Produce an explicit `RECURSION_FEEDBACK` instruction in the IR.

Feedback MUST NOT be implicit. A hidden write from Recursion into a
source's private state is a Gate-B failure.

## 6. Contraction requirement

Every `integrate` invocation MUST produce a `ContractionCertificate`
(see `07-CONTRACTION.md`) whose `result` is one of:

- `PROVEN_CONTRACTIVE`
- `BOUNDED_CONTRACTIVE`
- `NOT_PROVEN`
- `VIOLATED`
- `NUMERICALLY_INVALID`

An `integrate` invocation whose `result` is `NOT_PROVEN` MAY still
succeed as an `AppliedUncertified` transition. An invocation with
`result = VIOLATED` MUST produce `TransitionResult.Rejected`.

## 7. Read model

Reads from Recursion state are typed by clock domain and by the
requested view. A read MUST NOT observe state from a future
`ClockPosition in Integration`.

Reads of source contributions are visible only through the recorded
`source_contributions` map of a prior `RecursionStepResult`, never
by inspecting a source's private state directly.
