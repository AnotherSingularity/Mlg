"""aeon.certificate — Certificate + independent recheck.

Re-exports :class:`Certificate` and :class:`ContractionCertificate`
plus :func:`recheck_contraction` — a helper that independently
re-runs the verifier against transition+domain values supplied by
the caller (the mandate §3.5 independence requirement).

The recheck MUST NOT trust the certificate's `result`,
`measured_upper_bound`, `certified_scope`, or `arithmetic_kind`
fields; it recomputes them and compares.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from .contraction import (
    CertificationMethod,
    ContractionCertificate,
    ContractionResult,
    ContractionScope,
    Contractive,
)
from .core import Certificate
from .verifier import (
    ArithmeticKind,
    DomainBounds,
    TransitionDefinition,
    VerifierInput,
    verify,
)


def recheck_contraction(
    cert: ContractionCertificate,
    transition: TransitionDefinition,
    domain: DomainBounds,
    *,
    arithmetic: ArithmeticKind = ArithmeticKind.EXACT_RATIONAL,
    scope: ContractionScope | None = None,
) -> bool:
    """Return True iff an independent recompute agrees with the
    certificate on every semantic field.

    The recheck refuses to accept a certificate that:
    - claims a stronger status than the verifier can reproduce;
    - claims a certified_scope different from the recompute's scope;
    - claims an arithmetic_kind that was not actually used to
      produce the recompute's evidence;
    - claims a measured_upper_bound that does not match the
      recompute within its declared tolerance (0 tolerance for
      EXACT_RATIONAL: exact equality on Fraction is required).
    """

    scope = scope if scope is not None else cert.certified_scope
    contract = Contractive(
        metric=cert.metric,
        requested_margin=cert.requested_margin,
        numerical_tolerance=cert.numerical_tolerance,
        precision_policy=cert.arithmetic_precision,
        certification_method=cert.certification_method,
    )
    report = verify(VerifierInput(
        transition=transition,
        contract=contract,
        domain=domain,
        arithmetic=arithmetic,
        scope=scope,
    ))

    # Result must agree.
    if report.result is not cert.result:
        return False
    # certified_scope must agree.
    if report.certified_scope is not cert.certified_scope:
        return False
    # arithmetic_kind must agree.
    if report.arithmetic.value != cert.arithmetic_kind:
        return False
    # measured_upper_bound: for PROVEN_CONTRACTIVE via EXACT_RATIONAL,
    # equality is EXACT; float comparison uses declared tolerance.
    if cert.measured_upper_bound is None and report.computed_upper_bound is None:
        return True
    if cert.measured_upper_bound is None or report.computed_upper_bound is None:
        return False
    if cert.arithmetic_kind == ArithmeticKind.EXACT_RATIONAL.value \
            and cert.result is ContractionResult.PROVEN_CONTRACTIVE:
        # Exact-rational path: convert both to Fraction and compare.
        try:
            a = Fraction(cert.measured_upper_bound)
            b = Fraction(report.computed_upper_bound)
        except (TypeError, ValueError):
            return False
        return a == b
    return abs(cert.measured_upper_bound - report.computed_upper_bound) <= cert.numerical_tolerance


__all__ = [
    "Certificate",
    "ContractionCertificate",
    "ContractionResult",
    "ContractionScope",
    "recheck_contraction",
]
