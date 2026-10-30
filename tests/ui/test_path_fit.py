"""The middle-cropped renderings of a path a fitted path offers the browser, longest first."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import PurePosixPath, PureWindowsPath

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.ui import elements as hui
from haywire.ui.elements.path_fit import FIT_CLASS, MAX_CANDIDATES, PATH_FIT_CSS, crop_candidates

pytestmark = pytest.mark.unit


def test_a_deep_path_yields_every_candidate_in_order() -> None:
    path = PurePosixPath("/Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo")
    assert crop_candidates(path) == [
        "/Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo",
        "/Volumes/Ddrive/../haywire/haywire-repo",
        "/Volumes/../haywire-repo",
        "../haywire/haywire-repo",
        "../haywire-repo",
    ]


def test_a_candidate_that_elides_nothing_is_left_out() -> None:
    # Four parts: two leading + two trailing would hide nothing.
    path = PurePosixPath("/a/b/c/d")
    assert crop_candidates(path) == ["/a/b/c/d", "/a/../d", "../c/d", "../d"]


def test_a_short_path_has_only_the_shortenings_that_hide_something() -> None:
    assert crop_candidates(PurePosixPath("/a/b")) == ["/a/b", "../b"]
    assert crop_candidates(PurePosixPath("/a")) == ["/a"]
    assert crop_candidates(PurePosixPath("/")) == ["/"]


def test_a_windows_path_keeps_its_drive_and_separator() -> None:
    path = PureWindowsPath("C:/Users/me/projects/haywire/repo")
    assert crop_candidates(path) == [
        "C:\\Users\\me\\projects\\haywire\\repo",
        "C:\\Users\\me\\..\\haywire\\repo",
        "C:\\Users\\..\\repo",
        "..\\haywire\\repo",
        "..\\repo",
    ]


def test_no_path_yields_more_candidates_than_the_css_has_selectors_for() -> None:
    deep = "/".join(f"d{i}" for i in range(30))
    for path in (PurePosixPath("/" + deep), PurePosixPath(deep), PureWindowsPath("C:/" + deep)):
        assert len(crop_candidates(path)) <= MAX_CANDIDATES


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


def _shown(line: ui.element) -> list[str]:
    return [child.text for child in line.default_slot.children]  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_a_fitted_path_draws_every_rendering_and_titles_the_full_path(user: User) -> None:
    built: dict[str, hui.FittedPath] = {}
    path = PurePosixPath("/Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo")

    @ui.page("/")
    def page() -> None:
        built["line"] = hui.fitted_path(path)

    await user.open("/")
    line = built["line"]
    assert FIT_CLASS in line.classes
    assert _shown(line) == crop_candidates(path)
    assert line.props["title"] == str(path)
    assert line.path == path


@pytest.mark.anyio
async def test_set_path_and_set_text_replace_the_renderings(user: User) -> None:
    built: dict[str, hui.FittedPath] = {}

    @ui.page("/")
    def page() -> None:
        built["line"] = hui.fitted_path(text="Untitled")

    await user.open("/")
    line = built["line"]
    assert _shown(line) == ["Untitled"]
    assert "title" not in line.props
    assert line.path is None

    line.set_path(PurePosixPath("/a/b/c/d"))
    assert _shown(line) == crop_candidates(PurePosixPath("/a/b/c/d"))
    assert line.props["title"] == "/a/b/c/d"

    line.set_text("not saved")
    assert _shown(line) == ["not saved"]
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
async def test_showing_the_same_path_or_text_again_keeps_the_drawn_renderings(user: User) -> None:
    built: dict[str, hui.FittedPath] = {}

    @ui.page("/")
    def page() -> None:
        built["line"] = hui.fitted_path(PurePosixPath("/a/b/c/d"))

    await user.open("/")
    line = built["line"]
    drawn = list(line.default_slot.children)
    line.set_path(PurePosixPath("/a/b/c/d"))
    assert line.default_slot.children == drawn

    line.set_text("not saved")
    drawn = list(line.default_slot.children)
    line.set_text("not saved")
    assert line.default_slot.children == drawn
