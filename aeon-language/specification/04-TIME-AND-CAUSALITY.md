# Time and Causality

**Status:** REQUIRED — Phase 0
**Depends on:** `02-TYPE-SYSTEM.md`, `03-STATE-SEMANTICS.md`

## 1. Clock domains

A clock domain is a discrete monotonic ordering. Every source,
substrate, transition, signal frame, and state is associated with
exactly one clock domain.

Standard clock domains (initial, may be extended):

- `SourceLocal(source_id)` — a source's private clock.
- `Token` — the token clock (fast).
- `Integration` — the Recursion integration clock (slow or per-step).
- `Segment` — a coarse segmentation clock.
- User-defined domains via `CLOCK_DEFINE`.

## 2. Clock positions

A `ClockPosition` is a pair `(domain_id, tick)` where `tick` is a
non-negative integer strictly increasing within the domain. Two
positions with equal `domain_id` are strictly ordered. Two positions
with different `domain_id` are not ordered directly; they may be
ordered only through a declared relationship.

## 3. Clock relationships

Cross-domain use requires a declared relationship established by
`CLOCK_RELATE`. Standard relationships:

- `AggregatesFrom(fast, slow, window_size)` — `slow` ticks each time
  a window of `window_size` `fast` ticks completes.
- `DerivedFrom(a, b, mapping)` — `a`'s ticks are a declared function
  of `b`'s ticks.
- `Independent(a, b)` — explicitly no relationship; no cross-domain
  read is permitted.

Declaring a relationship does not merge the two domains: their
identities remain distinct in every frame and every state.

## 4. Aggregation windows

A window is a half-open interval `[start, end)` within one clock
domain. Windows are opened with `WINDOW_OPEN` and closed with
`WINDOW_CLOSE`. Every window carries an identity computed from its
domain, its bounds, and its declared relationship (if any).

A slow-clock integration whose consumed fast-clock window is
unidentified is a compile-time error. The
`RECURSION_INTEGRATE` instruction MUST record, in its produced
certificate, the exact identity or digest of every consumed window.

## 5. Causal invariants

The following causal invariants MUST hold for every valid Aeon
program and every conforming implementation:

1. **No future leakage.** A transition at position `p_t` in domain
   `C` MUST NOT observe a frame or state with position `p_t' > p_t`
   in the same domain `C`.

2. **Order preservation.** Frames within one clock domain are
   consumed in strictly increasing tick order unless the transition
   explicitly declares out-of-order acceptance (a `RandomAccess`
   contract).

3. **No duplicate consumption.** A frame consumed by an ownership
   transition MUST NOT be re-consumed by another ownership
   transition. Borrowed reads are unrestricted.

4. **Declared cross-domain read.** A transition MUST NOT read a
   frame or state from a clock domain other than its own without a
   declared cross-domain relationship in scope.

5. **Window validity.** A frame MAY only be observed inside a window
   for which it is a member.

6. **Aggregation identity.** An aggregation of a fast-clock window
   into a slow-clock frame MUST record the fast-clock window
   identity (or an equivalent frame-range digest) as part of the
   slow-clock frame's provenance.

Violation of any invariant produces `TransitionResult.Rejected` with
a `ContractViolation` naming the violated invariant. It is
prohibited (see constitution §6) to treat a causal violation as a
runtime `Failed`.

## 6. Replay determinism

Given:

- The same graph identity.
- The same source frame sequences (byte-identical canonical form).
- The same random seeds where declared.
- The same backend numerical policy.

The runtime MUST produce a byte-identical sequence of state
identifiers, certificates, and canonical outputs. Replay tests
verify this contract.

Note: byte-identical *outputs* across backends are not required in
general (see `13-CONFORMANCE.md` on backend parity tolerances); byte
identity of *state identifiers* is required within one backend
under replay.

## 7. Scheduling

A scheduler is any implementation that decides, per clock tick,
which transitions to execute. A conforming scheduler MUST respect
every causal invariant in §5 and MUST attribute every executed
transition to a specific clock position.

Two conforming schedulers on the same graph MUST produce the same
sequence of state identifiers (the causal ordering fixes it),
though they MAY execute independent transitions in different
concurrent orders internally.
