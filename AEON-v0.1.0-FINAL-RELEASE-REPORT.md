# Aeon v0.1.0 — Final Release Report

**Artifact:** `aeon-application-v0.1.0`
**Aeon Language version:** `0.1.0` @ `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`
**AEON_APPLICATION_RELEASE_SHA:** `f15bf0a654412caf2f961bf38b4431da0d762d71` (Windows-validated head; §14 reconciled)
**Application branch:** `claude/aeon-language-phase-0-24enl0`
**Report date:** 2026-07-30

This report collates the four distinct decisions demanded by
the Gate L / L15 / L16 / L16.3 mandates. **They are not
collapsed into one.** The application may be semantically
launch-certified with authoritative certified execution while
Windows distribution remains blocked, and package validation
may pass while signed release is blocked — the sections below
record each one separately.

---

## 1. Release decisions

| Decision                                | Verdict                                                                                        |
| --------------------------------------- | ---------------------------------------------------------------------------------------------- |
| **Semantic launch (Gate L-J)**          | `LAUNCH CERTIFIED` — head `a5aa0d61…`, CI `30541417494` / `30540941040`                        |
| **Certified runtime activation (L15)**  | `CERTIFIED RUNTIME ACTIVATED` — head `ae29a475f1…`, CI `30543678726` (9/9 green)               |
| **Windows package validation (L16)**    | `WINDOWS PACKAGE VALIDATED` — head `721ce5b8…`, aeon-windows CI `30545567117` (13/13 steps)    |
| **Windows signed release (L16.3)**      | `WINDOWS RELEASE BLOCKED` — no authorized code-signing credentials in this environment         |

**Exact unresolved requirement for the L16.3 decision:**
mandate §14 line "all required binaries are signed" — cannot be
met without an Authenticode certificate accessible from the
signing environment. Mandate §14 also forbids substituting a
self-signed certificate for public production certification, so
the decision is `WINDOWS RELEASE BLOCKED`.

---

## 2. L15 — Certified runtime activation

- **Starting SHA:** `293696af850603225bb461553a4178e37eee2b94`
- **Certified activation SHA:** `ae29a475f1dbab2250874ad904fa47e1753a31ca`
- **CI run:** `30543678726` — **9 / 9 jobs green** (Ubuntu, Python 3.10/3.11/3.12, PYTHONHASHSEED matrix)
- **Default runtime mode:** `CERTIFIED` (was `REFERENCE`) — single authoritative default at `aeon_app.certified.DEFAULT_RUNTIME_MODE`
- **Certified configuration digest:** `5cd0371f157fe9dd921c45b888ece3228aee7f9b3a247968e6c7714fdb88753d`
- **Semantic-graph digest:** `dbbb6c3bb2a7ee1e6d4945b6509cefaee2a77c92918237fa8098d66c05dac565`
- **Canonical-IR digest:** `9cf9ce5377d7f81e6382cc6aa4d647f2ee585818417cfefdb02b608e26f5ad76`
- **Aeon Language pin:** `0.1.0` @ `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`
- **Activation-test totals:** 100 / 100 passing
- **Certified soak:** deterministic across two independent passes; zero unexplained contract violations, zero silent fallbacks, zero replay divergence.
- **Full details:** `aeon-application/reports/L15-CERTIFIED-ACTIVATION-REPORT.md`.

## 3. L16 — Windows package validation

- **Validated SHA:** `721ce5b8440912ec842af16e96158b8315d33d7d`
- **CI run:** `30545567117` — **13 / 13 steps green** on `windows-latest`
- **Frozen certified digest verified inside packaged launcher:** `5cd0371f157fe9dd921c45b888ece3228aee7f9b3a247968e6c7714fdb88753d`
- **Full details:** `aeon-application/reports/L16-WINDOWS-PACKAGING-REPORT.md`.

### 3.1 Commits (L16 series, additive)

| SHA        | Purpose                                                                        |
| ---------- | ------------------------------------------------------------------------------ |
| `c05413a…` | L16: aeon_app.launcher + PyInstaller spec + Inno Setup + Windows workflow      |
| `2331d94…` | L16.1: PyInstaller path anchoring (SPECPATH) + dir path fix                    |
| `aae28a3…` | L16.1: absolute-import fix for PyInstaller frozen entry                        |
| `721ce5b…` | L16.1: consolidate windows workflow; best-effort upload; **validated on CI**   |
| `f15bf0a…` | L16.2: attach Windows release evidence + checksums to reports                  |

## 4. L16.3 — Signed Windows release (BLOCKED)

- **Reconciled release SHA:** `f15bf0a654412caf2f961bf38b4431da0d762d71`
  (per `aeon-application/reports/L16.3-RELEASE-HEAD-RECONCILIATION.md`)
- **Post-validation audit:** every commit after `721ce5b8` is
  `REPORT_ONLY`; zero `SEMANTIC` / `UNKNOWN` commits.
- **Aeon Language footprint since `b5e27a9…`:** `git diff --stat
  b5e27a9..HEAD -- aeon-language/` returns empty. Zero bytes
  changed under `aeon-language/` after the certified language
  commit.
- **Protected signing workflow:** `.github/workflows/aeon-windows-signed-release.yml`.
  Manual dispatch only, gated on the `signing` GitHub environment
  which the operator must configure with required reviewers,
  ref restrictions (`aeon-v*` tags or a protected release
  branch), and the environment secrets
  `CODE_SIGNING_CERT_THUMBPRINT` + `CODE_SIGNING_TIMESTAMP_URL`.
  No PFX, no password, no private key material lives in the
  repository or in GitHub secrets — the certificate must be
  supplied by a hardware token / HSM / managed signing service
  on the signing runner.

### 4.1 Signing environment (target, not yet realized)

The workflow expects an authorized signing environment with:
Windows 11 x64 or Windows Server 2022+, trusted system time,
controlled operator access, no untrusted build hooks, no
developer-modified binaries after build, SignTool from a pinned
Windows SDK, and an Authenticode certificate accessible via
`/sha1 <thumbprint>`.

### 4.2 Signing decision

**Signing status:** `SIGNED RELEASE: BLOCKED`.

**Reason (verbatim per mandate §14):** signing credentials are
not available. Substituting a self-signed certificate for public
production certification is expressly forbidden by mandate
§L16.5.6 and §14; the workflow file
`aeon-windows-signed-release.yml` therefore never falls back to
one.

### 4.3 Signed release CI evidence

No aeon-windows-signed-release run exists yet. The workflow is
installed but has never been dispatched because the required
`signing` GitHub environment (and its secrets) are not present
in this account.

### 4.4 Public release artifacts (not yet issued)

Per mandate §12 the following are prepared but not published:

- signed Windows installer — **BLOCKED** (unsigned installer
  built and validated on run 30545567117, but never labeled a
  production release)
- signed portable / onedir bundle — **BLOCKED**
- SHA-256 checksum file — template at
  `aeon-application/packaging/windows/CHECKSUMS.template.txt`
- release manifest — `aeon-application/release/RELEASE-MANIFEST.json`
  is published (unsigned form)
- signing manifest — schema documented in
  `aeon-windows-signed-release.yml`; produced only by a
  successful signing run
- license notices, release notes, known-limitations — this
  report + `AEON-GREENFIELD-BUILD-REPORT.md` +
  `aeon-application/reports/L15-CERTIFIED-ACTIVATION-REPORT.md` +
  `aeon-application/reports/L16-WINDOWS-PACKAGING-REPORT.md`

## 5. Terminal CI runs

| Workflow                        | Run id       | Head        | Conclusion             | Purpose                                          |
| ------------------------------- | ------------ | ----------- | ---------------------- | ------------------------------------------------ |
| aeon-application                | `30540941040`| `4ff963f`   | success                | Gate L-J packaging + release artifacts           |
| aeon-application                | `30541417494`| `a5aa0d6`   | success                | Gate L-J report head                             |
| aeon-application                | `30543678726`| `ae29a475f1`| success 9/9            | L15 certified activation                         |
| aeon-windows                    | `30545567117`| `721ce5b8`  | success 13/13 steps    | L16 Windows package validation on `windows-latest` |
| aeon-windows-signed-release     | *never dispatched* | —     | *n/a — signing blocked*| Would require the `signing` environment + secrets |

## 6. Tag publication status

### 6.1 Aeon Language tag

**Local tag:** `aeon-language-v0.1.0` → `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f` (present in the local repository).

**Remote publication:** BLOCKED. `git push origin aeon-language-v0.1.0` returns HTTP 403 from the local git proxy (a documented environmental constraint — the same proxy accepts branch pushes but rejects tag pushes). `git ls-remote --tags origin aeon-language-v0.1.0` returns empty.

**Required operator action:** a human operator with tag-push permission must publish the tag to the exact certified commit `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`. The full SHA remains authoritative in the meantime.

### 6.2 Aeon application tag

**Status:** NOT CREATED, per mandate §11.2 which conditions the `aeon-v0.1.0` tag on "After the signed release passes". Signed release is `BLOCKED`; therefore `aeon-v0.1.0` MUST NOT be published in this state. Creating it would misrepresent an unsigned candidate as a signed release.

## 7. Aeon Language — semantics unchanged

**Confirmation.** `git diff --stat b5e27a9..HEAD -- aeon-language/` returns empty across the entire branch. The certified language SHA `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f` remains pinned throughout L15, L16, and L16.3.

## 8. Known limitations

1. **Windows signing is blocked.** No signing credentials in the
   CI environment. The unsigned installer produced by
   `aeon-windows` run 30545567117 is labeled unsigned and must
   not be described as a signed production release.
2. **Certified backend is Python only.** Certified startup
   rejects any backend id other than `python`.
3. **Certified feedback stays at the zero gate.** Activating
   nonzero-gate feedback in CERTIFIED requires a new certified-
   activation revision (mandate §L15.2.5).
4. **Training outputs are development artifacts.** A trained
   checkpoint never automatically becomes certified.
5. **Windows launcher exposes only `--smoke` today.** Snapshot/
   replay CLI wrappers on Windows are scheduled for a later
   additive change; the semantic behavior is exercised on Linux
   CI on the identical code path.
6. **Aeon Language tag not published to remote.** Local proxy
   HTTP 403 environmental constraint — awaiting an operator with
   tag-push permission.

## 9. Operator actions still required

1. **Publish the Aeon Language tag** `aeon-language-v0.1.0` to
   commit `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`. Verify
   with `git ls-remote --tags origin aeon-language-v0.1.0`.
2. **Provide Windows code-signing credentials** to an authorized
   signing environment:
   - configure the GitHub `signing` environment with required
     reviewers and ref restrictions;
   - install the Authenticode certificate on a hardware
     token / HSM / signing service accessible to
     `windows-latest` (or a labeled self-hosted runner);
   - set environment secrets `CODE_SIGNING_CERT_THUMBPRINT`
     and `CODE_SIGNING_TIMESTAMP_URL`;
   - dispatch `aeon-windows-signed-release.yml` with
     `release_sha=f15bf0a654412caf2f961bf38b4431da0d762d71`;
   - require the run to be green;
   - record the resulting `SIGNING-MANIFEST.json`, signature
     verification results, and checksums as commit `L16.3-2`
     (and its follow-on `L16.3-3` / `L16.3-4` per mandate §15);
   - only then create and push `aeon-v0.1.0` at the release SHA;
   - only then issue `WINDOWS RELEASE CERTIFIED`.
3. **Publish the release artifacts** produced by the signed run
   (signed installer, signed launcher, `SIGNING-MANIFEST.json`,
   `CHECKSUMS.txt`, `RELEASE-MANIFEST.json`, license notices,
   release notes).
4. **Decide human-visible activation.** The runtime is
   authoritative; UX rollout, docs-site updates, and external
   announcements are outside this branch's scope.

## 10. Provenance envelope

- Application HEAD (post-L16.3-1 protected signing workflow): moves forward by two
  additive documentation/CI commits from the reconciled release SHA.
- **AEON_APPLICATION_RELEASE_SHA:** `f15bf0a654412caf2f961bf38b4431da0d762d71`
- Aeon Language SHA (pinned): `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`
- Application version: `0.1.0`
- Certified activation version: `0.1.0`
- Snapshot schema version: `0.1.0`
- Conformance schema version: `0.1.0`
- Evaluation schema version: `0.1.0`

---

*End of report.*
