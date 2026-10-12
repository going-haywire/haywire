"""``hui.key_hint`` and ``hui.icon_action(command=...)`` — a command's shortcut, shown where offered."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import ClassVar

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.core.signals import Copy, EditorCommand
from haywire.ui import elements as hui
from haywire.ui.app.shell import STATIC_CSS


@dataclass(frozen=True, kw_only=True)
class _Unbound(EditorCommand):
    command_id: ClassVar[str] = "test.unbound"
    label: ClassVar[str] = "Unbound"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


def _spans(root: ui.element, cls: str) -> list[ui.element]:
    return [el for el in [root, *root.descendants()] if cls in el._classes]


@pytest.mark.unit
@pytest.mark.anyio
async def test_key_hint_renders_both_platform_spellings(user: User) -> None:
    captured: dict[str, ui.element] = {}

    @ui.page("/")
    def page() -> None:
        with ui.row() as host:
            hui.key_hint(Copy)
        captured["host"] = host

    await user.open("/")

    host = captured["host"]
    mac = _spans(host, "hw-keys-mac")
    other = _spans(host, "hw-keys-other")
    assert [getattr(el, "text", None) for el in mac] == ["⌘C"]
    assert [getattr(el, "text", None) for el in other] == ["Ctrl+C"]
    for el in (*mac, *other):
        assert {"text-xs", "hw-text-dim", "ml-auto", "font-mono"} <= set(el._classes)


@pytest.mark.unit
@pytest.mark.anyio
async def test_key_hint_of_an_unbound_command_renders_nothing(user: User) -> None:
    captured: dict[str, ui.element] = {}

    @ui.page("/")
    def page() -> None:
        with ui.row() as host:
            hui.key_hint(_Unbound)
        captured["host"] = host

    await user.open("/")

    assert list(captured["host"].descendants()) == []


@pytest.mark.unit
@pytest.mark.anyio
async def test_icon_action_appends_the_shortcut_to_its_tooltip(user: User) -> None:
    captured: dict[str, ui.button] = {}

    @ui.page("/")
    def page() -> None:
        captured["btn"] = hui.icon_action(hui.icon.copy, tooltip="Copy", command=Copy)

    await user.open("/")

    btn = captured["btn"]
    targeted = [
        el
        for el in user._client.elements.values()
        if isinstance(el, ui.tooltip) and el.props.get("target") == f"#{btn.html_id}"
    ]
    assert [t.text for t in targeted] == ["Copy (Ctrl+C)"]


@pytest.mark.unit
def test_the_shell_css_hides_the_other_platforms_spelling() -> None:
    assert (
        'html[data-hw-platform="mac"] .hw-keys-other, html:not([data-hw-platform="mac"]) .hw-keys-mac'
        " { display: none; }"
    ) in STATIC_CSS
