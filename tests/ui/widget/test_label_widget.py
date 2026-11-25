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
from haywire.barn.builtin.widgets.basic_widgets import LabelWidget
from haywire.core.types.enums import PortType
from haywire.core.types.port import DataPort
from haywire.ui.hover_tip import TIP_ATTR
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
    assert text.props[TIP_ATTR] == _LONG

    port.set_value("Idle")
    await user.should_see("Idle")
    assert text.props[TIP_ATTR] == "Idle"


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
