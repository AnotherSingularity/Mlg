"""aeon_app.feedback — capability-negotiated bounded feedback.

Feedback is disabled by default (gates set to 0). At zero gate,
apply() is guaranteed to be behaviorally neutral: it returns
None and does NOT mutate the destination source's state.

Nonzero gates require:
- destination advertises the required capability;
- projection has a declared scale_upper_bound;
- clock relation declared (integration_to_source);
- state-ownership authorization from the runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple

from aeon.recursion import RecursionState
from aeon.signal import SignalFrame, new_signal_frame
from aeon.provenance import make_identity
from aeon.clock import ClockPosition


class FeedbackRefused(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code


@dataclass(frozen=True)
class FeedbackDecision:
    id: str                             # feedback config id
    origin_recursion: str
    destination_source: str
    projection_id: str
    gate: float
    required_capability: Optional[str]
    clock_relation: str
    scope: str                          # ContractionScope name
    applied: bool
    reason: str


def apply_feedback(
    *,
    feedback_id: str,
    recursion_state: RecursionState,
    projection,                          # ProjectionInstance from projections registry
    destination_offered_capabilities: Tuple[str, ...],
    required_capability: Optional[str],
    gate: float,
    clock_relation: str,
    scope: str,
    integration_clock_position: ClockPosition,
) -> Tuple[FeedbackDecision, Optional[SignalFrame]]:
    """Compute the feedback signal for a destination source.

    Returns ``(decision, signal)`` where ``signal`` is the
    feedback frame to be delivered to the destination source's
    next step, or None if the gate is 0.
    """

    if gate < 0.0:
        raise FeedbackRefused(
            "INVALID_GATE",
            f"feedback {feedback_id!r}: gate must be >= 0, got {gate}",
        )

    if gate == 0.0:
        # Zero-gate neutrality: emit no signal, no capability check
        # required (since nothing is applied).
        return (
            FeedbackDecision(
                id=feedback_id,
                origin_recursion="recursion",
                destination_source=projection.descriptor.output_type,
                projection_id=projection.descriptor.id,
                gate=0.0,
                required_capability=required_capability,
                clock_relation=clock_relation,
                scope=scope,
                applied=False,
                reason="gate=0 (neutral)",
            ),
            None,
        )

    # Nonzero gate: capability negotiation required (mandate §12).
    if required_capability is None:
        raise FeedbackRefused(
            "MISSING_REQUIRED_CAPABILITY",
            f"feedback {feedback_id!r}: nonzero gate requires "
            "a required_capability declaration",
        )
    if required_capability not in destination_offered_capabilities:
        raise FeedbackRefused(
            "CAPABILITY_NOT_OFFERED",
            f"feedback {feedback_id!r}: destination does not offer "
            f"required capability {required_capability!r}",
        )

    # Project the Recursion state through the (feedback) projection.
    # Build a synthetic Signal from the Recursion state's payload
    # so we reuse the projection's uniform apply() contract.
    origin_frame = new_signal_frame(
        source_id="recursion",
        sequence=integration_clock_position.tick,
        clock_position=integration_clock_position,
        payload=list(recursion_state.payload),
        originating_state_id=recursion_state.id,
    )
    manifold_input = projection.apply(origin_frame)
    # Scale by the runtime gate (further bounded above by the
    # projection's scale_upper_bound, which the projection already
    # applied).
    scaled_payload = tuple(x * gate for x in manifold_input.payload)
    signal = new_signal_frame(
        source_id=f"feedback.{feedback_id}",
        sequence=integration_clock_position.tick,
        clock_position=ClockPosition("source", integration_clock_position.tick),
        payload=list(scaled_payload),
        originating_state_id=make_identity("aeon_app.feedback_state", {
            "feedback_id": feedback_id,
            "recursion_state_id": recursion_state.id.digest,
            "gate": gate,
        }),
    )
    return (
        FeedbackDecision(
            id=feedback_id,
            origin_recursion="recursion",
            destination_source=projection.descriptor.output_type,
            projection_id=projection.descriptor.id,
            gate=gate,
            required_capability=required_capability,
            clock_relation=clock_relation,
            scope=scope,
            applied=True,
            reason="applied with capability-negotiated bounded projection",
        ),
        signal,
    )


__all__ = ["FeedbackDecision", "FeedbackRefused", "apply_feedback"]
