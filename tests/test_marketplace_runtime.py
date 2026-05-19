"""Tests for the two-tier marketplace runtime (spec §6)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from haywire.core.marketplace_runtime import (
    FetchResult,
    GlobalMarketplace,  # noqa: F401  # re-exported for downstream test modules
    MarketplaceEntry,
    ProjectMarketplace,  # noqa: F401  # re-exported for downstream test modules
    RemoteMarketplaceContents,
    RemoteSubscription,  # noqa: F401  # re-exported for downstream test modules
    _cache_path,
    _url_hash,
    cache_read,
    cache_write,
    fetch_with_cache_fallback,
    parse_global_marketplace,
    parse_marketstall_body,
    parse_project_marketplace,
    parse_remote_marketplace_body,
    serialize_global_marketplace,
    serialize_project_marketplace,
)
from haywire.core.marketplace_errors import MalformedGlobalMarketplaceError, RemoteFetchError


@pytest.mark.unit
def test_parse_empty_global(tmp_path: Path) -> None:
    """Empty file → empty GlobalMarketplace with all four sections empty."""
    f = tmp_path / "marketplace.toml"
    f.write_text("")
    gm = parse_global_marketplace(f)
    assert gm.marketplaces == []
    assert gm.marketstalls == []
    assert gm.packages == []
    assert gm.locals_ == []


@pytest.mark.unit
def test_parse_marketplaces_section(tmp_path: Path) -> None:
    f = tmp_path / "marketplace.toml"
    f.write_text(
        "[[marketplaces]]\n"
        'url = "https://maybites.github.io/haywire/marketplace.toml"\n'
        "ignores = []\n"
        "doubles = []\n"
    )
    gm = parse_global_marketplace(f)
    assert len(gm.marketplaces) == 1
    sub = gm.marketplaces[0]
    assert sub.url == "https://maybites.github.io/haywire/marketplace.toml"
    assert sub.ignores == []
    assert sub.doubles == []


@pytest.mark.unit
def test_parse_marketstalls_section(tmp_path: Path) -> None:
    f = tmp_path / "marketplace.toml"
    f.write_text(
        "[[marketstalls]]\n"
        'url = "https://author.example/marketstall.toml"\n'
        'ignores = ["haybale-skip"]\n'
        'doubles = ["haybale-double"]\n'
    )
    gm = parse_global_marketplace(f)
    assert len(gm.marketstalls) == 1
    sub = gm.marketstalls[0]
    assert sub.url == "https://author.example/marketstall.toml"
    assert sub.ignores == ["haybale-skip"]
    assert sub.doubles == ["haybale-double"]


@pytest.mark.unit
def test_parse_packages_section(tmp_path: Path) -> None:
    """Direct [[packages]] entries match the §7 MarketplaceEntry schema."""
    f = tmp_path / "marketplace.toml"
    f.write_text(
        "[[packages]]\n"
        'name = "haybale-foo"\n'
        'min_version = "0.0.1"\n'
        'source = "git"\n'
        'install_spec = "haybale-foo @ git+https://x.example/r.git"\n'
    )
    gm = parse_global_marketplace(f)
    assert len(gm.packages) == 1
    pkg = gm.packages[0]
    assert pkg.name == "haybale-foo"
    assert pkg.source == "git"


@pytest.mark.unit
def test_parse_locals_section(tmp_path: Path) -> None:
    """[[locals]] entries match Plan D's schema: name + path + optional metadata."""
    f = tmp_path / "marketplace.toml"
    f.write_text(
        "[[locals]]\n"
        'name = "haybale-my-project"\n'
        'path = "/Users/x/code/proj/barn/haybale-my-project"\n'
        'label = "My Project"\n'
    )
    gm = parse_global_marketplace(f)
    assert len(gm.locals_) == 1
    local = gm.locals_[0]
    assert local["name"] == "haybale-my-project"
    assert local["path"] == "/Users/x/code/proj/barn/haybale-my-project"
    assert local.get("label") == "My Project"


@pytest.mark.unit
def test_parse_all_four_sections(tmp_path: Path) -> None:
    """A realistic global file has all four sections mixed together."""
    f = tmp_path / "marketplace.toml"
    f.write_text(
        "[[marketplaces]]\n"
        'url = "https://maybites.github.io/haywire/marketplace.toml"\n'
        "\n"
        "[[marketstalls]]\n"
        'url = "https://author.example/marketstall.toml"\n'
        "\n"
        "[[packages]]\n"
        'name = "haybale-direct"\n'
        'min_version = "0.0.1"\n'
        "\n"
        "[[locals]]\n"
        'name = "haybale-local"\n'
        'path = "/tmp/local"\n'
    )
    gm = parse_global_marketplace(f)
    assert len(gm.marketplaces) == 1
    assert len(gm.marketstalls) == 1
    assert len(gm.packages) == 1
    assert len(gm.locals_) == 1


@pytest.mark.unit
def test_parse_malformed_toml_raises(tmp_path: Path) -> None:
    """A malformed TOML file raises MalformedGlobalMarketplaceError."""
    f = tmp_path / "marketplace.toml"
    f.write_text('this is = "not valid TOML\nbecause unterminated string')
    with pytest.raises(MalformedGlobalMarketplaceError) as exc_info:
        parse_global_marketplace(f)
    assert "marketplace.toml" in str(exc_info.value)


@pytest.mark.unit
def test_parse_duplicate_locals_raises(tmp_path: Path) -> None:
    """Two [[locals]] with the same name is the G5 collision — refused at parse time."""
    f = tmp_path / "marketplace.toml"
    f.write_text(
        '[[locals]]\nname = "haybale-foo"\npath = "/tmp/a"\n\n'
        '[[locals]]\nname = "haybale-foo"\npath = "/tmp/b"\n'
    )
    with pytest.raises(MalformedGlobalMarketplaceError) as exc_info:
        parse_global_marketplace(f)
    assert "haybale-foo" in str(exc_info.value)


@pytest.mark.unit
def test_parse_duplicate_packages_raises(tmp_path: Path) -> None:
    """Two [[packages]] with the same name — refused at parse time."""
    f = tmp_path / "marketplace.toml"
    f.write_text(
        '[[packages]]\nname = "haybale-foo"\nmin_version = "0.0.1"\n\n'
        '[[packages]]\nname = "haybale-foo"\nmin_version = "0.0.2"\n'
    )
    with pytest.raises(MalformedGlobalMarketplaceError) as exc_info:
        parse_global_marketplace(f)
    assert "haybale-foo" in str(exc_info.value)


@pytest.mark.unit
def test_parse_missing_file_returns_empty(tmp_path: Path) -> None:
    """A non-existent path returns an empty GlobalMarketplace (caller decides what to do)."""
    gm = parse_global_marketplace(tmp_path / "does-not-exist.toml")
    assert gm.marketplaces == [] and gm.marketstalls == []
    assert gm.packages == [] and gm.locals_ == []


@pytest.mark.unit
def test_parse_project_marketplace_empty(tmp_path: Path) -> None:
    f = tmp_path / "marketplace.toml"
    f.write_text("")
    pm = parse_project_marketplace(f)
    assert isinstance(pm, ProjectMarketplace)
    assert pm.locals_ == []
    assert pm.packages == []


@pytest.mark.unit
def test_parse_project_marketplace_locals_and_packages(tmp_path: Path) -> None:
    f = tmp_path / "marketplace.toml"
    f.write_text(
        "[[locals]]\n"
        'name = "haybale-my-project"\n'
        'path = "/tmp/proj/barn/haybale-my-project"\n'
        "\n"
        "[[packages]]\n"
        'name = "haybale-cached"\n'
        'min_version = "0.0.1"\n'
        'source = "git"\n'
        'install_spec = "haybale-cached @ git+https://x.example/r.git"\n'
        'via = "https://author.example/marketstall.toml"\n'
    )
    pm = parse_project_marketplace(f)
    assert len(pm.locals_) == 1
    assert pm.locals_[0]["name"] == "haybale-my-project"
    assert len(pm.packages) == 1
    assert pm.packages[0].via == "https://author.example/marketstall.toml"


@pytest.mark.unit
def test_parse_project_marketplace_stale_entry(tmp_path: Path) -> None:
    f = tmp_path / "marketplace.toml"
    f.write_text(
        "[[packages]]\n"
        'name = "haybale-stale-pkg"\n'
        'min_version = "0.0.1"\n'
        'source = "git"\n'
        'install_spec = "haybale-stale-pkg @ git+https://x.example/r.git"\n'
        "stale = true\n"
        'last_seen = "2026-05-10T08:00:00Z"\n'
    )
    pm = parse_project_marketplace(f)
    assert len(pm.packages) == 1
    assert pm.packages[0].stale is True
    assert pm.packages[0].last_seen == "2026-05-10T08:00:00Z"


@pytest.mark.unit
def test_parse_project_marketplace_ignores_marketplaces_marketstalls(tmp_path: Path) -> None:
    """Per spec §6: project marketplace has no [[marketplaces]] or [[marketstalls]] sections.
    If the file accidentally contains them, the parser silently ignores them (no error)."""
    f = tmp_path / "marketplace.toml"
    f.write_text(
        "[[marketplaces]]\n"
        'url = "https://x.example/m.toml"\n'
        "\n"
        "[[locals]]\n"
        'name = "haybale-foo"\n'
        'path = "/tmp/foo"\n'
    )
    pm = parse_project_marketplace(f)
    assert len(pm.locals_) == 1


@pytest.mark.unit
def test_parse_project_marketplace_missing_file(tmp_path: Path) -> None:
    pm = parse_project_marketplace(tmp_path / "does-not-exist.toml")
    assert pm.locals_ == [] and pm.packages == []


@pytest.mark.unit
def test_serialize_empty_global() -> None:
    gm = GlobalMarketplace()
    out = serialize_global_marketplace(gm)
    # Round-trip: serializing an empty GM and re-parsing yields an empty GM.
    import toml as _toml

    parsed = _toml.loads(out)
    assert parsed.get("marketplaces", []) == []
    assert parsed.get("marketstalls", []) == []
    assert parsed.get("packages", []) == []
    assert parsed.get("locals", []) == []


@pytest.mark.unit
def test_serialize_round_trip(tmp_path: Path) -> None:
    """Parse → serialize → parse yields the same GlobalMarketplace."""
    f = tmp_path / "marketplace.toml"
    original = (
        "[[marketplaces]]\n"
        'url = "https://maybites.github.io/haywire/marketplace.toml"\n'
        'ignores = ["haybale-skip"]\n'
        "\n"
        "[[marketstalls]]\n"
        'url = "https://author.example/marketstall.toml"\n'
        "\n"
        "[[packages]]\n"
        'name = "haybale-direct"\n'
        'min_version = "0.0.1"\n'
        "\n"
        "[[locals]]\n"
        'name = "haybale-local"\n'
        'path = "/tmp/local"\n'
        'label = "Local"\n'
    )
    f.write_text(original)

    gm1 = parse_global_marketplace(f)
    serialized = serialize_global_marketplace(gm1)
    f.write_text(serialized)
    gm2 = parse_global_marketplace(f)

    assert len(gm2.marketplaces) == 1
    assert gm2.marketplaces[0].url == gm1.marketplaces[0].url
    assert gm2.marketplaces[0].ignores == ["haybale-skip"]
    assert len(gm2.marketstalls) == 1
    assert len(gm2.packages) == 1
    assert gm2.packages[0].name == "haybale-direct"
    assert len(gm2.locals_) == 1
    assert gm2.locals_[0]["label"] == "Local"


@pytest.mark.unit
def test_serialize_omits_empty_sections() -> None:
    """Only non-empty sections appear in the output."""
    gm = GlobalMarketplace(locals_=[{"name": "haybale-only", "path": "/tmp/x"}])
    out = serialize_global_marketplace(gm)
    assert "[[locals]]" in out
    assert "[[marketplaces]]" not in out
    assert "[[marketstalls]]" not in out
    assert "[[packages]]" not in out


@pytest.mark.unit
def test_serialize_project_marketplace_empty() -> None:
    pm = ProjectMarketplace()
    out = serialize_project_marketplace(pm)
    import toml as _toml

    parsed = _toml.loads(out)
    assert parsed.get("locals", []) == []
    assert parsed.get("packages", []) == []


@pytest.mark.unit
def test_serialize_project_marketplace_round_trip(tmp_path: Path) -> None:
    pm1 = ProjectMarketplace(
        locals_=[{"name": "haybale-proj", "path": "/tmp/proj"}],
        packages=[
            MarketplaceEntry(
                name="haybale-cached",
                min_version="0.0.1",
                source="git",
                install_spec="haybale-cached @ git+https://x.example/r.git",
                via="https://author.example/marketstall.toml",
            )
        ],
    )
    f = tmp_path / "marketplace.toml"
    f.write_text(serialize_project_marketplace(pm1))
    pm2 = parse_project_marketplace(f)
    assert len(pm2.locals_) == 1
    assert pm2.locals_[0]["name"] == "haybale-proj"
    assert len(pm2.packages) == 1
    assert pm2.packages[0].via == "https://author.example/marketstall.toml"


@pytest.mark.unit
def test_serialize_project_marketplace_preserves_stale(tmp_path: Path) -> None:
    pm1 = ProjectMarketplace(
        packages=[
            MarketplaceEntry(
                name="haybale-gone",
                min_version="0.0.1",
                source="git",
                install_spec="haybale-gone @ git+https://x.example/r.git",
                stale=True,
                last_seen="2026-05-10T08:00:00Z",
            )
        ]
    )
    f = tmp_path / "marketplace.toml"
    f.write_text(serialize_project_marketplace(pm1))
    pm2 = parse_project_marketplace(f)
    assert pm2.packages[0].stale is True
    assert pm2.packages[0].last_seen == "2026-05-10T08:00:00Z"


@pytest.mark.unit
def test_url_hash_is_deterministic_and_short() -> None:
    url = "https://maybites.github.io/haywire/marketplace.toml"
    h1 = _url_hash(url)
    h2 = _url_hash(url)
    assert h1 == h2
    assert len(h1) == 16
    assert all(c in "0123456789abcdef" for c in h1)


@pytest.mark.unit
def test_url_hash_differs_per_url() -> None:
    a = _url_hash("https://example.com/a.toml")
    b = _url_hash("https://example.com/b.toml")
    assert a != b


@pytest.mark.unit
def test_cache_path_uses_haywire_cache_dir(tmp_path: Path, monkeypatch) -> None:
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)
    p = _cache_path("https://example.com/m.toml")
    assert p.parent == fake_home / ".haywire" / "cache"
    assert p.name.endswith(".toml")


@pytest.mark.unit
def test_cache_write_then_read_round_trips(tmp_path: Path, monkeypatch) -> None:
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)
    url = "https://example.com/m.toml"
    body = '[[packages]]\nname = "haybale-cached"\nmin_version = "0.0.1"\n'

    cache_write(url, body)
    cached, age_seconds = cache_read(url)
    assert cached == body
    assert age_seconds is not None
    assert age_seconds >= 0
    assert age_seconds < 5  # We just wrote it.


@pytest.mark.unit
def test_cache_read_missing_returns_none(tmp_path: Path, monkeypatch) -> None:
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)
    cached, age_seconds = cache_read("https://example.com/never-cached.toml")
    assert cached is None
    assert age_seconds is None


@pytest.mark.unit
def test_cache_write_overwrites_previous(tmp_path: Path, monkeypatch) -> None:
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)
    url = "https://example.com/m.toml"
    cache_write(url, "old content")
    cache_write(url, "new content")
    cached, _ = cache_read(url)
    assert cached == "new content"


@pytest.mark.unit
def test_fetch_success_caches_and_returns_fresh(tmp_path: Path, monkeypatch) -> None:
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

    body = '[[packages]]\nname = "haybale-x"\nmin_version = "0.0.1"\n'

    class _FakeResponse:
        def __init__(self, content: bytes) -> None:
            self._content = content

        def read(self) -> bytes:
            return self._content

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch("urllib.request.urlopen", return_value=_FakeResponse(body.encode("utf-8"))):
        result = fetch_with_cache_fallback("https://example.com/m.toml")

    assert isinstance(result, FetchResult)
    assert result.body == body
    assert result.from_cache is False
    assert result.cache_age is None

    # The cache file should now exist.
    cached, _ = cache_read("https://example.com/m.toml")
    assert cached == body


@pytest.mark.unit
def test_fetch_failure_falls_back_to_cache(tmp_path: Path, monkeypatch) -> None:
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

    # Pre-populate the cache.
    cache_write("https://example.com/m.toml", "cached body")

    with patch("urllib.request.urlopen", side_effect=OSError("network down")):
        result = fetch_with_cache_fallback("https://example.com/m.toml")

    assert result.body == "cached body"
    assert result.from_cache is True
    assert result.cache_age is not None and result.cache_age >= 0


@pytest.mark.unit
def test_fetch_failure_no_cache_raises(tmp_path: Path, monkeypatch) -> None:
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

    with patch("urllib.request.urlopen", side_effect=OSError("network down")):
        with pytest.raises(RemoteFetchError) as exc_info:
            fetch_with_cache_fallback("https://example.com/never-seen.toml")
    assert "https://example.com/never-seen.toml" in str(exc_info.value)


@pytest.mark.unit
def test_parse_marketstall_body_empty() -> None:
    assert parse_marketstall_body("") == []


@pytest.mark.unit
def test_parse_marketstall_body_single_entry() -> None:
    body = (
        "[[packages]]\n"
        'name = "haybale-foo"\n'
        'min_version = "0.0.1"\n'
        'source = "pypi"\n'
        'install_spec = "haybale-foo"\n'
    )
    entries = parse_marketstall_body(body)
    assert len(entries) == 1
    assert entries[0].name == "haybale-foo"
    assert entries[0].source == "pypi"


@pytest.mark.unit
def test_parse_marketstall_body_malformed_toml_returns_empty() -> None:
    """Malformed body returns an empty list — caller will surface as 'source unavailable'."""
    entries = parse_marketstall_body("not = valid toml = at all")
    assert entries == []


@pytest.mark.unit
def test_parse_marketstall_body_ignores_other_sections() -> None:
    """A marketstall body might accidentally contain [[locals]] or [[marketplaces]] —
    silently ignore everything except [[packages]]."""
    body = (
        "[[locals]]\n"
        'name = "haybale-stray"\n'
        'path = "/tmp/stray"\n'
        "\n"
        "[[packages]]\n"
        'name = "haybale-real"\n'
        'min_version = "0.0.1"\n'
    )
    entries = parse_marketstall_body(body)
    assert len(entries) == 1
    assert entries[0].name == "haybale-real"


@pytest.mark.unit
def test_parse_remote_marketplace_marketstalls_and_packages() -> None:
    body = (
        "[[marketstalls]]\n"
        'url = "https://author.example/marketstall.toml"\n'
        "\n"
        "[[packages]]\n"
        'name = "haybale-direct"\n'
        'min_version = "0.0.1"\n'
    )
    result = parse_remote_marketplace_body(body)
    assert isinstance(result, RemoteMarketplaceContents)
    assert len(result.marketstall_urls) == 1
    assert result.marketstall_urls[0] == "https://author.example/marketstall.toml"
    assert len(result.packages) == 1
    assert result.packages[0].name == "haybale-direct"


@pytest.mark.unit
def test_parse_remote_marketplace_ignores_nested_marketplaces() -> None:
    """Spec §6 line 187: resolution is one-level deep. [[marketplaces]] in a
    remote marketplace are ignored — no recursive chain-following."""
    body = (
        "[[marketplaces]]\n"
        'url = "https://nested.example/recursive.toml"\n'
        "\n"
        "[[marketstalls]]\n"
        'url = "https://author.example/m.toml"\n'
    )
    result = parse_remote_marketplace_body(body)
    assert result.marketstall_urls == ["https://author.example/m.toml"]
    # No assertion on nested marketplaces — they're discarded.


@pytest.mark.unit
def test_parse_remote_marketplace_malformed_returns_empty() -> None:
    result = parse_remote_marketplace_body("not = valid toml at all")
    assert result.marketstall_urls == []
    assert result.packages == []


@pytest.mark.unit
def test_parse_remote_marketplace_empty_body() -> None:
    result = parse_remote_marketplace_body("")
    assert result.marketstall_urls == []
    assert result.packages == []


from haywire.core.marketplace_runtime import apply_ignores  # noqa: E402


@pytest.mark.unit
def test_apply_ignores_drops_matching_names() -> None:
    pkgs = [
        MarketplaceEntry(name="haybale-foo", min_version="0.0.1"),
        MarketplaceEntry(name="haybale-bar", min_version="0.0.1"),
        MarketplaceEntry(name="haybale-baz", min_version="0.0.1"),
    ]
    out = apply_ignores(pkgs, ["haybale-bar"])
    names = [p.name for p in out]
    assert names == ["haybale-foo", "haybale-baz"]


@pytest.mark.unit
def test_apply_ignores_empty_passthrough() -> None:
    pkgs = [MarketplaceEntry(name="haybale-foo", min_version="0.0.1")]
    assert apply_ignores(pkgs, []) == pkgs


@pytest.mark.unit
def test_apply_ignores_drops_all() -> None:
    pkgs = [
        MarketplaceEntry(name="haybale-foo", min_version="0.0.1"),
        MarketplaceEntry(name="haybale-bar", min_version="0.0.1"),
    ]
    assert apply_ignores(pkgs, ["haybale-foo", "haybale-bar"]) == []


from haywire.core.marketplace_runtime import apply_locals_shadow  # noqa: E402


@pytest.mark.unit
def test_locals_shadow_silently_drops_matching_remote() -> None:
    locals_ = [{"name": "haybale-foo", "path": "/tmp/foo"}]
    packages = [
        MarketplaceEntry(name="haybale-foo", min_version="0.0.1"),  # shadowed
        MarketplaceEntry(name="haybale-bar", min_version="0.0.1"),  # kept
    ]
    out = apply_locals_shadow(locals_, packages)
    names = [p.name for p in out]
    assert names == ["haybale-bar"]


@pytest.mark.unit
def test_locals_shadow_no_collision_passthrough() -> None:
    locals_ = [{"name": "haybale-only-local", "path": "/tmp/x"}]
    packages = [MarketplaceEntry(name="haybale-only-remote", min_version="0.0.1")]
    out = apply_locals_shadow(locals_, packages)
    assert [p.name for p in out] == ["haybale-only-remote"]


@pytest.mark.unit
def test_locals_shadow_empty_locals_passthrough() -> None:
    packages = [MarketplaceEntry(name="haybale-foo", min_version="0.0.1")]
    assert apply_locals_shadow([], packages) == packages


from haywire.core.marketplace_runtime import apply_first_come_first_served  # noqa: E402


@pytest.mark.unit
def test_first_come_first_served_keeps_first() -> None:
    """If two entries share a name, the first one wins."""
    pkgs = [
        MarketplaceEntry(name="haybale-foo", min_version="0.0.1", source_label="first"),
        MarketplaceEntry(name="haybale-foo", min_version="0.0.2", source_label="second"),
        MarketplaceEntry(name="haybale-bar", min_version="0.0.1"),
    ]
    out = apply_first_come_first_served(pkgs)
    names = [p.name for p in out]
    assert names == ["haybale-foo", "haybale-bar"]
    foo = next(p for p in out if p.name == "haybale-foo")
    assert foo.source_label == "first"


@pytest.mark.unit
def test_first_come_first_served_no_duplicates_passthrough() -> None:
    pkgs = [
        MarketplaceEntry(name="haybale-foo", min_version="0.0.1"),
        MarketplaceEntry(name="haybale-bar", min_version="0.0.1"),
    ]
    assert apply_first_come_first_served(pkgs) == pkgs


@pytest.mark.unit
def test_first_come_first_served_empty_input() -> None:
    assert apply_first_come_first_served([]) == []


from haywire.core.marketplace_runtime import mark_stale_against_previous  # noqa: E402


@pytest.mark.unit
def test_mark_stale_adds_missing_entries_with_stale_flag() -> None:
    previous = [
        MarketplaceEntry(name="haybale-still-here", min_version="0.0.1"),
        MarketplaceEntry(name="haybale-gone", min_version="0.0.1"),
    ]
    fresh = [
        MarketplaceEntry(name="haybale-still-here", min_version="0.0.2"),  # version updated
        MarketplaceEntry(name="haybale-new", min_version="0.0.1"),
    ]
    out = mark_stale_against_previous(fresh, previous)
    names_to_stale = {p.name: p.stale for p in out}
    assert names_to_stale == {
        "haybale-still-here": False,
        "haybale-new": False,
        "haybale-gone": True,
    }
    gone = next(p for p in out if p.name == "haybale-gone")
    assert gone.last_seen  # non-empty ISO timestamp
    assert gone.last_seen.endswith("Z")


@pytest.mark.unit
def test_mark_stale_preserves_existing_last_seen() -> None:
    """If a package was already stale in the previous cache, keep its original last_seen."""
    previous = [
        MarketplaceEntry(
            name="haybale-old-stale",
            min_version="0.0.1",
            stale=True,
            last_seen="2026-05-10T08:00:00Z",
        ),
    ]
    fresh: list[MarketplaceEntry] = []
    out = mark_stale_against_previous(fresh, previous)
    assert len(out) == 1
    assert out[0].name == "haybale-old-stale"
    assert out[0].stale is True
    assert out[0].last_seen == "2026-05-10T08:00:00Z"


@pytest.mark.unit
def test_mark_stale_returns_fresh_when_previous_empty() -> None:
    fresh = [MarketplaceEntry(name="haybale-foo", min_version="0.0.1")]
    out = mark_stale_against_previous(fresh, [])
    assert out == fresh


from haywire.core.marketplace_runtime import RefreshReport, refresh  # noqa: E402


def _write_global(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _patch_urlopen(monkeypatch, responses: dict[str, str]) -> None:
    """Patch urllib.request.urlopen to return body bytes for known URLs."""

    class _Resp:
        def __init__(self, content: bytes) -> None:
            self._content = content

        def read(self) -> bytes:
            return self._content

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def _fake_urlopen(url, *args, **kwargs):
        if hasattr(url, "full_url"):
            url = url.full_url
        if url in responses:
            return _Resp(responses[url].encode("utf-8"))
        raise OSError(f"unmocked URL: {url}")

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)


@pytest.mark.unit
def test_refresh_writes_resolved_packages_to_project_cache(tmp_path: Path, monkeypatch) -> None:
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

    global_path = fake_home / ".haywire" / "marketplace.toml"
    _write_global(
        global_path,
        '[[marketstalls]]\nurl = "https://author.example/m.toml"\n',
    )

    project_path = tmp_path / "proj" / ".haywire" / "marketplace.toml"
    project_path.parent.mkdir(parents=True)
    project_path.write_text("")  # empty

    _patch_urlopen(
        monkeypatch,
        {
            "https://author.example/m.toml": (
                "[[packages]]\n"
                'name = "haybale-from-author"\n'
                'min_version = "0.0.1"\n'
                'source = "git"\n'
                'install_spec = "haybale-from-author @ git+https://x.example/r.git"\n'
            ),
        },
    )

    report = refresh(global_path, project_path)
    assert isinstance(report, RefreshReport)
    assert report.sources_fetched == 1
    assert report.sources_unavailable == 0

    pm = parse_project_marketplace(project_path)
    names = [p.name for p in pm.packages]
    assert "haybale-from-author" in names


@pytest.mark.unit
def test_refresh_preserves_project_locals(tmp_path: Path, monkeypatch) -> None:
    """[[locals]] in the project marketplace are untouched by refresh."""
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

    global_path = fake_home / ".haywire" / "marketplace.toml"
    _write_global(global_path, "")  # empty global

    project_path = tmp_path / "proj" / ".haywire" / "marketplace.toml"
    project_path.parent.mkdir(parents=True)
    project_path.write_text(
        '[[locals]]\nname = "haybale-my-project"\npath = "/tmp/proj/barn/haybale-my-project"\n'
    )

    refresh(global_path, project_path)

    pm = parse_project_marketplace(project_path)
    assert len(pm.locals_) == 1
    assert pm.locals_[0]["name"] == "haybale-my-project"


@pytest.mark.unit
def test_refresh_one_level_deep_resolution(tmp_path: Path, monkeypatch) -> None:
    """A subscribed remote marketplace's own [[marketplaces]] are NOT followed."""
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

    global_path = fake_home / ".haywire" / "marketplace.toml"
    _write_global(
        global_path,
        '[[marketplaces]]\nurl = "https://aggregator.example/mp.toml"\n',
    )
    project_path = tmp_path / "proj" / ".haywire" / "marketplace.toml"
    project_path.parent.mkdir(parents=True)
    project_path.write_text("")

    _patch_urlopen(
        monkeypatch,
        {
            "https://aggregator.example/mp.toml": (
                # This nested [[marketplaces]] must be IGNORED — one-level deep.
                "[[marketplaces]]\n"
                'url = "https://nested.example/should-not-fetch.toml"\n'
                "\n"
                "[[packages]]\n"
                'name = "haybale-from-aggregator"\n'
                'min_version = "0.0.1"\n'
            ),
            # Note: NO response for nested.example — if refresh tried to fetch
            # it, it would raise OSError("unmocked URL"). The test passing proves
            # the orchestrator stopped at one level deep.
        },
    )

    report = refresh(global_path, project_path)
    assert report.sources_unavailable == 0

    pm = parse_project_marketplace(project_path)
    names = [p.name for p in pm.packages]
    assert "haybale-from-aggregator" in names


@pytest.mark.unit
def test_refresh_remote_failure_counts_unavailable(tmp_path: Path, monkeypatch) -> None:
    """A failed fetch increments sources_unavailable; refresh still succeeds for other sources."""
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

    global_path = fake_home / ".haywire" / "marketplace.toml"
    _write_global(
        global_path,
        "[[marketstalls]]\n"
        'url = "https://ok.example/m.toml"\n'
        "\n"
        "[[marketstalls]]\n"
        'url = "https://broken.example/m.toml"\n',
    )
    project_path = tmp_path / "proj" / ".haywire" / "marketplace.toml"
    project_path.parent.mkdir(parents=True)
    project_path.write_text("")

    _patch_urlopen(
        monkeypatch,
        {
            "https://ok.example/m.toml": ('[[packages]]\nname = "haybale-ok"\nmin_version = "0.0.1"\n'),
            # No response for broken.example → OSError → counts as unavailable.
        },
    )

    report = refresh(global_path, project_path)
    assert report.sources_fetched == 1
    assert report.sources_unavailable == 1

    pm = parse_project_marketplace(project_path)
    names = [p.name for p in pm.packages]
    assert "haybale-ok" in names


@pytest.mark.unit
def test_refresh_marks_disappeared_entries_stale(tmp_path: Path, monkeypatch) -> None:
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

    global_path = fake_home / ".haywire" / "marketplace.toml"
    _write_global(
        global_path,
        '[[marketstalls]]\nurl = "https://author.example/m.toml"\n',
    )
    project_path = tmp_path / "proj" / ".haywire" / "marketplace.toml"
    project_path.parent.mkdir(parents=True)
    # Previous cache has haybale-was-here.
    project_path.write_text(
        "[[packages]]\n"
        'name = "haybale-was-here"\n'
        'min_version = "0.0.1"\n'
        'source = "git"\n'
        'install_spec = "haybale-was-here @ git+https://x.example/r.git"\n'
    )

    # The author's marketstall no longer lists haybale-was-here.
    _patch_urlopen(
        monkeypatch,
        {
            "https://author.example/m.toml": ('[[packages]]\nname = "haybale-new"\nmin_version = "0.0.1"\n'),
        },
    )

    refresh(global_path, project_path)

    pm = parse_project_marketplace(project_path)
    by_name = {p.name: p for p in pm.packages}
    assert "haybale-new" in by_name and by_name["haybale-new"].stale is False
    assert "haybale-was-here" in by_name and by_name["haybale-was-here"].stale is True


from haywire.core.marketplace_errors import DuplicateLocalNameError  # noqa: E402
from haywire.core.marketplace_runtime import add_local_to_global  # noqa: E402


@pytest.mark.unit
def test_add_local_to_global_appends_new_entry(tmp_path: Path) -> None:
    global_path = tmp_path / "marketplace.toml"
    global_path.write_text("")  # empty global

    add_local_to_global(
        global_path,
        name="haybale-my-project",
        path=Path("/tmp/proj/barn/haybale-my-project"),
        label="My Project",
        description="Local library for the my-project project",
    )

    gm = parse_global_marketplace(global_path)
    assert len(gm.locals_) == 1
    assert gm.locals_[0]["name"] == "haybale-my-project"
    assert gm.locals_[0]["path"] == "/tmp/proj/barn/haybale-my-project"
    assert gm.locals_[0].get("label") == "My Project"


@pytest.mark.unit
def test_add_local_to_global_refuses_duplicate(tmp_path: Path) -> None:
    global_path = tmp_path / "marketplace.toml"
    global_path.write_text('[[locals]]\nname = "haybale-existing"\npath = "/tmp/existing"\n')

    with pytest.raises(DuplicateLocalNameError) as exc_info:
        add_local_to_global(
            global_path,
            name="haybale-existing",
            path=Path("/tmp/new"),
        )
    assert "haybale-existing" in str(exc_info.value)
    # Original entry should still be there, unmodified.
    gm = parse_global_marketplace(global_path)
    assert len(gm.locals_) == 1
    assert gm.locals_[0]["path"] == "/tmp/existing"


@pytest.mark.unit
def test_add_local_to_global_preserves_other_sections(tmp_path: Path) -> None:
    """Adding a [[locals]] entry must not touch [[marketplaces]], [[marketstalls]],
    or [[packages]] in the same file."""
    global_path = tmp_path / "marketplace.toml"
    global_path.write_text(
        "[[marketplaces]]\n"
        'url = "https://maybites.github.io/haywire/marketplace.toml"\n'
        "ignores = []\n"
        "doubles = []\n"
    )

    add_local_to_global(
        global_path,
        name="haybale-new",
        path=Path("/tmp/new"),
    )

    gm = parse_global_marketplace(global_path)
    assert len(gm.marketplaces) == 1
    assert gm.marketplaces[0].url == "https://maybites.github.io/haywire/marketplace.toml"
    assert len(gm.locals_) == 1
    assert gm.locals_[0]["name"] == "haybale-new"
