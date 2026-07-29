# Ports and Capabilities

**Status:** REQUIRED (v0.1 required tier), PROVISIONAL (optional tier)
**Depends on:** `02-TYPE-SYSTEM.md`, `03-STATE-SEMANTICS.md`,
`04-TIME-AND-CAUSALITY.md`

## 1. Port descriptor

Every port carries a descriptor:

```
PortDescriptor {
    port_id                  : PortId
    port_version             : SemVer
    required_capabilities    : Set<CapabilityRef>
    offered_capabilities     : Set<CapabilityRef>
    accepted_input_types     : List<Type>
    emitted_output_types     : List<Type>
    clock_domain             : ClockDomainRef
    state_model              : StateModelRef
}
```

`PortDescriptor` is a value type. It is canonicalizable (see
`08-PROVENANCE.md`).

## 2. Required source port

Every conforming signal source implements the following interface
(status: REQUIRED for v0.1):

```
SignalSourcePort {
    describe()  -> PortDescriptor

    initialize(config, seed) -> SourceState

    step(input   : SignalFrame,
         state   : SourceState,   // owned
         clock   : ClockPosition)
        -> SourceStepResult

    read(state   : SourceState,   // borrowed
         request : ReadRequest)
        -> ReadResult

    snapshot(state : SourceState) -> SourceSnapshot

    restore(snapshot : SourceSnapshot) -> SourceState
}
```

`SourceStepResult` MUST have the shape:

```
SourceStepResult {
    next_state    : SourceState        // owned
    emissions     : List<SignalFrame>
    certificates  : List<Certificate<*>>
    diagnostics   : List<Diagnostic>
}
```

Note: this required surface is validated against the actual Aeon
recurrent implementation before promotion from `REQUIRED (v0.1)`
into a permanent commitment. Its shape MUST NOT be permanently
frozen merely because prior architectural study (e.g., RWKV-class
research) suggests it.

## 3. Capability tiers

### 3.1 REQUIRED capabilities

Every conforming source MUST offer these three capabilities.

| Capability      | Purpose                                              |
| --------------- | ---------------------------------------------------- |
| `VectorRead`    | Read a shaped vector from the source's current state |
| `VectorDrive`   | Accept a shaped vector as external input             |
| `PerTokenStep`  | Advance the source by one token-clock tick           |

Type contracts (initial):

```
VectorRead : SourceState -> ReadResult<Tensor<Float, Shape([dim])>>
VectorDrive : (SourceState, Tensor<Float, Shape([dim])>)
              -> SourceState
PerTokenStep : (SourceState, ClockPosition in Token)
              -> SourceStepResult
```

### 3.2 PROVISIONAL capabilities

The following capability identifiers are reserved but their exact
type contracts are `PROVISIONAL` until validated:

- `MatrixRead`  — read a shaped matrix from state.
- `LayerRead`   — read per-layer activations.
- `DecayControl` — configure or query decay parameters.
- `AssociationWrite` — direct associative write to state.
- `ConfigurableCadence` — reconfigure the source's step cadence.

## 4. Capability negotiation

Negotiation resolves the set of capabilities to be used between a
source and a substrate for a specific graph. Negotiation MUST be
deterministic and canonicalizable.

Negotiation returns:

```
NegotiationResult {
    compatible          : Bool
    selected_versions   : Map<CapabilityRef, SemVer>
    required_path       : List<CapabilityRef>
    optional_paths      : List<CapabilityRef>
    fallback_path       : List<CapabilityRef>
    incompatibilities   : List<Incompatibility>
}
```

Rules:

1. `compatible = false` iff any REQUIRED capability is not offered
   or its version constraint cannot be satisfied.
2. Optional capabilities MAY be selected only after negotiation; a
   graph MUST NOT probe for a capability at runtime by trying to
   call it.
3. Capability absence MUST produce an explicit result. It is
   prohibited (see constitution §6) to represent absence with
   `None`, a zero tensor, a failed attribute lookup, an exception
   caused by probing, or a silent fallback.
4. Ordering of the capability inputs to negotiation MUST NOT change
   the result. This is verified by a conformance property test.

## 5. Reading through a port

Reads through a port are typed by the capability being invoked and
by the source state's clock position. Read results have the type:

```
ReadResult<T> =
      Ready<T>
    | Unavailable<Reason>
    | Refused<ContractViolation>
```

`Unavailable` MUST NOT be silently coerced to a default value.
`Refused` MUST NOT be silently coerced to `Unavailable`.

## 6. Port compatibility

Two ports are compatible for a given projection contract iff:

- Their `port_version` values agree on major version.
- Every capability the projection requires is offered by the source
  side (or is provably not required by the projection).
- Every type constraint stated by the projection is satisfied by
  the source's `emitted_output_types` or `accepted_input_types`.
- Their `clock_domain` references are either identical or bridged
  by a declared clock relationship (see `04-TIME-AND-CAUSALITY.md`
  §3).

## 7. Version negotiation

Version selection is deterministic:

1. The compiler enumerates offered versions.
2. For each capability, the highest offered version satisfying the
   projection's version constraint is selected.
3. If no version satisfies the constraint, `compatible = false`.

Aeon does not perform prerelease version selection in v0.1.
