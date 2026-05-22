"""haywire share --save updates README marker blocks — spec §6.6."""

from __future__ import annotations

from pathlib import Path

import pytest


_MARKER_START = "<!-- marketstall:share-url:start -->"
_MARKER_END = "<!-- marketstall:share-url:end -->"


@pytest.mark.unit
def test_update_readme_markers_rewrites_block() -> None:
    """Block between markers replaced with inline-code line containing the URL."""
    from haywire_studio.share import _update_readme_markers

    content = f"# Foo\n\n## Subscribe\n\n{_MARKER_START}\n*placeholder text*\n{_MARKER_END}\n\nMore content."
    url = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    new_content = _update_readme_markers(content, url)

    assert new_content != content
    assert f"`{url}`" in new_content
    assert "placeholder text" not in new_content
    assert _MARKER_START in new_content
    assert _MARKER_END in new_content
    assert "More content." in new_content  # surrounding content preserved


@pytest.mark.unit
def test_update_readme_markers_no_markers_returns_unchanged() -> None:
    """File without marker pair is returned untouched."""
    from haywire_studio.share import _update_readme_markers

    content = "# Foo\n\nNo markers here.\n"
    assert _update_readme_markers(content, "https://example.com/x.toml") == content


@pytest.mark.unit
def test_update_readme_markers_multiple_blocks_all_updated() -> None:
    """Per spec §6.6: multiple marker pairs in one file are all updated to the same URL."""
    from haywire_studio.share import _update_readme_markers

    content = f"{_MARKER_START}\nA\n{_MARKER_END}\nsome text\n{_MARKER_START}\nB\n{_MARKER_END}\n"
    url = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    new_content = _update_readme_markers(content, url)

    assert new_content.count(f"`{url}`") == 2
    assert "A" not in new_content
    assert "B" not in new_content


@pytest.mark.unit
def test_share_save_updates_root_readme(tmp_path: Path) -> None:
    """End-to-end: share_save_repo rewrites the root README's marker block."""
    from unittest.mock import patch
    from haywire_studio.share import share_save_repo

    # Scaffold: root README + one barn library.
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text(f"# Project\n\n{_MARKER_START}\n*placeholder*\n{_MARKER_END}\n")
    lib_dir = tmp_path / "barn" / "haybale-foo"
    lib_dir.mkdir(parents=True)
    (lib_dir / "pyproject.toml").write_text(
        '[project]\nname = "haybale-foo"\nversion = "0.1.0"\ndescription = "x"\n'
    )

    with patch("haywire_studio.share._get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        with patch("haywire_studio.share._get_current_ref", return_value="main"):
            result = share_save_repo(tmp_path)

    expected_url = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    assert result.share_url == expected_url
    assert f"`{expected_url}`" in (tmp_path / "README.md").read_text()


@pytest.mark.unit
def test_share_save_updates_barn_library_readme(tmp_path: Path) -> None:
    from unittest.mock import patch
    from haywire_studio.share import share_save_repo

    (tmp_path / ".git").mkdir()
    lib_dir = tmp_path / "barn" / "haybale-foo"
    lib_dir.mkdir(parents=True)
    (lib_dir / "pyproject.toml").write_text(
        '[project]\nname = "haybale-foo"\nversion = "0.1.0"\ndescription = "x"\n'
    )
    (lib_dir / "README.md").write_text(f"# Foo\n\n{_MARKER_START}\n*placeholder*\n{_MARKER_END}\n")

    with patch("haywire_studio.share._get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        with patch("haywire_studio.share._get_current_ref", return_value="main"):
            share_save_repo(tmp_path)

    expected_url = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    assert f"`{expected_url}`" in (lib_dir / "README.md").read_text()


@pytest.mark.unit
def test_share_save_no_update_readme_flag_suppresses(tmp_path: Path) -> None:
    """--no-update-readme leaves all READMEs untouched."""
    from unittest.mock import patch
    from haywire_studio.share import share_save_repo

    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text(f"{_MARKER_START}\n*placeholder*\n{_MARKER_END}\n")
    lib_dir = tmp_path / "barn" / "haybale-foo"
    lib_dir.mkdir(parents=True)
    (lib_dir / "pyproject.toml").write_text(
        '[project]\nname = "haybale-foo"\nversion = "0.1.0"\ndescription = "x"\n'
    )

    with patch("haywire_studio.share._get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        with patch("haywire_studio.share._get_current_ref", return_value="main"):
            share_save_repo(tmp_path, update_readme=False)

    assert "placeholder" in (tmp_path / "README.md").read_text()


@pytest.mark.unit
def test_share_save_no_share_url_skips_readme_update(tmp_path: Path) -> None:
    """When share URL can't be derived (no remote), READMEs are not touched."""
    from unittest.mock import patch
    from haywire_studio.share import share_save_repo

    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text(f"{_MARKER_START}\n*placeholder*\n{_MARKER_END}\n")
    lib_dir = tmp_path / "barn" / "haybale-foo"
    lib_dir.mkdir(parents=True)
    (lib_dir / "pyproject.toml").write_text(
        '[project]\nname = "haybale-foo"\nversion = "0.1.0"\ndescription = "x"\n'
    )

    with patch("haywire_studio.share._get_remote_url", return_value=None):
        result = share_save_repo(tmp_path)

    assert result.share_url is None
    assert "placeholder" in (tmp_path / "README.md").read_text()


@pytest.mark.unit
def test_share_save_finds_case_insensitive_readme(tmp_path: Path) -> None:
    """Per spec §6.6: 'Readme.md' (case variant) is found if README.md is absent."""
    from unittest.mock import patch
    from haywire_studio.share import share_save_repo

    (tmp_path / ".git").mkdir()
    (tmp_path / "Readme.md").write_text(  # lowercase 'e', capital 'R'
        f"# x\n{_MARKER_START}\n*placeholder*\n{_MARKER_END}\n"
    )
    lib_dir = tmp_path / "barn" / "haybale-foo"
    lib_dir.mkdir(parents=True)
    (lib_dir / "pyproject.toml").write_text(
        '[project]\nname = "haybale-foo"\nversion = "0.1.0"\ndescription = "x"\n'
    )

    with patch("haywire_studio.share._get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        with patch("haywire_studio.share._get_current_ref", return_value="main"):
            share_save_repo(tmp_path)

    expected_url = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    assert f"`{expected_url}`" in (tmp_path / "Readme.md").read_text()
