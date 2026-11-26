"""LabelWidget: one line, cut to the node's width, the whole text on hover; and a size box on a select root.

The browser-side proof (the node's floor, the cut, a stable height) is in
``tests/ui/harness/test_chip_select_widget.py``.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.barn.builtin.types import STRING
from haywire.barn.builtin.widgets.basic_widgets import WRAPPED_LABEL_MAX_HEIGHT, LabelWidget
from haywire.core.types.enums import PortType
from haywire.core.types.port import DataPort
from haywire.ui.hover_tip import TIP_ATTR, TIP_DESC_ATTR, TIP_TYPE_ATTR
from haywire.ui.skin.pin_render import add_pin_tooltip
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget
from haywire.ui.widget.sizing import INLINE_BOX_CLASS, MIN_WIDTH_VAR, stamp_size_declaration

pytestmark = pytest.mark.unit

_LONG = "Listening 1 ch at 48000 Hz, blocks 256, latency 56.9 ms, lost 0, overflow 0"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


def _port(value: str, widget_config: dict | None = None) -> DataPort:
    port = DataPort(
        registry_id="status",
        registry_key=STRING.class_identity.registry_key,
        label="Status",
        id="status",
        type_cls=STRING,
        port_type=PortType.CONFIG,
        widget_config=widget_config or {},
    )
    port.set_value(value)
    return port


def test_a_label_declares_a_width_so_its_text_never_floors_the_node():
    assert LabelWidget.class_identity.min_width == 120
    assert LabelWidget.class_identity.min_height is None


def test_a_call_site_can_give_the_content_floor_back():
    assert LabelWidget(_port("x", {"min_width": None})).min_width is None


@pytest.mark.anyio
async def test_the_text_is_cut_to_one_line_and_hovering_shows_all_of_it(user: User) -> None:
    port = _port(_LONG)
    holder: dict[str, LabelWidget] = {}

    @ui.page("/")
    def page() -> None:
        holder["widget"] = LabelWidget(port)
        holder["widget"].render()

    await user.open("/")
    text = holder["widget"]._text
    assert "truncate" in text.classes
    assert text.text == _LONG
    assert text.props[TIP_DESC_ATTR] == _LONG
    assert TIP_ATTR not in text.props, "the tip's title is the card's: the port's label"

    port.set_value("Idle")
    await user.should_see("Idle")
    assert text.props[TIP_DESC_ATTR] == "Idle"

    port.set_value("")
    await user.should_not_see("Idle")
    assert TIP_DESC_ATTR not in text.props
    assert holder["widget"].ui_element is text, "the label is the root the card's port tip goes on"


@widget(description="A select as the widget's root", min_width=160)
class _SelectRootWidget(BaseWidget):
    def build(self) -> ui.select:
        return ui.select(options=["a", "b"], value=["a"], multiple=True).props("use-chips")


@pytest.mark.anyio
async def test_the_size_box_marker_is_a_class_on_a_select_root(user: User) -> None:
    """A Quasar field keeps only ``class`` and ``style`` on its root, so both halves must be those."""
    holder: dict[str, ui.element] = {}

    @ui.page("/")
    def page() -> None:
        widget_instance = _SelectRootWidget(_port(""))
        element = widget_instance.render()
        stamp_size_declaration(element, widget_instance)
        holder["element"] = element

    await user.open("/")
    element = holder["element"]
    assert INLINE_BOX_CLASS in element.classes
    assert element.style[MIN_WIDTH_VAR] == "160px"
    assert not any(name.startswith("data-hw-widget") for name in element.props)


def test_a_wrapping_label_gets_a_default_height_limit():
    assert LabelWidget(_port("x", {"properties": {"wrap": True}})).max_height == WRAPPED_LABEL_MAX_HEIGHT
    assert LabelWidget(_port("x", {"properties": {"wrap": True}, "max_height": 160})).max_height == 160
    assert LabelWidget(_port("x")).max_height is None, "a one-line label needs no height limit"


@pytest.mark.anyio
async def test_a_wrapping_label_breaks_its_text_instead_of_cutting_it(user: User) -> None:
    port = _port(_LONG, {"properties": {"wrap": True}})
    holder: dict[str, LabelWidget] = {}

    @ui.page("/")
    def page() -> None:
        holder["widget"] = LabelWidget(port)
        holder["widget"].render()

    await user.open("/")
    text = holder["widget"]._text
    assert "truncate" not in text.classes
    assert "whitespace-normal" in text.classes
    assert text.props[TIP_DESC_ATTR] == _LONG


@pytest.mark.anyio
async def test_the_port_tip_keeps_the_text_a_label_wrote_as_its_second_line(user: User) -> None:
    """``add_pin_tooltip`` writes the port's label and type, and leaves a widget's own second line."""
    port = _port(_LONG)
    port.description = "What the device is doing"
    holder: dict[str, ui.element] = {}

    @ui.page("/")
    def page() -> None:
        root = LabelWidget(port).render()
        add_pin_tooltip(ui.element("div"), port, trigger_el=root)
        holder["root"] = root

    await user.open("/")
    root = holder["root"]
    assert root.props[TIP_ATTR] == "Status"
    assert root.props[TIP_TYPE_ATTR] == "STRING"
    assert root.props[TIP_DESC_ATTR] == _LONG


@pytest.mark.anyio
async def test_the_port_tip_still_shows_the_port_description_on_other_widgets(user: User) -> None:
    port = _port("x")
    port.description = "What the device is doing"
    holder: dict[str, ui.element] = {}

    @ui.page("/")
    def page() -> None:
        trigger = ui.element("div")
        add_pin_tooltip(ui.element("div"), port, trigger_el=trigger)
        holder["trigger"] = trigger

    await user.open("/")
    assert holder["trigger"].props[TIP_DESC_ATTR] == "What the device is doing"
