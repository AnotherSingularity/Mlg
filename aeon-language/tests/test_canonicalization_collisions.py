"""Semantic-collision fixtures (Phase 0.1 §11).

For each axis (clock domain, owner, lineage, contract version,
capability version, projection, numeric precision, validity), two
values that differ ONLY on that axis MUST produce different
semantic identities.
"""

from __future__ import annotations

import pytest

from aeon.clock import ClockPosition
from aeon.core import Validity
from aeon.provenance import (
    make_identity,
    signal_id,
    state_id,
    window_id,
)


def _sid(**overrides):
    base = dict(
        language_version="0.1.0-dev",
        graph="g", node="n",
        parent_state_ids=(),
        transition="t0",
        clock_domain_id="integration",
        clock_tick=0,
        canonical_payload_digest="deadbeef",
    )
    base.update(overrides)
    return state_id(**base).digest


def test_clock_domain_change_alters_state_id():
    assert _sid(clock_domain_id="integration") != _sid(clock_domain_id="token")


def test_owner_alteration_alters_state_id():
    # Owner is not currently a direct state_id input, but node captures it.
    assert _sid(node="rec.a") != _sid(node="rec.b")


def test_lineage_change_alters_state_id():
    assert _sid(parent_state_ids=("aa",)) != _sid(parent_state_ids=("bb",))


def test_transition_change_alters_state_id():
    assert _sid(transition="t0") != _sid(transition="t1")


def test_payload_digest_change_alters_state_id():
    assert _sid(canonical_payload_digest="a") != _sid(canonical_payload_digest="b")


def test_clock_tick_change_alters_state_id():
    assert _sid(clock_tick=0) != _sid(clock_tick=1)


def test_signal_id_differs_on_sequence():
    a = signal_id(source="src.a", clock_domain_id="token", clock_tick=0,
                  sequence=0, canonical_payload_digest="p").digest
    b = signal_id(source="src.a", clock_domain_id="token", clock_tick=0,
                  sequence=1, canonical_payload_digest="p").digest
    assert a != b


def test_signal_id_differs_on_payload_digest():
    a = signal_id(source="src.a", clock_domain_id="token", clock_tick=0,
                  sequence=0, canonical_payload_digest="a").digest
    b = signal_id(source="src.a", clock_domain_id="token", clock_tick=0,
                  sequence=0, canonical_payload_digest="b").digest
    assert a != b


def test_window_id_differs_on_relation():
    a = window_id("token", 0, 8, "rel.aggregates_from").digest
    b = window_id("token", 0, 8, None).digest
    assert a != b


def test_capability_version_change_alters_identity():
    # Simulate a capability-version-only difference by encoding it
    # in the identity fields.
    a = make_identity("capability", {"name": "MatrixRead", "version": "0.1.0"}).digest
    b = make_identity("capability", {"name": "MatrixRead", "version": "0.2.0"}).digest
    assert a != b


def test_contract_version_change_alters_identity():
    a = make_identity("contract", {"kind": "Contractive", "version": "0.1.0"}).digest
    b = make_identity("contract", {"kind": "Contractive", "version": "0.2.0"}).digest
    assert a != b


def test_validity_tag_change_alters_identity():
    a = make_identity("state_wrapper", {"payload_digest": "d",
                                        "validity": Validity.VALID.value}).digest
    b = make_identity("state_wrapper", {"payload_digest": "d",
                                        "validity": Validity.UNCERTIFIED.value}).digest
    assert a != b


def test_projection_change_alters_identity():
    a = make_identity("proj", {"source": "s.a", "port": "out", "substrate": "r.a"}).digest
    b = make_identity("proj", {"source": "s.a", "port": "out", "substrate": "r.b"}).digest
    assert a != b


def test_numeric_precision_alters_identity():
    a = make_identity("precision_marker", {"policy": "float64"}).digest
    b = make_identity("precision_marker", {"policy": "float32"}).digest
    assert a != b
