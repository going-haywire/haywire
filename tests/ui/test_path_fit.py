"""What a fitted path hands the browser: the path's text, its parts, and the full path as tooltip."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from pathlib import PurePosixPath, PureWindowsPath

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.ui import elements as hui
from haywire.ui.elements.path_fit import FIT_CLASS, PARTS_ATTR, PATH_FIT_CSS, TEXT_ATTR, parts_attr

pytestmark = pytest.mark.unit


def test_parts_carry_the_anchor_the_separator_and_every_part() -> None:
    path = PurePosixPath("/Volumes/Ddrive/haywire/repo")
    assert json.loads(parts_attr(path)) == ["/", "/", "Volumes", "Ddrive", "haywire", "repo"]


def test_a_relative_path_has_no_anchor() -> None:
    assert json.loads(parts_attr(PurePosixPath("graphs/foo.haywire"))) == ["", "/", "graphs", "foo.haywire"]


def test_a_windows_path_keeps_its_drive_and_separator() -> None:
    path = PureWindowsPath("C:/Users/me/repo")
    assert json.loads(parts_attr(path)) == ["C:\\", "\\", "Users", "me", "repo"]


def test_a_very_long_path_keeps_every_part() -> None:
    path = PurePosixPath("/" + "/".join(f"d{i}" for i in range(30)))
    assert json.loads(parts_attr(path))[2:] == [f"d{i}" for i in range(30)]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


@pytest.mark.anyio
async def test_a_fitted_path_hands_over_its_parts_and_titles_the_full_path(user: User) -> None:
    built: dict[str, hui.FittedPath] = {}
    path = PurePosixPath("/Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo")

    @ui.page("/")
    def page() -> None:
        built["line"] = hui.fitted_path(path)

    await user.open("/")
    line = built["line"]
    assert FIT_CLASS in line.classes
    assert line.props[TEXT_ATTR] == str(path)
    assert line.props[PARTS_ATTR] == parts_attr(path)
    assert line.props["title"] == str(path)
    assert line.path == path
    assert not line.default_slot.children


@pytest.mark.anyio
async def test_set_path_and_set_text_replace_what_is_shown(user: User) -> None:
    built: dict[str, hui.FittedPath] = {}

    @ui.page("/")
    def page() -> None:
        built["line"] = hui.fitted_path(text="Untitled")

    await user.open("/")
    line = built["line"]
    assert line.props[TEXT_ATTR] == "Untitled"
    assert PARTS_ATTR not in line.props
    assert "title" not in line.props
    assert line.path is None

    line.set_path(PurePosixPath("/a/b/c/d"))
    assert line.props[TEXT_ATTR] == "/a/b/c/d"
    assert line.props[PARTS_ATTR] == parts_attr(PurePosixPath("/a/b/c/d"))
    assert line.props["title"] == "/a/b/c/d"

    line.set_text("not saved")
    assert line.props[TEXT_ATTR] == "not saved"
    assert PARTS_ATTR not in line.props
    assert "title" not in line.props
    assert line.path is None


@pytest.mark.anyio
async def test_the_script_is_sent_once_per_page_however_many_lines(user: User) -> None:
    sent: list[str] = []

    @ui.page("/")
    def page() -> None:
        client = ui.context.client
        original = client.run_javascript

        def spy(code: str, **kwargs):  # type: ignore[no-untyped-def]
            if "hwPathFit" in code:
                sent.append(code)
            return original(code, **kwargs)

        client.run_javascript = spy  # type: ignore[method-assign]
        for i in range(3):
            hui.fitted_path(PurePosixPath(f"/a/b/{i}"))

    await user.open("/")
    assert len(sent) == 1


def test_the_stylesheet_ships_with_the_studio() -> None:
    from haywire.ui.app.shell import STATIC_CSS

    assert PATH_FIT_CSS in STATIC_CSS


@pytest.mark.anyio
async def test_showing_the_same_path_or_text_again_sends_nothing(user: User) -> None:
    built: dict[str, hui.FittedPath] = {}

    @ui.page("/")
    def page() -> None:
        built["line"] = hui.fitted_path(PurePosixPath("/a/b/c/d"))

    await user.open("/")
    line = built["line"]
    updates: list[None] = []
    line.update = lambda: updates.append(None)  # type: ignore[method-assign]
    line.set_path(PurePosixPath("/a/b/c/d"))
    assert updates == []

    line.set_text("not saved")
    assert updates
    sent = len(updates)
    line.set_text("not saved")
    assert len(updates) == sent


@pytest.mark.anyio
async def test_set_path_after_set_text_of_the_same_string_still_sets_the_tooltip(user: User) -> None:
    built: dict[str, hui.FittedPath] = {}

    @ui.page("/")
    def page() -> None:
        built["line"] = hui.fitted_path(text="/a")

    await user.open("/")
    line = built["line"]
    line.set_path(PurePosixPath("/a"))
    assert line.props["title"] == "/a"
    assert line.path == PurePosixPath("/a")
