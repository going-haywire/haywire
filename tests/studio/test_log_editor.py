"""The Log editor shows the records logged after it draws, wherever draw() is called from."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haybale_studio.editors.log_editor import LogEditor


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


def _lines(log: ui.log) -> list[str]:
    return [child.text for child in log.default_slot.children if hasattr(child, "text")]


@pytest.mark.unit
@pytest.mark.anyio
async def test_a_record_logged_after_draw_reaches_the_panel(user: User) -> None:
    editor_box: dict[str, LogEditor] = {}

    @ui.page("/")
    def page() -> None:
        container = ui.column()
        # The caller of draw() is not inside the container: a transient element is the current slot.
        with ui.row() as transient:
            editor = LogEditor(MagicMock())
            editor.draw(MagicMock(), container)
        transient.delete()
        editor_box["editor"] = editor

    await user.open("/")
    editor = editor_box["editor"]
    try:
        logging.getLogger("tests.log_editor").warning("a record for the panel")
        for _ in range(30):
            if any("a record for the panel" in line for line in _lines(editor._log_element)):
                break
            await asyncio.sleep(0.1)
        assert any("a record for the panel" in line for line in _lines(editor._log_element))
    finally:
        editor.cleanup()
