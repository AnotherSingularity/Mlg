# L15 — Certified Runtime Activation Report

**Starting SHA:** `293696af850603225bb461553a4178e37eee2b94`
**L15 SHA:** *populated at commit time*
**Default runtime mode:** `CERTIFIED` (was `REFERENCE`)
**Certified activation version:** `0.1.0`
**Application version:** `0.1.0`
**Aeon Language version:** `0.1.0`
**Aeon Language certified commit:** `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`

## 1. Default-mode change

The single authoritative default is `aeon_app.certified.DEFAULT_RUNTIME_MODE`.
Every CLI entry point and every internal factory routes through
`aeon_app.cli._default_config()` / `aeon_app.certified.default_config()`
so there is exactly one location a reviewer must inspect to
understand what the application does when no mode is supplied.
Neither `reference_config()` nor any example changes its mode
default silently — REFERENCE-mode fixtures remain available and
explicit.

## 2. Frozen certified configuration

Archived at `aeon-application/configs/certified-v0.1.json`.
Every certified startup deterministically re-derives this
configuration and compares its digest to the frozen value.

| Field                    | Value                                                              |
| ------------------------ | ------------------------------------------------------------------ |
| `config_digest`          | `5cd0371f157fe9dd921c45b888ece3228aee7f9b3a247968e6c7714fdb88753d` |
| `graph_id`               | `dbbb6c3bb2a7ee1e6d4945b6509cefaee2a77c92918237fa8098d66c05dac565` |
| `ir_module_id`           | `9cf9ce5377d7f81e6382cc6aa4d647f2ee585818417cfefdb02b608e26f5ad76` |
| `instruction_count`      | `21`                                                               |
| `backend`                | `python`                                                           |
| `feedback_gates`         | `0.0` (approved certified value; §L15.2.5 keeps feedback at zero)  |

## 3. Language lock

The pinned lock is verified on every runtime invocation via
`aeon_app.config.language_lock.verify_language_lock()`. The
resource lives inside the installed package
(`aeon_app/AEON-LANGUAGE-LOCK.json`) and is loaded with
`importlib.resources`. Certified startup additionally verifies
that the loaded `aeon.LANGUAGE_VERSION` matches
`AEON_LANGUAGE_REQUIRED_VERSION` and that the certified commit
matches `AEON_LANGUAGE_CERTIFIED_COMMIT`.

## 4. Startup verification (`aeon_app.certified.verify_certified_startup`)

Runs before any source or Recursion state is initialized
(mandate §L15.2.4). Emits a `CertifiedStartupResult` with per-
check flags. On success:

    valid=True,
    application_version=APPLICATION_VERSION,
    language_version=lock.language_version,
    language_commit=lock.certified_commit,
    graph_digest=CERTIFIED_GRAPH_ID,
    ir_digest=CERTIFIED_IR_MODULE_ID,
    configuration_digest=CERTIFIED_CONFIG_DIGEST,
    backend=CERTIFIED_BACKEND_ID,
    checks={
        runtime_mode_is_certified, configuration_resolves,
        backend_matches, language_lock_verified,
        language_identity_matches, configuration_digest_matches,
        graph_digest_matches, ir_digest_matches,
        snapshot_and_certificate_schema_ok,
        no_experimental_components,
    }

## 5. No-silent-fallback semantics

`verify_certified_startup` raises `CertifiedStartupError` with a
specific machine-readable code on every failure class. Catching
this exception to run under REFERENCE or DEVELOPMENT is expressly
forbidden by mandate §L15.2.3 and by the docstring; the negative
test suite proves that mismatches propagate rather than degrade.

Failure codes surfaced by the negative test suite include:

- `STARTUP_NON_CERTIFIED_MODE`
- `STARTUP_CONFIG_INVALID`
- `STARTUP_BACKEND_MISMATCH`
- `STARTUP_LANGUAGE_LOCK_FAILED`
- `STARTUP_LANGUAGE_VERSION_MISMATCH`
- `STARTUP_LANGUAGE_COMMIT_MISMATCH`
- `STARTUP_LOADED_LANGUAGE_MISMATCH`
- `STARTUP_CONFIG_DIGEST_MISMATCH`
- `STARTUP_GRAPH_DIGEST_MISMATCH`
- `STARTUP_IR_DIGEST_MISMATCH`
- `STARTUP_IR_INSTRUCTION_COUNT_MISMATCH`
- `STARTUP_SNAPSHOT_SCHEMA_MISMATCH`
- `STARTUP_CERTIFICATE_SCHEMA_MISMATCH`
- `STARTUP_EXPERIMENTAL_SOURCE_REJECTED`
- `STARTUP_EXPERIMENTAL_PROJECTION_REJECTED`

## 6. Snapshot + replay under CERTIFIED

- `test_certified_snapshot_restores_under_certified` — snapshot
  taken in CERTIFIED mode, restored under CERTIFIED, continues
  execution deterministically.
- `test_incompatible_snapshot_config_is_rejected` — a snapshot
  from CERTIFIED cannot be restored under REFERENCE (or under a
  semantically different CERTIFIED configuration) without
  explicit migration; the operation is refused.

## 7. Certified-mode soak

`test_certified_soak_is_deterministic_and_convergent` performs a
bounded reproducible soak: 3 rounds × 4 source ticks + snapshot +
fresh restore + 4 more ticks. Two independent passes on the same
process produce byte-identical `graph_digest`, `ir_digest`,
`output count`, `certificate_ok`, and `final_state_identity`.
Zero unexplained contract violations, zero silent fallbacks, zero
replay divergence.

## 8. Test totals

Local test suite: **100 / 100 passing** (was 79 before L15).
New tests added in L15: `tests/test_certified.py` (21 tests).

## 9. CI evidence

*Populated after CI completes on the L15 activation SHA.*

- Workflow: `.github/workflows/aeon-application.yml`
- New job: `app_certified_activation`
  - `tests/test_certified.py` (in-process)
  - `aeon-app-check` reports `certified_execution_ready=true`
  - `aeon-app-inspect` shows `frozen_certified.matches_frozen=true`
  - `aeon-app-snapshot` + `aeon-app-replay` round-trip under CERTIFIED
- Preserved jobs: `app_tests` (py 3.10/3.11/3.12),
  `app_clean_install`, `app_conformance` (four hash seeds).

## 10. Known limitations

- Certified execution runs on the Python backend only. The
  NumPy backend is available for differential testing but is
  not certified for execution (mandate §L15.2.4 rejects any
  backend id other than `python` in CERTIFIED mode).
- Certified feedback remains at the zero gate. Nonzero-gate
  feedback is implemented and covered by REFERENCE-mode
  conformance, but activating it in CERTIFIED requires a new
  certified activation revision (mandate §L15.2.5).
- Training outputs are labeled `artifact_space=development`;
  a trained checkpoint does not automatically become certified.
- Windows packaging is a separate, subsequent decision (L16).

## 11. Runtime authority

Certified Aeon-application execution is **AUTHORITATIVE**.
The default runtime mode is `CERTIFIED`; every CLI entry point
resolves to it in the absence of an explicit `--mode` argument;
every startup runs the L15 verification gate; every failure
fails closed with no fallback.
