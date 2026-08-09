"""A row carries coordinates; locate turns them into whichever URL a caller needs."""

import pytest

from haywire.core.marketstall.locate import module_dir_path, resolve_row_path
from haywire.core.marketstall.types import Haybale

GH = Haybale(
    name="haybale-core",
    version="0.0.40",
    origin="https://github.com/going-haywire/haywire",
    install_spec=(
        "haybale-core @ git+https://github.com/going-haywire/haywire.git"
        "@v0.0.40#subdirectory=barn/haybale-core"
    ),
    examples_path="barn/haybale-core/examples/OVERVIEW.md",
)

GL = Haybale(
    name="haybale-core",
    version="0.0.40",
    origin="https://gitlab.com/group/sub/haywire",
    install_spec=(
        "haybale-core @ git+https://gitlab.com/group/sub/haywire.git@v0.0.40#subdirectory=barn/haybale-core"
    ),
    examples_path="barn/haybale-core/examples/OVERVIEW.md",
)


def test_github_raw_url():
    assert resolve_row_path(GH, GH.examples_path, form="raw") == (
        "https://raw.githubusercontent.com/going-haywire/haywire/v0.0.40/"
        "barn/haybale-core/examples/OVERVIEW.md"
    )


def test_github_blob_url_for_a_file():
    assert resolve_row_path(GH, GH.examples_path, form="blob") == (
        "https://github.com/going-haywire/haywire/blob/v0.0.40/barn/haybale-core/examples/OVERVIEW.md"
    )


def test_github_tree_url_for_a_directory():
    assert resolve_row_path(GH, module_dir_path(GH), form="tree") == (
        "https://github.com/going-haywire/haywire/tree/v0.0.40/barn/haybale-core/haybale_core/"
    )


def test_gitlab_nested_group_origin_parses():
    """GitLab owners can be nested; the repo is the last segment."""
    assert resolve_row_path(GL, GL.examples_path, form="raw") == (
        "https://gitlab.com/group/sub/haywire/-/raw/v0.0.40/barn/haybale-core/examples/OVERVIEW.md"
    )


def test_ref_comes_from_install_spec_not_origin():
    """The commit is named in exactly one place, so nothing can contradict it."""
    row = Haybale(
        name="x",
        origin="https://github.com/o/r",
        install_spec="x @ git+https://github.com/o/r.git@v9.9.9#subdirectory=libs/x",
    )
    assert "/v9.9.9/" in (resolve_row_path(row, module_dir_path(row), form="raw") or "")


def test_unknown_host_yields_none_rather_than_a_wrong_url():
    row = Haybale(
        name="x",
        origin="https://git.example.invalid/o/r",
        install_spec="x @ git+https://git.example.invalid/o/r.git@v1#subdirectory=x",
    )
    assert resolve_row_path(row, module_dir_path(row), form="raw") is None


@pytest.mark.parametrize(
    "row",
    [Haybale(name="x", version="1.0"), Haybale(name="x", version="1.0", origin="https://github.com/o/r")],
)
def test_missing_coordinates_yield_none(row):
    assert resolve_row_path(row, "some/path", form="raw") is None


def test_empty_path_yields_none():
    assert resolve_row_path(GH, "", form="raw") is None
