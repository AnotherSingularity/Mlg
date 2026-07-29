# Phase 0 evidence reconciliation

**Date:** 2026-07-29
**Head at reconciliation start:** `7680ffa7f97e48afc8282a6c3475fec2767c5506`
**Branch:** `claude/aeon-language-phase-0-24enl0`
**Remote:** `origin`

This document is an **additive correction** to
`PHASE-0-REPORT.md`. Per Phase 0.1 mandate §1.5, it reconciles
the Phase 0 report against a mechanical re-audit performed from
a clean checkout of the branch. It does not rewrite the original
report; both documents remain in the tree.

## 1. Handoff verification

### 1.1 Repository state

- Working tree: clean.
- Staged changes: none.
- Untracked files: none.
- Tags: none.
- CI workflows: none (no `.github/workflows/` directory).
- Remotes: `origin` only.

### 1.2 Commit-chain audit

Chronological order (from `git log --format="%h %s" --reverse`):

| P    | SHA       | Files touched (subsystem)                                      |
| ---- | --------- | -------------------------------------------------------------- |
| P0   | be98c51   | README, LICENSE, .gitignore                                    |
| P1   | c79aa11   | specification/00-CONSTITUTION.md, 01-ONTOLOGY.md               |
| P2   | d1a51ea   | specification/02–13 (12 documents)                             |
| P3   | d7112fb   | aeon.core, aeon.serialization, aeon.clock, aeon.provenance,    |
|      |           | aeon.state, aeon.signal                                        |
| P4   | 9f8ecc1   | aeon.capability, aeon.port                                     |
| P5   | 24cc960   | aeon.contraction, aeon.recursion                               |
| P6   | d71e829   | schemas/ir-module.schema.json, aeon.graph, aeon.ir             |
| P8   | 3dd3562   | compiler/{__init__,ast,formatter,lexer,parser,validator}.py    |
| P9,  | 6ba5250   | runtime/{__init__,interpreter,replay,scheduler}.py,            |
| P10, |           | aeon.sources.dummy                                             |
| P11  |           |                                                                |
| P12  | fcb1f17   | tests/ (12 modules; 66 tests)                                  |
| P13  | 042fd57   | backends/python/, compiler/cli.py, examples/two_sources.aeon   |
| —    | 7680ffa   | PHASE-0-REPORT.md                                              |

**P7 has no dedicated commit.** The Phase 0.1 mandate §1.2 flags
this as a discrepancy requiring precise attribution. The truth
is:

- `aeon.serialization` (canonical byte-stable serialization) is
  in commit **d7112fb** (P3).
- Semantic hashing (`digest`, `digest_bytes`, the module-id and
  state-id formulas) is in commits **d7112fb** (P3, primitives)
  and **d71e829** (P6, IRModule.compute_module_id and golden
  ordering).

Bundling P7 into P3 and P6 is acceptable under mandate §1.2 iff
the deliverables exist. They do. This reconciliation records
that fact explicitly rather than leaving it implicit in the
narrative.

**P9, P10, P11 are combined into commit 6ba5250.** The commit
body disclosed the bundling. Under mandate §14 ("Do not combine
multiple closure stages merely for convenience") the bundle was
justified end-to-end (an interpreter with no scheduler cannot
run a graph; sources with no interpreter cannot be exercised).
Future closure commits (C0–C10) will each be their own commit.

### 1.3 File-surface audit

| Claim in `PHASE-0-REPORT.md`                       | Verified? |
| -------------------------------------------------- | --------- |
| 14 normative specification documents               | Yes       |
| Canonical IR schema at `schemas/ir-module.schema.json` | Yes   |
| Compiler and parser present                        | Yes       |
| Formatter present                                  | Yes       |
| Static validator present                           | Yes       |
| Reference interpreter present                      | Yes       |
| Scheduler present                                  | Yes       |
| Snapshot/restore support in ReferenceContractiveRecursion, DummyVectorSource, DummyRichSource | Yes |
| Deterministic replay driver present                | Yes       |
| Standard-library modules present                   | Partial (see Gate G reassessment) |
| Python backend present                             | Yes       |
| Eight CLI tools present                            | Yes       |
| 66 tests                                           | Yes (`pytest tests/ -q` reports `66 passed`) |
| Phase 0 report present                             | Yes       |

### 1.4 Reproducing the reported evidence

Re-executed from a fresh `git clone` of the branch into
`/tmp/aeon_verify/fresh`, using **only the documented commands**
(there is no packaging; PYTHONPATH must be set as per the
README):

- `python3 -m pytest tests/ -q` → `66 passed in 0.38s`. **Reproduces.**
- `aeoncheck examples/two_sources.aeon` → `OK`. **Reproduces.**
- `aeonc examples/two_sources.aeon -o /tmp/tv.ir.json --seed 1
  --ticks-per-clock 4` → `module_id=f3e80de6c505b2e30f4351ca` with
  49 instructions. **Reproduces byte-identically.**
- `aeonir /tmp/tv.ir.json` → prints envelope + counts.
  **Reproduces.**
- `aeonrun examples/two_sources.aeon --seed 1 --ticks-per-clock 4`
  → 4 `PROVEN_CONTRACTIVE` certificates. **Reproduces
  numerically; but see §2.1 below — the label is overstated.**
- `aeongraph examples/two_sources.aeon` → well-formed DOT.
  **Reproduces.**
- `aeonreplay examples/two_sources.aeon --seed 1
  --ticks-per-clock 4` → `identical: true`. **Reproduces.**
- `aeontest` → `66 passed`. **Reproduces.**
- `aeonfmt examples/two_sources.aeon --check` → **fails**
  (exit 5). **Does not reproduce a clean-file claim** (the
  original report never explicitly claimed the example was
  already canonical, but any reasonable reader would infer it
  from "verified end-to-end with all eight tools"). See §2.2.

**PYTHONHASHSEED matrix** on `aeonc`:

    PYTHONHASHSEED=0      → sha256 d647c78bb11c0e8d7b0cc320f0966d088ee337bdd777b5c51823217b4d3c69ec
    PYTHONHASHSEED=1      → sha256 d647c78bb11c0e8d7b0cc320f0966d088ee337bdd777b5c51823217b4d3c69ec
    PYTHONHASHSEED=42     → sha256 d647c78bb11c0e8d7b0cc320f0966d088ee337bdd777b5c51823217b4d3c69ec
    PYTHONHASHSEED=random → sha256 d647c78bb11c0e8d7b0cc320f0966d088ee337bdd777b5c51823217b4d3c69ec

Canonical IR bytes are stable across hash seeds. Good.

## 2. Corrections to `PHASE-0-REPORT.md`

The following statements from the Phase 0 report require
correction.

### 2.1 Contraction certification is overstated

`PHASE-0-REPORT.md §6 Gate H` and its CLI evidence report the
example as producing **`PROVEN_CONTRACTIVE`** certificates.
That label is a **formal claim** in the specification
(`07-CONTRACTION.md §2`) reserved for a proven upper bound that
`effective Lipschitz bound < declared margin < 1` for the
complete certified transition and declared domain.

What the reference substrate actually does is emit the
`CertificationMethod.SYMBOLIC_PARAMETERIZATION` result for its
own linear update rule `next[i] = margin * (decay * s + (1-decay) * a)`,
which is L∞-contractive **for that rule**. The substrate does
not currently:

- verify that the projections into it are bounded within the
  declared domain;
- verify that the aggregate of arbitrary source frames stays
  within a state bound that keeps the rule contractive;
- perform an independent recomputation of the bound.

Per Phase 0.1 mandate §3.1–§3.3, the correct label for what
was actually produced is `BOUNDED_CONTRACTIVE` (sound
numerical bound), not `PROVEN_CONTRACTIVE`. Phase 0.1 commit
C1 will downgrade the default emission, introduce an
independent verifier, and add negative fixtures.

**Effect on Gate B (contraction semantics):** the specification
in `07-CONTRACTION.md` is correct — the vocabulary and the
distinction between `PROVEN_CONTRACTIVE` / `BOUNDED_CONTRACTIVE`
/ `NOT_PROVEN` / `VIOLATED` / `NUMERICALLY_INVALID` is documented
faithfully. The **implementation** was overstating; fixing the
implementation is a code change, not a spec change.

### 2.2 aeonfmt on the example fails --check

`examples/two_sources.aeon` is not canonical because:

- The formatter drops `#` comments (the parser does not preserve
  them). The example file has a header comment.
- The formatter sorts sources alphabetically. The example
  declares `transformer` before `persistence`.

Both are known and semantically intentional; the example simply
was not run through `aeonfmt --write`. Phase 0.1 commit C0
either rewrites the example canonically or adjusts formatter to
preserve at least a leading comment block. The simplest fix is
to regenerate the example.

**Effect on gate assessments:** none. `aeonfmt --check` is doing
its job; the example fixture was authored non-canonically.

### 2.3 No packaging

`PHASE-0-REPORT.md` does not claim installability. The mandate's
§1.4 clean-install requirement cannot be satisfied without
`pyproject.toml` / `setup.py`. Phase 0.1 must add packaging
before Gate J can be evaluated for "clean-install test green"
(mandate §15). Adding packaging is in scope for C8/C9.

### 2.4 Report Gate H should be PARTIAL, not PASS

`PHASE-0-REPORT.md` grades Gate H as PASS. Per Phase 0.1
mandate §2.4, Gate H PASS requires **fresh-process deterministic
replay** and **explicit failure on invalid schedules**. The
Phase 0 evidence covered same-process replay only. Downgrade to
PARTIAL until fresh-process replay is added (C7 covers this).

### 2.5 Report Gate D should acknowledge scope

`PHASE-0-REPORT.md` grades Gate D as PASS. Per Phase 0.1
mandate §2.2, Gate D PASS requires proving canonicalization
across fresh processes, differing hash seeds, differing insertion
orders, differing source formatting, snapshot/restore, and both
backends after the second exists.

- Fresh-process determinism: verified in this audit
  (PYTHONHASHSEED matrix). Retain PASS on this axis.
- Both backends: only one backend exists. Cross-backend evidence
  cannot exist yet. Downgrade Gate D to PARTIAL until the second
  backend (C5) provides differential evidence.

### 2.6 Gate G PARTIAL rationale unchanged

`PHASE-0-REPORT.md §6 Gate G` correctly grades PARTIAL for
missing dedicated `aeon.types`, `aeon.identity`, `aeon.causality`,
`aeon.contract`, `aeon.certificate`, `aeon.projection`,
`aeon.snapshot`, `aeon.testing`, `aeon.math`, `aeon.tensor`,
`aeon.runtime`. Phase 0.1 commit C4 will provide those.

## 3. Corrected gate table (pending Phase 0.1 closure work)

Post-reconciliation, before any C1–C10 work lands:

| Gate | Phase 0 report | Reconciled |
| ---- | -------------- | ---------- |
| A    | PASS           | PASS       |
| B    | PASS           | PASS       |
| C    | PARTIAL        | PARTIAL    |
| D    | PASS           | **PARTIAL** (only one backend; cross-backend evidence absent) |
| E    | PASS           | PASS       |
| F    | PARTIAL        | PARTIAL    |
| G    | PARTIAL        | PARTIAL    |
| H    | PASS           | **PARTIAL** (no fresh-process replay evidence) |
| I    | PARTIAL        | PARTIAL    |
| J    | NOT PASSED     | NOT PASSED |
| K    | NOT GRANTED    | NOT GRANTED |

The Phase 0.1 closure sequence (C0–C10) is committed to
addressing every PARTIAL above and providing the CI, packaging,
independent verifier, and fresh-process replay evidence needed
to reassess Gate J mechanically.
