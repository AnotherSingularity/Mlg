# Migration Map

**Baseline audit SHA:** `2763c913d75bced7fd96553316b951608891c214`
**Aeon Language SHA:** `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`

Per mandate §5 the migration map records, for every component,
its migration target, migration tranche, parity method, and
rollback method.

## Migration table

The inventory contains zero application components, so the
migration table contains zero rows:

| Component identity | Current file:symbol | Runtime responsibility | Migration target | Tranche | Parity method | Rollback method |
| ------------------ | ------------------- | ---------------------- | ---------------- | ------- | ------------- | --------------- |
| _(none)_ | _(none)_ | _(none)_ | _(none)_ | _(n/a)_ | _(n/a)_ | _(n/a)_ |

## Structural note

Mandate §1 requires this migration to be "a controlled
migration, not a greenfield redesign." A greenfield redesign is
what would be required to populate this table if no application
exists. Producing a synthetic application to "migrate from"
would be:

1. A violation of §1 (would be a greenfield redesign disguised).
2. A violation of §2 ("Do not classify behavior changes as
   parity") — every new-implementation output would be
   compared against fabricated legacy, and parity would be
   vacuously true.
3. A violation of §6.3 ("Do not claim parity from a single
   successful example").
4. A violation of §11.1 (`INTENTIONAL_SEMANTIC_CHANGE` would be
   the only honest classification for every fixture, but the
   mandate requires that classification to have "documented
   rationale; explicit approval; new expected fixture; updated
   specification or application contract; no concealment as
   numerical variance" — none of which exists).

The migration table therefore remains empty.
