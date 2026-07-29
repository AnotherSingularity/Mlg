"""State identity, ownership, lineage."""

from __future__ import annotations

import pytest

from aeon.clock import ClockDomain, ClockKind
from aeon.core import Validity
from aeon.state import (
    OwnershipError,
    OwnershipTable,
    Shape,
    new_state,
    payload_digest,
)


def _pos():
    return ClockDomain("token", ClockKind.TOKEN).position(0)


def test_state_has_stable_identity():
    s1 = new_state(language_version="0.1.0-dev", graph="g", node="n",
                   owner="src.a", value={"v": [1, 2, 3]},
                   shape=Shape((3,)), clock_position=_pos(), transition="t0")
    s2 = new_state(language_version="0.1.0-dev", graph="g", node="n",
                   owner="src.a", value={"v": [1, 2, 3]},
                   shape=Shape((3,)), clock_position=_pos(), transition="t0")
    assert s1.id == s2.id


def test_equal_payload_distinct_lineage_distinct_state_id():
    s1 = new_state(language_version="0.1.0-dev", graph="g", node="n",
                   owner="src.a", value={"v": [1, 2, 3]},
                   shape=Shape((3,)), clock_position=_pos(), transition="t0")
    s2 = new_state(language_version="0.1.0-dev", graph="g", node="n",
                   owner="src.a", value={"v": [1, 2, 3]},
                   shape=Shape((3,)), clock_position=_pos(), transition="t1")
    assert s1.id != s2.id
    assert payload_digest(s1.value) == payload_digest(s2.value)


def test_ownership_double_consume_fails():
    s = new_state(language_version="0.1.0-dev", graph="g", node="n",
                  owner="src.a", value={"v": []},
                  shape=Shape((0,)), clock_position=_pos(), transition="t0")
    tab = OwnershipTable()
    tab.introduce(s.id)
    tab.consume(s.id)
    with pytest.raises(OwnershipError):
        tab.consume(s.id)


def test_ownership_borrow_ok_after_consume_as_historical():
    s = new_state(language_version="0.1.0-dev", graph="g", node="n",
                  owner="src.a", value={"v": []},
                  shape=Shape((0,)), clock_position=_pos(), transition="t0")
    tab = OwnershipTable()
    tab.introduce(s.id)
    tab.consume(s.id)
    # Historical read is permitted (auditable).
    tab.borrow(s.id)


def test_ownership_unknown_state_fails():
    s = new_state(language_version="0.1.0-dev", graph="g", node="n",
                  owner="src.a", value={"v": []},
                  shape=Shape((0,)), clock_position=_pos(), transition="t0")
    tab = OwnershipTable()
    with pytest.raises(OwnershipError):
        tab.consume(s.id)


def test_state_validity_default_uncertified():
    s = new_state(language_version="0.1.0-dev", graph="g", node="n",
                  owner="src.a", value={},
                  shape=Shape(()), clock_position=_pos(), transition="t0")
    assert s.validity is Validity.UNCERTIFIED
