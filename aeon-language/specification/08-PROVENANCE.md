# Provenance, Identity, and Canonical Serialization

**Status:** REQUIRED — Phase 0
**Depends on:** `03-STATE-SEMANTICS.md`, `04-TIME-AND-CAUSALITY.md`

## 1. Identity scheme

An Aeon identity is a cryptographic digest of the identity's
defining fields under the language's canonical serialization
(`§4` below). The default digest is `BLAKE2b-256`. Implementations
MAY offer alternative digests but MUST default to `BLAKE2b-256` for
conformance-visible identities.

Identities MUST NOT be derived from:

- Host memory addresses (Python `id()`, C++ pointers, etc.).
- Object identity in the host language.
- Nondeterministic iteration order (Python `set`, unordered
  dictionaries as inputs, etc.).
- Process ID, thread ID, or timestamps.
- Local temporary filesystem paths.
- Randomness that is not part of a declared seed.

## 2. State identity

```
StateId = digest(
    language_version,
    graph_id,
    node_id,
    parent_state_ids,          // sorted by (owner_id, tick)
    transition_id,
    clock_position,
    canonical_payload_digest,
)
```

Where `canonical_payload_digest = digest(canonical_serialize(value))`.

## 3. Payload identity vs state identity

`canonical_payload_digest` is a **payload identity**. Two states
with equal `canonical_payload_digest` MAY share their payload
digest, but their `StateId` values will differ if any other
identity component differs (a different `transition_id`, a
different lineage, a different clock position).

Implementations MUST preserve this distinction. Reducing state
identity to payload identity is a Gate-B failure.

## 4. Canonical serialization

Canonical serialization MUST satisfy:

1. **Deterministic field order.** Field order is fixed by the
   schema for each type (see `09-CANONICAL-IR.md`).
2. **Deterministic collection order.** Sets are serialized as
   sorted arrays under a defined key. Maps are serialized as sorted
   arrays of `[key, value]` pairs under a defined key ordering.
3. **Identifier normalization.** Identifiers are normalized to NFC
   Unicode and lower-cased when the schema defines them as
   case-insensitive.
4. **Number encoding.** Integers are serialized in decimal.
   `ExactRational` uses `numerator/denominator` in lowest terms.
   Floats use the shortest round-trip decimal representation
   preserving exact value.
5. **String normalization.** UTF-8, NFC.
6. **Optional-field treatment.** Absent optional fields are
   omitted, not serialized as `null`. Explicitly-null values, when
   permitted, are serialized as `null`.
7. **Version inclusion.** The serialized envelope carries the
   language version and the schema version.
8. **Unknown-field behavior.** Deserializers MUST reject unknown
   fields unless the schema explicitly permits extension.

Golden fixtures in `conformance/fixtures/serialization/` verify
byte-stability across implementations.

## 5. Provenance record

Every graph, state, transition, certificate, and snapshot carries a
`Provenance` record:

```
Provenance {
    language_version   : LanguageVersion
    graph_id           : GraphId
    node_id            : NodeId | null
    transition_id      : TransitionId | null
    clock_position     : ClockPosition | null
    parent_ids         : List<ParentRef>
    implementation     : ImplementationRef
    active_contracts   : List<ContractRef>
    created_at_tick    : LogicalTick
}
```

`LogicalTick` is a per-run monotonic counter (not wall-clock).
`ImplementationRef` names the concrete backend and version.

## 6. Lineage

Lineage is the append-only ordered chain of parent state
identifiers leading to a state. It is a subset of provenance
restricted to state descent.

Lineage records MUST NOT:

- overwrite a parent;
- rewrite history;
- omit active contracts;
- omit the implementation version;
- detach a state from its source or Recursion owner.

## 7. Canonicalization operation

The `CANONICALIZE` instruction takes any serializable Aeon value
and produces its canonical byte sequence. The `DIGEST` instruction
takes bytes and produces a digest under a declared method.

Both are pure; both produce byte-identical results for equal
inputs; both MUST be free of iteration-order effects.

## 8. Cross-implementation identity

Two conforming implementations that process the same source program
under the same declared policy MUST produce identical `GraphId`,
identical canonical IR bytes, and identical `StateId` values for
the same declared inputs and seeds. This is a Gate-D/I requirement.
