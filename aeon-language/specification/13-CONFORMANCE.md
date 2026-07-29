# Conformance

**Status:** REQUIRED — Phase 0

## 1. What conformance means

An implementation is conforming for Aeon Language version `V` iff:

1. It parses every source program that the reference compiler for
   `V` parses, and rejects every source program that the reference
   compiler for `V` rejects.
2. It produces canonical IR byte-identical to the reference for
   every accepted source program.
3. Its runtime produces:
   - Byte-identical `StateId` sequences to the reference under
     replay, given the same seeds and inputs.
   - Byte-identical certificate contents (modulo declared
     numerical tolerances in `Contractive` contracts).
   - Byte-identical canonical provenance and lineage records.
4. It passes the conformance fixture suite in `conformance/`.

## 2. Fixture categories

The conformance suite is organized by fixture category:

- `conformance/fixtures/serialization/`
    Canonical serialization golden fixtures for every schema type.
- `conformance/fixtures/ir/`
    Source ↔ IR golden fixtures.
- `conformance/fixtures/state/`
    State identity, lineage, and snapshot fixtures.
- `conformance/fixtures/ports/`
    Required-tier source fixtures.
- `conformance/fixtures/optional/`
    Optional-capability fixtures (only run for implementations
    declaring support).
- `conformance/fixtures/causality/`
    Causal invariant fixtures (positive and negative).
- `conformance/fixtures/contraction/`
    Contraction-certificate fixtures.
- `conformance/fixtures/schedule/`
    Deterministic replay fixtures.
- `conformance/fixtures/negative/`
    Programs that MUST be rejected, with the expected diagnostic
    code.

## 3. Required tests (mandate §20)

The conformance suite MUST verify:

### Identity and state
- Every state receives a stable identity.
- Equal payloads do not erase distinct lineage.
- State cannot be mutated after move.
- State branching is explicit.
- Snapshot and restore preserve semantic identity where required.
- Restore produces the same next transition under identical
  inputs.

### Ports and capabilities
- Required-tier sources pass one common conformance suite.
- Optional capability paths activate only after negotiation.
- Absent capabilities use declared fallback.
- Required-capability absence rejects the graph.
- Negotiation is deterministic.
- Capability ordering does not change the result.

### Time and causality
- Future frames cannot affect earlier transitions.
- Frame order is preserved.
- Aggregation records the frames consumed.
- Clock-domain crossing without a declared relation fails.
- Equivalent schedules replay identically.

### Recursion and contraction
- Bounded inputs produce contract-compliant outputs under declared
  assumptions.
- Contraction certificates contain all required evidence.
- `NOT_PROVEN` remains distinct from `VIOLATED`.
- Invalid arithmetic cannot produce a valid certificate.
- Source identity and contribution survive integration.

### Serialization
- Canonical forms are byte-stable.
- Unordered host collections cannot perturb output.
- Equivalent source formatting produces identical IR.
- Semantic differences alter canonical identity.
- Golden fixture hashes remain stable.

### Runtime
- Interpreter execution is deterministic.
- Malformed instructions are rejected.
- Invalid operands are rejected.
- Illegal state ownership is rejected.
- Partial execution cannot masquerade as certified completion.
- Replay reconstructs the same state lineage.

### Backend parity
For every supported backend:
- Run shared fixtures.
- Compare semantic outputs.
- Compare certification status.
- Compare lineage.
- Document permitted numerical variance.
- Reject variance outside the declared tolerance contract.

## 4. Running conformance

`aeontest` runs the full suite. A conforming implementation MUST
pass every fixture in the "required" set for its declared
capability declarations. Optional fixtures are run for
implementations declaring the corresponding capability.

## 5. Freeze contract

Aeon Language v0.1 MUST NOT be frozen unless, on the freeze commit:

- All `REQUIRED` specification items are resolved.
- Gates A through I pass.
- The Canonical IR version is frozen.
- The public API is versioned.
- The migration policy is published.
- The reference runtime is deterministic under all replay
  fixtures.
- The conformance suite is green.
- CI on the freeze commit is green.

Only after these conditions may a `aeon-language-v0.1.0` annotated
tag be created. See `12-VERSIONING.md` §7.
