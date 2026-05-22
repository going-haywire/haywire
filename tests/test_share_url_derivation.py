"""haywire share URL derivation via host providers — spec §6.1."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


_LIB_PYPROJECT = """[project]
name = "haybale-foo"
version = "0.1.0"
description = "x"

[tool.hatch.build.targets.wheel]
packages = ["haybale_foo"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""

_LIB_INIT = (
    '"""Foo."""\n'
    "from haywire.core.library.base import BaseLibrary\n"
    "from haywire.core.library.decorator import library\n"
    "\n"
    '@library(label="Foo", id="foo", version="0.1.0", description="x",\n'
    '         url="", help_url="", author="", author_url="",\n'
    "         dependencies=[], tags=[], file_watcher=False)\n"
    "class Library(BaseLibrary):\n"
    "    def register_components(self): pass\n"
    "    def validate(self) -> bool: return True\n"
)


def _make_repo(tmp_path: Path) -> Path:
    """Scaffold a minimal repo with one barn library."""
    (tmp_path / ".git").mkdir()
    lib_dir = tmp_path / "barn" / "haybale-foo"
    lib_dir.mkdir(parents=True)
    pkg = lib_dir / "haybale_foo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(_LIB_INIT)
    (lib_dir / "pyproject.toml").write_text(_LIB_PYPROJECT)
    return tmp_path


@pytest.mark.unit
def test_share_save_returns_share_url_for_github_remote(tmp_path: Path) -> None:
    from haywire_studio.share import share_save_repo

    repo = _make_repo(tmp_path)
    with patch("haywire_studio.share._get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        with patch("haywire_studio.share._get_current_ref", return_value="main"):
            result = share_save_repo(repo)

    assert result.share_url == "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    assert result.out_path == repo / "marketstall.toml"
    assert result.warning is None


@pytest.mark.unit
def test_share_save_returns_share_url_for_gitlab_remote(tmp_path: Path) -> None:
    from haywire_studio.share import share_save_repo

    repo = _make_repo(tmp_path)
    with patch(
        "haywire_studio.share._get_remote_url", return_value="https://gitlab.com/alice/cool-libs.git"
    ):
        with patch("haywire_studio.share._get_current_ref", return_value="main"):
            result = share_save_repo(repo)

    assert result.share_url == "https://gitlab.com/alice/cool-libs/-/blob/main/marketstall.toml"


@pytest.mark.unit
def test_share_save_no_remote_warns(tmp_path: Path) -> None:
    from haywire_studio.share import share_save_repo

    repo = _make_repo(tmp_path)
    with patch("haywire_studio.share._get_remote_url", return_value=None):
        result = share_save_repo(repo)

    assert result.share_url is None
    assert result.warning is not None
    assert "remote" in result.warning.lower()


@pytest.mark.unit
def test_share_save_unknown_host_warns_with_config_snippet(tmp_path: Path) -> None:
    from haywire_studio.share import share_save_repo

    repo = _make_repo(tmp_path)
    with patch("haywire_studio.share._get_remote_url", return_value="https://gitlab.zhdk.ch/alice/libs.git"):
        with patch("haywire_studio.share._get_current_ref", return_value="main"):
            result = share_save_repo(repo)

    assert result.share_url is None
    assert result.warning is not None
    assert "gitlab.zhdk.ch" in result.warning
    assert "[[hosts]]" in result.warning  # ready-to-paste config snippet
    assert "config.toml" in result.warning


@pytest.mark.unit
def test_share_save_with_explicit_ref(tmp_path: Path) -> None:
    """--ref <ref> argument overrides the current-branch default."""
    from haywire_studio.share import share_save_repo

    repo = _make_repo(tmp_path)
    with patch("haywire_studio.share._get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        result = share_save_repo(repo, ref="v0.2.0")

    assert result.share_url == "https://github.com/alice/cool-libs/blob/v0.2.0/marketstall.toml"


@pytest.mark.unit
def test_share_save_with_tag_argument(tmp_path: Path) -> None:
    """--tag <tag> argument uses the tag name as ref."""
    from haywire_studio.share import share_save_repo

    repo = _make_repo(tmp_path)
    with patch("haywire_studio.share._get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        result = share_save_repo(repo, tag="v0.2.0")

    assert result.share_url == "https://github.com/alice/cool-libs/blob/v0.2.0/marketstall.toml"


@pytest.mark.unit
def test_share_save_with_tag_latest_resolves_to_most_recent_tag(tmp_path: Path) -> None:
    from haywire_studio.share import share_save_repo

    repo = _make_repo(tmp_path)
    with patch("haywire_studio.share._get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        with patch("haywire_studio.share._get_latest_tag", return_value="v0.3.0"):
            result = share_save_repo(repo, tag="latest")

    assert result.share_url == "https://github.com/alice/cool-libs/blob/v0.3.0/marketstall.toml"


@pytest.mark.unit
def test_derive_share_url_no_args(tmp_path: Path) -> None:
    """`haywire share` (no args) derives the URL without writing files."""
    from haywire_studio.share import ShareSaveResult, derive_share_url_only

    repo = _make_repo(tmp_path)
    (repo / "marketstall.toml").write_text("# placeholder\n")
    with patch("haywire_studio.share._get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        with patch("haywire_studio.share._get_current_ref", return_value="main"):
            result = derive_share_url_only(repo)

    assert isinstance(result, ShareSaveResult)
    assert result.share_url == "https://github.com/alice/cool-libs/blob/main/marketstall.toml"


@pytest.mark.unit
def test_derive_share_url_only_no_file_warns(tmp_path: Path) -> None:
    """If marketstall.toml doesn't exist, surface a helpful message."""
    from haywire_studio.share import derive_share_url_only

    repo = _make_repo(tmp_path)
    # No marketstall.toml created.
    with patch("haywire_studio.share._get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        with patch("haywire_studio.share._get_current_ref", return_value="main"):
            result = derive_share_url_only(repo)

    assert result.share_url is None
    assert "marketstall.toml" in result.warning
