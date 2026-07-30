# Aeon Repository — Ruthless Independent Audit

**Artifact audited:** `Mlg-claude-aeon-language-phase-0-24enl0 (1).zip`  
**Audit basis:** Static inspection, clean local test execution, coverage runs, adversarial execution, IR execution, certified-startup tampering, snapshot tampering, launcher inspection, and release-workflow review.  
**Audit date:** 2026-07-30

## Final verdict

**RELEASE CERTIFICATION REJECTED.**

The repository is a substantial and internally consistent prototype, but the following published states are not supported by the code in this ZIP:

- `LAUNCH CERTIFIED` — **withdraw**
- `CERTIFIED RUNTIME ACTIVATED` — **withdraw**
- `WINDOWS PACKAGE VALIDATED` — retain only as **unsigned installer smoke-tested**, not semantic release validation
- `Aeon Language v0.1.0 complete` — reclassify as **experimental topology DSL/runtime prototype**

Do not sign, tag, or publicly release this revision.

## Evidence reproduced

- Language suite: **223 passed**
- Application suite: **100 passed**
- Language coverage: approximately **78%**
- Application coverage: approximately **87%**
- No `.git` directory was present in the ZIP, so commit ancestry, tags, branch state, and reported GitHub Actions run IDs cannot be independently authenticated from this artifact.

Passing tests demonstrate that the repository agrees with its own tests. They do not validate the central architectural or certification claims.

# Critical findings

## C-01 — The application does not execute its canonical Aeon IR

`aeon-application/src/aeon_app/graph/builder.py:518-584` generates an instruction stream containing `SOURCE_STEP` followed by `RECURSION_INTEGRATE`, but it never emits the `SOURCE_READ`, `SIGNAL_FORM`, or `SIGNAL_PROJECT` operations needed to create the `minput.*` bindings consumed by Recursion.

The IR passes `validate_ir()` and then crashes when passed to the reference interpreter:

```text
IR_VALIDATE PASS 21
IR_EXEC_UNCAUGHT KeyError "'minput.attention'"
```

The actual application runs through `aeon_app.application.ApplicationSession`, a separate bespoke Python execution path. Searches of the application code show that the language interpreter is not its authoritative runtime.

**Impact:** The canonical IR is an identity/reporting artifact, not the executable semantics of the application. Claims that the application executes through the Aeon language runtime are false.

## C-02 — The language scheduler discards source output and injects zero vectors

`aeon-language/runtime/scheduler.py:193-224` emits `SOURCE_READ`, then removes the intended `SIGNAL_FORM` instruction and replaces the payload with:

```python
[0.0] * _substrate_dim(...)
```

The comment explicitly states that this is an adapter workaround.

**Impact:** Source output does not reach Recursion in the generated reference program. A certified transition can therefore describe the integration of fabricated zero signals rather than actual source state.

## C-03 — The application falsely widens the contraction certificate scope

`aeon-application/src/aeon_app/recursion/__init__.py:94-123` receives a certificate scoped to `RECURSION_CORE` and changes it to `PROJECTED_RECURSION` whenever the inner result is `PROVEN_CONTRACTIVE`.

No composed proof of the source projection, aggregation, residual paths, or feedback is performed. Declaring domain bounds is not a proof that the projection preserves the required Lipschitz bound.

The running application reports:

```text
CERT_RESULT PROVEN_CONTRACTIVE
CERT_SCOPE PROJECTED_RECURSION
```

**Impact:** The certificate claims a wider mathematical guarantee than was established. This invalidates the certified output status.

## C-04 — “Certified startup” does not bind or verify executable code

`aeon-application/src/aeon_app/certified/__init__.py` verifies version strings, configuration, graph digest, and IR digest. Those digests identify declarations/configuration, not the installed Python implementation bytes.

Adversarial test:

1. Certified startup passed.
2. `ApplicationSession._fresh_frame_for` was monkeypatched to generate zero inputs.
3. Certified startup still passed.
4. Application output changed materially.

```text
CERT_START_BASE_VALID True
CERT_START_TAMPER_VALID True
CERT_OUTPUT_CHANGED True
```

**Impact:** A modified or malicious implementation can produce different behavior while still being labeled `CERTIFIED`.

## C-05 — Certified snapshots accept tampered semantic identity

`aeon-application/src/aeon_app/persistence/__init__.py:116-132` checks only schema/application/language versions and the language commit string. `aeon_app.application.restore()` checks the configuration digest and restores only source state, Recursion state, and clock positions.

The following tampered fields were all accepted during restore:

```text
graph_id ACCEPTED
ir_module_id ACCEPTED
runtime_mode ACCEPTED
backend_id ACCEPTED
event_log_digest ACCEPTED
```

The restore path also fails to restore or verify active windows, scheduler state, capability negotiation, active contracts, random state, feedback biases, and event-log continuity.

**Impact:** A snapshot from a different graph/runtime/backend or altered lineage can be accepted as certified state.

# High-severity findings

## H-01 — IR validation does not validate executable dataflow

`aeon-language/standard_library/aeon/ir.py:256-340` performs structural checks but does not prove that bindings are defined before use or that operands satisfy semantic types and opcode preconditions.

That is why the application IR passes validation and crashes with an undefined `minput.attention` binding.

## H-02 — The interpreter is fail-open for unimplemented semantic instructions

`aeon-language/runtime/interpreter.py:369-413` treats `CONTRACT_CERTIFY`, `CONTRACT_REQUIRE`, provenance, and lineage operations as no-ops. Other unimplemented opcodes generate a warning and execution continues.

The interpreter also catches only `InterpreterError` and `OwnershipError`; ordinary `KeyError`, `ValueError`, and implementation exceptions can escape unstructured.

**Impact:** A program can complete despite unimplemented contract/provenance semantics, while malformed programs can crash outside the defined error model.

## H-03 — The compiler cannot execute the IR it writes

`aeon-language/compiler/cli.py:111-120` raises `NotImplementedError` for IR loading. `aeonc` writes canonical IR, but `aeonrun` cannot load and execute that artifact; it recompiles from source instead.

**Impact:** The compile/deploy boundary is incomplete. The emitted IR is not a deployable program artifact.

## H-04 — The application’s aggregation window does not aggregate its recorded frames

`ApplicationSession.step_tick()` records emission IDs into a window. `integrate_window()` ignores those recorded frames and synthesizes one frame per source from each source’s latest state payload (`aeon_app/application/__init__.py:219-251`).

Earlier frames in a multi-tick integration window are discarded.

**Impact:** The actual runtime does not implement the documented multi-clock aggregation semantics or accurately identify consumed frames.

## H-05 — Source-state ownership is not enforced

The interpreter introduces and consumes ownership for Recursion state, but `SOURCE_STEP` overwrites source state bindings without consuming the previous state or introducing the new state through the ownership table.

**Impact:** The language’s claimed linear state-ownership model is incomplete at a core boundary.

## H-06 — Replay does not compare complete state

`aeon-language/runtime/replay.py:51-63` compares output IDs/digests, contraction certificates, trace opcodes/summaries, and halt reason. It does not compare source states, Recursion state, ownership state, window state, provenance records, or complete lineage.

`ExecutionOutcome.state_bindings` is declared but the interpreter never copies its internal bindings into it.

**Impact:** “Deterministic replay” can pass while internal semantic state differs.

## H-07 — Launcher release-integrity verification is absent

`aeon_app.launcher._release_manifest()` claims that missing/tampered manifests are rejected, but when `release.json` is absent it silently returns version constants. No `release.json` exists in the package tree.

Observed result:

```text
MANIFEST_SOURCE constants
```

No signature or digest of the manifest is checked.

**Impact:** The packaged launcher can call itself certified without a verified release manifest.

## H-08 — The “desktop launcher” is a console smoke utility

`aeon-launcher.spec:72` sets `console=True`. Ordinary launch performs startup verification, emits JSON, and exits. There is no GUI, long-running event loop, user input surface, or model interaction.

**Impact:** “Windows application launch” is materially overstated. The artifact is a packaged CLI/smoke executable.

## H-09 — Signed release workflow contains execution and environment defects

`.github/workflows/aeon-windows-signed-release.yml` uses `windows-latest` while expecting a certificate already installed in the machine certificate store by thumbprint. A normal GitHub-hosted runner will not possess that certificate or HSM context.

The signed/source parity step writes `install-smoke.json` from one working directory, then attempts to read it from another. It also deliberately opens a nonexistent path before the real comparison. The workflow has not been proven by execution.

**Impact:** The protected signing workflow is not release-ready.

## H-10 — Release manifest contradicts the claimed final state

`aeon-application/release/RELEASE-MANIFEST.json` declares:

```text
default_runtime_mode = REFERENCE
CERTIFIED mode is NOT activated
test_count_reference = 79
```

The source claims `CERTIFIED` is active and the current application suite contains 100 tests.

**Impact:** The frozen release evidence is stale and cannot support certification.

## H-11 — The release is not reproducible

Dependencies and build tools are not fully pinned. The project uses minimum-version specifications and floating hosted runner images. PyInstaller, installer tooling, and package transitive dependencies can change between builds.

There is no complete dependency lock or SBOM binding the release to exact artifacts.

## H-12 — Reported repository and CI evidence is unauthenticated in this ZIP

No `.git` history, signed tag, provenance attestation, or exported CI evidence accompanies the source archive.

**Impact:** Named SHAs, branch ancestry, tags, and workflow run IDs remain documentary claims, not independently verifiable evidence in this audit artifact.

# Architectural truth

## The “language” is currently a topology DSL

The source grammar supports source declarations, Recursion declarations, projections, schedules, and a small set of schedule statements. It does not provide a general programming-language surface such as:

- values and user variables
- expressions
- functions
- branching
- general loops
- modules/imports
- user-defined types
- a complete memory model
- exception/control-flow semantics
- general I/O

The advertised “expression-level type system” mostly validates declarations, named capabilities, clocks, and dimensions; there are no general source-language expressions to type-check.

**Accurate classification:** experimental graph/topology DSL with a partial reference interpreter.

## The application is a deterministic synthetic reference demo

Inputs are generated internally from `(source_id, tick)` in `ApplicationSession._fresh_frame_for()`. There is no operational tokenizer, user-input adapter, dataset interface, or useful model task.

Training uses synthetic targets and finite-difference updates over projection scales; it does not train a complete attention/recurrent cognitive system.

**Accurate classification:** deterministic architecture fixture and runtime prototype, not a launchable AI application.

# Positive findings

The audit did find meaningful engineering work:

- Clear separation between language and application directories.
- Canonical serialization and digesting are used extensively.
- Strong attention to deterministic identifiers and explicit metadata.
- 323 tests pass in aggregate.
- Several negative tests and hash-seed checks exist.
- The code is readable, typed in many core areas, and organized around explicit contracts.
- The team repeatedly preserved honest BLOCKED decisions around unavailable signing credentials.

These strengths justify continuing the project. They do not justify the present certification status.

# Required truth correction

Immediately replace the public/internal status with:

```text
AEON LANGUAGE: EXPERIMENTAL PROTOTYPE
AEON APPLICATION: REFERENCE DEMONSTRATOR
CERTIFIED RUNTIME: REJECTED BY INDEPENDENT AUDIT
WINDOWS PACKAGE: UNSIGNED SMOKE PACKAGE ONLY
PUBLIC RELEASE: PROHIBITED
```

# Mandatory correction order

## R0 — Withdraw certification claims

Create an additive audit-rejection commit. Preserve all previous reports, but mark their conclusions withdrawn by independent review. Create no release tags and sign no artifacts.

## R1 — Choose one authoritative execution engine

The application must execute canonical Aeon IR through the language runtime, or the IR/runtime claims must be removed. Delete the dual-semantics arrangement.

Acceptance:

- The application’s compiled IR executes end-to-end.
- No undefined bindings exist.
- Direct Python execution and IR execution are not separate semantic authorities.

## R2 — Repair IR and interpreter semantics

- Implement use-before-definition validation.
- Validate opcode operand types and result types.
- Reject unsupported opcodes before execution.
- Make contract/provenance/lineage instructions real or remove them from v0.1.
- Catch all execution failures into the structured runtime error model.
- Implement canonical IR deserialization and execution.

## R3 — Remove fabricated signal flow

Eliminate zero-vector substitution in the scheduler. Carry actual source reads into `SIGNAL_FORM`/projection bindings and test payload lineage end-to-end.

## R4 — Rebuild contraction certification

- Remove the automatic scope upgrade.
- Prove every included projection and feedback component.
- Compose sound bounds for the exact claimed scope.
- Reserve `PROVEN_CONTRACTIVE` for a verified bound over the whole certified map.
- Otherwise emit `BOUNDED_CONTRACTIVE` or `NOT_PROVEN`.

## R5 — Bind certification to executable artifacts

Certified startup must verify:

- installed distribution hash or signed manifest
- implementation module digests
- source and substrate descriptors actually loaded
- backend implementation identity
- exact dependency lock/SBOM
- graph, IR, config, and schema digests

The monkeypatch test used in this audit must fail certified startup.

## R6 — Make snapshots semantically complete

Verify and restore all frozen fields, including graph, IR, mode, backend, clocks, active windows, scheduler state, capability negotiation, contracts, random state, feedback state, and event-log lineage. Every tamper case in this report must be rejected.

## R7 — Implement real aggregation and replay

Integrate the actual emitted frames inside each window. Replay must compare complete source, Recursion, clock, window, ownership, lineage, and certificate state.

## R8 — Rebuild release packaging

- Generate and package a signed release manifest.
- Reject missing or altered manifests.
- Decide whether the product is a CLI or a desktop app; package and describe it honestly.
- Fix and execute the signing workflow on an authorized signing environment.
- Pin the complete toolchain and dependencies.

## R9 — Independent recertification

Certification must be performed against a fresh clone and immutable commit by a test harness that is not merely the repository’s own conformance wrapper.

Required adversarial gates:

- application IR executes successfully
- zero-signal substitution impossible
- code tampering detected
- snapshot tampering rejected
- certificate scope cannot be widened without proof
- unsupported instructions fail closed
- signed package/source semantic parity passes
- complete Git/tag/CI provenance is available

# Release rule

No claim containing `CERTIFIED`, `VALIDATED`, or `PROVEN` should be restored until every critical and high-severity finding above is closed with mechanical evidence.
