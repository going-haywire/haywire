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


# ─────────────────────────────────────────────────────────────────────────────
# Round-trip: what this publisher writes, the consumer's parser must accept.
#
# `haywire share` shipped marketstalls in which every string field was a
# character array — `version = ["0", ".", "0", ".", "3", "6"]`. `read_toml`
# parses with tomlkit, whose `String` subclasses `str`, so every
# `isinstance(v, str)` guard admitted it; `toml.dumps` then serialized the
# subclass as a sequence. The file was valid TOML the whole way, so nothing
# upstream complained — and `parsing.py` rejected the feed on subscribe.
#
# The absent test was this one: writing and re-reading in the same breath.
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def repo_with_haybale_toml(repo: Path) -> Path:
    """`repo`, with a real haybale.toml — the canon source the writer reads.

    The bare `repo` fixture declares metadata only in pyproject, so `read_haybale`
    returns an empty row and the tomlkit path is never exercised.
    """
    module_dir = repo / "barn" / "haybale-alpha" / "haybale_alpha"
    # find_module_dir() keys off __init__.py; without it the writer falls back
    # to a bare Haybale and never reads the file this test is about.
    (module_dir / "__init__.py").touch()
    (module_dir / "haybale.toml").write_text(
        'name = "haybale-alpha"\n'
        'id = "alpha"\n'
        'label = "Alpha"\n'
        'version = "0.3.1"\n'
        'description = "First library"\n'
        'on_reload = "restart"\n'
        'tags = ["vision", "camera"]\n'
        'os = ["macos", "linux"]\n'
        'linked_libraries = ["haybale_core"]\n'
        'origin = "https://github.com/acme/haybale-alpha"\n'
        'origin_provider = "github"\n'
        "\n"
        "[[authors]]\n"
        'name = "acme"\n'
        'url = "https://acme.example"\n'
    )
    return repo


def test_written_marketstall_parses_back(repo_with_haybale_toml: Path) -> None:
    """The feed this writes must survive the parser a subscriber runs on it."""
    from haywire.core.marketstall.parsing import parse_global_marketplace

    result = write_marketstall(repo_with_haybale_toml, update_readme=False)
    parsed = parse_global_marketplace(result.out_path)

    row = next(h for h in parsed.haybales if h.name == "haybale-alpha")
    assert row.version == "0.3.1"
    assert row.label == "Alpha"
    assert row.description == "First library"
    assert row.tags == ["vision", "camera"]
    assert row.os == ["macos", "linux"]
    assert row.linked_libraries == ["haybale_core"]
    assert row.origin == "https://github.com/acme/haybale-alpha"
    assert row.authors == [("acme", "https://acme.example")]


def test_written_fields_are_exactly_str_not_a_subclass(repo_with_haybale_toml: Path) -> None:
    """`type(...) is str`, not `isinstance`.

    tomlkit's String passes `isinstance(v, str)`, which is precisely why the
    corruption reached a published feed. An isinstance assertion here would
    have gone green against the broken writer.
    """
    result = write_marketstall(repo_with_haybale_toml, update_readme=False)
    raw = toml.loads(result.out_path.read_text())
    entry = next(e for e in raw["haybales"] if e["name"] == "haybale-alpha")

    for field in ("name", "label", "version", "description", "origin", "origin_provider"):
        assert type(entry[field]) is str, f"{field} serialized as {type(entry[field]).__name__}"
    for field in ("tags", "os", "linked_libraries"):
        assert all(type(v) is str for v in entry[field]), f"{field} holds non-str items"
