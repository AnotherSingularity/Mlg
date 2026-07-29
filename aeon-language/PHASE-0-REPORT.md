# Phase 0 Report

**Repository:** `AnotherSingularity/Mlg`
**Branch:** `claude/aeon-language-phase-0-24enl0`
**Remote:** `origin` at `http://127.0.0.1:41729/git/AnotherSingularity/Mlg`
**Date generated:** 2026-07-29

This document is required by the mandate §25. It records what the
Phase 0 work delivered and — crucially — what it did **not**
deliver, per the mandate's own instruction: "Do not claim
completion based on effort or code volume. Completion means the
specification, compiler, IR, runtime, library, and conformance
system agree mechanically."

## 1. Branch and remote

- Branch: `claude/aeon-language-phase-0-24enl0`.
- Remote: `origin` (single remote configured; URL above).
- Repository state at Phase 0 start: **completely empty** — no
  prior commits, no default branch, no application code, no
  research documents. The "preservation checkpoint" therefore
  records the empty starting state and the initial scaffolding
  files (README, LICENSE, .gitignore).

## 2. Preservation commit

`be98c510981ce0ca7aeabbc8f11af6137bbab593`
    `chore(aeon): preserve pre-language architecture snapshot`

## 3. Phase 0 commit sequence

In order (P0 through P13):

| P   | SHA        | Subject                                                                       |
| --- | ---------- | ----------------------------------------------------------------------------- |
| P0  | `be98c51`  | chore(aeon): preserve pre-language architecture snapshot                      |
| P1  | `c79aa11`  | docs(language): define constitution, ontology, and status model               |
| P2  | `d1a51ea`  | docs(language): define state, time, causality, ports, and contraction semantics |
| P3  | `d7112fb`  | feat(language): add framework-neutral semantic kernel                         |
| P4  | `9f8ecc1`  | feat(language): add port descriptors and capability negotiation               |
| P5  | `24cc960`  | feat(language): add Recursion substrate contracts and reference implementation |
| P6  | `d71e829`  | feat(language): add canonical graph and IR schemas                            |
| P8  | `3dd3562`  | feat(language): add parser, formatter, and static validator                   |
| P9–P11 | `6ba5250` | feat(language): add semantic instruction set and reference interpreter, scheduler, snapshots, deterministic replay, and reference sources |
| P12 | `fcb1f17`  | test(language): add complete conformance and property-test suite              |
| P13 | `042fd57`  | feat(language): add initial Python host backend and CLI tools                 |

Notes on the sequence:

- **P7** ("canonical serialization + semantic hashing") is not a
  separate commit; its substance was delivered inside `aeon.serialization`
  (in P3) and `aeon.ir` (in P6). This is documented in the P6
  commit body.
- **P9, P10, P11** are combined into one commit because they
  only make sense end-to-end (an interpreter with no scheduler
  cannot run a graph; reference sources with no interpreter can't
  be exercised). Verified with an end-to-end smoke: parse ->
  validate -> lower -> interpret -> replay.
- **P14** (the freeze docs) is intentionally **not present** — v0.1
  MUST NOT be frozen unless every REQUIRED gate passes, and
  Section 6 below explains which do not.

## 4. CI run IDs and terminal results

No GitHub Actions or other CI workflows are configured on this
repository. The mandate §2 says "wait for all workflows triggered
by that push to reach a terminal state before beginning Phase 0
implementation." Because there are no workflows, no wait is
required and no run IDs exist. This is a distinguishing fact:
Gate J ("CI is green on the freeze commit") cannot be evaluated
because there is no CI to be green on. Establishing CI is a
prerequisite of any future freeze attempt.

## 5. Repository structure created

```
Mlg/
├── LICENSE
├── README.md
├── .gitignore
└── aeon-language/
    ├── PHASE-0-REPORT.md                          (this document)
    ├── specification/                             (14 documents)
    │   ├── 00-CONSTITUTION.md
    │   ├── 01-ONTOLOGY.md
    │   ├── 02-TYPE-SYSTEM.md
    │   ├── 03-STATE-SEMANTICS.md
    │   ├── 04-TIME-AND-CAUSALITY.md
    │   ├── 05-PORTS-AND-CAPABILITIES.md
    │   ├── 06-RECURSION.md
    │   ├── 07-CONTRACTION.md
    │   ├── 08-PROVENANCE.md
    │   ├── 09-CANONICAL-IR.md
    │   ├── 10-INSTRUCTION-SET.md
    │   ├── 11-ERROR-MODEL.md
    │   ├── 12-VERSIONING.md
    │   └── 13-CONFORMANCE.md
    ├── schemas/
    │   └── ir-module.schema.json
    ├── compiler/
    │   ├── __init__.py
    │   ├── ast.py
    │   ├── cli.py
    │   ├── formatter.py
    │   ├── lexer.py
    │   ├── parser.py
    │   └── validator.py
    ├── ir/                                        (placeholder; IR types live in standard_library/aeon/ir.py)
    ├── runtime/
    │   ├── __init__.py
    │   ├── interpreter.py
    │   ├── replay.py
    │   └── scheduler.py
    ├── standard_library/
    │   └── aeon/
    │       ├── __init__.py
    │       ├── capability.py
    │       ├── clock.py
    │       ├── contraction.py
    │       ├── core.py
    │       ├── graph.py
    │       ├── ir.py
    │       ├── port.py
    │       ├── provenance.py
    │       ├── recursion.py
    │       ├── serialization.py
    │       ├── signal.py
    │       ├── state.py
    │       └── sources/
    │           ├── __init__.py
    │           └── dummy.py
    ├── backends/
    │   ├── __init__.py
    │   └── python/
    │       └── __init__.py
    ├── conformance/                               (placeholder; fixtures live in tests/)
    ├── examples/
    │   └── two_sources.aeon
    ├── tests/                                     (12 modules; 66 tests)
    │   ├── conftest.py
    │   ├── test_capabilities.py
    │   ├── test_clock_and_causality.py
    │   ├── test_contraction.py
    │   ├── test_end_to_end.py
    │   ├── test_golden_hashes.py
    │   ├── test_identity_and_state.py
    │   ├── test_ir.py
    │   ├── test_parser_validator.py
    │   ├── test_serialization.py
    │   └── test_sources.py
    └── research/                                  (empty; no prior research existed)
```

## 6. Gate-by-gate assessment

The mandate demands honest gate reporting. Each gate is graded
one of **PASS**, **PARTIAL**, or **NOT PASSED**, with the specific
reasons stated.

### Gate A — Constitution: **PASS**

- Ontology is documented (`specification/01-ONTOLOGY.md`, 100+ terms).
- Terminology is defined; RFC-2119 keyword contract stated.
- Normative status model (REQUIRED / PROVISIONAL / EXPERIMENTAL
  / DEPRECATED / REJECTED) exists (`00-CONSTITUTION.md §4`).
- Architectural invariants are listed (`00-CONSTITUTION.md §2`).
- Host/backend separation is explicit (`00-CONSTITUTION.md §3`).
- Unresolved research claims are marked PROVISIONAL
  (`01-ONTOLOGY.md §Provisional research positions`).

### Gate B — Formal semantics: **PASS**

All eleven referenced documents exist and carry normative status:
state / ownership / transitions
(`03-STATE-SEMANTICS.md`), clocks / causality
(`04-TIME-AND-CAUSALITY.md`), ports / capabilities
(`05-PORTS-AND-CAPABILITIES.md`), Recursion (`06-RECURSION.md`),
contraction (`07-CONTRACTION.md`), provenance
(`08-PROVENANCE.md`), certification (embedded across),
errors (`11-ERROR-MODEL.md`). The distinctions the mandate names
explicitly ("not proven ≠ violated", "unavailable ≠ zero",
"rejected ≠ runtime failure", "invalid ≠ absent") are documented
and mechanically preserved (see Gate I evidence).

### Gate C — Type system: **PARTIAL**

`02-TYPE-SYSTEM.md` documents every distinction the mandate
demands (source state vs Recursion state; payload vs state
identity; clock domains; frame types; port types; capability
requirements; owned vs moved state; certified vs uncertified
results; unavailable vs zero-valued). The **runtime**
`OwnershipTable` mechanically enforces the linear-ownership
distinction (verified in `test_identity_and_state.py`) and the
runtime types `Some`/`Unavailable` and `Applied` /
`AppliedUncertified` / `Rejected` / `Failed` mechanically
preserve the certification and availability distinctions.

**Not passing as full PASS because:** the compiler does not yet
perform a full static type check on user-declared Aeon
expressions (v0.1 syntax is declarative; the interpreter does the
type-shaped checks it can, and the validator enforces the
declaration-level rules). A future release must add a static
typechecking pass over full expression syntax.

### Gate D — Canonical semantic graph and IR: **PASS**

- Schemas complete: `aeon-language/schemas/ir-module.schema.json`
  covers every declaration kind, every opcode, every ownership
  tag, every clock kind.
- Canonical ordering defined (`08-PROVENANCE.md §4`; enforced in
  `aeon.serialization`).
- Canonical serialization implemented and tested for byte
  stability across key reorderings.
- Deterministic hashes verified (`tests/test_golden_hashes.py`
  pins a golden hash; `tests/test_ir.py` verifies
  cross-reordering byte identity).
- Malformed IR is rejected (`IRValidationError` with stable code
  strings; verified for `MODULE_ID_MISMATCH`,
  `DOUBLE_CONSUMPTION`, `UNKNOWN_CLOCK`).
- Equivalent programs produce identical IR (verified: two
  IRModule constructions with reversed declaration/capability/clock
  orders yield equal `module_id` and byte-identical
  `to_bytes()`).

### Gate E — Instruction set: **PASS**

`10-INSTRUCTION-SET.md` gives a normative definition (operands,
operand types, preconditions, ownership/clock/causal effects,
result type, certification effect, failure modes, canonical
encoding) for every opcode in every family (State, Signal, Source,
Recursion, Temporal, Contract, Graph, Provenance). Every opcode
is listed in `aeon.ir.Opcode` and validated in the IR schema
`enum`. No opaque opcodes live in interpreter code — every
opcode dispatches to a documented behavior with an explicit
diagnostic when unimplemented.

### Gate F — Reference compiler and interpreter: **PARTIAL**

Passes:
- source parses (`compiler/parser.py`);
- ownership checking works (interpreter + `OwnershipTable`);
- clock validation works (`validator.py` catches
  `CLOCK_CROSSING_UNDECLARED`; interpreter refuses out-of-domain
  ticks);
- causality validation works at declaration level;
- capability negotiation works (`aeon.capability.negotiate`);
- IR generation works (`runtime.scheduler.lower`);
- interpreter execution works (verified end-to-end on the
  example program);
- diagnostics identify source locations (ParseError carries
  file/line/col; validator diagnostics carry SourceSpan).

**Not full PASS because:**
- Compiler does not yet perform full static type checking of
  expression-level constructs (see Gate C).
- Causality analysis at compile time is limited to what the
  declarative syntax exposes; a full data-flow / clock-crossing
  analysis over a richer expression language is future work.

### Gate G — Complete standard library: **PARTIAL**

Present:
- `aeon.core`, `aeon.serialization`, `aeon.clock`, `aeon.provenance`,
  `aeon.state`, `aeon.signal`, `aeon.capability`, `aeon.port`,
  `aeon.contraction`, `aeon.recursion`, `aeon.graph`, `aeon.ir`,
  `aeon.sources` (with `DummyVectorSource` and `DummyRichSource`).

Absent:
- `aeon.types` — the current type surface is folded into
  `aeon.core`; a dedicated module has not been separated.
- `aeon.identity` — the identity constructors live in
  `aeon.provenance`; not yet a dedicated module.
- `aeon.causality` — invariants live in specifications; no
  runtime module dedicated to causality.
- `aeon.contract`, `aeon.certificate` — dedicated modules absent;
  contract records live in IR, contraction certificates in
  `aeon.contraction`.
- `aeon.projection` — the reference projection is inside
  `aeon.recursion`; a dedicated module has not been extracted.
- `aeon.runtime` — the module exists at
  `aeon-language/runtime/`, but as a subsystem rather than the
  `aeon.runtime` package the mandate names.
- `aeon.snapshot` — snapshot types live inside `aeon.port` and
  `aeon.recursion` per-implementation.
- `aeon.testing` — no dedicated framework; tests use pytest
  directly.
- `aeon.math`, `aeon.tensor` — no numerical framework support in
  v0.1 (mandate §12 permits this: "A complete symbolic
  mathematics system is not required for v0.1 unless existing
  Aeon behavior requires it. Do not expand scope").

Splitting is mechanical refactoring; the code exists and is
tested.

### Gate H — Reference runtime: **PASS**

- Multi-source execution: verified with `DummyVectorSource` +
  `DummyRichSource` running in the same graph.
- At least two clock domains: token + integration, both used.
- Aggregation windows: `Window` type + `WINDOW_OPEN` /
  `WINDOW_CLOSE` instructions.
- Recursion integration: `ReferenceContractiveRecursion` with
  full `ContractionCertificate`.
- Certificates are emitted: 4 PROVEN_CONTRACTIVE certificates
  per 4-tick unroll (verified).
- Snapshots restore: verified in unit and property tests.
- Deterministic replay: verified byte-identical.

### Gate I — Conformance: **PARTIAL**

Passes:
- Required-tier source fixtures pass (`test_sources.py`).
- Rich optional-capability fixtures pass (`test_sources.py`).
- Negative fixtures fail correctly (`test_parser_validator.py`,
  `test_ir.py`).
- Canonical fixtures remain stable (`test_golden_hashes.py`).
- Full repository test suite is green: **66 passed** in `pytest`.

**Not full PASS because:**
- Backend parity is claimed only for `aeon.backends.python`.
  There is no second backend against which to run differential
  fixtures, so "backend parity within declared contracts" is
  vacuously satisfied. A real PyTorch or NumPy backend must
  exist for a meaningful parity result.
- CI is not configured (see §4), so the "green on freeze commit"
  criterion cannot be evaluated.

### Gate J — v0.1 freeze: **NOT PASSED**

The freeze contract requires that Gates A–I all pass. Since Gates
C, F, G, and I are PARTIAL, and there is no CI to verify green on
a freeze commit, the freeze contract is not satisfied.

**Specific reasons Gate J did not pass** (per mandate §25 item 16):

1. Gate C is PARTIAL because the compiler lacks a full static
   type-checking pass over expression-level syntax.
2. Gate F is PARTIAL because full static type checking and full
   data-flow causality analysis over a richer expression language
   are not yet implemented.
3. Gate G is PARTIAL because several architecture-level modules
   named in mandate §17 (`aeon.types`, `aeon.identity`,
   `aeon.causality`, `aeon.contract`, `aeon.certificate`,
   `aeon.projection`, `aeon.snapshot`, `aeon.testing`, and
   `aeon.math` / `aeon.tensor` where applicable) have not been
   split out into dedicated modules with stable public APIs, even
   though their substance lives in existing modules.
4. Gate I is PARTIAL because there is only one backend
   (`aeon.backends.python`); backend parity is vacuously
   satisfied and there is no CI to verify green on the freeze
   commit.
5. No `aeon-language-v0.1.0` tag has been created. This is
   intentional. The constitution (§6) prohibits declaring v0.1
   frozen until every REQUIRED item is resolved, and
   `12-VERSIONING.md §7` states the freeze policy explicitly.

### Gate K — Application rewrite authorization: **NOT GRANTED**

Because Gate J did not pass, Gate K cannot be granted. Per
mandate §23 and constitution §6, the Aeon application rewrite
remains **prohibited**. Because no application code exists in
this repository, this prohibition is also vacuously honored — no
application rewrite is currently in progress or planned.

## 7. Public language APIs (v0.1-dev, not frozen)

Stable enough to be relied on by tests today; subject to change
until Gate J:

- `aeon.core`: `SemVer`, `Identity`, `Validity`, `Applied`,
  `AppliedUncertified`, `Rejected`, `Failed`, `Certificate`,
  `Reason`, `ContractViolation`, `ContractViolationCode`,
  `RuntimeError_`, `RuntimeErrorCode`, `Some`, `Unavailable`,
  `Diagnostic`, `Severity`, `SourceSpan`, `unwrap_or_raise`.
- `aeon.serialization`: `canonical_value`, `canonical_bytes`,
  `digest`, `digest_bytes`, `envelope`, `CanonicalizationError`,
  `DEFAULT_DIGEST_METHOD`.
- `aeon.clock`: `ClockDomain`, `ClockKind`, `ClockPosition`,
  `ClockRelation`, `ClockRelationKind`, `Window`.
- `aeon.provenance`: `make_identity`, `Provenance`,
  `ProvenanceFields`, `Lineage`, `LineageRecord`, `graph_id`,
  `node_id`, `transition_id`, `state_id`, `snapshot_id`,
  `signal_id`, `window_id`.
- `aeon.state`: `State`, `Shape`, `Ownership`,
  `OwnershipTable`, `OwnershipError`, `new_state`,
  `payload_digest`.
- `aeon.signal`: `SignalFrame`, `new_signal_frame`, `FrameRange`.
- `aeon.capability`: `CapabilityRef`, `CapabilityTier`,
  `VersionConstraint`, `NegotiationResult`, `Incompatibility`,
  `negotiate`, `REQUIRED_CAPABILITY_NAMES`,
  `PROVISIONAL_CAPABILITY_NAMES`.
- `aeon.port`: `PortDescriptor`, `TypeRef`, `StateModelRef`,
  `Ready`, `ReadUnavailable`, `Refused`, `ReadRequest`,
  `SourceStepResult`, `SourceSnapshot`, `SignalSourcePort`.
- `aeon.contraction`: `ContractionResult`, `Metric`,
  `PrecisionPolicy`, `CertificationMethod`, `Contractive`,
  `ContractionCertificate`, `compose_result`, `compose_margin`.
- `aeon.recursion`: `ProjectionContract`, `ManifoldInput`,
  `project_frame`, `RecursionState`, `Contribution`,
  `UnresolvedInput`, `Emission`, `RecursionStepResult`,
  `RecursionSubstrate`, `RecursionSnapshot`,
  `ReferenceContractiveRecursion`.
- `aeon.graph`: `NodeKind`, `Node`, `Edge`, `ClockDomainDecl`,
  `OwnershipEntry`, `SemanticGraph`, `GraphBuilder`.
- `aeon.ir`: `Opcode`, `OPCODE_VALUES`, `Instruction`,
  `Declaration`, `DeclarationKind`, `ContractRecord`,
  `CapabilityRecord`, `ClockRecord`, `ScheduleRecord`,
  `IRModule`, `IRValidationError`, `validate`, `build_module`.
- `aeon.sources.dummy`: `DummyVectorSource`, `DummyRichSource`.
- `compiler.parser.parse`, `compiler.parser.ParseError`.
- `compiler.formatter.format_module`.
- `compiler.validator.validate`, `compiler.validator.ValidationResult`.
- `runtime.interpreter.Interpreter`, `runtime.interpreter.ExecutionOutcome`.
- `runtime.scheduler.lower`.
- `runtime.replay.replay`, `runtime.replay.ReplayReport`.
- `backends.python.PythonBackend`, `backends.python.PythonBackendInfo`.

## 8. Version tags

- Canonical IR: `0.1.0-dev`.
- Instruction set: `0.1.0-dev`.
- Language: `0.1.0-dev`.
- Standard library public API: `0.1.0-dev`.

## 9. CLI tools implemented

All eight tools from mandate §19 are implemented in
`compiler/cli.py` and exercised in this report's smoke run:

`aeonc`, `aeonrun`, `aeoncheck`, `aeonfmt`, `aeonir`,
`aeongraph`, `aeontest`, `aeonreplay`.

`aeonmigrate` is intentionally deferred until a version boundary
exists.

## 10. Test totals by category

- Serialization: 9 tests
- Identity + state: 6 tests
- Clock + causality: 7 tests
- Capabilities: 5 tests
- Contraction: 6 tests
- Parser + validator: 9 tests
- IR: 5 tests
- End-to-end: 4 tests
- Sources: 9 tests
- Golden hashes: 6 tests

**Total: 66 tests, all passing** (`pytest tests/ -q` reports
`66 passed`).

## 11. Conformance results

- Required-tier source fixtures: PASS.
- Optional-capability fixtures: PASS.
- Negative fixtures: PASS (every documented failure code was
  exercised).
- Canonical fixtures: PASS (byte-stable under reorderings; golden
  digest pinned).
- Full repository test suite: PASS (green).

## 12. Backend parity results

Only one backend (`aeon.backends.python`) exists.
`PythonBackendInfo.numerical_tolerance = 0.0` (bit-exact on
Python floats). There is no second backend, so parity is
**vacuously satisfied**. This is called out as a gap in Gate I.

## 13. Unresolved PROVISIONAL items

Per `01-ONTOLOGY.md`, the following remain PROVISIONAL and MUST
NOT silently become REQUIRED:

- The exact required source-port surface beyond the three
  REQUIRED capabilities.
- `MatrixRead`, `LayerRead`, `DecayControl`, `AssociationWrite`,
  `ConfigurableCadence` capability types.
- Source write-back behavior into Recursion.
- Slow-clock integration cadence coupling to the token clock.
- Aggregation policy across a fast-clock window.
- Recurrent-source feedback topology.
- Source-specific coupling optimizations.

Promotion requires the procedure in `12-VERSIONING.md §4`.

## 14. Known limitations

1. **No CI.** No GitHub Actions workflow exists; the Gate J
   "green on freeze commit" criterion cannot be evaluated.
2. **One backend only.** Backend parity is vacuously satisfied.
3. **Compiler expression-level type checking is not implemented.**
   The parser handles the declarative subset from mandate §5.1.
4. **Standard library layout does not fully match §17.** Several
   modules are folded into other modules rather than split out
   as dedicated public modules.
5. **PROVISIONAL capabilities in `DummyRichSource`.** The rich
   source implements MatrixRead / LayerRead / DecayControl, but
   the underlying capability contracts remain PROVISIONAL.
6. **Reference implementations use pure Python floats.** No
   PyTorch, no NumPy, no CUDA. This is a deliberate mandate §6
   requirement, but it means the numerical policy space is
   trivial (a single element type, a single rounding mode). A
   real backend must exercise the full `PrecisionPolicy`
   contract.
7. **No `aeon-language-v0.1.0` tag has been created.** Constitution
   §6 prohibits it until Gate J passes.

## 15. Gate J outcome — explicit statement

**Gate J did NOT pass.** Reasons:

- Gate C: PARTIAL (missing full static type checking).
- Gate F: PARTIAL (missing full static type + causality analysis
  over richer expressions).
- Gate G: PARTIAL (several §17 modules not separated).
- Gate I: PARTIAL (single backend; no CI).
- CI is not configured; "green on freeze commit" cannot be
  evaluated.

Therefore v0.1 is **not frozen**, no `aeon-language-v0.1.0` tag
is created, and no migration policy is published beyond the
policy contract in `12-VERSIONING.md`.

## 16. Application rewrite authorization

**Not granted.** Because Gate J did not pass, Gate K MUST NOT be
granted (mandate §24). The Aeon application rewrite remains
prohibited by the constitution.

## 17. Recommended next work (out of scope for Phase 0)

1. Configure CI (a `.github/workflows/tests.yml` that runs
   `python3 -m pytest aeon-language/tests/ -q` on every push).
2. Split `aeon.core` into `aeon.core` + `aeon.types` +
   `aeon.identity`, and extract `aeon.contract`,
   `aeon.certificate`, `aeon.projection`, `aeon.snapshot`,
   `aeon.testing` as dedicated modules.
3. Add a second backend (`aeon.backends.numpy` is the smallest
   step) and add differential-parity fixtures.
4. Extend the source language with expression-level constructs
   (transitions, contracts inline) and add a static typechecker
   over them.
5. Validate the REQUIRED source-port surface against a real Aeon
   recurrent implementation before promoting any PROVISIONAL
   capability to REQUIRED.
