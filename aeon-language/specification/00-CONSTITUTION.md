# Aeon Language Constitution

**Document status:** REQUIRED — Phase 0
**Applies to:** Aeon Language v0.1 (in development, not frozen)
**Normative:** Yes

This document is the governing specification of the Aeon Language. All
other specification documents in this directory derive their authority
from this constitution. Where any other document conflicts with this
one, this document controls.

## 1. First invariant

> **No host-language representation, backend framework, source
> implementation, or physical substrate defines Aeon's semantics. Aeon
> semantics are defined exclusively by the versioned language
> specification, canonical intermediate representation, and conformance
> contracts.**

Any Python class, PyTorch tensor, CUDA kernel, C++ struct, or hardware
device that executes an Aeon program is an implementation. It does not
determine what the program means. A conforming implementation must
reproduce the semantics defined by this specification family, the
Canonical Aeon IR (`09-CANONICAL-IR.md`), the Aeon Semantic Machine
Instruction Set (`10-INSTRUCTION-SET.md`), and the conformance suite
(`13-CONFORMANCE.md`).

## 2. Architectural invariants

The following are structural invariants of Aeon. They MUST hold for
every valid Aeon program and every conforming implementation.

1. **Substrate independence.** The Recursion substrate is
   source-agnostic. It MUST NOT branch on a source's implementation
   class, host type, or framework. It MAY branch only on negotiated
   semantic capabilities defined in `05-PORTS-AND-CAPABILITIES.md`.

2. **Source pluggability.** An arbitrary number of independently
   evolving signal sources project through negotiated ports into
   Recursion. A recurrent source, a transformer source, a sensor
   source, an error source, a specialist processor, and any future
   source implementation are equally valid behind the source port
   contract.

3. **Contractive integration.** Every Recursion integration is
   contractive under a declared metric and a declared numerical
   policy, or it is explicitly certified as `NOT_PROVEN`,
   `BOUNDED_CONTRACTIVE`, or `VIOLATED`. See `07-CONTRACTION.md`.

4. **Causality preservation.** Every integration preserves causality.
   No transition may observe a frame from its own future, and no clock
   domain may be crossed without an explicit declared relationship.
   See `04-TIME-AND-CAUSALITY.md`.

5. **Provenance preservation.** Every transition preserves
   provenance: source identity, clock position, state lineage, active
   contracts, and language version. Lineage records are append-only.
   See `08-PROVENANCE.md`.

6. **Clock identity preservation.** A frame carries the identity of
   its originating clock domain. Aggregation and cross-domain
   projection MUST record the frames or frame-range digests they
   consumed.

7. **State lineage preservation.** State identity incorporates
   semantic ancestry. Two payloads that hash identically MAY share a
   payload digest but MUST NOT share a state identity unless their
   lineage is identical.

8. **Validity preservation.** A `TransitionResult` distinguishes
   `Applied` (with certificate) from `AppliedUncertified`,
   `Rejected`, and `Failed`. These states MUST NOT be silently
   coerced into one another.

9. **Certification preservation.** A transition that produces an
   uncertified result MUST NOT propagate that result into a
   downstream certified state. Certification status is a first-class
   attribute of state.

## 3. Host and backend separation

The Aeon language kernel MUST NOT depend on any host framework
implementation. Specifically:

- The framework-neutral kernel (`aeon.core`, `aeon.state`,
  `aeon.signal`, `aeon.clock`, `aeon.port`, `aeon.capability`,
  `aeon.contract`, `aeon.contraction`, `aeon.recursion`, `aeon.graph`,
  `aeon.ir`, `aeon.serialization`, `aeon.provenance`) MUST NOT import
  PyTorch, NumPy, CUDA bindings, or any other numerical framework.
- Host backends (`aeon.backends.python`, `aeon.backends.pytorch`,
  `aeon.backends.cuda`, and any future backend) are implementations
  of the language. They lower semantic operations into concrete host
  operations. They MUST NOT redefine language semantics.
- A source implementation (e.g., `aeon.sources.transformer`,
  `aeon.sources.recurrent`, `aeon.sources.rwkv_class`) is an
  implementation behind a source port. It MUST NOT be relied upon by
  the Recursion substrate, the compiler, the interpreter, or the
  standard library.

Violation of host/backend separation is a Gate-A failure.

## 4. Normative status model

Every specification statement in every Aeon document MUST carry
exactly one of the following statuses:

- `REQUIRED` — must be implemented for conformance.
- `PROVISIONAL` — under active study; NOT required for conformance
  until promoted to `REQUIRED`. Provisional items MUST NOT silently
  become required through implementation drift.
- `EXPERIMENTAL` — implemented but not stabilized. May change or be
  removed. Not eligible for the conformance suite.
- `DEPRECATED` — retained for compatibility. New programs MUST NOT
  rely on it. Removal timeline MUST be documented.
- `REJECTED` — considered and rejected. Retained here so that the
  rationale is preserved and the item is not silently re-adopted.

Normative-language keywords (`MUST`, `MUST NOT`, `REQUIRED`, `SHALL`,
`SHALL NOT`, `SHOULD`, `SHOULD NOT`, `MAY`) carry their RFC 2119
meanings. Vague terms such as "normally," "probably," "safe," and
"correct" MUST NOT be used to express normative requirements without a
defined contract.

## 5. Versioning

Aeon uses semantic versioning:

- `major.minor.patch` for the language.
- The Canonical IR carries its own independent version, referenced
  in every IR document.
- The Instruction Set carries its own independent version.
- Every capability declaration carries its own semantic version.

Version boundaries are documented in `12-VERSIONING.md`. Migration
policy is published only after Gate J.

## 6. Prohibitions

The following are prohibited under this constitution until the
corresponding gate is passed and the corresponding authorization is
issued.

Until Gate J:

- MUST NOT declare Aeon Language v0.1 frozen.
- MUST NOT publish a v0.1.0 tag.
- MUST NOT promote a PROVISIONAL specification item to REQUIRED
  without evidence recorded in the specification.

Until Gate K:

- MUST NOT rewrite the Aeon application into the new language.
- MUST NOT delete the current application implementation.
- MUST NOT change model behavior to fit an unfinished language
  abstraction.

Always:

- MUST NOT make RWKV-class behavior mandatory in the core language.
- MUST NOT make transformer behavior mandatory in the core language.
- MUST NOT specialize Recursion to any source implementation.
- MUST NOT treat tensors as self-describing semantic objects.
- MUST NOT use Python object identity as Aeon identity.
- MUST NOT treat absent data as zero.
- MUST NOT treat uncertified output as certified.
- MUST NOT equate inability to prove contraction with proof of
  violation.
- MUST NOT hide clock crossings inside adapters.
- MUST NOT permit future information leakage.
- MUST NOT vendor external codebases as production Aeon
  implementations.
- MUST NOT import external model implementations as production
  dependencies of the language kernel.

## 7. Governing objectives (recap)

1. Preserve the current Aeon work exactly as it exists.
   *(Phase 0 preservation commit — see repository P0 commit.)*
2. Establish the Aeon language in the repository as an independent,
   versioned subsystem.
3. Convert Aeon's architectural concepts into formal language
   semantics.
4. Implement the complete framework-neutral library, canonical IR,
   reference compiler, interpreter, runtime, and conformance suite.
5. Freeze Aeon Language v0.1 only after every required gate passes.
6. Prohibit the application rewrite until the language receives
   formal rewrite authorization.

## 8. Document register

- `00-CONSTITUTION.md` — this document.
- `01-ONTOLOGY.md` — defined terms.
- `02-TYPE-SYSTEM.md` — the Aeon type system.
- `03-STATE-SEMANTICS.md` — state, ownership, moves, snapshots.
- `04-TIME-AND-CAUSALITY.md` — clocks, windows, causal invariants.
- `05-PORTS-AND-CAPABILITIES.md` — port descriptors, capabilities,
  negotiation.
- `06-RECURSION.md` — the Recursion substrate contract.
- `07-CONTRACTION.md` — contraction semantics and certificates.
- `08-PROVENANCE.md` — identity, lineage, canonicalization.
- `09-CANONICAL-IR.md` — canonical intermediate representation.
- `10-INSTRUCTION-SET.md` — semantic machine instructions.
- `11-ERROR-MODEL.md` — validity states, rejection, failure.
- `12-VERSIONING.md` — version boundaries and migration policy.
- `13-CONFORMANCE.md` — the conformance contract.
