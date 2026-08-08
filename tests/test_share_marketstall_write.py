"""The marketstall walk and write, split out of share_save_repo."""

from pathlib import Path

import pytest
import toml

from haywire.core.publishing import NoBarnError, build_marketstall_entries, write_marketstall

pytestmark = pytest.mark.unit


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo with two barn libraries and a root README carrying the marker pair."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    for name, version in (("haybale-alpha", "0.3.1"), ("haybale-beta", "0.3.1")):
        lib = repo / "barn" / name
        (lib / name.replace("-", "_")).mkdir(parents=True)
        (lib / "pyproject.toml").write_text(
            f'[project]\nname = "{name}"\nversion = "{version}"\ndescription = "d"\n'
        )
        (lib / "README.md").write_text(
            "# lib\n<!-- marketstall:share-url:start -->\nold\n<!-- marketstall:share-url:end -->\n"
        )
    (repo / "README.md").write_text(
        "# root\n<!-- marketstall:share-url:start -->\nold\n<!-- marketstall:share-url:end -->\n"
    )
    return repo


def test_build_entries_covers_every_barn_library(repo: Path) -> None:
    """The feed's contract is 'every haybale this repo offers' — a partial
    rebuild would silently delete sibling entries."""
    entries = build_marketstall_entries(repo)
    assert sorted(e["name"] for e in entries) == ["haybale-alpha", "haybale-beta"]


def test_build_entries_skips_dirs_without_pyproject(repo: Path) -> None:
    (repo / "barn" / "scratch").mkdir()
    assert len(build_marketstall_entries(repo)) == 2


def test_build_entries_without_barn_raises(tmp_path: Path) -> None:
    with pytest.raises(NoBarnError):
        build_marketstall_entries(tmp_path)


def test_write_marketstall_writes_the_feed(repo: Path) -> None:
    result = write_marketstall(repo)
    assert result.out_path == repo / "marketstall.toml"
    data = toml.loads(result.out_path.read_text())
    assert sorted(p["name"] for p in data["haybales"]) == ["haybale-alpha", "haybale-beta"]


def test_write_marketstall_runs_no_drift_gate(repo: Path, monkeypatch) -> None:
    """Drift is step 2's decision. A second gate here would re-ask a settled question."""
    from haywire.core import publishing

    def _boom(*_a, **_kw):
        raise AssertionError("write_marketstall must not run the drift gate")

    monkeypatch.setattr(publishing, "detect_share_drift", _boom)
    write_marketstall(repo)  # must not raise


def test_write_marketstall_reports_every_written_path(repo: Path) -> None:
    """Step 5 stages exactly what it's told; a missed README ships a stale URL."""
    result = write_marketstall(repo)
    names = {p.name for p in result.written}
    assert "marketstall.toml" in names
    # No git remote in this fixture, so no URL is derivable and no README is rewritten.
    assert result.share_url is None
    assert result.warning is not None


def test_write_marketstall_skips_readmes_when_asked(repo: Path) -> None:
    result = write_marketstall(repo, update_readme=False)
    assert result.readmes == []


def test_written_property_puts_the_feed_first(repo: Path) -> None:
    result = write_marketstall(repo, update_readme=False)
    assert result.written[0] == result.out_path


def _add_lib(repo: Path, name: str, *, decorator: str, pyproject_extra: str = "") -> None:
    """Add a barn library whose __init__.py carries a given decorator block."""
    lib = repo / "barn" / name
    module = lib / name.replace("-", "_")
    module.mkdir(parents=True)
    (lib / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "0.1.0"\ndescription = "d"\n{pyproject_extra}'
    )
    (module / "__init__.py").write_text(decorator)


def _entry(repo: Path, name: str) -> dict:
    return next(e for e in build_marketstall_entries(repo) if e["name"] == name)


def _decorator(lib_id: str, os_values: list[str] | None = None) -> str:
    """A decorator block as ruff format writes it — double-quoted, one kwarg per line."""
    os_line = f"    os={os_values!r},\n".replace("'", '"') if os_values is not None else ""
    return f'@library(\n    id="{lib_id}",\n    label="{lib_id.title()}",\n{os_line})\nclass Library: ...\n'


def test_os_read_from_the_decorator(repo: Path) -> None:
    """os moved from [tool.haywire] to the decorator in migration step 7."""
    _add_lib(
        repo,
        "haybale-demo",
        decorator=_decorator("demo", ["macos", "linux"]),
    )
    assert sorted(_entry(repo, "haybale-demo")["os"]) == ["linux", "macos"]


def test_os_falls_back_to_tool_haywire(repo: Path) -> None:
    """Libraries not yet migrated still declare it in pyproject."""
    _add_lib(
        repo,
        "haybale-old",
        decorator=_decorator("old"),
        pyproject_extra='\n[tool.haywire]\nos = ["windows"]\n',
    )
    assert _entry(repo, "haybale-old")["os"] == ["windows"]


def test_decorator_os_wins_over_pyproject(repo: Path) -> None:
    """A migrated library that still carries the old key must not read the stale one."""
    _add_lib(
        repo,
        "haybale-both",
        decorator=_decorator("both", ["linux"]),
        pyproject_extra='\n[tool.haywire]\nos = ["windows"]\n',
    )
    assert _entry(repo, "haybale-both")["os"] == ["linux"]


def test_unknown_decorator_os_value_is_dropped(repo: Path) -> None:
    """_get_decorator_list_field converts `_` to `-`; the filter stops the mangled
    value reaching a feed row, where it would gate installation on a platform
    name nothing matches."""
    _add_lib(
        repo,
        "haybale-typo",
        decorator=_decorator("typo", ["mac_os", "linux"]),
    )
    assert _entry(repo, "haybale-typo")["os"] == ["linux"]
