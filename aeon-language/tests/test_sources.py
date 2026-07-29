"""Reference source conformance."""

from __future__ import annotations

import pytest

from aeon.capability import (
    CapabilityRef,
    CapabilityTier,
    VersionConstraint,
    negotiate,
)
from aeon.clock import ClockPosition
from aeon.core import SemVer
from aeon.port import Ready, ReadRequest, ReadUnavailable
from aeon.provenance import make_identity
from aeon.signal import new_signal_frame
from aeon.sources.dummy import DummyRichSource, DummyVectorSource


def _frame(payload):
    origin = make_identity("state", {"src": "x"})
    return new_signal_frame(
        source_id="drive", sequence=0,
        clock_position=ClockPosition("token", 0),
        payload=list(payload), originating_state_id=origin,
    )


def test_dummy_vector_source_offers_all_required():
    src = DummyVectorSource("v")
    desc = src.describe()
    offered = {c.name for c in desc.offered_capabilities}
    assert {"VectorRead", "VectorDrive", "PerTokenStep"} <= offered


def test_dummy_vector_source_step_deterministic():
    src = DummyVectorSource("v", 4)
    s0 = src.initialize({}, 42)
    s1 = src.step(_frame([1.0, 2.0, 3.0, 4.0]), s0, ClockPosition("token", 1)).next_state
    s2 = src.step(_frame([1.0, 2.0, 3.0, 4.0]), s0, ClockPosition("token", 1)).next_state
    assert s1.payload == s2.payload
    assert s1.id == s2.id


def test_dummy_vector_source_step_input_dim_mismatch_raises():
    src = DummyVectorSource("v", 4)
    s0 = src.initialize({}, 0)
    with pytest.raises(ValueError):
        src.step(_frame([1.0, 2.0]), s0, ClockPosition("token", 1))


def test_dummy_vector_source_snapshot_restore_round_trip():
    src = DummyVectorSource("v", 4)
    s = src.initialize({}, 3)
    s = src.step(_frame([1.0, 1.0, 1.0, 1.0]), s, ClockPosition("token", 1)).next_state
    snap = src.snapshot(s)
    restored = src.restore(snap)
    assert restored.payload == s.payload
    assert restored.dimension == s.dimension


def test_dummy_vector_source_unknown_read_returns_unavailable():
    src = DummyVectorSource("v", 4)
    s = src.initialize({}, 0)
    result = src.read(s, ReadRequest(kind="matrix"))
    assert isinstance(result, ReadUnavailable)


def test_dummy_rich_source_offers_optional_capabilities():
    src = DummyRichSource("r", 4)
    desc = src.describe()
    offered = {c.name for c in desc.offered_capabilities}
    assert {"MatrixRead", "LayerRead", "DecayControl"} <= offered


def test_dummy_rich_source_matrix_read_ready():
    src = DummyRichSource("r", 4)
    s = src.initialize({}, 1)
    r = src.read(s, ReadRequest(kind="matrix"))
    assert isinstance(r, Ready)
    assert len(r.value) == 4 and len(r.value[0]) == 4


def test_dummy_rich_source_layer_out_of_range_unavailable():
    src = DummyRichSource("r", 4, layers=3)
    s = src.initialize({}, 1)
    r = src.read(s, ReadRequest(kind="layer", params={"index": 99}))
    assert isinstance(r, ReadUnavailable)


def test_rich_source_negotiates_all_offered():
    src = DummyRichSource("r", 4)
    desc = src.describe()
    result = negotiate(
        offered=list(desc.offered_capabilities),
        required=[VersionConstraint(c.name, c.version) for c in desc.required_capabilities],
        optional=[
            VersionConstraint("MatrixRead", SemVer(0, 1, 0)),
            VersionConstraint("LayerRead", SemVer(0, 1, 0)),
            VersionConstraint("DecayControl", SemVer(0, 1, 0)),
        ],
    )
    assert result.compatible
    assert {"MatrixRead", "LayerRead", "DecayControl"} <= set(result.optional_paths)
