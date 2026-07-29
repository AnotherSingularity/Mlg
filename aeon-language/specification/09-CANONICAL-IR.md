# Canonical Aeon IR

**IR version:** `0.1.0-dev`
**Status:** REQUIRED — Phase 0
**Depends on:** `08-PROVENANCE.md`, `10-INSTRUCTION-SET.md`

## 1. Purpose

The Canonical Aeon IR is a deterministic, serializable, schema-
validated intermediate representation of a semantic graph.
Equivalent programs MUST produce byte-identical IR under the
canonical serialization defined in `08-PROVENANCE.md`.

## 2. Module structure

A canonical IR module is a JSON document with the top-level
envelope:

```
{
  "aeon_ir_version": "0.1.0-dev",
  "language_version": "0.1.0-dev",
  "digest_method": "blake2b-256",
  "module_id": "<GraphId digest>",
  "declarations": [ ... ],
  "graph": { ... },
  "contracts": [ ... ],
  "capabilities": [ ... ],
  "clocks": [ ... ],
  "schedule": { ... },
  "instructions": [ ... ]
}
```

The schema is defined in `../schemas/ir-module.schema.json`.

## 3. Determinism requirements

1. Field order inside every object follows the schema.
2. Arrays whose elements are unordered semantically MUST be sorted
   under the schema-declared sort key.
3. Numeric encoding follows `08-PROVENANCE.md §4`.
4. String encoding is UTF-8 NFC.
5. Unknown fields are rejected.
6. Two source programs whose semantic graphs are equal produce
   byte-identical IR.
7. Two source programs whose semantic graphs differ MUST produce
   distinct IR — the canonicalization MUST NOT collapse distinct
   semantics.

## 4. Declaration types

Declarations declare graph nodes and their bindings:

- `source_declaration`      — declares a signal source and its
                              port descriptor.
- `recursion_declaration`   — declares a Recursion substrate.
- `projection_declaration`  — declares a projection contract from
                              a source into a substrate.
- `clock_declaration`       — declares a clock domain.
- `clock_relation`          — declares a cross-domain relationship.
- `contract_binding`        — binds a contract to a transition or
                              projection.
- `window_declaration`      — declares an aggregation window.
- `output_declaration`      — declares a program output.
- `snapshot_declaration`    — declares a snapshot point.

Every declaration carries an `id`, a `kind`, and a canonical body.

## 5. Graph section

```
"graph": {
  "graph_id":  "<digest>",
  "nodes":     [ { "id": "...", "kind": "...", ... } ],
  "edges":     [ { "id": "...", "from": "...", "to": "...", ... } ],
  "clock_domains": [ ... ],
  "ownership_map": { ... }
}
```

Nodes and edges are sorted by `id`.

## 6. Instructions section

The `instructions` array is the linearized execution schedule of
semantic instructions (see `10-INSTRUCTION-SET.md`). Each instruction
is:

```
{
  "opcode":       "STATE_NEW",
  "operands":     [ ... ],
  "operand_types":[ ... ],
  "preconditions":[ ... ],
  "clock":        "<ClockDomainRef>",
  "clock_position":"<ClockPosition>",
  "contract":     "<ContractRef>|null",
  "result_binding":"<ResultId>",
  "source_span":  "<SourceSpan>"
}
```

## 7. Validation

An IR module is valid iff:

1. It conforms to `../schemas/ir-module.schema.json`.
2. Its `module_id` equals `digest(canonical(body_without_module_id))`.
3. Every referenced identifier resolves.
4. Every instruction's operands satisfy the instruction's declared
   type requirements (see `10-INSTRUCTION-SET.md`).
5. Every ownership consumption is followed by no further mutation
   of the same state binding.
6. Every clock crossing is authorized by a declared relation.
7. The instruction stream is causally consistent with the declared
   clock domains.

Invalid IR MUST NOT be executed by a conforming interpreter.

## 8. Hashing

`digest(canonical(module))` is stable across runs of the same
version. Golden fixtures in
`conformance/fixtures/ir/` verify hash stability.

## 9. Version stability

Between v0.1 versions, the IR schema MAY evolve. Every non-additive
change bumps the `aeon_ir_version` and requires an entry in
`12-VERSIONING.md`. Additive changes (new optional fields) MUST NOT
change the digest of a module that does not use them.
