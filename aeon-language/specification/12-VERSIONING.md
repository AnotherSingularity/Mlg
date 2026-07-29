# Versioning

**Status:** REQUIRED — Phase 0

## 1. Version identifiers

Aeon uses semantic versioning `MAJOR.MINOR.PATCH` for four
independent version streams:

| Stream                     | Current       |
| -------------------------- | ------------- |
| Language                   | `0.1.0-dev`   |
| Canonical IR               | `0.1.0-dev`   |
| Instruction set            | `0.1.0-dev`   |
| Standard library public API| `0.1.0-dev`   |

A stream MAY advance independently of others. Every artifact
carries the version of every stream it depends on.

## 2. Change classes

- **Additive** — a new optional field, a new opcode, a new
  capability, a new backend. Additive changes bump `MINOR`.
- **Non-additive** — a schema field renamed or removed, an opcode
  renamed or removed, a capability removed. Non-additive changes
  bump `MAJOR`.
- **Bugfix** — behavioral fix that brings implementation into line
  with specification. Bumps `PATCH`.

## 3. Determinism and versioning

Any change that changes the byte-level canonical serialization of
an existing valid IR module or valid state — even a "bugfix" — MUST
be treated as non-additive.

## 4. Provisional promotion

Promoting a `PROVISIONAL` item to `REQUIRED` MUST:

1. Record the promotion in this document with the promotion date
   (logical, tied to a commit) and the evidence.
2. Update the item's status in its home specification document.
3. Update the ontology (`01-ONTOLOGY.md`) if the term's status
   changed.

Promotion is not implicit. An implementation MAY implement a
`PROVISIONAL` item, but the conformance suite MUST NOT require it
until promotion.

## 5. Deprecation

A `DEPRECATED` item:

- Remains implemented for at least one MINOR release after
  deprecation is announced.
- Has a removal target `MAJOR` version stated at deprecation.
- Has a migration path documented at deprecation.
- Is excluded from conformance-required additions but is still
  covered by conformance regression fixtures for its remaining
  lifetime.

## 6. Migration policy

Migration tooling (`aeonmigrate`) MAY be added after the first
version boundary exists — that is, after v0.1 freezes and v0.2 or
v1.0 begins. Until then, migration is not a specified concern.

## 7. Freeze policy

Freezing a version MUST NOT occur until all Gate-A through Gate-I
requirements pass on the freeze commit and CI is green. See
`13-CONFORMANCE.md` §5.

## 8. Backward compatibility of hashes

An additive schema change MUST NOT change the digest of any
canonical value that does not use the new field. This is verified
by the golden hash fixtures in `conformance/fixtures/`.

If an additive change would change existing digests, the change is
non-additive and requires a `MAJOR` bump.
