"""Unit tests for inspect_node's row builders — the shapes an agent reads.

These exercise _settings_payload / _Filters directly rather than over MCP: the
hidden-collapse path needs a ``visible_when``-gated field, and no node
registered in this repo declares one (the motivating case lives in the
gitignored haybale-visiongraph library).
"""

import pytest

from haywire.barn.builtin.types import BOOL, INT, STRING
from haywire.core.settings import NodeSettings, SettingsRegistry, setting

pytestmark = pytest.mark.unit


class Flags(NodeSettings):
    enable = setting[BOOL](False, label="Enable", description="Master switch", category="Flags")


class Tuning(NodeSettings):
    """A gated bag: ``visible_when`` is same-bag, so the controller lives here."""

    enable = setting[BOOL](False, label="Enable", category="Tuning")
    threshold = setting[INT](
        5,
        min=0,
        max=10,
        label="Threshold",
        category="Tuning",
        metadata={"visible_when": ("enable", True)},
    )
    mode = setting[STRING]("fast", label="Mode", category="Tuning")


def _tools():
    import haybale_graph_editor.farmhands.editor_tools as t

    return t


def _node(**bags):
    """A stand-in node exposing settings bags the way @node wires them."""
    registry = SettingsRegistry()

    def list_setting_bags(self):
        return {name: getattr(self, name) for name in type(self)._settings_bags}

    node = type("FakeNode", (), {"list_setting_bags": list_setting_bags})()
    type(node)._settings_bags = {name: cls for name, cls in bags.items()}
    for name, cls in bags.items():
        setattr(node, name, cls(registry=registry))
    return node


def _flat(payload) -> dict:
    rows = []
    for per_bag in payload.values():
        if isinstance(per_bag, dict):
            for group in per_bag.values():
                rows.extend(group)
        else:
            rows.extend(per_bag)
    return {r["name"]: r for r in rows}


def test_payload_nests_by_bag_then_category():
    t = _tools()
    node = _node(flags=Flags, tuning=Tuning)
    payload = t._settings_payload(node, ["flags", "tuning"], "info", t._Filters([], [], [], []))
    assert set(payload) == {"flags", "tuning"}
    assert set(payload["flags"]) == {"Flags"}
    assert set(payload["tuning"]) == {"Tuning"}


def test_same_category_in_two_bags_does_not_merge():
    """Bag is the outer key precisely so a shared category label cannot collide."""
    t = _tools()

    class A(NodeSettings):
        one = setting[INT](1, category="Shared")

    class B(NodeSettings):
        two = setting[INT](2, category="Shared")

    node = _node(a=A, b=B)
    payload = t._settings_payload(node, ["a", "b"], "info", t._Filters([], [], [], []))
    assert [r["name"] for r in payload["a"]["Shared"]] == ["one"]
    assert [r["name"] for r in payload["b"]["Shared"]] == ["two"]


def test_hidden_field_collapses_to_existence_only():
    """A field the user cannot see collapses — but is still reported as present."""
    t = _tools()
    node = _node(tuning=Tuning)
    assert node.tuning.effective_ui_state("threshold").name == "HIDDEN"

    rows = _flat(t._settings_payload(node, ["tuning"], "all", t._Filters([], [], [], [])))
    assert rows["threshold"] == {
        "name": "threshold",
        "accessor": "tuning",
        "ui_state": "hidden",
    }
    # A visible sibling in the same bag is unaffected.
    assert rows["mode"]["value"] == "fast"


def test_by_name_expands_a_hidden_field():
    """Naming it IS the explicit request, so the full row comes back."""
    t = _tools()
    node = _node(tuning=Tuning)
    rows = _flat(t._settings_payload(node, ["tuning"], "all", t._Filters(["threshold"], [], [], [])))
    row = rows["threshold"]
    assert row["value"] == 5
    assert row["min"] == 0
    assert row["max"] == 10
    # Still flagged: the agent must know the user cannot see this field.
    assert row["ui_state"] == "hidden"


def test_opening_the_gate_makes_the_field_live():
    """The collapse is state, not structure — which is why we collapse, not omit.

    An agent told "enable depth and set the threshold" must be able to discover
    the field after flipping the flag; omitting hidden rows would have made the
    node look incapable.
    """
    t = _tools()
    node = _node(tuning=Tuning)
    node.tuning.enable = True

    rows = _flat(t._settings_payload(node, ["tuning"], "all", t._Filters([], [], [], [])))
    assert rows["threshold"]["value"] == 5
    assert rows["threshold"]["max"] == 10
    assert "ui_state" not in rows["threshold"]


def test_filters_and_across_axes():
    t = _tools()
    node = _node(flags=Flags, tuning=Tuning)
    payload = t._settings_payload(
        node, ["flags", "tuning"], "info", t._Filters([], ["tuning"], ["Tuning"], [])
    )
    assert set(payload) == {"tuning"}
    assert set(_flat(payload)) == {"enable", "threshold", "mode"}

    # A bag/category pair that cannot co-occur yields nothing.
    empty = t._settings_payload(node, ["flags", "tuning"], "info", t._Filters([], ["flags"], ["Tuning"], []))
    assert empty == {}


def test_unmatched_is_keyed_per_axis_and_ignores_and_exclusion():
    """unmatched means 'no such thing here', not 'excluded by a sibling axis'."""
    t = _tools()
    node = _node(flags=Flags, tuning=Tuning)

    filters = t._Filters(["nope"], ["tuning"], ["Tuning"], [])
    t._settings_payload(node, ["flags", "tuning"], "info", filters)
    assert filters.unmatched() == {"by_name": ["nope"]}

    # 'enable' exists but is excluded by by_bag — that is not a miss.
    ok = t._Filters(["enable"], ["tuning"], [], [])
    t._settings_payload(node, ["flags", "tuning"], "info", ok)
    assert ok.unmatched() == {}


def test_constraints_resolve_callable_options():
    """A live callable in widget_config is resolved like SelectWidget.build() does."""
    t = _tools()
    resolved = t._constraints({"properties": {"options": lambda: ["a", "b"]}})
    assert resolved["options"] == ["a", "b"]


def test_constraints_reports_a_failing_options_probe():
    t = _tools()

    def boom():
        raise RuntimeError("no hardware")

    out = t._constraints({"properties": {"options": boom}})
    assert "no hardware" in out["options_unavailable"]
    assert "options" not in out


def test_constraints_drops_unserializable_and_reserved_keys():
    t = _tools()
    out = t._constraints({"properties": {"min": 1, "value": 99, "blob": object()}})
    assert out == {"min": 1}
