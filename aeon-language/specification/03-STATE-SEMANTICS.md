# State Semantics

**Status:** REQUIRED — Phase 0
**Depends on:** `02-TYPE-SYSTEM.md`

## 1. State record

Every state value has the record:

```
State<T, O, C> {
    id             : StateId
    owner          : OwnerId       // source_id or substrate_id
    value          : T
    shape          : Shape
    clock_position : ClockPosition in C
    lineage        : Lineage
    validity       : Validity
    contract_bindings : List<Contract<*>>
}
```

`StateId` MUST be computed by the identity scheme defined in
`08-PROVENANCE.md`. `StateId` MUST NOT be derived from a host memory
address, from a Python `id()`, from process id, or from any
nondeterministic iteration order.

## 2. Ownership

State ownership is linear by default:

- The declaration `state s = initialize P` binds `s` as `own`.
- The move expression `move s` transfers ownership out of the current
  scope.
- After a move, the moved binding is `frozen` in scope: it MAY be
  read as an immutable historical state (for audit) but MUST NOT be
  re-mutated or used as the current state.
- Reading through a `borrow` binding does not move.

The compiler MUST reject:

- **Double mutation** — two mutations of the same live `own` state
  without an intervening move.
- **Use after move** — reading a moved binding except through an
  explicit historical audit contract.
- **Undeclared shared mutable state** — two writers with concurrent
  ownership of the same state identity.
- **Cross-source private-state mutation** — a source may mutate its
  own private state only; it MUST NOT mutate another source's
  private state.
- **Lineage replacement** — no operation may overwrite `lineage`.
- **Owner impersonation** — a transition running under owner `O` MUST
  NOT produce a state with a different `owner` unless a declared
  transfer contract authorizes it.

## 3. Transitions

A transition is a typed function:

```
Transition<I, O, C_in, C_out> {
    input_frames  : List<Signal<*, C_in>>
    input_states  : List<State<*, own_or_borrow, *>>
    output_state  : State<O, owner, C_out>
}
```

Executing a transition:

1. Consumes the declared `own` inputs (moves them).
2. Reads the declared `borrow` inputs without moving.
3. Produces one output state whose `lineage` extends the input
   state lineages.

Two transitions with disjoint owned-input sets MAY execute
concurrently.

## 4. Fork

State branching is explicit:

```
(a, b) = fork snapshot s
```

`fork` consumes `s` and produces two states `a` and `b`, each with
its own `StateId` and its own `Lineage` extending `s`'s lineage. The
compiler MUST reject any use of `s` after a `fork`.

## 5. Snapshots

A snapshot is a canonical, restorable serialization of a state:

```
Snapshot {
    snapshot_id  : SnapshotId
    of           : StateId
    canonical    : Bytes    // canonical serialization
    provenance   : Provenance
    version      : LanguageVersion
}
```

Snapshots MUST be canonical (see `08-PROVENANCE.md` and the
serialization contract). Restoring a snapshot MUST produce a state
whose `id` derives deterministically from the snapshot; two restores
of the same snapshot MUST yield the same `StateId`.

Restoring a snapshot MUST NOT rewrite the lineage of any state that
existed before the restore. A restore is itself a lineage event.

## 6. State identity

State identity is computed as:

```
StateId = digest(
    language_version,
    graph_id,
    node_id,
    parent_state_ids,   // ordered
    transition_id,
    clock_position,
    canonical_payload_digest,
)
```

Where `canonical_payload_digest` is derived from the canonical
serialization of `value` (see `08-PROVENANCE.md`). Two states with
equal `canonical_payload_digest` MAY share a payload digest but MUST
NOT share `StateId` unless every component above is equal.

## 7. Validity states

Every state carries a `Validity` from the set:

```
VALID
PROVISIONALLY_VALID
UNCERTIFIED
CONTRACT_VIOLATED
INVALID
UNAVAILABLE
```

Transition rules:

- `VALID` inputs MAY produce a `VALID` output only if a matching
  certificate is produced.
- Any `INVALID`, `CONTRACT_VIOLATED`, or `UNAVAILABLE` input
  produces a same-tagged output unless a declared recovery contract
  handles it.
- `UNCERTIFIED` propagates as `UNCERTIFIED` unless a
  `CONTRACT_CERTIFY` step succeeds.
- `PROVISIONALLY_VALID` is not `VALID`; a downstream consumer that
  requires `VALID` MUST reject it.

## 8. Certification effect

Certification is a first-class effect. A transition typed
`Transition<I, Certified<O>, ...>` MUST attach a `Certificate<O>` to
its output state. The certificate MUST include:

- The bound contract identifier and version.
- The transition identifier.
- The input state identifiers (ordered).
- The clock position.
- The certification method and its parameters.
- The result (see `07-CONTRACTION.md` for the contraction case).

Absence of a certificate on a `Certified<O>` transition is a
Gate-B/E failure of the implementation.
