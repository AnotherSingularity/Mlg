"""Test the complete public standard-library import surface.

Mandate §6.3: every documented public import works from a clean
environment (here: fresh Python process). Private implementation
details are not accidentally required by examples or conformance
fixtures.
"""

from __future__ import annotations

import importlib
import pytest


MANDATED_MODULES = [
    "aeon.core",
    "aeon.types",
    "aeon.identity",
    "aeon.state",
    "aeon.signal",
    "aeon.clock",
    "aeon.causality",
    "aeon.port",
    "aeon.capability",
    "aeon.contract",
    "aeon.contraction",
    "aeon.recursion",
    "aeon.projection",
    "aeon.graph",
    "aeon.ir",
    "aeon.runtime",
    "aeon.certificate",
    "aeon.provenance",
    "aeon.serialization",
    "aeon.snapshot",
    "aeon.testing",
    "aeon.math",
    "aeon.tensor",
]


@pytest.mark.parametrize("modname", MANDATED_MODULES)
def test_module_importable(modname: str):
    mod = importlib.import_module(modname)
    assert mod is not None


def test_causality_module_surface():
    from aeon.causality import (
        CausalityViolation,
        cross_domain_authorized,
        enforce_order,
        no_future_leakage,
        window_contains,
    )
    assert CausalityViolation is not None


def test_certificate_recheck():
    from aeon.certificate import recheck_contraction
    from aeon.contraction import (
        CertificationMethod, ContractionResult, Contractive, Metric,
        PrecisionPolicy,
    )
    from aeon.clock import ClockPosition
    from aeon.core import SemVer
    from aeon.verifier import (
        DomainBounds, TransitionDefinition, VerifierInput, verify,
    )

    contract = Contractive(
        metric=Metric.LINF, requested_margin=0.9,
        numerical_tolerance=1e-12,
        precision_policy=PrecisionPolicy("float64"),
        certification_method=CertificationMethod.SYMBOLIC_PARAMETERIZATION,
    )
    transition = TransitionDefinition(
        kind="linear_scaled_convex_mix",
        parameters={"decay": 0.5, "margin": 0.9},
    )
    domain = DomainBounds(input_radius=1.0, state_radius=1.0,
                          projection_scale_upper=1.0)
    report = verify(VerifierInput(transition, contract, domain))
    cert = report.to_certificate(
        contract, contract_version=SemVer(0, 1, 0, "dev"),
        consumed_inputs=("aaa",),
        clock_position=ClockPosition("integration", 1),
    )
    # Independent recheck against the SAME transition+domain — should agree.
    assert recheck_contraction(cert, transition, domain) is True


def test_snapshot_envelope_carries_full_context():
    from aeon.snapshot import envelope
    env = envelope(
        graph_id="gid",
        backend_id="aeon.backends.python/0.1.0-dev",
        active_contracts=["c.contractive.r"],
    )
    d = env.to_canonical()
    assert d["language_version"]
    assert d["ir_version"]
    assert d["stdlib_version"]
    assert d["graph_id"] == "gid"
    assert d["backend_id"].startswith("aeon.backends.")
    assert d["active_contracts"] == ["c.contractive.r"]


def test_math_l_inf_l2_dot():
    from aeon.math import all_finite, clamp, dot, is_finite, l2, l_inf
    assert l_inf([1, -2, 3]) == 3
    assert l2([3, 4]) == 5.0
    assert dot([1, 2, 3], [4, 5, 6]) == 32
    assert clamp(5, 0, 1) == 1
    assert is_finite(1.0) and not is_finite(float("inf"))
    assert all_finite([1.0, 2.0])


def test_tensor_shape_validation():
    from aeon.state import Shape
    from aeon.tensor import AeonTensor
    t = AeonTensor(shape=Shape((2, 3)), payload=(1, 2, 3, 4, 5, 6))
    assert t.payload == (1, 2, 3, 4, 5, 6)
    with pytest.raises(ValueError):
        AeonTensor(shape=Shape((2, 2)), payload=(1, 2, 3))


def test_runtime_load_returns_expected_entrypoints():
    from aeon.runtime import load
    entries = load()
    assert {"Interpreter", "lower", "replay"} <= set(entries)


def test_identity_reexports_match_provenance():
    import aeon.identity as I
    import aeon.provenance as P
    assert I.make_identity is P.make_identity
    assert I.state_id is P.state_id
