# Gate L Definitions

**Status:** REQUIRED — Gate L
**Depends on:** `00-APPLICATION-CONSTITUTION.md`

## Gates

| Gate  | Name                     | Pass condition (summary)                                                   |
| ----- | ------------------------ | -------------------------------------------------------------------------- |
| L-A   | Application specification | constitution + architecture + modes + gates documented normatively         |
| L-B   | Structural graph          | all nodes/edges typed, ports negotiate, clocks explicit, IR stable         |
| L-C   | Source conformance       | both sources satisfy REQUIRED source-port conformance                       |
| L-D   | Recursion correctness    | multi-source integration + honest scope + fail-closed on invalid           |
| L-E   | Runtime determinism      | reference execution deterministic across hash seeds + fresh process        |
| L-F   | Persistence              | snapshot round-trip reproduces next transition                             |
| L-G   | Feedback                 | zero-gate neutrality proven; nonzero bounded; ownership preserved          |
| L-H   | Training                 | training fixture reproduces initial state, losses, updated parameters      |
| L-I   | Operational readiness    | all CLI tools work post-install; CI green; package builds                  |
| L-J   | Application certification | Gates L-A..L-I pass + language pinned + full conformance + CI green + manifest verifies |

## Launch decision

After Gate L-J only two outputs are permitted:

    LAUNCH CERTIFIED
    LAUNCH BLOCKED

No intermediate wording ("mostly ready", "ready except",
"functionally complete") is permitted.

## Windows packaging (L16)

L16 MAY begin only after LAUNCH CERTIFIED. Windows packaging
MUST NOT alter application semantics. If Gate L-J does not
pass, L16 is prohibited.
