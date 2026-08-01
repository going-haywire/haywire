"""The marketstall walk and write, split out of share_save_repo."""

from pathlib import Path

import pytest
import toml

from haywire_studio.packaging.share import NoBarnError, build_marketstall_entries, write_marketstall

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
    from haywire_studio.packaging import share

    def _boom(*_a, **_kw):
        raise AssertionError("write_marketstall must not run the drift gate")

    monkeypatch.setattr(share, "detect_share_drift", _boom)
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
