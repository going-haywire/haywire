"""A settings form drawn with a write gate is read-only while the gate refuses.

The gate is asked again at every write, so a row drawn while it allowed still
refuses once it stops allowing.
"""

from typing import Any, cast
from unittest.mock import patch

import pytest
from nicegui import Client, ui

from haywire.barn.builtin.types import FLOAT, INT, OPTIONAL
from haywire.core.settings import Settings, setting
from haywire.ui.panel import render_utils
from haywire.ui.panel.render_utils import render_settings

from tests.ui.panel.render_ctx import make_render_ctx

pytestmark = pytest.mark.integration


def _noop_page() -> None:  # registration target for a headless Client
    pass


class _GateSettings(Settings):
    gain = setting[FLOAT](1.0, label="Gain")
    count = setting[OPTIONAL[INT]](3, label="Count")


class _StubGate:
    def __init__(self, allows: bool) -> None:
        self.allowed = allows
        self.written_calls = 0

    def allows(self) -> bool:
        return self.allowed

    def written(self) -> None:
        self.written_calls += 1


def _walk(element):
    yield element
    for child in element.default_slot.children:
        yield from _walk(child)


def _walk_skip_menus(element):
    yield element
    if type(element).__name__ == "ContextMenu":
        return
    for child in element.default_slot.children:
        yield from _walk_skip_menus(child)


def _find_field_row(root, attr_name: str):
    for el in _walk(root):
        if getattr(el, "_props", {}).get("data-field") == attr_name:
            return el
    return None


def _widget_is_disabled(row) -> bool:
    for el in _walk_skip_menus(row):
        if getattr(el, "_props", {}).get("disable") is True:
            return True
        style = getattr(el, "_style", {}) or {}
        if style.get("opacity") == "0.5" and style.get("pointer-events") == "none":
            return True
    return False


def _menu_item_text(item) -> str:
    for child in item.default_slot.children:
        text = getattr(child, "text", None)
        if text is not None:
            return text
    return ""


def _menu_items(row) -> dict[str, Any]:
    return {_menu_item_text(el): el for el in _walk(row) if type(el).__name__ == "MenuItem"}


def _render(bag, gate) -> tuple[Any, dict[str, Any]]:
    """Render *bag* with *gate*; return the anchor and each row's ``on_edit``, by field name."""
    on_edits: dict[str, Any] = {}
    real = render_utils._resolve_widget_instance

    def _capture(defn, on_edit, **kwargs):
        on_edits[defn._attr_name] = on_edit
        return real(defn, on_edit, **kwargs)

    client = Client(cast(Any, _noop_page), request=None)
    with client, patch.object(render_utils, "_resolve_widget_instance", _capture):
        anchor = ui.column()
        with anchor:
            render_settings(make_render_ctx(), bag, gate=gate)
    return anchor, on_edits


def test_rows_render_disabled_when_refused():
    bag = _GateSettings()
    anchor, _ = _render(bag, _StubGate(allows=False))

    row = _find_field_row(anchor, "gain")
    assert row is not None
    assert _widget_is_disabled(row)


def test_rows_render_enabled_when_allowed():
    bag = _GateSettings()
    anchor, _ = _render(bag, _StubGate(allows=True))

    assert not _widget_is_disabled(_find_field_row(anchor, "gain"))


def test_a_stale_row_refuses_at_write_time():
    bag = _GateSettings()
    gate = _StubGate(allows=True)
    _anchor, on_edits = _render(bag, gate)

    gate.allowed = False
    on_edits["gain"](5.0)

    assert bag.gain == 1.0
    assert gate.written_calls == 0


def test_written_called_after_edit():
    bag = _GateSettings()
    gate = _StubGate(allows=True)
    _anchor, on_edits = _render(bag, gate)

    on_edits["gain"](5.0)

    assert bag.gain == 5.0
    assert gate.written_calls == 1


def test_a_refused_reset_leaves_the_value():
    bag = _GateSettings()
    bag.gain = 4.0
    gate = _StubGate(allows=True)
    anchor, _ = _render(bag, gate)
    reset = _menu_items(_find_field_row(anchor, "gain"))["Reset to default"]

    gate.allowed = False
    _click(reset)

    assert bag.gain == 4.0
    assert gate.written_calls == 0


def test_an_accepted_reset_is_written():
    bag = _GateSettings()
    bag.gain = 4.0
    gate = _StubGate(allows=True)
    anchor, _ = _render(bag, gate)

    _click(_menu_items(_find_field_row(anchor, "gain"))["Reset to default"])

    assert bag.gain == 1.0
    assert gate.written_calls == 1


def test_a_refused_set_to_none_leaves_the_value():
    bag = _GateSettings()
    gate = _StubGate(allows=True)
    anchor, _ = _render(bag, gate)

    gate.allowed = False
    _click(_menu_items(_find_field_row(anchor, "count"))["Set to none"])

    assert bag.count == 3


def test_reset_and_set_to_none_grey_while_refused():
    bag = _GateSettings()
    bag.count = 5
    anchor, _ = _render(bag, _StubGate(allows=False))

    items = _menu_items(_find_field_row(anchor, "count"))
    assert items["Reset to default"].enabled is False
    assert items["Set to none"].enabled is False


def test_no_gate_behaves_as_today():
    bag = _GateSettings()
    anchor, on_edits = _render(bag, None)

    assert not _widget_is_disabled(_find_field_row(anchor, "gain"))
    on_edits["gain"](5.0)
    assert bag.gain == 5.0


def _click(item) -> None:
    """Fire a NiceGUI element's registered click handler headlessly."""
    listener_id = next(iter(item._event_listeners))
    item._handle_event({"listener_id": listener_id, "args": {}})
