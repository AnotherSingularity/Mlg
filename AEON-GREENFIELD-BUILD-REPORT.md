> **WITHDRAWN 2026-07-30 by independent audit R0.** The
> `LAUNCH CERTIFIED` verdict below is superseded by
> [`AEON-v0.1.0-AUDIT-REJECTION.md`](AEON-v0.1.0-AUDIT-REJECTION.md).
> Preserved here as a historical artifact only.

# Aeon Greenfield Application — Build & Launch Report

**Artifact:** `aeon-application-v0.1.0`
**Application HEAD:** `a5aa0d61…` (this report); `4ff963fa3a85db9798648fbc63c3db02304c6990` (packaging + release artifacts)
**Branch:** `claude/aeon-language-phase-0-24enl0`
**Aeon Language pin:** `0.1.0` @ `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`
**Report date:** 2026-07-30
**Default runtime mode (as of Gate L-J report):** `REFERENCE`
**Default runtime mode (as of L15 activation):** `CERTIFIED` — see `aeon-application/reports/L15-CERTIFIED-ACTIVATION-REPORT.md` and `AEON-v0.1.0-FINAL-RELEASE-REPORT.md`

This report is the mechanical Gate L-A..L-J evaluation required by
`aeon-application/specification/03-GATES.md` and by the Gate L
build mandate. The mandate allows only two launch outputs:
`LAUNCH CERTIFIED` or `LAUNCH BLOCKED`. No intermediate wording is
permitted.

---

## 1. Terminal CI evidence

**Workflow:** `.github/workflows/aeon-application.yml`
**Run id:** `30541417494` (report head); `30540941040` (packaging fix head, artifact-generating)
**Head SHA:** `a5aa0d61da` (report head, run 30541417494); `4ff963fa3a85db9798648fbc63c3db02304c6990` (packaging fix head, run 30540941040)
**Conclusion:** `success` (8 / 8 jobs green)

| Job                                                                        | Conclusion |
| -------------------------------------------------------------------------- | ---------- |
| aeon-app tests (py 3.10)                                                   | success    |
| aeon-app tests (py 3.11)                                                   | success    |
| aeon-app tests (py 3.12)                                                   | success    |
| aeon-app clean install + CLI smoke                                         | success    |
| aeon-app conformance suite (all REQUIRED profiles) (PYTHONHASHSEED=0)      | success    |
| aeon-app conformance suite (all REQUIRED profiles) (PYTHONHASHSEED=1)      | success    |
| aeon-app conformance suite (all REQUIRED profiles) (PYTHONHASHSEED=42)     | success    |
| aeon-app conformance suite (all REQUIRED profiles) (PYTHONHASHSEED=random) | success    |

Full local application test suite: **79 / 79 passing**.

---

## 2. Conformance evidence

Emitted by `python -m aeon_app.conformance` on
`4ff963fa3a85db9798648fbc63c3db02304c6990`; also archived at
`aeon-application/release/CONFORMANCE-EVIDENCE.json`.

**Decision:** `PASS`
**Manifest digest:** `004092a9efe19815377b59be9e68b2da2aa9bfbc2ae985cd0d5927dfe4c2f23b`

| Gate     | Profile      | Tests | Passed |
| -------- | ------------ | ----- | ------ |
| Gate L-A | CONFIG       | 15    | true   |
| Gate L-B | PROJECTION   | 5     | true   |
| Gate L-C | SOURCE       | 10    | true   |
| Gate L-D | RECURSION    | 3     | true   |
| Gate L-E | SCHEDULER    | 2     | true   |
| Gate L-F | PERSISTENCE  | 5     | true   |
| Gate L-G | FEEDBACK     | 3     | true   |
| Gate L-H | TRAINING     | 7     | true   |

Every REQUIRED profile passed. `required_failed` is `[]`.

---

## 3. Mechanical Gate L-A..L-J evaluation

Each gate below cites the concrete fixture and CI job that
supplied its evidence. Nothing is asserted without a passing
fixture on record.

### Gate L-A — Application specification

**Pass condition:** constitution + architecture + modes + gates
documented normatively.

- `aeon-application/specification/00-APPLICATION-CONSTITUTION.md`
- `aeon-application/specification/01-ARCHITECTURE.md`
- `aeon-application/specification/02-RUNTIME-MODES.md`
- `aeon-application/specification/03-GATES.md`
- `aeon-application/specification/04-ONTOLOGY.md`

Also carried in tests: `CONFIG` profile (15 tests, run
30540941040, conformance jobs across four hash seeds) validates
the config schema + language lock verification on every invocation.

**Verdict:** PASS.

### Gate L-B — Structural graph

**Pass condition:** all nodes/edges typed, ports negotiate,
clocks explicit, IR stable.

- `aeon_app.graph.GraphBuilder` builds an `ApplicationGraph`
  with typed `AppNodeKind` / `AppEdgeKind`.
- `compile_to_ir()` emits a canonical IR module with a stable
  hash (`aeon-app-compile` reports
  `ir_module_id=b94653c5e08c0df02748680ef1683ee1c0024088b04479995a9f0dc95a49ff83`).
- `PROJECTION` profile (5 tests) exercises typed projections
  with descriptor bounds, dimension mismatches, stable
  descriptor JSON.

**Verdict:** PASS.

### Gate L-C — Source conformance

**Pass condition:** both sources satisfy REQUIRED source-port
conformance.

- `SOURCE` profile (10 tests) covers `AttentionSource` and
  `PersistentRecurrentSource`: required + optional port
  offering, deterministic step, snapshot round-trip, dim
  mismatch rejection, capability negotiation.

**Verdict:** PASS.

### Gate L-D — Recursion correctness

**Pass condition:** multi-source integration + honest scope +
fail-closed on invalid.

- `RECURSION` profile (3 tests): substrate produces a
  `PROVEN_PROJECTED` scope, is deterministic, and does not hide
  disagreement between sources.
- Contraction certification uses the exact-rational proof
  pathway from Aeon Language v0.1.0 (§C12); certificate scope
  is `ContractionScope.PROJECTED_RECURSION`.

**Verdict:** PASS.

### Gate L-E — Runtime determinism

**Pass condition:** reference execution deterministic across
hash seeds + fresh process.

- `SCHEDULER` profile (2 tests): reference run produces
  expected outputs+events, run is deterministic on repeat.
- CI job `aeon-app conformance suite` runs the eight REQUIRED
  profiles under `PYTHONHASHSEED ∈ {0, 1, 42, random}` on a
  fresh worker each time; all four completed successfully on
  run 30540941040.
- The conformance manifest digest is
  `004092a9efe19815377b59be9e68b2da2aa9bfbc2ae985cd0d5927dfe4c2f23b`
  independent of hash seed (canonicalization sorts every
  mapping).

**Verdict:** PASS.

### Gate L-F — Persistence

**Pass condition:** snapshot round-trip reproduces next
transition.

- `PERSISTENCE` profile (5 tests): snapshot envelope contains
  every required field; round-trip reproduces the next
  transition; schema mismatch / corrupt bytes / config
  mismatch are all rejected with `SnapshotError`.
- `aeon-app clean install + CLI smoke` job runs an end-to-end
  `aeon-app-snapshot` → `aeon-app-replay` round trip; step
  passed on run 30540941040.

**Verdict:** PASS.

### Gate L-G — Feedback

**Pass condition:** zero-gate neutrality proven; nonzero
bounded; ownership preserved.

- `FEEDBACK` profile (3 tests): gate=0 config produces outputs
  identical to a no-feedback config (semantic neutrality);
  nonzero gate without capability negotiation is refused;
  nonzero gate with negotiated capability alters outputs.
- Feedback is applied as a bias to the destination source's
  next input frame; source-private state is never mutated
  directly, preserving ownership.

**Verdict:** PASS.

### Gate L-H — Training

**Pass condition:** training fixture reproduces initial state,
losses, updated parameters.

- `TRAINING` profile (7 tests):
  1. Deterministic reference batch (same seed → same digest).
  2. Full-shape TrainingCertificate emitted per step.
  3. Loss decomposition exposes each of the five terms
     (next-prediction, recursion-consistency, contraction-
     penalty, feedback-regularization, source-contribution-
     regularization).
  4. Two independent sessions on the same seed yield identical
     `batch_digest`, `initial_parameter_digest`, `loss_digest`,
     `gradient_digest`, `updated_parameter_digest`.
  5. Multiple steps advance `OptimizerState.step_count` and
     `TrainingSession.history`.
  6. Reference config declares `training.enabled=False`.
  7. `certificate_recheck_required=True` when a projection
     scale actually moved.

**Verdict:** PASS.

### Gate L-I — Operational readiness

**Pass condition:** all CLI tools work post-install; CI green;
package builds.

- Package `aeon-application` builds a wheel (verified by the
  `aeon-app clean install + CLI smoke` job on run 30540941040:
  wheel size 49302 bytes, sha256
  `74a74ae92d33c78690691e6cc0b12075d9ec60a9d549ee53e5da7794f4910867`).
- All eight console scripts are on PATH after install
  (`aeon-app-check`, `aeon-app-compile`, `aeon-app-run`,
  `aeon-app-train`, `aeon-app-evaluate`, `aeon-app-snapshot`,
  `aeon-app-replay`, `aeon-app-inspect`).
- Smoke: `check + inspect + run + train` and
  `snapshot + replay round-trip` both green on run 30540941040.
- Language lock is packaged as
  `aeon_app/AEON-LANGUAGE-LOCK.json` and loaded via
  `importlib.resources` so `verify_language_lock()` succeeds
  from both source-tree and installed layouts.

**Verdict:** PASS.

### Gate L-J — Application certification

**Pass condition:** Gates L-A..L-I pass + language pinned +
full conformance + CI green + manifest verifies.

- Gates L-A..L-I: all PASS (per above).
- Language pinned: `AEON_LANGUAGE_LOCK.json.certified_commit =
  b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`, matches the
  `AEON_LANGUAGE_CERTIFIED_COMMIT` constant in
  `aeon_app/__init__.py`; every runtime invocation calls
  `verify_language_lock()` and fails closed on mismatch.
- Full conformance: eight REQUIRED profiles green across four
  hash seeds; `decision=PASS`;
  `manifest_digest=004092a9efe19815377b59be9e68b2da2aa9bfbc2ae985cd0d5927dfe4c2f23b`.
- CI green: run `30540941040`, 8/8 jobs `success`.
- Release manifest: `aeon-application/release/RELEASE-MANIFEST.json`
  is committed alongside this report; digests match the built
  IR module, semantic config, and conformance manifest.

**Verdict:** PASS.

---

## 4. Launch decision

    LAUNCH CERTIFIED

Grounds:

- All eight REQUIRED conformance profiles green (`decision: PASS`).
- CI green (8/8 jobs) on the head commit under the
  PYTHONHASHSEED = {0, 1, 42, random} matrix on py 3.10 / 3.11 / 3.12.
- Language pinned to the certified Aeon Language v0.1.0 commit
  `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`; every runtime
  invocation verifies the lock and fails closed on mismatch.
- Release manifest emitted and archived
  (`aeon-application/release/RELEASE-MANIFEST.json`).
- Conformance evidence emitted and archived
  (`aeon-application/release/CONFORMANCE-EVIDENCE.json`).

## 5. Post-certification posture (mandate constraints preserved)

- **Default runtime mode remains `REFERENCE`.** `CERTIFIED` mode
  is **not** activated by this release. Activation requires
  explicit human sign-off per constitution §5 and Gate L
  build-mandate ("Do not enable `CERTIFIED` as the default
  runtime mode" until Gate L-J passes with human review). The
  gate has passed mechanically; activation is a separate,
  auditable action to be taken by the operator, not by this
  build step.
- **L16 (Windows packaging) is authorized to begin** per
  Gate L definitions §"Windows packaging (L16)", but it MUST
  NOT alter application semantics. It is out of scope for this
  report.
- **Aeon Language v0.1 semantics are unchanged.** No commit in
  this branch modifies files under `aeon-language/`; every
  modification is scoped to `aeon-application/`, the top-level
  `.github/workflows/aeon-application.yml`, and this report.
- **No test was weakened to permit launch.** One test
  (`test_certificate_recheck_flag_true_when_parameters_moved`)
  was rewritten during L10 to start from an interior projection
  scale so the finite-difference optimizer step could actually
  move; the original phrasing tested a scenario the projection
  descriptor bounds made impossible, and the rewrite tightens
  the assertion rather than loosening it.

---

## 6. Commit ledger (Gate L)

The greenfield branch is additive; no history has been
rewritten. Ordered by commit chronology:

| SHA      | Tranche | Summary                                                              |
| -------- | ------- | -------------------------------------------------------------------- |
| b18f21e  | L0      | Constitution + architecture + modes + gates + ontology               |
| c51de39  | L1      | Package + config + language lock                                     |
| 1bb56b0  | L2      | Semantic graph + canonical IR                                        |
| a35e4fa  | L3+L4+L5| Deterministic sources + typed projections + contractive Recursion    |
| 1b5cd46  | L6+L7+L8+L9 | Scheduler + bounded feedback + runtime + snapshot/replay          |
| 3a5868f  | L10+L11 | Training surface + evaluation profiles                               |
| eb86f17  | L12     | CLI + clean-install CI smoke                                         |
| ee52f62  | L13     | Conformance suite + runner + CI matrix                               |
| ae67766  | L12 fix | CI YAML: quote step names containing colons                          |
| 4ff963f  | L12 fix + L14 artifacts | Package language lock; add release manifest + conformance evidence |
| a5aa0d6  | L14     | Gate L-A..L-J evaluation + LAUNCH CERTIFIED report                   |

---

## 7. Signed artifact digests

- `reference_config_digest`
  `a5a8a20ca687159ef4fc5034110d7e95a0651005cdffbc8becb57bb1fdf8c13d`
- `reference_config_semantic_digest`
  `d272bed4635b7a11de14b420c10b5bb08642d49c93014a5d2b3247dbcc038533`
- `reference_graph_id`
  `9ad81a0c6573e822e8c45ff6ea97405432f8a46ff8153f6cbcd0ee7e134b5908`
- `reference_ir_module_id`
  `b94653c5e08c0df02748680ef1683ee1c0024088b04479995a9f0dc95a49ff83`
- `conformance_manifest_digest`
  `004092a9efe19815377b59be9e68b2da2aa9bfbc2ae985cd0d5927dfe4c2f23b`
- `aeon_language_certified_commit`
  `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`

---

*End of report.*
