# Aeon Type System

**Status:** REQUIRED — Phase 0
**Depends on:** `00-CONSTITUTION.md`, `01-ONTOLOGY.md`

## 1. Purpose

The Aeon type system MUST statically distinguish:

1. Source state from Recursion state.
2. Payload identity from state identity.
3. Clock domains.
4. Frame types.
5. Port types.
6. Capability requirements.
7. Owned state from moved state.
8. Certified results from uncertified results.
9. Unavailable values from zero-valued values.

Violation of any of these distinctions by an implementation is a
Gate-C failure.

## 2. Kind system

Aeon types are stratified into kinds:

- `*`               — value kind.
- `State`           — the kind of stateful values.
- `Signal`          — the kind of signal frame values.
- `Port<*>`         — the kind of ports over a value kind.
- `Capability`      — the kind of capability names.
- `Contract<*>`     — the kind of contracts over a value kind.
- `Certificate<*>`  — the kind of certificates over a value kind.
- `Clock`           — the kind of clock domains.
- `Shape`           — the kind of shape descriptors.

Kind mixing (e.g., passing a `State` where a plain `*` is required)
is a static error.

## 3. Nominal + structural typing

Types have both a nominal identity (module-qualified name and
version) and a structural signature (fields, shape, clock domain).
Two nominal types with structurally equal signatures are NOT
substitutable unless a declared coercion contract exists.

## 4. Numerical types

The following numerical types are part of the language (v0.1):

- `Integer` — arbitrary-precision integer.
- `Fixed(scale, width)` — fixed-point number.
- `ExactRational` — arbitrary-precision rational.
- `Float(precision)` — IEEE-754 floating-point, precision-tagged
  (`Float(f32)`, `Float(f64)`, `Float(bf16)`, `Float(f16)`).
- `Interval(bound_type)` — closed interval over `bound_type`.
- `Bounded(lo, hi, element)` — element type with runtime-checked
  bounds.
- `Probability` — a `Float`-valued type constrained to `[0, 1]`.
- `Tensor<Element, Shape>` — element-typed, shape-typed tensor.
- `Matrix<Element, Rows, Cols>` — element-typed, dimension-typed
  matrix (sugar for `Tensor<Element, Shape([Rows, Cols])>`).

Rules:

1. Conversions that widen precision are implicit; conversions that
   narrow, round, or change type family are explicit.
2. `NaN` and `Inf` MUST NOT enter a state whose contract does not
   admit them.
3. `Bounded` violations produce `TransitionResult.Rejected` (not
   `Failed`).
4. `Probability` is closed under multiplication and convex
   combination; other operations require an explicit conversion.

## 5. Frame and state types

A frame type is written `Signal<T, C>` where `T` is the payload type
and `C` is the clock domain. Two frames with the same `T` but
different `C` are distinct types.

A state type is written `State<T, O, C>` where `T` is the payload
type, `O` is the owner (source id or substrate id), and `C` is the
clock domain.

## 6. Ownership annotations

Every state binding carries an ownership annotation:

- `own` — the binding owns the state and may consume it (move).
- `borrow` — the binding may read but may not consume the state.
- `shared_immut` — multiple readers, no mutation.
- `frozen` — historical snapshot; may never be re-mutated.

Move rules are specified in `03-STATE-SEMANTICS.md`.

## 7. Result types

A transition result type is:

```
TransitionResult<T> =
      Applied<T, Certificate<T>>
    | AppliedUncertified<T, Reason>
    | Rejected<ContractViolation>
    | Failed<RuntimeError>
```

The compiler MUST forbid pattern-match exhaustion errors on
`TransitionResult<T>`.

## 8. Availability

Optional values use `Option<T>` = `Some<T> | Unavailable`. It is a
static error to coerce `Unavailable` into `T` without an explicit
default binding, and it is prohibited (see constitution §6) to treat
`Unavailable` as zero.

## 9. Certification-tagged types

A value type `T` may be qualified as `Certified<T>` or
`Uncertified<T>`. The compiler MUST forbid assignment of an
`Uncertified<T>` into a binding typed `Certified<T>` without an
explicit certification step (`CONTRACT_CERTIFY`).

## 10. Shape and dimension

Shapes are first-class. A shape is an ordered tuple of dimensions,
each of which is either:

- a positive integer literal;
- a named symbolic dimension (`dim.hidden`, `dim.tokens`);
- a shape variable (`?d`).

Shape equality is structural. Shape mismatch is a compile-time
diagnostic when both shapes are concrete; otherwise it is a
transition-time `Rejected`.

## 11. Clock-domain typing

Every operation is typed by the clock domain(s) it observes and
emits. A cross-domain read is a static error unless a
`WINDOW_OPEN`/`WINDOW_CLOSE` aggregation with a declared clock
relation is in scope.

## 12. Contract typing

Contracts are values (`Contract<T>`). Binding a contract to a
transition is typed:

```
bind : Contract<T> -> Transition<I, T> -> BoundTransition<I, T>
```

An unbound transition MAY execute; its result type is then
`AppliedUncertified` unless the transition itself is contract-free
by declaration.
