"""L10: deterministic training surface."""

from __future__ import annotations

from dataclasses import replace

import pytest

from aeon_app.training import (
    LossResult,
    OptimizerState,
    TrainingCertificate,
    TrainingSession,
    make_reference_batch,
    make_training_session,
)


def test_training_batch_deterministic():
    a = make_reference_batch(seed=1, ticks=4)
    b = make_reference_batch(seed=1, ticks=4)
    assert a.digest() == b.digest()


def test_training_step_produces_full_certificate():
    session = make_training_session()
    batch = make_reference_batch(seed=1, ticks=4)
    cert = session.step(batch)
    assert isinstance(cert, TrainingCertificate)
    assert cert.application_version == "0.1.0"
    assert cert.batch_digest == batch.digest()
    assert cert.initial_parameter_digest
    assert cert.loss_digest
    assert cert.gradient_digest
    assert cert.updated_parameter_digest
    assert cert.optimizer_digest


def test_loss_decomposition_reports_every_term():
    from aeon_app.training import _forward
    from aeon_app.config import reference_config
    cfg = replace(reference_config(), runtime_mode="DEVELOPMENT")
    fwd = _forward(cfg, make_reference_batch(seed=1, ticks=4))
    L = fwd.loss
    # Every term is a real number (may be zero) and total is a
    # weighted sum of the five components.
    assert isinstance(L.total, float)
    assert isinstance(L.next_prediction, float)
    assert isinstance(L.recursion_consistency, float)
    assert isinstance(L.contraction_penalty, float)
    assert isinstance(L.feedback_regularization, float)
    assert isinstance(L.source_contribution_regularization, float)


def test_training_reproducibility_two_sessions_agree():
    """The mandate-§18.3 reproducibility fixture: two independent
    sessions on the same seed produce identical certificates."""
    batch = make_reference_batch(seed=7, ticks=4)
    a = make_training_session().step(batch)
    b = make_training_session().step(batch)
    assert a.batch_digest == b.batch_digest
    assert a.initial_parameter_digest == b.initial_parameter_digest
    assert a.loss_digest == b.loss_digest
    assert a.gradient_digest == b.gradient_digest
    assert a.updated_parameter_digest == b.updated_parameter_digest


def test_multiple_steps_advance_optimizer_state():
    session = make_training_session(learning_rate=1e-4)
    batch = make_reference_batch(seed=1, ticks=4)
    session.step(batch)
    session.step(batch)
    assert session.optimizer.step_count == 2
    assert len(session.history) == 2


def test_training_disabled_in_reference_mode_by_default():
    """The reference config has training.enabled=False. Whether a
    caller can still run training depends on runtime_mode: REFERENCE
    prohibits training via the constitution §5. Here we just verify
    the reference config declares training disabled."""
    from aeon_app.config import reference_config
    assert reference_config().training.enabled is False


def test_certificate_recheck_flag_true_when_parameters_moved():
    """When the optimizer step actually moves any projection scale,
    the certificate must flag a contraction re-check. We start from
    an interior point so descent isn't blocked by the scale bound."""
    from aeon_app.config import reference_config
    cfg = replace(reference_config(), runtime_mode="DEVELOPMENT")
    interior = tuple(
        replace(p, scale_upper_bound=p.scale_upper_bound * 0.5)
        for p in cfg.projections
    )
    cfg = replace(cfg, projections=interior)
    session = make_training_session(config=cfg, learning_rate=1e-3)
    batch = make_reference_batch(seed=1, ticks=4)
    cert = session.step(batch)
    assert cert.certificate_recheck_required is True
