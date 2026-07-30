# Aeon v0.1.0 — Final Release Report

**Artifact:** `aeon-application-v0.1.0`
**Aeon Language version:** `0.1.0` @ `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`
**Report date:** 2026-07-30
**Application branch:** `claude/aeon-language-phase-0-24enl0`

This report collates the three distinct decisions demanded by
the Gate L / L15 / L16 mandates. **They are not collapsed into
one.** The application may be semantically launch-certified with
authoritative certified execution while Windows distribution
remains blocked, and package validation may pass while signed
release is blocked — the sections below record each one
separately.

---

## 1. Release decisions

| Decision                                | Verdict                                                                                     |
| --------------------------------------- | ------------------------------------------------------------------------------------------- |
| **Semantic launch (Gate L-J)**          | `LAUNCH CERTIFIED` — head `a5aa0d61…`, CI `30541417494` / `30540941040`                     |
| **Certified runtime activation (L15)**  | `CERTIFIED RUNTIME ACTIVATED` — head `ae29a475f1…`, CI `30543678726` (9/9 green)            |
| **Windows package validation (L16)**    | *populated by aeon-windows CI on head `c05413a…`; see §5*                                   |
| **Windows signed release**              | `WINDOWS RELEASE BLOCKED` — no signing credentials in this environment (mandate §L16.5.6)   |

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
- **Activation-test totals:** 100 / 100 passing (was 79 pre-L15; +21 in `tests/test_certified.py`)
- **Certified soak:** `test_certified_soak_is_deterministic_and_convergent` returns byte-identical results across two independent passes on the same process (zero unexplained contract violations, zero silent fallbacks, zero replay divergence).
- **Full details:** `aeon-application/reports/L15-CERTIFIED-ACTIVATION-REPORT.md`.

## 3. L16 — Windows packaging

Only reference-CI infrastructure and specification have landed
on Linux. Actual Windows evidence is produced by the
`aeon-windows` workflow running on GitHub Actions
`windows-latest`. See §5 below for the current status.

### 3.1 Commits (L16 series, additive)

| SHA        | Purpose                                                                    |
| ---------- | -------------------------------------------------------------------------- |
| `c05413a…` | L16: aeon_app.launcher + PyInstaller spec + Inno Setup + Windows workflow  |
| *pending*  | L16.1: validated Windows bundle + installer (populated by CI on windows-latest) |
| *pending*  | L16.2: Windows release evidence + checksums                                |
| *pending*  | L16.3: signed release (only when signing credentials become available)     |

### 3.2 Toolchain (see `.github/workflows/aeon-windows.yml`)

- Runner: `windows-latest` (Windows Server 2022, x64)
- Python: `3.11` via `actions/setup-python@v5`
- PyInstaller: installed in-job
- Installer compiler: Inno Setup 6 (pre-installed on windows-latest)
- Signing: **credentials not present**; unsigned validation only

### 3.3 Bundle + installer digests

*Populated by the `windows-package` job on the first successful
`aeon-windows` run.* The recorded values come from the SHA-256
checksums this job uploads
(`aeon-application/windows-bundle.sha256.txt`,
`aeon-application/windows-installer.sha256.txt`).

## 4. Aeon Language — semantics unchanged

**Confirmation.** No file under `aeon-language/` has been
modified by any commit in this branch. Verified at each turn
with `git diff <prior-head> HEAD -- aeon-language/` returning
zero lines. The certified language SHA
`b5e27a9bbc836897d9ac20d92c7d2fb786335f8f` remains pinned
throughout L15 and L16.

## 5. Terminal CI runs

| Workflow            | Run id       | Head        | Conclusion  | Purpose                                   |
| ------------------- | ------------ | ----------- | ----------- | ----------------------------------------- |
| aeon-application    | `30540941040`| `4ff963f`   | success     | Gate L-J packaging + release artifacts    |
| aeon-application    | `30541417494`| `a5aa0d6`   | success     | Gate L-J report head                      |
| aeon-application    | `30543678726`| `ae29a475f1`| success 9/9 | L15 certified activation                  |
| aeon-application    | *pending*    | `c05413a…`  | *pending*   | Post-L16 Linux CI (should stay green)     |
| aeon-windows        | *pending*    | `c05413a…`  | *pending*   | L16 windows-package + clean-install       |

## 6. Known limitations

1. **Windows signing is blocked.** No signing credentials are
   available in the CI environment; the unsigned installer is
   labeled unsigned and must not be described as a signed
   production release.
2. **Certified backend is Python only.** The NumPy backend
   remains supported for differential testing and REFERENCE
   mode; certified startup rejects any backend id other than
   `python`.
3. **Certified feedback stays at the zero gate.** Nonzero-gate
   feedback is implemented but activating it in CERTIFIED
   requires a new certified-activation revision (mandate §L15.2.5).
4. **Training outputs are development artifacts.** A trained
   checkpoint never automatically becomes certified.
5. **Windows launcher exposes only smoke path.**
   `aeon-launcher.exe --smoke` performs certified startup + a
   short deterministic run; snapshot/replay CLI wrappers on
   Windows are scheduled for a subsequent L16.x additive
   change. Snapshot/replay correctness is exercised on Linux CI
   on the identical code path.
6. **Aeon Language tag not published.** The remote tag
   `aeon-language-v0.1.0` is not pushable through the local git
   proxy (documented environmental constraint). A human
   operator with tag-push permission should publish the tag to
   commit `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`. The full
   SHA remains authoritative pending that action.

## 7. Operator actions still required

1. **Publish the Aeon Language tag** `aeon-language-v0.1.0` to
   commit `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`.
2. **Provide Windows code-signing credentials** to a suitable
   signing environment. Sign the launcher `.exe`, the primary
   application `.exe`, and the installer `.exe` with SignTool;
   verify via `signtool verify /pa /v <path>`; commit the
   certificate subject, thumbprint, timestamping result, and
   verification result as L16.3.
3. **Rerun `aeon-windows` on windows-latest** and record the
   run id + per-job conclusions into
   `aeon-application/reports/L16-WINDOWS-PACKAGING-REPORT.md`
   as an additive commit.
4. **Decide human-visible activation.** The runtime is
   authoritative; UX rollout, documentation-site updates, and
   external announcements are outside this branch's scope.

## 8. Provenance envelope

- Application HEAD (post-L16 infra): `c05413a`
- Aeon Language SHA (pinned): `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`
- Application version: `0.1.0`
- Certified activation version: `0.1.0`
- Snapshot schema version: `0.1.0`
- Conformance schema version: `0.1.0`
- Evaluation schema version: `0.1.0`

---

*End of report.*
