"""aeon_app.projections — first-class typed projections.

Each projection has: input/output type, input/output shape,
numerical precision, clock relation, parameter state (if any),
contract, boundedness declaration, and provenance behavior.

Projections carry INDEPENDENT identity and their own snapshots
(mandate §11): projection parameters are not hidden inside
source or Recursion code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Tuple

from aeon.provenance import make_identity
from aeon.recursion import ManifoldInput
from aeon.serialization import canonical_bytes, canonical_value, digest
from aeon.signal import SignalFrame


PROJECTION_SCHEMA_VERSION = "0.1.0"


@dataclass(frozen=True)
class ProjectionDescriptor:
    id: str
    input_type: str
    output_type: str
    input_shape: Tuple[int, ...]
    output_shape: Tuple[int, ...]
    numerical_precision: str
    clock_relation: str
    scale_upper_bound: float
    contract: str
    boundedness: str = "L_inf <= scale_upper_bound * input_L_inf"

    def to_canonical(self) -> dict:
        return canonical_value({
            "id": self.id,
            "input_type": self.input_type,
            "output_type": self.output_type,
            "input_shape": list(self.input_shape),
            "output_shape": list(self.output_shape),
            "numerical_precision": self.numerical_precision,
            "clock_relation": self.clock_relation,
            "scale_upper_bound": self.scale_upper_bound,
            "contract": self.contract,
            "boundedness": self.boundedness,
        })


@dataclass(frozen=True)
class ProjectionParameters:
    scale: float

    def to_canonical(self) -> dict:
        return canonical_value({"scale": self.scale})

    def digest(self) -> str:
        return digest(self.to_canonical())


class _LinearScaledProjection:
    """Shared logic for scale-only projections."""

    descriptor: ProjectionDescriptor
    params: ProjectionParameters

    def __init__(self, params: ProjectionParameters | None = None) -> None:
        self.params = params or ProjectionParameters(scale=self.descriptor.scale_upper_bound)
        if not (0.0 <= self.params.scale <= self.descriptor.scale_upper_bound):
            raise ValueError(
                f"projection {self.descriptor.id!r}: scale {self.params.scale} "
                f"outside [0, {self.descriptor.scale_upper_bound}]"
            )

    def apply(self, frame: SignalFrame[Any]) -> ManifoldInput:
        payload = tuple(float(x) for x in frame.payload)
        if len(payload) != self.descriptor.input_shape[0]:
            raise ValueError(
                f"projection {self.descriptor.id!r}: input dim "
                f"{len(payload)} != {self.descriptor.input_shape[0]}"
            )
        scaled = tuple(x * self.params.scale for x in payload)
        ident = make_identity("aeon_app.manifold_input", {
            "projection_id": self.descriptor.id,
            "source_id": frame.source_id,
            "origin_frame_id": frame.id.digest,
            "payload": list(scaled),
        })
        return ManifoldInput(
            id=ident,
            projection_id=self.descriptor.id,
            source_id=frame.source_id,
            origin_frame_id=frame.id.digest,
            payload=scaled,
        )


class AttentionToRecursion(_LinearScaledProjection):
    descriptor = ProjectionDescriptor(
        id="attention_to_recursion",
        input_type="Signal<Vec,source>",
        output_type="ManifoldInput",
        input_shape=(4,), output_shape=(4,),
        numerical_precision="float64",
        clock_relation="source_to_integration",
        scale_upper_bound=1.0,
        contract="Bounded",
    )


class RecurrentToRecursion(_LinearScaledProjection):
    descriptor = ProjectionDescriptor(
        id="recurrent_to_recursion",
        input_type="Signal<Vec,source>",
        output_type="ManifoldInput",
        input_shape=(4,), output_shape=(4,),
        numerical_precision="float64",
        clock_relation="source_to_integration",
        scale_upper_bound=1.0,
        contract="Bounded",
    )


class RecursionToAttentionFeedback(_LinearScaledProjection):
    descriptor = ProjectionDescriptor(
        id="feedback_to_attention",
        input_type="Signal<Vec,integration>",
        output_type="Signal<Vec,source>",
        input_shape=(4,), output_shape=(4,),
        numerical_precision="float64",
        clock_relation="integration_to_source",
        scale_upper_bound=0.5,
        contract="Bounded",
    )


class RecursionToRecurrentFeedback(_LinearScaledProjection):
    descriptor = ProjectionDescriptor(
        id="feedback_to_recurrent",
        input_type="Signal<Vec,integration>",
        output_type="Signal<Vec,source>",
        input_shape=(4,), output_shape=(4,),
        numerical_precision="float64",
        clock_relation="integration_to_source",
        scale_upper_bound=0.5,
        contract="Bounded",
    )


REGISTRY: Mapping[str, Any] = {
    "aeon_app.projections.attention_to_recursion:AttentionToRecursion": AttentionToRecursion,
    "aeon_app.projections.recurrent_to_recursion:RecurrentToRecursion": RecurrentToRecursion,
    "aeon_app.projections.feedback:RecursionToAttentionFeedback": RecursionToAttentionFeedback,
    "aeon_app.projections.feedback:RecursionToRecurrentFeedback": RecursionToRecurrentFeedback,
}


def resolve_projection(implementation: str) -> Any:
    cls = REGISTRY.get(implementation)
    if cls is None:
        raise KeyError(f"unknown projection implementation {implementation!r}")
    return cls


__all__ = [
    "PROJECTION_SCHEMA_VERSION",
    "ProjectionDescriptor",
    "ProjectionParameters",
    "AttentionToRecursion",
    "RecurrentToRecursion",
    "RecursionToAttentionFeedback",
    "RecursionToRecurrentFeedback",
    "REGISTRY",
    "resolve_projection",
]
