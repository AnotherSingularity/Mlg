"""aeon.certificate — the certificate subsystem's public surface.

Re-exports the universal :class:`Certificate` from :mod:`aeon.core`
and the specialized :class:`ContractionCertificate` from
:mod:`aeon.contraction`. Adds :func:`recheck` — a helper that
independently re-validates a certificate against its declared
evidence (mandate §3.5).
"""

from __future__ import annotations

from typing import Any

from .contraction import ContractionCertificate, ContractionResult
from .core import Certificate
from .verifier import DomainBounds, TransitionDefinition, VerifierInput, verify


def recheck_contraction(
    cert: ContractionCertificate,
    transition: TransitionDefinition,
    domain: DomainBounds,
) -> bool:
    """Independently re-run the verifier on the transition + domain
    that a certificate claims to cover and return True iff the
    result and computed_upper_bound agree with the certificate.

    Callers pass the transition and domain from the graph, NOT from
    the certificate; that is the mandate §3.5 independence
    requirement.
    """

    from .contraction import Contractive
    contract = Contractive(
        metric=cert.metric,
        requested_margin=cert.requested_margin,
        numerical_tolerance=cert.numerical_tolerance,
        precision_policy=cert.arithmetic_precision,
        certification_method=cert.certification_method,
    )
    report = verify(VerifierInput(transition, contract, domain))
    if report.result is not cert.result:
        return False
    if cert.measured_upper_bound is None and report.computed_upper_bound is None:
        return True
    if cert.measured_upper_bound is None or report.computed_upper_bound is None:
        return False
    return abs(cert.measured_upper_bound - report.computed_upper_bound) <= cert.numerical_tolerance


__all__ = [
    "Certificate",
    "ContractionCertificate",
    "ContractionResult",
    "recheck_contraction",
]
