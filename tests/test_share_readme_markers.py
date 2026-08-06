"""haywire share --save updates README marker blocks — spec §6.6."""

from __future__ import annotations

from pathlib import Path

import pytest


_MARKER_START = "<!-- marketstall:share-url:start -->"
_MARKER_END = "<!-- marketstall:share-url:end -->"


@pytest.mark.unit
def test_update_readme_markers_rewrites_block() -> None:
    """Block between markers replaced with inline-code line containing the URL."""
    from haywire.core.publishing.readme import _update_readme_markers

    content = f"# Foo\n\n## Subscribe\n\n{_MARKER_START}\n*placeholder text*\n{_MARKER_END}\n\nMore content."
    url = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    new_content = _update_readme_markers(content, url)

    assert new_content != content
    assert url in new_content
    assert "placeholder text" not in new_content
    assert _MARKER_START in new_content
    assert _MARKER_END in new_content
    assert "More content." in new_content  # surrounding content preserved


@pytest.mark.unit
def test_update_readme_markers_with_tagged_url_adds_second_link() -> None:
    """When tagged_url is given, the block carries both links, each labeled."""
    from haywire.core.publishing.readme import _update_readme_markers

    content = f"{_MARKER_START}\n*placeholder*\n{_MARKER_END}\n"
    url = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    tagged_url = "https://github.com/alice/cool-libs/blob/v1.2.0/marketstall.toml"
    new_content = _update_readme_markers(content, url, tagged_url=tagged_url)

    assert url in new_content
    assert tagged_url in new_content
    assert new_content.index(url) < new_content.index(tagged_url)  # branch-live URL comes first


@pytest.mark.unit
def test_update_readme_markers_no_tagged_url_omits_second_link() -> None:
    """Without tagged_url, only the branch-live URL appears (back-compat)."""
    from haywire.core.publishing.readme import _update_readme_markers

    content = f"{_MARKER_START}\n*placeholder*\n{_MARKER_END}\n"
    url = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    new_content = _update_readme_markers(content, url)

    assert new_content.count("marketstall.toml") == 1


@pytest.mark.unit
def test_update_readme_markers_pypi_url_leads_the_block() -> None:
    """The PyPI feed is the primary install path, so it is listed first."""
    from haywire.core.publishing.readme import _update_readme_markers

    content = f"{_MARKER_START}\n*placeholder*\n{_MARKER_END}\n"
    url = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    tagged_url = "https://github.com/alice/cool-libs/blob/v1.2.0/marketstall.toml"
    pypi_url = "https://alice.github.io/cool-libs/marketplace.toml"
    new_content = _update_readme_markers(content, url, tagged_url=tagged_url, pypi_url=pypi_url)

    assert new_content.index(pypi_url) < new_content.index(url) < new_content.index(tagged_url)
    assert "recommended" in new_content


@pytest.mark.unit
def test_update_readme_markers_without_pypi_url_omits_it() -> None:
    """A project with no deployed PyPI feed keeps the two git links only."""
    from haywire.core.publishing.readme import _update_readme_markers

    content = f"{_MARKER_START}\n*placeholder*\n{_MARKER_END}\n"
    url = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    new_content = _update_readme_markers(content, url)

    assert "recommended" not in new_content
    assert url in new_content


@pytest.mark.unit
def test_update_readme_markers_no_markers_returns_unchanged() -> None:
    """File without marker pair is returned untouched."""
    from haywire.core.publishing.readme import _update_readme_markers

    content = "# Foo\n\nNo markers here.\n"
    assert _update_readme_markers(content, "https://example.com/x.toml") == content


@pytest.mark.unit
def test_update_readme_markers_multiple_blocks_all_updated() -> None:
    """Per spec §6.6: multiple marker pairs in one file are all updated to the same URL."""
    from haywire.core.publishing.readme import _update_readme_markers

    content = (
        f"{_MARKER_START}\nplaceholder-one\n{_MARKER_END}\n"
        f"some text\n{_MARKER_START}\nplaceholder-two\n{_MARKER_END}\n"
    )
    url = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    new_content = _update_readme_markers(content, url)

    assert new_content.count(url) == 2
    assert "placeholder-one" not in new_content
    assert "placeholder-two" not in new_content


@pytest.mark.unit
def test_share_save_updates_root_readme(tmp_path: Path) -> None:
    """End-to-end: write_marketstall rewrites the root README's marker block."""
    from unittest.mock import patch

    from haywire.core.publishing import write_marketstall
    from haywire.core.publishing import url as share_url

    # Scaffold: root README + one barn library.
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text(f"# Project\n\n{_MARKER_START}\n*placeholder*\n{_MARKER_END}\n")
    lib_dir = tmp_path / "barn" / "haybale-foo"
    lib_dir.mkdir(parents=True)
    (lib_dir / "pyproject.toml").write_text(
        '[project]\nname = "haybale-foo"\nversion = "0.1.0"\ndescription = "x"\n'
    )

    with patch.object(share_url, "_get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        with patch.object(share_url, "_get_current_ref", return_value="main"):
            result = write_marketstall(tmp_path)

    expected_url = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    assert result.share_url == expected_url
    assert expected_url in (tmp_path / "README.md").read_text()


@pytest.mark.unit
def test_share_save_with_tag_writes_both_links_to_readme(tmp_path: Path) -> None:
    """End-to-end: passing tag= gives the README a branch-live AND a frozen link."""
    from unittest.mock import patch

    from haywire.core.publishing import write_marketstall
    from haywire.core.publishing import url as share_url

    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text(f"# Project\n\n{_MARKER_START}\n*placeholder*\n{_MARKER_END}\n")
    lib_dir = tmp_path / "barn" / "haybale-foo"
    lib_dir.mkdir(parents=True)
    (lib_dir / "pyproject.toml").write_text(
        '[project]\nname = "haybale-foo"\nversion = "0.1.0"\ndescription = "x"\n'
    )

    with patch.object(share_url, "_get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        with patch.object(share_url, "_get_current_ref", return_value="main"):
            result = write_marketstall(tmp_path, tag="v1.2.0")

    branch_url = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    tagged_url = "https://github.com/alice/cool-libs/blob/v1.2.0/marketstall.toml"
    assert result.share_url == branch_url
    assert result.tagged_url == tagged_url
    readme_text = (tmp_path / "README.md").read_text()
    assert branch_url in readme_text
    assert tagged_url in readme_text


@pytest.mark.unit
def test_share_save_updates_barn_library_readme(tmp_path: Path) -> None:
    from unittest.mock import patch

    from haywire.core.publishing import write_marketstall
    from haywire.core.publishing import url as share_url

    (tmp_path / ".git").mkdir()
    lib_dir = tmp_path / "barn" / "haybale-foo"
    lib_dir.mkdir(parents=True)
    (lib_dir / "pyproject.toml").write_text(
        '[project]\nname = "haybale-foo"\nversion = "0.1.0"\ndescription = "x"\n'
    )
    (lib_dir / "README.md").write_text(f"# Foo\n\n{_MARKER_START}\n*placeholder*\n{_MARKER_END}\n")

    with patch.object(share_url, "_get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        with patch.object(share_url, "_get_current_ref", return_value="main"):
            write_marketstall(tmp_path)

    expected_url = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    assert expected_url in (lib_dir / "README.md").read_text()


@pytest.mark.unit
def test_share_save_no_update_readme_flag_suppresses(tmp_path: Path) -> None:
    """--no-update-readme leaves all READMEs untouched."""
    from unittest.mock import patch

    from haywire.core.publishing import write_marketstall
    from haywire.core.publishing import url as share_url

    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text(f"{_MARKER_START}\n*placeholder*\n{_MARKER_END}\n")
    lib_dir = tmp_path / "barn" / "haybale-foo"
    lib_dir.mkdir(parents=True)
    (lib_dir / "pyproject.toml").write_text(
        '[project]\nname = "haybale-foo"\nversion = "0.1.0"\ndescription = "x"\n'
    )

    with patch.object(share_url, "_get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        with patch.object(share_url, "_get_current_ref", return_value="main"):
            write_marketstall(tmp_path, update_readme=False)

    assert "placeholder" in (tmp_path / "README.md").read_text()


@pytest.mark.unit
def test_share_save_no_share_url_skips_readme_update(tmp_path: Path) -> None:
    """When share URL can't be derived (no remote), READMEs are not touched."""
    from unittest.mock import patch

    from haywire.core.publishing import write_marketstall
    from haywire.core.publishing import url as share_url

    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text(f"{_MARKER_START}\n*placeholder*\n{_MARKER_END}\n")
    lib_dir = tmp_path / "barn" / "haybale-foo"
    lib_dir.mkdir(parents=True)
    (lib_dir / "pyproject.toml").write_text(
        '[project]\nname = "haybale-foo"\nversion = "0.1.0"\ndescription = "x"\n'
    )

    with patch.object(share_url, "_get_remote_url", return_value=None):
        result = write_marketstall(tmp_path)

    assert result.share_url is None
    assert "placeholder" in (tmp_path / "README.md").read_text()


@pytest.mark.unit
def test_share_save_finds_case_insensitive_readme(tmp_path: Path) -> None:
    """Per spec §6.6: 'Readme.md' (case variant) is found if README.md is absent."""
    from unittest.mock import patch

    from haywire.core.publishing import write_marketstall
    from haywire.core.publishing import url as share_url

    (tmp_path / ".git").mkdir()
    (tmp_path / "Readme.md").write_text(  # lowercase 'e', capital 'R'
        f"# x\n{_MARKER_START}\n*placeholder*\n{_MARKER_END}\n"
    )
    lib_dir = tmp_path / "barn" / "haybale-foo"
    lib_dir.mkdir(parents=True)
    (lib_dir / "pyproject.toml").write_text(
        '[project]\nname = "haybale-foo"\nversion = "0.1.0"\ndescription = "x"\n'
    )

    with patch.object(share_url, "_get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        with patch.object(share_url, "_get_current_ref", return_value="main"):
            write_marketstall(tmp_path)

    expected_url = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    assert expected_url in (tmp_path / "Readme.md").read_text()


@pytest.mark.unit
def test_read_pypi_marketplace_url_reads_the_key(tmp_path: Path) -> None:
    """The URL is project-scoped config, authored once in pyproject.toml."""
    from haywire.core.publishing.marketstall import read_pypi_marketplace_url

    (tmp_path / "pyproject.toml").write_text(
        "[tool.haywire.marketstall]\n"
        'pypi_marketplace_url = "https://alice.github.io/cool-libs/marketplace.toml"\n'
    )
    assert read_pypi_marketplace_url(tmp_path) == "https://alice.github.io/cool-libs/marketplace.toml"


@pytest.mark.unit
@pytest.mark.parametrize(
    "content",
    [
        pytest.param(None, id="no-pyproject"),
        pytest.param("[project]\nname = 'x'\n", id="no-marketstall-block"),
        pytest.param("[tool.haywire.marketstall]\nsource_url = 'https://x'\n", id="key-absent"),
        pytest.param("[tool.haywire.marketstall]\npypi_marketplace_url = ''\n", id="empty-string"),
        pytest.param("[tool.haywire.marketstall]\npypi_marketplace_url = 42\n", id="not-a-string"),
        pytest.param("this is not { valid toml", id="malformed-toml"),
    ],
)
def test_read_pypi_marketplace_url_is_lenient(tmp_path: Path, content: str | None) -> None:
    """Every unreadable/absent case means 'no PyPI feed' — never an exception.

    An optional README link must not be able to fail a publish.
    """
    from haywire.core.publishing.marketstall import read_pypi_marketplace_url

    if content is not None:
        (tmp_path / "pyproject.toml").write_text(content)
    assert read_pypi_marketplace_url(tmp_path) is None


@pytest.mark.unit
def test_share_save_writes_pypi_link_from_config(tmp_path: Path) -> None:
    """End-to-end: the configured PyPI feed lands on top of the README block."""
    from unittest.mock import patch

    from haywire.core.publishing import write_marketstall
    from haywire.core.publishing import url as share_url

    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text(f"# Project\n\n{_MARKER_START}\n*placeholder*\n{_MARKER_END}\n")
    (tmp_path / "pyproject.toml").write_text(
        "[tool.haywire.marketstall]\n"
        'pypi_marketplace_url = "https://alice.github.io/cool-libs/marketplace.toml"\n'
    )
    lib_dir = tmp_path / "barn" / "haybale-foo"
    lib_dir.mkdir(parents=True)
    (lib_dir / "pyproject.toml").write_text(
        '[project]\nname = "haybale-foo"\nversion = "0.1.0"\ndescription = "x"\n'
    )

    with patch.object(share_url, "_get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        with patch.object(share_url, "_get_current_ref", return_value="main"):
            result = write_marketstall(tmp_path, tag="v1.2.0")

    pypi_url = "https://alice.github.io/cool-libs/marketplace.toml"
    branch_url = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    tagged_url = "https://github.com/alice/cool-libs/blob/v1.2.0/marketstall.toml"

    assert result.pypi_url == pypi_url
    readme_text = (tmp_path / "README.md").read_text()
    assert readme_text.index(pypi_url) < readme_text.index(branch_url) < readme_text.index(tagged_url)


@pytest.mark.unit
def test_share_save_without_pypi_config_omits_the_link(tmp_path: Path) -> None:
    """A project that doesn't publish to PyPI gets the two git links, as before."""
    from unittest.mock import patch

    from haywire.core.publishing import write_marketstall
    from haywire.core.publishing import url as share_url

    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text(f"# Project\n\n{_MARKER_START}\n*placeholder*\n{_MARKER_END}\n")
    lib_dir = tmp_path / "barn" / "haybale-foo"
    lib_dir.mkdir(parents=True)
    (lib_dir / "pyproject.toml").write_text(
        '[project]\nname = "haybale-foo"\nversion = "0.1.0"\ndescription = "x"\n'
    )

    with patch.object(share_url, "_get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        with patch.object(share_url, "_get_current_ref", return_value="main"):
            result = write_marketstall(tmp_path)

    assert result.pypi_url is None
    assert "recommended" not in (tmp_path / "README.md").read_text()
