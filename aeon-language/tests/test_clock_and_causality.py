"""Clock domain, position, window semantics."""

from __future__ import annotations

import pytest

from aeon.clock import (
    ClockDomain,
    ClockKind,
    ClockPosition,
    ClockRelation,
    ClockRelationKind,
    Window,
)


def test_position_monotonic_within_domain():
    tok = ClockDomain("token", ClockKind.TOKEN)
    p0 = tok.position(0)
    p1 = tok.position(1)
    assert p0 < p1


def test_position_cross_domain_compare_raises():
    a = ClockPosition("token", 5)
    b = ClockPosition("integration", 5)
    with pytest.raises(ValueError):
        _ = a < b


def test_window_contains():
    p = ClockPosition("token", 3)
    w = Window("w1", "token", 0, 5)
    assert w.contains(p)
    assert not w.contains(ClockPosition("token", 5))
    assert not w.contains(ClockPosition("integration", 3))


def test_window_bounds_validation():
    with pytest.raises(ValueError):
        Window("w1", "token", 5, 5)
    with pytest.raises(ValueError):
        Window("w1", "token", -1, 5)


def test_clock_relation_aggregates_requires_window_size():
    with pytest.raises(ValueError):
        ClockRelation("a", "b", ClockRelationKind.AGGREGATES_FROM)


def test_clock_relation_distinct_domains():
    with pytest.raises(ValueError):
        ClockRelation("a", "a", ClockRelationKind.INDEPENDENT)


def test_position_rejects_negative_tick():
    with pytest.raises(ValueError):
        ClockPosition("token", -1)
