# Contraction Semantics

**Status:** REQUIRED — Phase 0
**Depends on:** `02-TYPE-SYSTEM.md`, `06-RECURSION.md`

## 1. Contract type

```
Contractive<M> {
    metric                : MetricRef       // e.g. L2, spectral norm
    requested_margin      : Bounded(0, 1, Float)
    numerical_tolerance   : Float
    precision_policy      : PrecisionPolicy
    certification_method  : CertificationMethodRef
}
```

Where `PrecisionPolicy` names an arithmetic policy (element type,
rounding mode, accumulation width). The contract binding fixes the
policy under which the contraction is claimed; a claim made under
one policy does not carry over to another.

## 2. Result vocabulary

A contraction check produces one of:

- `PROVEN_CONTRACTIVE`     — the contract holds symbolically or by a
                             conservative bound.
- `BOUNDED_CONTRACTIVE`    — the contract holds within the declared
                             numerical tolerance.
- `NOT_PROVEN`             — the check was inconclusive.
- `VIOLATED`               — the contract was checked and does NOT
                             hold.
- `NUMERICALLY_INVALID`    — the check itself was corrupted (NaN,
                             overflow, etc.).

**Critical distinction (constitution §6):**
`NOT_PROVEN` MUST NOT be equated with `VIOLATED`. Failure to prove
is not proof of failure. The compiler and runtime MUST expose these
as distinct tags.

## 3. Certificate shape

```
ContractionCertificate {
    contract_version      : SemVer
    metric                : MetricRef
    requested_margin      : Bounded(0, 1, Float)
    measured_upper_bound  : Float | Unavailable
    numerical_tolerance   : Float
    arithmetic_precision  : PrecisionPolicy
    certification_method  : CertificationMethodRef
    result                : ContractionResult
    consumed_inputs       : List<InputDigest>   // frame/state digests
    clock_position        : ClockPosition
}
```

An implementation MUST populate every field. `measured_upper_bound`
MAY be `Unavailable` only when the method does not produce one (a
symbolic method may not); it MUST NOT be `Unavailable` for
numerical methods.

## 4. Certification methods

At least the following methods are defined in v0.1:

- `SpectralPowerIteration(iterations, tolerance)` — numerical
  upper bound on operator spectral radius via power iteration.
- `SingularValueDecomposition` — direct SVD-based bound (may be
  reference-only for small dimensions).
- `SymbolicParameterization(scheme)` — a claim that the mapping is
  contractive by construction of its parameterization. The scheme
  identifier documents the parameterization (e.g., an
  orthogonal-then-scaled parameterization).

Methods MAY be added in later versions. Removing a method requires
`DEPRECATED` status and a migration policy (`12-VERSIONING.md`).

## 5. Verification against declared policy

The runtime MUST verify the *effective* transition under the
declared `PrecisionPolicy` — not the abstract mathematical
transition and not the transition under some other precision that
happens to be convenient.

An assertion that a construction (for example, a Cayley
parameterization) mathematically implies a spectral bound is not
itself a certificate. The certificate MUST demonstrate the bound
under the actual arithmetic being used, or MUST declare the method
as `SymbolicParameterization` and identify what the symbolic claim
does *not* cover (nonlinearities, projection matrices, input
bounds, state bounds).

If the existing Cayley parameterization is incorporated, the
following MUST be documented and tested in the implementation:

- The precise matrix construction (parameter vector to matrix).
- The singular-value bound implied by the construction.
- The effect of nonlinearities interposed with the linear map.
- The effect of projection matrices interposed with the linear map.
- Tolerance handling under the declared `PrecisionPolicy`.
- State and input bounds required for the claim to hold.
- Failure behavior when the guarantee cannot be proven (`NOT_PROVEN`
  vs `VIOLATED`).

## 6. Composition

The composition of two `PROVEN_CONTRACTIVE` transitions under the
same metric with margins `m_1` and `m_2` is contractive with
margin `m_1 * m_2`. Composition of a `BOUNDED_CONTRACTIVE` with any
other yields at best `BOUNDED_CONTRACTIVE`; composition with a
`NOT_PROVEN` yields `NOT_PROVEN`; composition with a `VIOLATED`
yields `VIOLATED`; composition with a `NUMERICALLY_INVALID` yields
`NUMERICALLY_INVALID`.

An implementation MUST propagate the least favorable tag through
composition. Silent upgrade of tag through composition is a
Gate-B/E failure.
