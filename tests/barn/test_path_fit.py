"""The middle-cropped renderings of a path the Volumes editor offers the browser, longest first."""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath

import pytest
from haybale_studio.editors.path_fit import crop_candidates

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
