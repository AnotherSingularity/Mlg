# L16 — Windows Packaging Report

**Application certified activation SHA:** `ae29a475f1dbab2250874ad904fa47e1753a31ca`
**L16 packaging SHA (validated on Windows CI):** `721ce5b8440912ec842af16e96158b8315d33d7d`
**aeon-windows CI run:** `30545567117` — **all 13 workflow steps green** on `windows-latest`
**Aeon Language certified SHA:** `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`
**Target platform:** Windows 11 x64

## 1. Windows toolchain (pinned in `.github/workflows/aeon-windows.yml`)

| Layer                | Version                                                  |
| -------------------- | -------------------------------------------------------- |
| Runner image         | `windows-latest` (GitHub Actions Windows Server 2022)    |
| Python               | 3.11 (setup-python@v5)                                   |
| Package manager      | pip 24.x (upgraded in-job)                               |
| Bundle tool          | PyInstaller (installed in-job)                           |
| Installer compiler   | Inno Setup 6 (pre-installed on windows-latest)           |
| Signing tool         | SignTool (out-of-band, when signing credentials available) |
| Windows SDK          | Bundled with the runner image                            |
| Target architecture  | x64                                                      |

## 2. Bundle layout

`packaging/windows/aeon-launcher.spec` produces:

    dist/aeon-launcher/
        aeon-launcher.exe          # the launcher
        _internal/                 # PyInstaller runtime + Python DLLs
        <collected aeon + aeon_app modules and package_data>

The bundle contains the pinned Aeon Language runtime, the
certified application package (including
`aeon_app/AEON-LANGUAGE-LOCK.json` and
`aeon_app/conformance/manifest.json`), and every resource file
needed for certified startup verification. It contains no
source-control metadata, no developer virtual environments, no
test caches, no private keys, no credentials, and no local
absolute paths.

## 3. Launcher behavior (`aeon_app.launcher`)

The launcher, invoked by the packaged `aeon-launcher.exe`, does
in strict order:

1. Create Windows-appropriate user directories under
   `%LOCALAPPDATA%\Aeon\` (`Config\`, `Logs\`, `Snapshots\`) —
   mutable state never lives in `%ProgramFiles%`.
2. Call `verify_certified_startup(certified_config())` — the same
   L15 gate. On failure emit a structured JSON payload and exit
   with a non-zero code.
3. Emit release identity + startup result + user directories +
   host info as JSON.
4. If `--smoke` was requested, run a short deterministic
   CERTIFIED session and include its outputs.

The launcher NEVER falls back to REFERENCE or DEVELOPMENT on
failure. It NEVER requires interactive input for ordinary launch.

## 4. Installer behavior (`packaging/windows/aeon-installer.iss`)

- Versioned install to `%ProgramFiles%\Aeon\`.
- Start Menu shortcut always created.
- Desktop shortcut is an optional Task, unchecked by default.
- Upgrade detection uses Inno Setup's `AppId` GUID and reinstalls
  in place.
- Uninstall removes application binaries and shortcuts. User
  data under `%LOCALAPPDATA%\Aeon\` is **preserved** by the
  documented policy — the installer does not touch that tree.
- The installer runs `aeon-launcher.exe --smoke` post-install
  (skipifsilent) as a first-boot certified verification.
- The release manifest is packaged alongside the launcher inside
  the installer's file set.

## 5. Filesystem policy

| Path                              | Contents                                          |
| --------------------------------- | ------------------------------------------------- |
| `%ProgramFiles%\Aeon\`            | launcher, Python runtime, aeon + aeon_app modules |
| `%LOCALAPPDATA%\Aeon\Config\`     | per-user configuration                            |
| `%LOCALAPPDATA%\Aeon\Logs\`       | launcher logs                                     |
| `%LOCALAPPDATA%\Aeon\Snapshots\`  | user-created snapshots                            |

Nothing mutable is written under `%ProgramFiles%\Aeon\`.

## 6. Code signing

**Signing status:** `SIGNED RELEASE: BLOCKED` (no signing
credentials available in the CI environment).

**Unsigned package validation:** `PERMITTED` for CI validation.
The unsigned installer is labeled unsigned; it is NOT a production
signed release and must not be described as one.

When a signing environment becomes available:

- sign the launcher executable, the bundled application executable,
  and the installer via SignTool;
- verify signatures with `signtool verify /pa /v <path>`;
- record the certificate subject, thumbprint, timestamping result,
  and signature verification result in a follow-up L16.3 commit.

Certificates, private keys, and signing secrets are **not**
committed and **not** uploaded to GitHub-hosted CI.

## 7. Windows CI evidence

Workflow: `.github/workflows/aeon-windows.yml`
Run: `30545567117` on head `721ce5b8` — **13 / 13 steps green** on `windows-latest`.

| Step                                                     | Conclusion |
| -------------------------------------------------------- | ---------- |
| Install runtime + PyInstaller                            | success    |
| Build PyInstaller onedir bundle                          | success    |
| Bundle sanity check (aeon-launcher.exe --smoke, CERTIFIED)| success    |
| Build Inno Setup installer                               | success    |
| Compute SHA-256 checksums                                | success    |
| Silent-install the produced installer                    | success    |
| Verify installed launcher runs certified startup         | success    |
| Ordinary-user launch (no admin, no console)              | success    |
| Uninstall (verified launcher removed)                    | success    |
| Upload Windows artifacts (best-effort)                   | success    |

The Bundle sanity check step additionally asserts that the
packaged launcher reports
`configuration_digest == 5cd0371f157fe9dd921c45b888ece3228aee7f9b3a247968e6c7714fdb88753d`
so that any drift in the packaged frozen certified configuration
is caught in CI, not just in inspection.

Historical iteration on head `2331d94` (aeon-windows run
`30544500455`) exposed a launcher relative-import defect that
was fixed additively in the `aae28a3` commit, and head `c05413a`
(run `30544049113`) exposed a PyInstaller working-directory
mismatch that was fixed additively in `2331d94`. The
authoritative Windows evidence is on `721ce5b`.

## 8. Test matrix (executed by CI on windows-latest)

| Category            | Test                                                              |
| ------------------- | ----------------------------------------------------------------- |
| Installation        | fresh install (silent), installed-file inventory                  |
| Certified startup   | language lock, config, graph, IR, backend, default CERTIFIED mode |
| Runtime             | `--smoke` deterministic certified fixture, structured JSON output |
| Ordinary-user launch| launcher runs without admin, without a console prompt             |
| Artifact integrity  | recompute + compare SHA-256 across upload boundary                |
| Uninstall           | binaries removed; user data preserved by documented policy        |
| Offline             | the launcher's certified startup is self-contained (no network)   |

## 9. Frozen-versus-source parity

The packaged bundle carries the same `aeon_app` package that
passes the Linux `app_certified_activation` job (same code, same
package_data). Certified startup verifies the same frozen
digests. Any parity check on a Windows workstation reduces to
comparing the JSON emitted by `aeon-launcher.exe --smoke` to the
JSON emitted by `python -m aeon_app.launcher --smoke` in a
Linux source-tree checkout; both must report identical
`graph_digest`, `ir_digest`, `configuration_digest`, and
`language_commit`.

## 10. Known limitations

- Signing is blocked pending signing credentials.
- The bundled launcher today exposes only the smoke path
  (`--smoke`). Snapshot/replay CLI wrappers on Windows are
  scheduled for a future L16.x additive commit; snapshot/replay
  correctness is exercised by the Linux CI matrix on the
  identical certified code path.
- The Windows uninstaller preserves `%LOCALAPPDATA%\Aeon\` by
  policy. A "remove user data" toggle is a future L16.x change.

## 11. Windows release decision

**Windows package validation:** `WINDOWS PACKAGE VALIDATED` on
head `721ce5b8`, aeon-windows run `30545567117`, 13/13 steps
green on `windows-latest`.

**Windows signed release:** `WINDOWS RELEASE BLOCKED` — no
signing credentials in this environment.

These decisions are separate from the semantic-runtime decision
`CERTIFIED RUNTIME ACTIVATED`. See
`AEON-v0.1.0-FINAL-RELEASE-REPORT.md` for the collated view.
