"""``hui.count_badge`` — a count on a status colour, readable in every theme.

Both colours come from tokens: the fill is the status token, the text the page
background, so the pair stays legible however a theme sets them.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.ui import elements as hui


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


@pytest.mark.unit
@pytest.mark.anyio
@pytest.mark.parametrize("tone", ["warning", "danger", "info"])
async def test_the_badge_reads_its_colours_from_tokens(user: User, tone: str) -> None:
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        captured["badge"] = hui.count_badge(3, tone=tone)

    await user.open("/")

    badge: ui.badge = captured["badge"]  # type: ignore[assignment]
    assert badge.text == "3"
    assert badge._style["background"] == f"var(--hw-{tone})"
    assert badge._style["color"] == "var(--hw-bg-page)"
    assert "color" not in badge.props


@pytest.mark.unit
def test_an_unknown_tone_is_refused() -> None:
    with pytest.raises(ValueError, match="tone"):
        hui.count_badge(1, tone="purple")
