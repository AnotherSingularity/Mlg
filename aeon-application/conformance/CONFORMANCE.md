# Aeon Application v0.1.0 — Conformance Suite

The application conformance suite is the mechanical body of
evidence used to answer Gate L-A through L-J. Every profile in
`manifest.json` maps to concrete pytest fixtures inside
`aeon-application/tests/`. A run is considered **passing** iff
every REQUIRED profile reports `passed=true` **and** the running
Aeon Language commit matches the pinned commit in
`aeon-application/AEON-LANGUAGE-LOCK.json`.

## Running

```
python -m aeon_app.conformance
```

Emits a canonical JSON report to stdout containing the manifest
digest, per-profile pass/fail counts, and an aggregate decision.
Return code is `0` if every REQUIRED profile passed, `1`
otherwise.

## Determinism

The suite is deterministic under PYTHONHASHSEED. The reference
CI pins seeds `{0, 1, 42, random}`; a fresh, unmodified checkout
must produce byte-identical manifest digests across all four
runs. Any divergence is a Gate L-F (runtime determinism)
regression and blocks launch.

## Governance

- The manifest schema is versioned; changes require bumping
  `schema_version` and updating this document.
- Adding a profile is additive. Removing or re-scoping an
  existing REQUIRED profile is a launch-blocking change and must
  be recorded in the release report.
- The suite MUST NOT be relaxed to permit progress. If a
  fixture is genuinely defective, fix the fixture; if the
  application is defective, fix the application. Never edit the
  manifest to route around a red profile.
