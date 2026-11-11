"""``merge_ports``: saved ports follow the code where only the code changed, and conflict where both did."""

from __future__ import annotations

import copy
from typing import Any

from haywire.core.node.declaration_merge import merge_ports

_FLOAT = {"registry_key": "float"}
_INT = {"registry_key": "int"}


def _port(port_id: str, recipe: dict | None = None, **kwargs: Any) -> dict[str, Any]:
    """A declaration entry, or a saved port without a value: its floor plus *kwargs*."""
    return {"recipe": recipe or _FLOAT, "kwargs": {"id": port_id, "port_type": "inlet", **kwargs}}


def _default_value(entry: dict[str, Any]) -> Any:
    """What a port built from *entry* saves while nobody set it."""
    return {"value": entry["kwargs"].get("default", 0.0)}


def _merge(base: dict, saved: dict, code: dict, code_full: dict | None = None):
    return merge_ports(base, saved, code, code if code_full is None else code_full, _default_value)


def test_a_port_the_code_left_alone_is_kept_as_saved():
    base = {"a": _port("a", label="A")}
    saved = {"a": {**_port("a"), "field_data": {"value": 3.0}}}

    merged = _merge(base, saved, copy.deepcopy(base))

    assert merged is not None
    assert merged.ports == saved
    assert merged.changes == []


def test_a_field_only_the_code_changed_follows_the_code():
    base = {"a": _port("a", label="Old")}
    saved = {"a": {**_port("a"), "field_data": {"value": 3.0}}}

    merged = _merge(base, saved, {"a": _port("a", label="New")})

    assert merged is not None
    assert merged.ports == saved  # nothing saved for the label: the port takes the code's
    assert merged.changes == ["ports/a/label"]


def test_a_field_changed_on_both_sides_is_a_conflict():
    base = {"a": _port("a", label="Old")}
    saved = {"a": _port("a", label="Mine")}

    assert _merge(base, saved, {"a": _port("a", label="New")}) is None


def test_a_field_both_sides_changed_to_the_same_value_follows_the_code():
    base = {"a": _port("a", label="Old")}
    saved = {"a": _port("a", label="New")}

    merged = _merge(base, saved, {"a": _port("a", label="New")})

    assert merged is not None
    assert "label" not in merged.ports["a"]["kwargs"]


def test_another_field_of_the_same_port_keeps_what_the_file_changed():
    base = {"a": _port("a", label="Old")}
    saved = {"a": _port("a", single_link=True)}

    merged = _merge(base, saved, {"a": _port("a", label="New")})

    assert merged is not None
    assert merged.ports["a"]["kwargs"]["single_link"] is True


def test_a_display_order_the_user_set_wins_over_a_changed_one():
    base = {"a": _port("a", order=1)}
    saved = {"a": _port("a", order=5, hidden=True)}

    merged = _merge(base, saved, {"a": _port("a", order=2, hidden=False)}, {"a": _port("a", order=2)})

    assert merged is not None
    assert merged.ports["a"]["kwargs"]["order"] == 5
    assert merged.ports["a"]["kwargs"]["hidden"] is True


def test_a_floor_field_saved_as_declared_follows_the_code():
    base = {"a": _port("a")}
    saved = {"a": _port("a")}
    code = {"a": {"recipe": _FLOAT, "kwargs": {"id": "a", "port_type": "outlet"}}}

    merged = _merge(base, saved, code)

    assert merged is not None
    assert "port_type" not in merged.ports["a"]["kwargs"]
    assert merged.changes == ["ports/a/port_type"]


def test_a_port_new_in_the_code_is_added_after_the_port_it_follows():
    base = {"a": _port("a"), "c": _port("c")}
    saved = {"a": _port("a"), "c": _port("c"), "grown": _port("grown")}
    code = {"a": _port("a"), "b": _port("b", label="B"), "c": _port("c")}

    merged = _merge(base, saved, code)

    assert merged is not None
    assert list(merged.ports) == ["a", "b", "c", "grown"]
    assert merged.ports["b"] == code["b"]
    assert merged.changes == ["ports/b (added)"]


def test_a_port_the_code_removed_is_left_out():
    base = {"a": _port("a"), "gone": _port("gone")}
    saved = {"a": _port("a"), "gone": {**_port("gone"), "field_data": {"value": 2.0}}}

    merged = _merge(base, saved, {"a": _port("a")})

    assert merged is not None
    assert list(merged.ports) == ["a"]
    assert merged.changes == ["ports/gone (removed)"]


def test_a_port_the_node_retyped_and_the_code_removed_is_a_conflict():
    base = {"gone": _port("gone")}
    saved = {"gone": _port("gone", _INT)}

    assert _merge(base, saved, {}) is None


def test_a_port_the_node_retyped_and_the_code_changed_is_a_conflict():
    base = {"a": _port("a", label="Old")}
    saved = {"a": _port("a", _INT, label="Old")}

    assert _merge(base, saved, {"a": _port("a", label="New")}) is None


def test_a_port_the_node_retyped_stays_when_the_code_left_it_alone():
    base = {"a": _port("a"), "b": _port("b", label="Old")}
    saved = {"a": _port("a", _INT), "b": _port("b")}

    merged = _merge(base, saved, {"a": _port("a"), "b": _port("b", label="New")})

    assert merged is not None
    assert merged.ports["a"] == saved["a"]


def test_a_port_the_node_grew_itself_that_the_code_now_declares_is_a_conflict():
    saved = {"a": _port("a"), "extra": _port("extra")}

    assert _merge({"a": _port("a")}, saved, {"a": _port("a"), "extra": _port("extra")}) is None


def test_a_port_the_node_removed_stays_away_while_the_code_leaves_it_alone():
    base = {"a": _port("a", label="Old"), "dropped": _port("dropped")}
    saved = {"a": _port("a")}

    merged = _merge(base, saved, {"a": _port("a", label="New"), "dropped": _port("dropped")})

    assert merged is not None
    assert list(merged.ports) == ["a"]


def test_a_port_the_node_removed_and_the_code_changed_is_a_conflict():
    base = {"a": _port("a"), "dropped": _port("dropped", label="Old")}
    saved = {"a": _port("a")}

    assert _merge(base, saved, {"a": _port("a"), "dropped": _port("dropped", label="New")}) is None


def test_an_untouched_port_takes_the_type_the_code_gave_it():
    base = {"a": _port("a")}
    saved = {"a": {**_port("a"), "field_data": {"value": 0.0}}}
    code = {"a": _port("a", _INT, label="Count")}

    merged = _merge(base, saved, code)

    assert merged is not None
    assert merged.ports["a"] == code["a"]
    assert merged.changes == ["ports/a/recipe"]


def test_a_port_with_a_set_value_whose_type_the_code_changed_is_a_conflict():
    base = {"a": _port("a")}
    saved = {"a": {**_port("a"), "field_data": {"value": 7.0}}}

    assert _merge(base, saved, {"a": _port("a", _INT)}) is None


def test_a_value_nobody_set_follows_a_changed_default():
    base = {"a": _port("a", default=1.0)}
    saved = {"a": {**_port("a"), "field_data": {"value": 1.0}}}

    merged = _merge(base, saved, {"a": _port("a", default=2.0)})

    assert merged is not None
    assert "field_data" not in merged.ports["a"]


def test_a_set_value_stays_when_the_default_changes():
    base = {"a": _port("a", default=1.0)}
    saved = {"a": {**_port("a"), "field_data": {"value": 9.0}}}

    merged = _merge(base, saved, {"a": _port("a", default=2.0)})

    assert merged is not None
    assert merged.ports["a"]["field_data"] == {"value": 9.0}


def test_a_value_counts_as_set_when_the_earlier_default_cannot_be_built():
    base = {"a": _port("a", default=1.0)}
    saved = {"a": {**_port("a"), "field_data": {"value": 1.0}}}

    def broken(entry: dict[str, Any]) -> Any:
        raise ValueError("type gone")

    merged = merge_ports(base, saved, {"a": _port("a", default=2.0)}, {"a": _port("a", default=2.0)}, broken)

    assert merged is not None
    assert merged.ports["a"]["field_data"] == {"value": 1.0}


def test_the_saved_ports_are_not_changed():
    base = {"a": _port("a", label="Old"), "gone": _port("gone")}
    saved = {"a": _port("a", label="New"), "gone": _port("gone")}
    before = copy.deepcopy(saved)

    _merge(base, saved, {"a": _port("a", label="New")})

    assert saved == before
