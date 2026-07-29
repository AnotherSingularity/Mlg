"""aeon_app.training — deterministic training surface.

Training is a **distinct** application surface (mandate §10 and
§18): it does not modify runtime transitions in place. A
TrainingSession runs a forward pass, computes a decomposed loss,
computes a symbolic gradient over a small trainable parameter,
applies an optimizer step, and re-evaluates any affected
certificates.

Version 1 trains only a small ProjectionParameters.scale value.
The dataset is a deterministic synthetic sequence.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from aeon.serialization import canonical_bytes, canonical_value, digest

from .. import APPLICATION_VERSION
from ..application import ApplicationSession, new_session, run
from ..config import ApplicationConfig, reference_config
from ..projections import resolve_projection


@dataclass(frozen=True)
class TrainingBatch:
    id: str
    seed: int
    ticks: int
    target_values: Tuple[Tuple[float, ...], ...]

    def to_canonical(self) -> dict:
        return canonical_value({
            "id": self.id, "seed": self.seed, "ticks": self.ticks,
            "target_values": [list(t) for t in self.target_values],
        })

    def digest(self) -> str:
        return digest(self.to_canonical())


@dataclass(frozen=True)
class LossResult:
    total: float
    next_prediction: float
    recursion_consistency: float
    contraction_penalty: float
    feedback_regularization: float
    source_contribution_regularization: float

    def to_canonical(self) -> dict:
        return canonical_value({
            "total": self.total,
            "next_prediction": self.next_prediction,
            "recursion_consistency": self.recursion_consistency,
            "contraction_penalty": self.contraction_penalty,
            "feedback_regularization": self.feedback_regularization,
            "source_contribution_regularization": self.source_contribution_regularization,
        })

    def digest(self) -> str:
        return digest(self.to_canonical())


@dataclass(frozen=True)
class ForwardResult:
    outputs_digest: str
    loss: LossResult
    per_output_payload_digests: Tuple[str, ...]


@dataclass(frozen=True)
class BackwardResult:
    gradient_digest: str
    per_parameter_gradients: Mapping[str, float]


@dataclass(frozen=True)
class OptimizerState:
    identity: str
    step_count: int
    learning_rate: float
    updated_parameters: Mapping[str, float]

    def to_canonical(self) -> dict:
        return canonical_value({
            "identity": self.identity, "step_count": self.step_count,
            "learning_rate": self.learning_rate,
            "updated_parameters": dict(self.updated_parameters),
        })

    def digest(self) -> str:
        return digest(self.to_canonical())


@dataclass(frozen=True)
class TrainingCertificate:
    application_version: str
    batch_digest: str
    initial_parameter_digest: str
    loss_digest: str
    gradient_digest: str
    updated_parameter_digest: str
    optimizer_digest: str
    certificate_recheck_required: bool

    def to_canonical(self) -> dict:
        return canonical_value({
            "application_version": self.application_version,
            "batch_digest": self.batch_digest,
            "initial_parameter_digest": self.initial_parameter_digest,
            "loss_digest": self.loss_digest,
            "gradient_digest": self.gradient_digest,
            "updated_parameter_digest": self.updated_parameter_digest,
            "optimizer_digest": self.optimizer_digest,
            "certificate_recheck_required": self.certificate_recheck_required,
        })

    def digest(self) -> str:
        return digest(self.to_canonical())


# ---------------------------------------------------------------------------
# Deterministic training driver
# ---------------------------------------------------------------------------


def make_reference_batch(seed: int, ticks: int) -> TrainingBatch:
    # Deterministic synthetic target: shifted, scaled input pattern.
    targets = tuple(
        tuple(float(((seed + t + i) % 5)) * 0.1 for i in range(4))
        for t in range(1, ticks + 1)
    )
    return TrainingBatch(id=f"reference/seed={seed}/ticks={ticks}",
                         seed=seed, ticks=ticks, target_values=targets)


def _forward(config: ApplicationConfig, batch: TrainingBatch) -> ForwardResult:
    session = new_session(config)
    outputs = run(session, ticks=batch.ticks)
    # Decomposed loss.
    integration = next(c for c in config.clocks if c.id == config.recursion.clock)
    window_size = integration.window_size or 1
    n_outputs = len(outputs)
    # Next-prediction loss: MSE between output payload and the target
    # for the last tick of the corresponding window.
    next_pred = 0.0
    for i, out in enumerate(outputs):
        window_end_tick = (i + 1) * window_size
        target = batch.target_values[window_end_tick - 1]
        next_pred += sum((a - b) ** 2 for a, b in zip(out.payload, target))
    next_pred /= max(1, n_outputs)
    # Recursion consistency: penalizes payload magnitude growth.
    recursion_consistency = sum(sum(x * x for x in out.payload)
                                for out in outputs) / max(1, n_outputs)
    # Contraction penalty: |measured_upper_bound - target_margin|**2
    # per certificate; if the substrate did not meet margin, penalize.
    contraction_pen = 0.0
    for out in outputs:
        ub = out.contraction_certificate.get("measured_upper_bound") or 0.0
        margin = out.contraction_certificate.get("requested_margin") or 1.0
        # Penalize being ABOVE margin; below is fine.
        contraction_pen += max(0.0, ub - margin) ** 2
    # Feedback regularization: total |gate|**2 (encourages gates to stay
    # small unless training pushes otherwise).
    feedback_reg = sum(f.gate ** 2 for f in config.feedback)
    # Source contribution regularization: variance of per-source
    # magnitudes across outputs (encourages balanced contributions).
    src_reg = 0.0
    for out in outputs:
        mags = [c["magnitude"] for c in out.source_contributions]
        if mags:
            mean = sum(mags) / len(mags)
            src_reg += sum((m - mean) ** 2 for m in mags) / len(mags)
    loss = LossResult(
        total=next_pred + 0.01 * recursion_consistency +
              1.0 * contraction_pen + 0.1 * feedback_reg + 0.01 * src_reg,
        next_prediction=next_pred,
        recursion_consistency=recursion_consistency,
        contraction_penalty=contraction_pen,
        feedback_regularization=feedback_reg,
        source_contribution_regularization=src_reg,
    )
    per_out = tuple(digest(list(out.payload)) for out in outputs)
    outputs_digest = digest(list(per_out))
    return ForwardResult(outputs_digest=outputs_digest, loss=loss,
                         per_output_payload_digests=per_out)


def _backward_and_step(
    config: ApplicationConfig,
    forward: ForwardResult,
    trainable: Mapping[str, float],
    optimizer_state: OptimizerState,
    epsilon: float = 1e-4,
) -> Tuple[BackwardResult, Mapping[str, float], OptimizerState]:
    """Finite-difference gradient over the trainable parameters
    (currently: each projection's scale). Then apply a single
    SGD step at the configured learning_rate."""
    # Per-projection hard cap from the implementation descriptor.
    caps: Dict[str, float] = {}
    for p in config.projections:
        cls = resolve_projection(p.implementation)
        caps[p.component_id] = cls.descriptor.scale_upper_bound
    grads: Dict[str, float] = {}
    for name, val in trainable.items():
        cap = caps[name]
        # Signed perturbation that respects the projection's bound: if
        # val + epsilon would exceed the cap, use a backward difference.
        step = epsilon if val + epsilon <= cap else -epsilon
        perturbed = _apply_trainable(config, {**trainable, name: val + step})
        f_perturbed = _forward(perturbed, make_reference_batch(
            seed=config.training.seed,
            ticks=config.inference.ticks,
        ))
        grads[name] = (f_perturbed.loss.total - forward.loss.total) / step
    lr = optimizer_state.learning_rate
    # Clamp updates to each projection's descriptor bound [0, cap].
    new_params = {
        name: max(0.0, min(caps[name], val - lr * grads[name]))
        for name, val in trainable.items()
    }
    updated = OptimizerState(
        identity=optimizer_state.identity,
        step_count=optimizer_state.step_count + 1,
        learning_rate=lr,
        updated_parameters=new_params,
    )
    return (BackwardResult(gradient_digest=digest(canonical_value(grads)),
                           per_parameter_gradients=grads),
            new_params, updated)


def _apply_trainable(config: ApplicationConfig,
                     trainable: Mapping[str, float]) -> ApplicationConfig:
    """Apply trainable projection.scale values to the config."""
    projs = []
    for p in config.projections:
        if p.component_id in trainable:
            projs.append(replace(p, scale_upper_bound=trainable[p.component_id]))
        else:
            projs.append(p)
    return replace(config, projections=tuple(projs))


@dataclass
class TrainingSession:
    config: ApplicationConfig
    optimizer: OptimizerState
    history: List[TrainingCertificate] = field(default_factory=list)

    def step(self, batch: TrainingBatch) -> TrainingCertificate:
        trainable = {p.component_id: p.scale_upper_bound for p in self.config.projections}
        initial_digest = digest(canonical_value(trainable))
        forward = _forward(self.config, batch)
        backward, new_params, updated_opt = _backward_and_step(
            self.config, forward, trainable, self.optimizer,
        )
        self.config = _apply_trainable(self.config, new_params)
        self.optimizer = updated_opt
        cert = TrainingCertificate(
            application_version=APPLICATION_VERSION,
            batch_digest=batch.digest(),
            initial_parameter_digest=initial_digest,
            loss_digest=forward.loss.digest(),
            gradient_digest=backward.gradient_digest,
            updated_parameter_digest=digest(canonical_value(new_params)),
            optimizer_digest=updated_opt.digest(),
            # If any projection.scale changed materially, the
            # contraction assumptions may need to be re-checked.
            certificate_recheck_required=any(
                abs(new_params[n] - v) > 1e-6 for n, v in trainable.items()
            ),
        )
        self.history.append(cert)
        return cert


def make_training_session(config: Optional[ApplicationConfig] = None,
                          learning_rate: float = 1e-3) -> TrainingSession:
    cfg = config or replace(reference_config(),
                             runtime_mode="DEVELOPMENT")
    opt = OptimizerState(
        identity="sgd/0.1.0",
        step_count=0,
        learning_rate=learning_rate,
        updated_parameters={p.component_id: p.scale_upper_bound
                            for p in cfg.projections},
    )
    return TrainingSession(config=cfg, optimizer=opt)


__all__ = [
    "TrainingBatch", "LossResult", "ForwardResult", "BackwardResult",
    "OptimizerState", "TrainingCertificate", "TrainingSession",
    "make_reference_batch", "make_training_session",
]
