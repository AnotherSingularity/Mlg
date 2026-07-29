# Runtime Modes

**Status:** REQUIRED — Gate L
**Depends on:** `00-APPLICATION-CONSTITUTION.md` §5

The application supports exactly three runtime modes. Any
unknown mode string is fail-closed. The default until Gate L-J
passes is `REFERENCE`.

## REFERENCE

Purpose: semantic fixtures, compiler tests, runtime tests,
snapshot tests, replay tests, conformance.

Constraints:

- Only deterministic reference source implementations may be
  loaded.
- Small fixed dimensions (default hidden dim: 4 per source).
- CPU execution only (either the Python reference backend or
  the pure-NumPy backend).
- Fixed seed policy; overriding the seed policy is rejected.
- Reference scheduler; no experimental cadence strategies.
- Complete tracing enabled by default.
- Strict validation: every configuration mismatch is an error.
- Training is prohibited in this mode.

## DEVELOPMENT

Purpose: iteration on real components.

Constraints:

- Any registered source implementation may be loaded.
- Dimensions are configurable within the shape contract.
- Training is permitted.
- Debug tracing is available.
- Experimental capabilities may be used; each MUST be marked
  `experimental=True` in its capability descriptor.
- Checkpoints may be written that are not fully sealed
  (marked `provisional=True`).

## CERTIFIED

Purpose: the launched application.

Constraints (each is a startup check; failure is fail-closed):

- Configuration digest matches an approved digest recorded in
  `aeon-application/reports/AEON-GREENFIELD-BUILD-REPORT.md`
  Gate L-J.
- The pinned Aeon Language certified SHA is loaded.
- Only approved source implementations are loaded.
- Only approved backends are loaded.
- Snapshot schema version matches the approved value.
- Capability negotiation must be `compatible = true` with no
  incompatibilities.
- Conformance runner reports `overall_conformance_result = PASS`.

`CERTIFIED` MUST NOT be the default until Gate L-J passes.

## Mode transitions

Modes are chosen once per application session. The application
does not switch modes at runtime. A failed startup check in
`CERTIFIED` mode raises `AeonModeRejected` (fail-closed); it
MUST NOT silently fall back to `DEVELOPMENT` or `REFERENCE`.
