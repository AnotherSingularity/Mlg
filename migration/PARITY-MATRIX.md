# Parity Matrix

**Baseline audit SHA:** `2763c913d75bced7fd96553316b951608891c214`
**Aeon Language SHA:** `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`

Per mandate §11 this document records the classification
(`EXACT`, `WITHIN_DECLARED_TOLERANCE`, `INTENTIONAL_SEMANTIC_CHANGE`,
`MISMATCH`, `NOT_COMPARABLE`) for every comparison between the
legacy implementation and the Aeon migration.

## Parity results

Every comparison requires two implementations. The application
inventory records zero legacy implementations. Every possible
comparison therefore terminates at:

- **`NOT_COMPARABLE`** — mandate §11.1 says this classification
  "requires an explanation and blocks activation unless the
  behavior is demonstrably irrelevant." The explanation here
  is: **no legacy behavior exists to compare against**. This is
  not demonstrably irrelevant, so activation of the
  hypothetical Aeon path is **blocked** for every fixture.

## Numerical parity envelope (mandate §11.2)

No numerical operations exist to bound.

## Shadow duration (mandate §11.3)

No shadow can be run because there is no legacy execution to
shadow.

## Consequence for Gate K-B (mandate §12)

Gate K-B ("Behavioral parity") requires:

- every required fixture is `EXACT` or `WITHIN_DECLARED_TOLERANCE`;
- every intentional semantic change has explicit approval;
- no unexplained mismatch remains;
- replay and restore parity pass.

Every fixture is `NOT_COMPARABLE`. Gate K-B is unpassable.
