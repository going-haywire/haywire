"""The pin menu's value verbs, against a real bag behind a real promoted port.

Reset and "Set to none" were Properties-row-only. That was a gap the moment a
promoted pin could carry its own editable widget: a value typed on the node card
could only be undone somewhere else entirely — and on an optional field whose
declared default is absence, it could not be undone at all, because Reset greys
while the field carries no local opinion.

``poll`` is the load-bearing half. A row that polls true without a resolvable
setting renders a verb with nothing behind it; one that polls false where it
should act is the trap this fixes.

The unit-level half (no port, unpromoted port) lives in
``tests/ui/graph_canvas/test_pin_menu_panels.py``; these need the library-system
graph fixture, which is scoped to ``tests/core``.
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from haybale_graph_editor.panels.graph.menu.port.port import (
    ClearSettingMenuPanel,
    ResetSettingMenuPanel,
)
from haywire.core.graph.base import BaseGraph
from haywire.core.node.promotion import promote_setting
from haywire.core.session.context import SessionContext
from haywire.core.types.enums import PortType
from haywire.ui.widget.factory import _widget_model_for

SETTINGS_NODE = "haybale-testing:node:SettingsNode"


def _ctx(port: Any, node_wrapper: Any) -> SessionContext:
    """A ctx whose EditState carries both the pin and its node wrapper.

    The value verbs resolve port -> (bag, descriptor) through the node, so both
    halves must be present; the identity rows on this surface never need the
    node, which is why the unit-level helper leaves it None.
    """
    edit_stub = SimpleNamespace(active_port=port, active_node=node_wrapper)
    fake_data = MagicMock()
    fake_data.__getitem__.return_value = edit_stub
    ctx = SessionContext(session_id="t", app=MagicMock())
    ctx.data = fake_data
    ctx.session = MagicMock()
    return ctx


@pytest.fixture
def promoted(graph_with_library_system: BaseGraph):
    """Promote one ``example.<field>`` to an outlet; yield (ctx, node, port)."""

    def _make(field: str) -> tuple[SessionContext, Any, Any]:
        wrapper = graph_with_library_system.create_node_wrapper(SETTINGS_NODE, position=(0, 0))
        assert wrapper is not None
        node: Any = wrapper.node
        promote_setting(node, "example", field, direction=PortType.OUTLET)
        port = node.ports[type(node.example).__dict__[field].storage_key]
        return _ctx(port, wrapper), node, port

    return _make


@pytest.mark.integration
class TestResetRow:
    def test_greys_while_the_field_is_clean(self, promoted):
        ctx, _node, _port = promoted("example_float")
        assert ResetSettingMenuPanel.poll(ctx) is False

    def test_enables_once_the_field_carries_an_opinion(self, promoted):
        ctx, _node, port = promoted("example_float")
        _widget_model_for(port).set_value(0.25)  # the card edit
        assert ResetSettingMenuPanel.poll(ctx) is True

    def test_the_verb_restores_the_declared_default(self, promoted):
        ctx, node, port = promoted("optional_with_default")
        _widget_model_for(port).set_value(7)
        assert node.example.optional_with_default == 7

        bag, descriptor = _resolve(node, port)
        bag._reset(descriptor._attr_name)
        assert node.example.optional_with_default == -1


@pytest.mark.integration
class TestSetToNoneRow:
    def test_absent_from_a_non_optional_field(self, promoted):
        ctx, _node, _port = promoted("example_float")
        assert ClearSettingMenuPanel.poll(ctx) is False

    def test_greys_while_the_value_is_already_absent(self, promoted):
        ctx, _node, _port = promoted("optional_int")
        assert ClearSettingMenuPanel.poll(ctx) is False

    def test_enables_on_an_optional_field_holding_a_value(self, promoted):
        # The exact reported sequence: promote to outlet, show the pin widget,
        # enter a value. Previously this left NO enabled route back to absence,
        # because the field's default is itself absence.
        ctx, _node, port = promoted("optional_int")
        _widget_model_for(port).set_value(42)
        assert ClearSettingMenuPanel.poll(ctx) is True

    def test_the_two_verbs_differ_where_the_default_is_a_value(self, promoted):
        # optional_with_default rests at -1: Reset goes back to -1, Set to none
        # goes to absence. Both enabled, landing in different places.
        ctx, node, port = promoted("optional_with_default")
        _widget_model_for(port).set_value(7)
        assert ResetSettingMenuPanel.poll(ctx) is True
        assert ClearSettingMenuPanel.poll(ctx) is True

        bag, descriptor = _resolve(node, port)
        setattr(bag, descriptor._attr_name, None)
        assert node.example.optional_with_default is None
        assert ClearSettingMenuPanel.poll(ctx) is False  # nothing left to clear
        assert ResetSettingMenuPanel.poll(ctx) is True  # ...but still resettable


def _resolve(node: Any, port: Any):
    """The (bag, descriptor) behind a promoted port — what the menu verbs act on."""
    from haywire.core.node.promotion import _resolve_promoted

    return _resolve_promoted(node, port.id)
