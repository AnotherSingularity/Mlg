"""Mechanical reproduction of the 2026-07-30 independent-audit
findings.

Each test in this module documents a *reproducible* defect
identified by the audit and cited in
``AEON-v0.1.0-AUDIT-REJECTION.md`` (R0).

The tests are marked ``xfail(strict=True)`` because we want the
CI suite to STAY GREEN while the defects are unclosed — the
xfail records that "this SHOULD have raised / rejected /
differed", so when R1..R9 land and the defect is closed the
test will *unexpectedly pass*, ``strict=True`` will flip it
red, and we will be forced to remove the xfail marker in the
same commit that closes the finding.

Do NOT relax any of these markers as a way to make CI happy.
They are the mechanical proof that the audit's claims are real.
"""

from __future__ import annotations

from dataclasses import replace

import pytest


AUDIT_XFAIL_REASON = (
    "Audit-reproduction test for R0. The behavior asserted here is "
    "the CORRECT behavior; the current implementation exhibits the "
    "defect documented by the audit. Remove the xfail marker in the "
    "same commit that closes the corresponding C / H finding."
)


# ---------------------------------------------------------------------------
# C-04 — certified startup does not bind executable implementation bytes
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason=AUDIT_XFAIL_REASON)
def test_c04_certified_startup_rejects_runtime_code_tamper():
    """Certified startup MUST reject a session whose runtime code
    has been swapped out. A monkeypatch that changes the input
    frames MUST cause verify_certified_startup to fail (or the
    subsequent session to refuse to run).

    Today this test fails: verify_certified_startup returns
    valid=True in both the pristine and the tampered case, and
    the tampered session produces materially different output.
    """
    from aeon.clock import ClockPosition
    from aeon.provenance import make_identity
    from aeon.signal import new_signal_frame

    from aeon_app import application as A
    from aeon_app.application import new_session, run
    from aeon_app.certified import certified_config, verify_certified_startup

    baseline = verify_certified_startup(certified_config())
    assert baseline.valid is True

    orig = A.ApplicationSession._fresh_frame_for

    def zero_frame(self, source_id, tick):
        cfg = next(s for s in self.config.sources
                   if s.component_id == source_id)
        payload = [0.0] * cfg.dimension
        return new_signal_frame(
            source_id=f"input.{source_id}", sequence=tick,
            clock_position=ClockPosition("source", tick), payload=payload,
            originating_state_id=make_identity(
                "aeon_app.input",
                {"source_id": source_id, "tick": tick, "payload": payload},
            ),
        )

    A.ApplicationSession._fresh_frame_for = zero_frame
    try:
        # After R5 lands, this call SHOULD raise (implementation
        # bytes no longer match the frozen certified identity).
        result_tamper = verify_certified_startup(certified_config())
        # Or: startup passes but a subsequent new_session refuses.
        s = new_session(certified_config())
        out = run(s, ticks=2)
        A.ApplicationSession._fresh_frame_for = orig
        s2 = new_session(certified_config())
        out2 = run(s2, ticks=2)
        # Correct outcome: EITHER tamper-startup rejected, OR
        # tamper-session refused, OR outputs are byte-identical.
        assert (
            result_tamper.valid is False
            or [list(o.payload) for o in out]
                == [list(o.payload) for o in out2]
        )
    finally:
        A.ApplicationSession._fresh_frame_for = orig


# ---------------------------------------------------------------------------
# C-05 — certified snapshots accept tampered semantic identity
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason=AUDIT_XFAIL_REASON)
@pytest.mark.parametrize(
    "field,value",
    [
        ("graph_id", "a" * 64),
        ("ir_module_id", "b" * 64),
        ("runtime_mode", "REFERENCE"),
        ("backend_id", "numpy"),
        ("event_log_digest", "c" * 64),
    ],
)
def test_c05_snapshot_restore_rejects_tampered_field(field, value):
    """A certified snapshot restore MUST refuse a snapshot whose
    semantic-identity fields have been altered. Today the restore
    path only checks the language lock, schema/app/lang version
    strings, and the configuration digest — every field
    parametrised here is trusted.
    """
    from aeon_app.application import new_session, restore, run
    from aeon_app.certified import certified_config
    from aeon_app.persistence import load_snapshot

    cfg = certified_config()
    session = new_session(cfg)
    run(session, ticks=2)
    original = load_snapshot(session.snapshot().to_bytes())
    tampered = replace(original, **{field: value})
    tampered_bytes = tampered.to_bytes()

    with pytest.raises(Exception):
        restore(cfg, load_snapshot(tampered_bytes))


# ---------------------------------------------------------------------------
# C-01 — application does not emit SIGNAL_FORM / SIGNAL_PROJECT in its IR
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason=AUDIT_XFAIL_REASON)
def test_c01_compiled_ir_carries_source_and_projection_dataflow():
    """The application's compiled IR MUST contain the
    source-read / signal-form / signal-project instructions
    needed to define the ``minput.*`` bindings that
    RECURSION_INTEGRATE consumes. Today it only contains
    CLOCK_DEFINE / CLOCK_TICK / SOURCE_INIT / SOURCE_STEP /
    RECURSION_INIT / RECURSION_INTEGRATE.
    """
    from aeon_app.certified import certified_config
    from aeon_app.graph import build_from_config, compile_to_ir

    cfg = certified_config()
    ir = compile_to_ir(cfg, build_from_config(cfg))
    opcode_names = {str(inst.opcode).split(".")[-1] for inst in ir.instructions}
    # The correct IR must contain at least one of the dataflow
    # opcodes that produce the minput.* bindings.
    dataflow_opcodes = {"SOURCE_READ", "SIGNAL_FORM", "SIGNAL_PROJECT"}
    assert dataflow_opcodes & opcode_names, (
        f"IR is missing all dataflow opcodes; got {sorted(opcode_names)}"
    )


# ---------------------------------------------------------------------------
# C-03 — contraction certificate scope widened without composed proof
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason=AUDIT_XFAIL_REASON)
def test_c03_contraction_scope_not_widened_without_composed_proof():
    """The application's Recursion substrate MUST NOT unilaterally
    widen a certificate scoped to RECURSION_CORE into
    PROJECTED_RECURSION unless a composed proof over the source
    projection, aggregation, and feedback paths is established.
    """
    from aeon_app.application import new_session, run
    from aeon_app.certified import certified_config

    session = new_session(certified_config())
    outputs = run(session, ticks=2)
    assert outputs, "no outputs produced"
    for out in outputs:
        cert = out.contraction_certificate
        scope = str(cert.get("certified_scope", "")).upper()
        result = str(cert.get("result", "")).upper()
        # Correct behavior after R4:
        # If scope is claimed as PROJECTED_RECURSION, the
        # certificate MUST carry a "composed_proof" field with
        # evidence. Absent that field, the claim is invalid.
        if "PROJECTED_RECURSION" in scope and "PROVEN" in result:
            assert cert.get("composed_proof") is not None, (
                "PROVEN_CONTRACTIVE at PROJECTED_RECURSION scope "
                "requires composed_proof evidence"
            )
