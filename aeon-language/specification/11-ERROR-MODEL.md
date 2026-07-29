# Error Model

**Status:** REQUIRED — Phase 0
**Depends on:** `03-STATE-SEMANTICS.md`, `07-CONTRACTION.md`, `10-INSTRUCTION-SET.md`

## 1. Result tags

Every transition, instruction, and certified operation produces a
`TransitionResult<T>` from the set:

```
TransitionResult<T> =
      Applied<T, Certificate<T>>
    | AppliedUncertified<T, Reason>
    | Rejected<ContractViolation>
    | Failed<RuntimeError>
```

The following coercions are prohibited (see constitution §6):

- `AppliedUncertified` → `Applied`   (silent certification)
- `Rejected`           → `Failed`    (contract violation → runtime error)
- `Failed`             → `Rejected`  (runtime error → contract violation)
- `Rejected`           → `AppliedUncertified` (rejection → tolerated)

## 2. Validity states (recap)

From `03-STATE-SEMANTICS.md`:

```
VALID
PROVISIONALLY_VALID
UNCERTIFIED
CONTRACT_VIOLATED
INVALID
UNAVAILABLE
```

Runtime rules:

- No implementation may silently upgrade validity.
- Downgrades occur automatically on contract failure.
- `UNAVAILABLE` values MUST NOT be observed as zero.

## 3. Reasons and violations

### 3.1 `Reason` (for `AppliedUncertified`)
- `NoContractBound`
- `CertificationInconclusive`
- `MethodNotApplicable`
- `PolicyAllowsUncertified(policy_id)`

### 3.2 `ContractViolation` (for `Rejected`)
- `TypeMismatch`
- `ShapeMismatch`
- `OwnershipViolation`
- `CausalityViolation`
- `ClockCrossingUndeclared`
- `WindowIdentityMissing`
- `FutureLeakage`
- `DuplicateConsumption`
- `ContractionViolated`
- `NumericalInvalid`
- `CapabilityAbsent`
- `NegotiationFailure`
- `SnapshotMismatch`

### 3.3 `RuntimeError` (for `Failed`)
- `HostFrameworkError(details)`
- `OutOfMemory`
- `IoError(details)`
- `InternalConsistencyError(details)`

A `Failed` result is a bug or an environmental failure. It is not a
semantic outcome and MUST NOT be produced as a substitute for
`Rejected`.

## 4. Diagnostics

Every error carries a `Diagnostic` value:

```
Diagnostic {
    severity     : error | warning | info
    code         : DiagnosticCode
    message      : String
    source_span  : SourceSpan | null
    involved_ids : List<Ref>
    remediation  : String | null
}
```

Compiler and validator diagnostics MUST include a `source_span`
when the diagnostic originates from a source-level construct.

## 5. Halting model

The runtime halts when:

1. A program's declared outputs are all `EMIT`ted, or
2. A `Rejected` propagates to the top-level program scope, or
3. A `Failed` propagates to the top-level program scope, or
4. An explicit `HALT` instruction executes (if added in a later
   version).

On a halt, the runtime MUST publish:

- The final validity of every declared output.
- The final certificate for every certified transition.
- The lineage of every produced state.
- The consumed provenance of every emitted frame.

## 6. Recovery contracts

A recovery contract MAY specify that a `Rejected` of a particular
`ContractViolation` code is handled by an alternative transition.
Recovery is explicit and typed; it MUST NOT be implicit. A recovery
MUST NOT convert `NUMERICALLY_INVALID` into `VALID` — the recovery's
successor state must itself be independently certified.

## 7. Partial execution

A partially executed transition (interrupted by `Failed`) MUST NOT
produce a successor state visible to any downstream consumer. Its
partial effects, if any, MUST be discarded, and the pre-transition
state MUST remain the current state.

The runtime MUST log the partial execution with a `Diagnostic` and
MUST NOT emit any certificate purporting to cover it.
