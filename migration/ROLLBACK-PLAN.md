# Rollback Plan

**Baseline audit SHA:** `2763c913d75bced7fd96553316b951608891c214`
**Aeon Language SHA:** `b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`

Per mandate §14 rollback capability must be preserved until
final launch acceptance. Per mandate §1 objective 10 an
"immediate rollback path" must remain until acceptance.

## Rollback target

A rollback restores the application to the last known-good
legacy state. The application inventory records **no legacy
state**. The rollback target is therefore undefined.

## Rollback switch

Mandate §13 requires that "Legacy remains available through an
explicit rollback switch" and prohibits "Silent fallback from
Aeon to legacy". Both are moot: nothing in this repository
implements the legacy path a rollback would restore.

## Preserved artifacts

Mandate §14 K17 requires preserving:

- historical migration readers where required — **N/A, no
  legacy readers exist**.
- archived fixtures — **N/A, no legacy fixtures exist**.
- baseline documentation — **this migration/ directory records
  the empty baseline**.
- rollback release artifact — **N/A, no legacy release exists**.
- provenance records — **the git history from Phase 0 forward
  is the provenance; the LEGACY_BASELINE_SHA is defined below
  as identical to the current HEAD because no application-only
  reference exists**.

## Recorded SHAs

- `LEGACY_BASELINE_SHA = 2763c913d75bced7fd96553316b951608891c214`
  — set to the audit HEAD because no earlier commit represents a
  distinct legacy application state.
- `AEON_LANGUAGE_SHA = b5e27a9bbc836897d9ac20d92c7d2fb786335f8f`
  — the certified Aeon Language v0.1.0 commit
  (`aeon-language/AEON-LANGUAGE-v0.1.0-RELEASE-REPORT.md`).

## Interpretation

A rollback that restores nothing is not a rollback. The rollback
plan cannot be exercised in a Gate-K-A-through-K-E sense in this
repository.
