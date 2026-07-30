# Aeon v0.1.0 — Independent Audit Rejection (R0)

**Status:** all prior certification and validation claims on
this branch are **WITHDRAWN**.

An independent audit — captured in
`docs/audit/2026-07-30-AEON_RUTHLESS_AUDIT.md` — rejects release
certification. This commit is the R0 additive record demanded
by the audit's mandatory correction order. It **preserves**
every previous report (they are historical artifacts of the
prior workflow) but supersedes their conclusions by independent
review.

No release tag has been created. No artifact has been signed.
No public release is authorized.

## 1. Corrected public/internal status

| Layer                        | Prior status (WITHDRAWN)          | Corrected status                                    |
| ---------------------------- | --------------------------------- | --------------------------------------------------- |
| Aeon Language                | v0.1.0 CERTIFIED                  | EXPERIMENTAL PROTOTYPE                              |
| Aeon Application (semantic)  | LAUNCH CERTIFIED                  | REFERENCE DEMONSTRATOR                              |
| Certified runtime activation | CERTIFIED RUNTIME ACTIVATED       | REJECTED BY INDEPENDENT AUDIT                       |
| Windows package              | WINDOWS PACKAGE VALIDATED         | UNSIGNED SMOKE PACKAGE ONLY                         |
| Public release               | (pending signing)                 | PROHIBITED until every C / H finding is closed      |
| Aeon Language remote tag     | (pending operator publication)    | MUST NOT be published against a rejected candidate  |
| Application remote tag       | not created                       | MUST NOT be created                                 |

## 2. Reproduced audit evidence

The most-severe audit findings were reproduced locally against
the current branch head **before** this withdrawal was written:

### C-01 — Application does not execute its canonical Aeon IR

The application's `graph.compile_to_ir(certified_config())`
emits 21 instructions whose opcodes are only:

    CLOCK_DEFINE (x2), CLOCK_TICK (x6),
    RECURSION_INIT (x1), RECURSION_INTEGRATE (x2),
    SOURCE_INIT (x2), SOURCE_STEP (x8)

No `SOURCE_READ`, no `SIGNAL_FORM`, no `SIGNAL_PROJECT`. The
`minput.*` bindings that `RECURSION_INTEGRATE` consumes are
never defined by the emitted stream. The application's runtime
in `aeon_app.application.ApplicationSession` is a separate
Python execution path; the canonical IR is an identity /
reporting artifact, not the executable semantics.

### C-04 — Certified startup does not bind implementation bytes

Reproduced (script recorded in `tests/audit/test_audit_reproduction.py`):

    CERT_START_BASE_VALID True
    CERT_START_TAMPER_VALID True   (after monkeypatching
                                     ApplicationSession._fresh_frame_for
                                     to emit zero payload)
    CERT_OUTPUT_CHANGED True

A modified implementation produces materially different output
while `verify_certified_startup(certified_config())` still
returns `valid=True`. The audit's finding is confirmed.

### C-05 — Certified snapshots accept tampered semantic identity

Reproduced against `aeon_app.application.restore` at HEAD:

    graph_id         ACCEPTED (tampered → 'a'*64)
    ir_module_id     ACCEPTED (tampered → 'b'*64)
    runtime_mode     ACCEPTED (tampered → 'REFERENCE')
    backend_id       ACCEPTED (tampered → 'numpy')
    event_log_digest ACCEPTED (tampered → 'c'*64)

`restore()` verifies only the language lock, the snapshot
schema/application/language version fields, and the
configuration digest. Everything else is trusted.

### H-10 — Release manifest is stale

`aeon-application/release/RELEASE-MANIFEST.json` before this
commit declared:

    default_runtime_mode = REFERENCE
    test_count_reference = 79
    release_notes: "First greenfield Aeon-native application …
                    CERTIFIED mode is NOT activated by this
                    release …"

But the source of truth after L15 says CERTIFIED is the default,
the test count is 100, and the L16 launcher was built and
smoke-tested. The manifest was never regenerated after L15;
the frozen release evidence contradicted the running source.

This commit does not fix the underlying defect; it flags the
manifest as WITHDRAWN. Rebuilding it correctly is scope for R8.

### Other findings (documentary confirmation)

C-02, C-03, H-01…H-09, H-11, H-12 are described in the audit
document; they are not further reproduced here because the four
above are already load-bearing for the withdrawal. R1–R9 will
address each finding individually.

## 3. What R0 does

1. Adds this document (`AEON-v0.1.0-AUDIT-REJECTION.md`) at the
   repo root.
2. Preserves the audit source at
   `docs/audit/2026-07-30-AEON_RUTHLESS_AUDIT.md` verbatim.
3. Prepends a **WITHDRAWN** banner to every prior report that
   the audit contradicts:
   - `AEON-v0.1.0-FINAL-RELEASE-REPORT.md`
   - `AEON-GREENFIELD-BUILD-REPORT.md`
   - `aeon-application/reports/L15-CERTIFIED-ACTIVATION-REPORT.md`
   - `aeon-application/reports/L16-WINDOWS-PACKAGING-REPORT.md`
   - `aeon-application/reports/L16.3-RELEASE-HEAD-RECONCILIATION.md`
4. Marks `aeon-application/release/RELEASE-MANIFEST.json` as
   **WITHDRAWN** by injecting a top-level `_withdrawn` block
   (leaving the historical fields intact, per audit rule
   "preserve previous reports").
5. Adds `aeon-application/tests/audit/test_audit_reproduction.py`
   which mechanically reproduces the C-04 (code tamper) and
   C-05 (snapshot tamper) findings as `pytest.xfail`-marked
   regression tests. **Every one of them SHOULD fail (i.e., the
   tampering should be rejected) once R5 / R6 land.** Until
   then, they document the reproducible defect.

## 4. What R0 does NOT do

- **No signing.** No release tag. No artifact publication.
- **No re-engineering.** R1 (single execution engine),
  R2 (IR/interpreter), R3 (signal-flow fix), R4 (contraction
  scope), R5 (bind cert to executable bytes), R6 (semantic
  snapshot restore), R7 (real aggregation + replay), R8
  (release packaging), R9 (independent recertification) — none
  are in scope for R0. They are separate additive workstreams.
- **No claim withdrawal from Aeon Language commits.** Files
  under `aeon-language/` remain byte-identical to the certified
  Aeon Language commit `b5e27a9…`; that commit's own audit-scope
  reclassification is documented here but the language history
  is not rewritten. Anyone consuming the language SHA directly
  now inherits the corrected "EXPERIMENTAL PROTOTYPE" status.
- **No tag deletion.** Local tag `aeon-language-v0.1.0` remains
  attached to `b5e27a9…` because the audit rule forbids force
  updates to any already-published tag. The tag has never
  reached the remote (documented environmental HTTP 403), so
  the "not published" side is already correct — the operator
  handoff (§1) that would have pushed it is CANCELLED by this
  R0 commit.

## 5. Path forward (informational, non-authoritative)

The audit's mandatory correction order R1–R9 must be executed
against the current architecture. The audit's release rule is:

> No claim containing `CERTIFIED`, `VALIDATED`, or `PROVEN` should
> be restored until every critical and high-severity finding above
> is closed with mechanical evidence.

This commit is the honest reset. Every future R1…R9 commit must
be additive, must not restore any withdrawn certification claim
without first closing the corresponding C / H finding, and must
be independently recertified per R9.
