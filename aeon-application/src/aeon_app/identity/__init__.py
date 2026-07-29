"""aeon_app.identity — application-scoped identity primitives.

Wraps `aeon.identity` so the application's identity kinds are
distinct from language kinds and traceable to the application
version.
"""

from __future__ import annotations

from typing import Any, Mapping

from aeon.identity import Identity, make_identity
from aeon.serialization import digest

from .. import APPLICATION_VERSION


def app_state_id(*, component_id: str, parent_ids: tuple[str, ...],
                 clock_domain_id: str, clock_tick: int,
                 payload_digest: str) -> Identity:
    return make_identity("aeon_app.state", {
        "application_version": APPLICATION_VERSION,
        "component_id": component_id,
        "parent_ids": sorted(parent_ids),
        "clock_domain_id": clock_domain_id,
        "clock_tick": clock_tick,
        "payload_digest": payload_digest,
    })


def app_transition_id(*, component_id: str, clock_domain_id: str,
                      clock_tick: int, invocation: int) -> Identity:
    return make_identity("aeon_app.transition", {
        "application_version": APPLICATION_VERSION,
        "component_id": component_id,
        "clock_domain_id": clock_domain_id,
        "clock_tick": clock_tick,
        "invocation": invocation,
    })


def app_event_id(*, kind: str, sequence: int, parent_event_ids: tuple[str, ...],
                 body_digest: str) -> Identity:
    return make_identity("aeon_app.event", {
        "application_version": APPLICATION_VERSION,
        "kind": kind,
        "sequence": sequence,
        "parent_event_ids": sorted(parent_event_ids),
        "body_digest": body_digest,
    })


def app_graph_id(*, graph_name: str, config_digest: str) -> Identity:
    return make_identity("aeon_app.graph", {
        "application_version": APPLICATION_VERSION,
        "graph_name": graph_name,
        "config_digest": config_digest,
    })


def canonical_digest(value: Any) -> str:
    return digest(value)


__all__ = [
    "Identity",
    "app_state_id",
    "app_transition_id",
    "app_event_id",
    "app_graph_id",
    "canonical_digest",
]
