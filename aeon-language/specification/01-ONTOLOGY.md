# Aeon Ontology

**Document status:** REQUIRED — Phase 0
**Depends on:** `00-CONSTITUTION.md`

This document defines the terms used throughout the Aeon
specification. Terms not defined here MUST NOT be used with normative
weight elsewhere in the specification.

## Core terms

### Aeon (system)
A versioned, substrate-independent state-transition system in which
independently evolving signal sources project through negotiated ports
into a contractive recursive manifold, and every integration preserves
causality, provenance, clock identity, state lineage, validity, and
certification status.

### Signal source
An independently evolving producer of typed signal frames. Every
source implements a `SignalSourcePort` (see
`05-PORTS-AND-CAPABILITIES.md`). Examples of source implementations
include recurrent networks, transformer networks, sensor drivers,
error accumulators, and specialist processors. **A source
implementation is not the architecture.**

### Signal frame
A typed, versioned, provenance-carrying unit of output emitted by a
source. See `04-TIME-AND-CAUSALITY.md` for temporal properties.

### Recursion (substrate)
The contractive recursive manifold that integrates projections from
multiple sources into a single evolving certified state. The Recursion
substrate is source-agnostic (see `06-RECURSION.md`).

### Projection
A contract-bounded mapping from a signal frame (produced by a source
via its port) into a manifold-input of the Recursion substrate. A
projection is an implementation of a projection contract, not of a
source.

### Port
A typed interface through which a source or substrate exposes its
capabilities and state model. Ports carry version and capability
descriptors (see `05-PORTS-AND-CAPABILITIES.md`).

### Capability
A stable, versioned, named contract describing an operation a source
or substrate may provide. Capabilities are divided into a REQUIRED
tier that every conforming source MUST provide and an OPTIONAL tier
that is negotiated per-graph.

### Contract
A machine-checkable pre/post/invariant specification bound to a
transition, port, capability, or projection. Contracts are values
(`Contract<T>`) and are canonicalized. See `07-CONTRACTION.md` for
contraction contracts specifically.

### Certificate
Evidence that a contract was checked and its result. A certificate is
a value (`Certificate<T>`) carrying the checked contract's version,
inputs, method, result, and any measured bounds.

### State
A typed value with an identity, an owner, a shape, a clock position,
a lineage, a validity, and its bound contracts. See
`03-STATE-SEMANTICS.md`.

### Transition
A move from one state to a successor state, driven by declared input
signal frames within a declared clock domain. See
`03-STATE-SEMANTICS.md` and `04-TIME-AND-CAUSALITY.md`.

### Transition result
A tagged value distinguishing `Applied` (with certificate),
`AppliedUncertified` (with reason), `Rejected` (with contract
violation), or `Failed` (with runtime error). See `11-ERROR-MODEL.md`.

### Clock domain
A discrete monotonic ordering under which a set of events, frames,
and transitions is timed. Every source, substrate, transition, frame,
and state is associated with exactly one clock domain (see
`04-TIME-AND-CAUSALITY.md`). Cross-domain use requires an explicit
declared relationship.

### Clock position
An identifier for a specific moment in a clock domain. Two clock
positions in the same domain are strictly ordered.

### Window
A bounded, half-open interval `[start, end)` within a clock domain
identifying a set of frames or events available for a specific
aggregation or projection.

### Provenance
The append-only record of how a state, signal frame, certificate, or
snapshot came to exist: language version, graph identity, node
identity, parent state identifiers, transition identifier, clock
position, and canonical payload identity.

### Lineage
The specific, ordered chain of parent state identifiers leading to a
given state. Lineage is a subset of provenance dedicated to state
descent.

### Snapshot
A canonical, restorable serialization of a state (or set of states)
together with its provenance. Snapshots participate in identity: a
snapshot of state `S` has an identity derived from `S`'s identity and
the snapshot policy.

### Semantic graph
The typed graph produced by resolving an Aeon source program. Node
identity, edge identity, port types, owned states, clock domains,
contracts, and capabilities are all named in the graph.

### Canonical IR
A deterministic, serializable, schema-validated intermediate
representation of a semantic graph. Equivalent programs produce
byte-identical canonical IR. See `09-CANONICAL-IR.md`.

### Instruction
A member of the Aeon Semantic Machine Instruction Set (see
`10-INSTRUCTION-SET.md`). Instructions have formal operands, types,
preconditions, effects, and canonical encodings.

### Backend
An implementation that lowers Aeon instructions into concrete host
operations (Python, PyTorch, NumPy, C++, CUDA, or a future substrate).
Backends implement the language; they do not define it.

## Distinctions that MUST NOT be conflated

- **Payload identity vs state identity.**
  Two states may have equal payloads (identical byte-level contents)
  yet distinct state identities if their lineage differs.

- **Uncertified vs certified.**
  A result is not certified merely because it exists. Certification
  requires a matching contract binding and a produced certificate.

- **Rejected vs failed.**
  `Rejected` is a semantic outcome — a contract violation. `Failed`
  is a runtime outcome — the implementation was unable to complete
  the operation. Neither is a substitute for the other.

- **Not proven vs violated.**
  Failure to prove a property (e.g., contraction) is not the same as
  proof of its negation. See `07-CONTRACTION.md`.

- **Unavailable vs zero.**
  Absence of a value is not zero. Absence must produce an explicit
  `UNAVAILABLE` result.

- **Absent vs invalid.**
  A value that is not present is not the same as a value that has
  been contract-checked and found invalid.

- **Source private state vs Recursion state.**
  A source's internal state (e.g., a source's own recurrent buffers)
  is not the Recursion substrate's state. The two participate in
  different clock domains and different ownership scopes.

- **Semantic graph vs execution plan.**
  The semantic graph is what a program means. An execution plan is
  one deterministic strategy for executing it on a specific backend.

- **Contract vs certificate.**
  A contract is a specification. A certificate is evidence of
  checking it.

- **Capability vs implementation.**
  A capability is a versioned named contract. An implementation is
  code that satisfies (some subset of) capabilities.

## Reserved capability names (initial candidates)

The following capability identifiers are reserved in the v0.1 pre-freeze
period. Their exact request/result types are defined in
`05-PORTS-AND-CAPABILITIES.md`.

| Capability             | Status       |
| ---------------------- | ------------ |
| `VectorRead`           | REQUIRED     |
| `VectorDrive`          | REQUIRED     |
| `PerTokenStep`         | REQUIRED     |
| `MatrixRead`           | PROVISIONAL  |
| `LayerRead`            | PROVISIONAL  |
| `DecayControl`         | PROVISIONAL  |
| `AssociationWrite`     | PROVISIONAL  |
| `ConfigurableCadence`  | PROVISIONAL  |

The three REQUIRED capabilities constitute the required-tier source
contract. Every conforming source MUST implement them. Provisional
capabilities are subject to change until validated against an actual
Aeon source implementation (see `05-PORTS-AND-CAPABILITIES.md`).

## Provisional research positions

The following positions from prior architectural study are recorded
as `PROVISIONAL` until validated:

- The exact required source-port surface beyond the three REQUIRED
  capabilities above.
- Matrix-state reads (`MatrixRead`).
- Source write-back behavior into the Recursion substrate.
- Slow-clock integration cadence and its coupling to the token clock.
- Aggregation policy across a fast-clock window.
- Recurrent-source feedback topology.
- Direct association writes (`AssociationWrite`).
- Decay-control behavior (`DecayControl`).
- Layer-level reads (`LayerRead`).
- Source-specific coupling optimizations.

A promotion from `PROVISIONAL` to `REQUIRED` MUST be recorded in this
document and in the corresponding subsystem specification, with
evidence.
