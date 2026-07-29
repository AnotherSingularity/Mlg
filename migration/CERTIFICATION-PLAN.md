# Certification Plan

**Baseline audit SHA:** `2763c913d75bced7fd96553316b951608891c214`
**Aeon Language SHA:** `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`

Per mandate §15 launch certification requires a complete
application candidate exercised through the certification
matrix.

## Certification matrix

The mandate §15.1 requires, from a fresh clone + installed
package:

- build — **applies to Aeon Language; no application to build**.
- install — **applies to Aeon Language; no application to install**.
- static checks — **applies to Aeon Language; no application to check**.
- full tests — **223 pass on Aeon Language; no application tests exist**.
- conformance — **8 profiles PASS on Aeon Language; no
  application profile exists**.
- canonical IR verification — **language subsystem's IR verifier
  passes; no application IR exists to verify**.
- source-port conformance — **`SOURCE_REQUIRED` and `SOURCE_RICH`
  profiles PASS on Aeon Language reference sources; no
  application source exists**.
- Recursion certification — **PROVEN_CONTRACTIVE via exact
  rational on the reference substrate; no application substrate
  exists**.
- snapshot and restore — **language subsystem's snapshot tests
  pass; no application snapshot exists**.
- deterministic replay — **fresh-process + PYTHONHASHSEED matrix
  PASS on the Aeon Language; no application replay exists**.
- backend tests — **Python vs NumPy differential PASSES on the
  language; no application backend selection exists**.
- CLI tests — **9 CLI tools tested clean; no application CLI
  exists**.
- application smoke tests — **no application exists**.
- sustained execution — **no application exists**.
- release-manifest verification — **language subsystem's manifest
  verifies (`test_release_manifest.py`); no application manifest
  exists**.

## Application release manifest (mandate §15.2)

Required fields and their status:

| Field | Value |
| ----- | ----- |
| application version | **UNDEFINED** — no application |
| application commit SHA | `2763c913d75bced7fd96553316b951608891c214` (repo head — not distinguishable from language head) |
| Aeon Language version | `0.1.0` |
| Aeon Language certified SHA | `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f` |
| semantic graph digest (application) | **UNDEFINED** |
| canonical IR digest (application) | **UNDEFINED** |
| public API digest (application) | **UNDEFINED** |
| snapshot schema version | `0.1.0` (language) |
| certificate schema version | `0.1.0` (language) |
| supported backend versions | `aeon.backends.python 0.1.0`, `aeon.backends.numpy 0.1.0` |
| test fixture digests | recorded in the Aeon Language release manifest; none application-specific |
| CI run IDs | `30472658596` (language release-candidate); no application CI runs |

## Interpretation

Every certification-matrix line either applies to the Aeon
Language (already certified as v0.1.0) or requires an
application that does not exist. No application-scoped
certification is achievable in this repository.
