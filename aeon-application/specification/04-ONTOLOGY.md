# Aeon Application Ontology

**Status:** REQUIRED — Gate L
**Depends on:** `00-APPLICATION-CONSTITUTION.md`

Terms used with normative weight in the application
specification.

- **AeonOutput** — the structured result of an inference or
  training step. Distinct from `AeonTransitionResult` (which is
  Aeon-Language-scoped).
- **ApplicationGraph** — the typed semantic graph produced by
  the application from its configuration, before compilation
  to canonical Aeon IR.
- **ApplicationConfig** — the resolved, versioned configuration
  record whose digest is part of every snapshot and every
  output's provenance.
- **AttentionSource** — an Aeon-original signal source using an
  attention-style state update. Not a wrapper for an external
  transformer implementation.
- **PersistentRecurrentSource** — an Aeon-original signal
  source providing persistent temporal state via a decay-
  blended recurrent update. Not a wrapper for an external
  recurrent implementation.
- **ContractiveRecursion (application)** — the application's
  Recursion substrate, which wraps the certified Aeon Language
  `ReferenceContractiveRecursion` and emits application-scoped
  certificates.
- **FeedbackGate** — a numeric gate value that scales a feedback
  projection. A gate of 0 MUST be behaviorally neutral.
- **IntegrationClock** — the slow clock on which the Recursion
  substrate integrates; distinct from source clocks.
- **SourceClock** — the fast clock on which sources step.
- **AggregationWindow** — a half-open interval on the source
  clock whose frames are consumed by the next integration.
- **Certificate scope** — `RECURSION_CORE`,
  `PROJECTED_RECURSION`, `INTEGRATION_TRANSITION`, or
  `CLOSED_LOOP_TRANSITION`. The application's initial
  certificate scope is `INTEGRATION_TRANSITION` where domain
  bounds are declared; `RECURSION_CORE` otherwise.
- **Validity** — the enumeration `{VALID,
  PROVISIONALLY_VALID, UNCERTIFIED, CONTRACT_VIOLATED, INVALID,
  UNAVAILABLE}`. Never collapsed into a Boolean.
- **Application graph digest** — the BLAKE2b-256 digest of the
  canonical serialization of the ApplicationGraph.
- **Configuration digest** — the BLAKE2b-256 digest of the
  canonical serialization of the resolved ApplicationConfig.
- **Language lock** — the machine-readable record binding the
  application to a specific certified Aeon Language commit
  (`AEON-LANGUAGE-LOCK.json`).
