"""ArrowHeadWidget: None and the common arrows first; More reveals every head."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.barn.builtin.types import STRING
from haywire.barn.builtin.widgets.arrow_head_widget import ArrowHeadWidget, preview_svg
from haywire.core.edge.arrow_heads import get_arrow_head
from haywire.core.types.enums import PortType
from haywire.core.types.port import DataPort


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


def _port() -> DataPort:
    port = DataPort(
        registry_id="head",
        registry_key=STRING.class_identity.registry_key,
        label="Head",
        id="head",
        type_cls=STRING,
        port_type=PortType.INLET,
    )
    port.set_value("none")
    return port


@pytest.mark.unit
def test_a_preview_draws_the_glyph_in_the_current_colour():
    svg = preview_svg(get_arrow_head("triangle"))
    assert "currentColor" in svg
    assert "context-stroke" not in svg
    assert "M0,-3 L5,0 L0,3 Z" in svg


@pytest.mark.unit
@pytest.mark.anyio
async def test_picking_a_common_head_stores_its_name(user: User) -> None:
    port = _port()

    @ui.page("/")
    def page() -> None:
        ArrowHeadWidget(port).render()

    await user.open("/")
    user.find(marker="arrow-head-open").click()

    assert port.get_value() == "open"


@pytest.mark.unit
@pytest.mark.anyio
async def test_more_reveals_the_rest_of_the_heads(user: User) -> None:
    port = _port()

    @ui.page("/")
    def page() -> None:
        ArrowHeadWidget(port).render()

    await user.open("/")
    await user.should_not_see(marker="arrow-head-zero_or_one")
    user.find(marker="arrow-head-more").click()
    user.find(marker="arrow-head-zero_or_one").click()

    assert port.get_value() == "zero_or_one"


@pytest.mark.unit
@pytest.mark.anyio
async def test_the_button_previews_the_stored_head(user: User) -> None:
    port = _port()
    captured: dict[str, ArrowHeadWidget] = {}

    @ui.page("/")
    def page() -> None:
        captured["widget"] = ArrowHeadWidget(port)
        captured["widget"].render()

    await user.open("/")
    port.set_value("diamond")

    head = get_arrow_head("diamond")
    assert head is not None
    assert captured["widget"]._preview.content == preview_svg(head)
