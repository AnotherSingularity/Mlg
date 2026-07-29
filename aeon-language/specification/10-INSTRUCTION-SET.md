# Aeon Semantic Machine Instruction Set

**Instruction set version:** `0.1.0-dev`
**Status:** REQUIRED — Phase 0

## 1. Instruction families

The v0.1 instruction set is grouped into eight families:

```
State        STATE_NEW, STATE_READ, STATE_REPLACE, STATE_SNAPSHOT,
             STATE_RESTORE, STATE_RELEASE

Signal       SIGNAL_FORM, SIGNAL_PROJECT, SIGNAL_ROUTE, SIGNAL_BUFFER,
             SIGNAL_AGGREGATE, SIGNAL_EMIT

Source       SOURCE_INIT, SOURCE_STEP, SOURCE_READ, SOURCE_DRIVE,
             SOURCE_QUERY_CAPABILITY

Recursion    RECURSION_INIT, RECURSION_PROJECT, RECURSION_INTEGRATE,
             RECURSION_READ, RECURSION_FEEDBACK

Temporal     CLOCK_DEFINE, CLOCK_TICK, CLOCK_RELATE,
             WINDOW_OPEN, WINDOW_CLOSE

Contract     CONTRACT_BIND, CONTRACT_CHECK, CONTRACT_REQUIRE,
             CONTRACT_REJECT, CONTRACT_CERTIFY

Graph        NODE_ENTER, NODE_EXIT, EDGE_TRANSFER, FORK, JOIN, SELECT

Provenance   LINEAGE_ATTACH, LINEAGE_DERIVE, PROVENANCE_RECORD,
             CANONICALIZE, DIGEST
```

## 2. Universal definition schema

Every instruction is defined by:

```
Instruction {
    opcode                : Ident
    operands              : List<OperandSpec>
    operand_types         : List<Type>
    preconditions         : List<Precondition>
    state_ownership_effect: List<OwnershipEffect>
    clock_effect          : List<ClockEffect>
    causal_effect         : List<CausalEffect>
    result_type           : Type
    certification_effect  : CertificationEffect
    failure_modes         : List<FailureMode>
    canonical_encoding    : EncodingSpec
}
```

Opaque instructions whose semantics live only in interpreter code
are prohibited (see constitution §6). Every instruction below has a
normative definition here.

## 3. State family

### 3.1 `STATE_NEW`
- **Operands:** `type: TypeRef`, `owner: OwnerId`, `initializer: ValueRef`, `clock: ClockDomainRef`
- **Preconditions:** initializer conforms to `type`; owner is a declared source or substrate.
- **Ownership effect:** introduces a new `own` binding.
- **Clock effect:** assigns `clock_position = current(clock)`.
- **Result:** `State<T, owner, clock>` with fresh `StateId`.
- **Certification effect:** `UNCERTIFIED` unless contract-bound.
- **Failure modes:** type mismatch → `Rejected`; owner unknown → `Failed`.

### 3.2 `STATE_READ`
- **Operands:** `state: StateRef`, `view: ViewSpec`
- **Preconditions:** binding is `borrow`, `shared_immut`, or the reader is the owner.
- **Ownership effect:** none (does not move).
- **Result:** view value.
- **Failure modes:** view type mismatch → `Rejected`.

### 3.3 `STATE_REPLACE`
- **Operands:** `state: StateRef (own)`, `new_value: ValueRef`, `transition: TransitionRef`
- **Preconditions:** binding is `own`; `new_value` conforms to state's `T`.
- **Ownership effect:** consumes `state`; produces a successor state whose lineage extends `state`'s lineage with `transition`.
- **Result:** new `State<T, owner, clock>` with fresh `StateId`.
- **Certification effect:** inherits contract binding of `transition` if any.

### 3.4 `STATE_SNAPSHOT`
- **Operands:** `state: StateRef`, `policy: SnapshotPolicy`
- **Preconditions:** `state` is readable.
- **Result:** `Snapshot` (canonical bytes + provenance).
- **Certification effect:** none.

### 3.5 `STATE_RESTORE`
- **Operands:** `snapshot: SnapshotRef`, `owner: OwnerId`
- **Preconditions:** `snapshot` is valid; `owner` is compatible with the snapshot's original owner or authorized by a transfer contract.
- **Result:** new `State<T, owner, clock>` whose `StateId` derives deterministically from `snapshot`.

### 3.6 `STATE_RELEASE`
- **Operands:** `state: StateRef (own)`
- **Ownership effect:** consumes `state` and produces no successor (state becomes historically frozen).
- **Failure modes:** state currently borrowed → `Rejected`.

## 4. Signal family

### 4.1 `SIGNAL_FORM`
- **Operands:** `source: SourceId`, `payload: ValueRef`, `clock: ClockDomainRef`, `sequence: Integer`
- **Result:** `SignalFrame<T, C>` with `SignalId` computed under `08-PROVENANCE.md`.

### 4.2 `SIGNAL_PROJECT`
- **Operands:** `frame: SignalRef`, `projection: ProjectionRef`
- **Preconditions:** `projection` accepts `frame`'s type; port compatibility.
- **Result:** `ManifoldInput`.
- **Failure modes:** projection contract violated → `Rejected`.

### 4.3 `SIGNAL_ROUTE`
- **Operands:** `frame: SignalRef`, `destination: NodeRef`
- **Effect:** delivers `frame` to `destination`'s input buffer.

### 4.4 `SIGNAL_BUFFER`
- **Operands:** `frame: SignalRef`, `buffer: BufferRef`
- **Effect:** appends to buffer.

### 4.5 `SIGNAL_AGGREGATE`
- **Operands:** `window: WindowRef`, `policy: AggregationPolicy`
- **Preconditions:** `window` is closed.
- **Result:** aggregated `SignalFrame` in the target clock domain.
- **Provenance effect:** produced frame's provenance records the consumed window identity.

### 4.6 `SIGNAL_EMIT`
- **Operands:** `frame: SignalRef`, `output: OutputRef`
- **Effect:** emits `frame` to a program output.

## 5. Source family

### 5.1 `SOURCE_INIT`
- **Operands:** `source: SourceRef`, `config: ConfigRef`, `seed: SeedRef`
- **Result:** `SourceState`.

### 5.2 `SOURCE_STEP`
- **Operands:** `source: SourceRef`, `state: SourceStateRef (own)`, `input: SignalRef`, `clock: ClockDomainRef`
- **Result:** `SourceStepResult`.

### 5.3 `SOURCE_READ`
- **Operands:** `source: SourceRef`, `state: SourceStateRef (borrow)`, `request: ReadRequest`
- **Result:** `ReadResult<T>`.

### 5.4 `SOURCE_DRIVE`
- **Operands:** `source: SourceRef`, `state: SourceStateRef (own)`, `drive_value: ValueRef`
- **Precondition:** `VectorDrive` capability negotiated.
- **Result:** successor `SourceState`.

### 5.5 `SOURCE_QUERY_CAPABILITY`
- **Operands:** `source: SourceRef`, `capability: CapabilityRef`
- **Result:** `Some<CapabilitySpec>` or `Unavailable`.
- **Note:** this instruction reflects the negotiated result. It MUST NOT be used to probe unnegotiated capabilities at runtime.

## 6. Recursion family

### 6.1 `RECURSION_INIT`
- **Operands:** `substrate: SubstrateRef`, `config`, `seed`
- **Result:** `RecursionState`.

### 6.2 `RECURSION_PROJECT`
- **Operands:** `substrate`, `frame: SignalRef`, `projection: ProjectionRef`
- **Result:** `ManifoldInput`.

### 6.3 `RECURSION_INTEGRATE`
- **Operands:** `substrate`, `state: RecursionStateRef (own)`, `inputs: List<ManifoldInputRef>`, `clock_position: ClockPosition in Integration`
- **Preconditions:** contract binding requires a `Contractive` contract in scope.
- **Result:** `RecursionStepResult` containing a `ContractionCertificate`.
- **Certification effect:** produces `Certificate<RecursionState>`.

### 6.4 `RECURSION_READ`
- **Operands:** `substrate`, `state (borrow)`, `request`
- **Result:** `RecursionReadResult`.

### 6.5 `RECURSION_FEEDBACK`
- **Operands:** `substrate`, `state (borrow)`, `target_source: SourceRef`, `mapping: FeedbackMappingRef`
- **Precondition:** `Feedback` capability negotiated; clock relation declared.
- **Result:** `SignalFrame` in the target source's clock domain.

## 7. Temporal family

### 7.1 `CLOCK_DEFINE`
- **Operands:** `id: ClockDomainRef`, `kind: ClockKind`
- **Result:** clock domain handle.

### 7.2 `CLOCK_TICK`
- **Operands:** `clock: ClockDomainRef`
- **Effect:** advances the clock's tick by 1.

### 7.3 `CLOCK_RELATE`
- **Operands:** `a: ClockDomainRef`, `b: ClockDomainRef`, `relation: ClockRelation`
- **Effect:** installs the relation between `a` and `b`.

### 7.4 `WINDOW_OPEN`
- **Operands:** `window: WindowRef`, `clock`, `start`
- **Effect:** opens a window in `clock` starting at `start`.

### 7.5 `WINDOW_CLOSE`
- **Operands:** `window: WindowRef`, `end`
- **Effect:** closes the window and computes its identity.

## 8. Contract family

### 8.1 `CONTRACT_BIND`
- **Operands:** `contract: ContractRef`, `target: TransitionRef|ProjectionRef`
- **Effect:** binds contract to target.

### 8.2 `CONTRACT_CHECK`
- **Operands:** `contract: ContractRef`, `subject: StateRef|SignalRef`
- **Result:** `CheckOutcome` = `Passed | Failed | Inconclusive`.
- **Note:** `Inconclusive` is not `Failed`.

### 8.3 `CONTRACT_REQUIRE`
- **Operands:** `contract`, `subject`
- **Effect:** `CONTRACT_CHECK` followed by `Rejected` if not `Passed`.

### 8.4 `CONTRACT_REJECT`
- **Operands:** `reason: ContractViolationRef`
- **Effect:** terminates the current transition with `Rejected`.

### 8.5 `CONTRACT_CERTIFY`
- **Operands:** `contract`, `subject`, `method`, `evidence`
- **Result:** `Certificate<T>` bound to `subject`.
- **Precondition:** evidence adequate to the method.

## 9. Graph family

### 9.1 `NODE_ENTER` / `NODE_EXIT`
- Bracket a node's execution span for provenance.

### 9.2 `EDGE_TRANSFER`
- **Operands:** `edge: EdgeRef`, `payload: ValueRef`
- **Effect:** transfers `payload` along an edge (typed by `edge`).

### 9.3 `FORK`
- **Operands:** `state: StateRef (own)`, `n: Integer >= 2`
- **Result:** `n` states each with distinct `StateId` and lineage.

### 9.4 `JOIN`
- **Operands:** `states: List<StateRef>`, `policy: JoinPolicy`
- **Result:** joined `State` whose lineage records every parent.

### 9.5 `SELECT`
- **Operands:** `predicate`, `then_target`, `else_target`
- **Effect:** deterministic branch. `predicate` MUST be a pure function of already-available inputs (no clock or randomness dependence beyond declared seeds).

## 10. Provenance family

### 10.1 `LINEAGE_ATTACH`
- **Operands:** `child: StateRef`, `parents: List<StateRef>`, `transition: TransitionRef`
- **Effect:** append-only attachment; MUST NOT overwrite an existing lineage.

### 10.2 `LINEAGE_DERIVE`
- **Operands:** `state: StateRef`, `parent_ids: List<StateId>`, `transition: TransitionRef`
- **Result:** computed lineage record for `state`.

### 10.3 `PROVENANCE_RECORD`
- **Operands:** `subject: Any`, `fields: ProvenanceFields`
- **Effect:** attaches a `Provenance` record.

### 10.4 `CANONICALIZE`
- **Operands:** `value: ValueRef`
- **Result:** canonical bytes under the language's canonical serialization.

### 10.5 `DIGEST`
- **Operands:** `bytes: BytesRef`, `method: DigestMethod`
- **Result:** digest.

## 11. Canonical encoding

Every instruction's canonical JSON encoding follows the schema in
`../schemas/ir-module.schema.json` (§6 above). The `opcode` string
is a stable identifier; renaming an opcode is a breaking IR change
and requires an IR version bump.

## 12. Failure model

Every instruction has explicit failure modes. The instruction MUST
either:

- Succeed with a typed result.
- Produce `TransitionResult.Rejected` for a contract violation.
- Produce `TransitionResult.Failed` for a runtime implementation
  problem.
- Produce `AppliedUncertified` where the specification permits.

Silent success on a failing precondition is a Gate-E failure.
