"""Entry parsers — single-entry dict-to-dataclass conversions."""

from __future__ import annotations

from pathlib import Path

import pytest

from haywire.core.marketstall.errors import MalformedMarketplaceError


@pytest.mark.unit
def test_parse_haybale_entry_minimal() -> None:
    from haywire.core.marketstall.parsing import _parse_haybale_entry

    raw = {"name": "haybale-foo", "min_version": "0.1.0"}
    h = _parse_haybale_entry(raw)
    assert h.name == "haybale-foo"
    assert h.min_version == "0.1.0"
    assert h.os == []


@pytest.mark.unit
def test_parse_haybale_entry_full() -> None:
    from haywire.core.marketstall.parsing import _parse_haybale_entry

    raw = {
        "name": "haybale-vision",
        "min_version": "0.2.0",
        "label": "Vision",
        "description": "X",
        "author": "Alice",
        "source": "git",
        "install_spec": "haybale-vision @ git+...",
        "tags": ["vision"],
        "os": ["macos", "linux"],
        "dependencies": ["haybale-core"],
        "source_url": "https://x.example",
        "docs_url": "https://x.example/docs",
        "via": "https://feed.example",
        "last_seen": "2026-05-20T00:00:00Z",
        "stale": True,
    }
    h = _parse_haybale_entry(raw)
    assert h.os == ["macos", "linux"]
    assert h.stale is True
    assert h.via == "https://feed.example"


@pytest.mark.unit
def test_parse_haybale_entry_missing_name_raises() -> None:
    from haywire.core.marketstall.parsing import _parse_haybale_entry

    with pytest.raises(MalformedMarketplaceError, match="name"):
        _parse_haybale_entry({"min_version": "0.1.0"})


@pytest.mark.unit
def test_parse_subscription_minimal() -> None:
    from haywire.core.marketstall.parsing import _parse_subscription

    raw = {"url": "https://x.example/m.toml"}
    sub = _parse_subscription(raw, "markets")
    assert sub.url == "https://x.example/m.toml"
    assert sub.ignores == []
    assert sub.doubles == []
    assert sub.blocked == []


@pytest.mark.unit
def test_parse_subscription_with_blocked() -> None:
    from haywire.core.marketstall.parsing import _parse_subscription

    raw = {
        "url": "https://x.example/m.toml",
        "ignores": ["haybale-skip"],
        "doubles": [],
        "blocked": ["haybale-untrusted"],
    }
    sub = _parse_subscription(raw, "stalls")
    assert sub.ignores == ["haybale-skip"]
    assert sub.blocked == ["haybale-untrusted"]


@pytest.mark.unit
def test_parse_subscription_missing_url_raises() -> None:
    from haywire.core.marketstall.parsing import _parse_subscription

    with pytest.raises(MalformedMarketplaceError, match="url"):
        _parse_subscription({}, "markets")


@pytest.mark.unit
def test_parse_heap_entry_minimal() -> None:
    from haywire.core.marketstall.parsing import _parse_heap_entry

    raw = {"name": "haybale-my-project", "path": "/abs/path"}
    out = _parse_heap_entry(raw)
    assert out["name"] == "haybale-my-project"
    assert out["path"] == "/abs/path"


@pytest.mark.unit
def test_parse_heap_entry_missing_name_raises() -> None:
    from haywire.core.marketstall.parsing import _parse_heap_entry

    with pytest.raises(MalformedMarketplaceError, match="name"):
        _parse_heap_entry({"path": "/p"})


@pytest.mark.unit
def test_parse_heap_entry_missing_path_raises() -> None:
    from haywire.core.marketstall.parsing import _parse_heap_entry

    with pytest.raises(MalformedMarketplaceError, match="path"):
        _parse_heap_entry({"name": "x"})


@pytest.mark.unit
def test_parse_global_marketplace_empty_file_returns_empty(tmp_path: Path) -> None:
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "marketplace.toml"
    f.write_text("")
    mf = parse_global_marketplace(f)
    assert mf.markets == []
    assert mf.stalls == []
    assert mf.haybales == []


@pytest.mark.unit
def test_parse_global_marketplace_missing_file_returns_empty(tmp_path: Path) -> None:
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "does-not-exist.toml"
    mf = parse_global_marketplace(f)
    assert mf.markets == []


@pytest.mark.unit
def test_parse_global_marketplace_all_three_sections(tmp_path: Path) -> None:
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "marketplace.toml"
    f.write_text(
        "[[markets]]\n"
        'url = "https://aggregator.example/marketplace.toml"\n'
        "ignores = []\n"
        "doubles = []\n"
        "blocked = []\n"
        "\n"
        "[[stalls]]\n"
        'url = "https://alice.example/marketstall.toml"\n'
        'ignores = ["haybale-skip"]\n'
        "doubles = []\n"
        'blocked = ["haybale-untrusted"]\n'
        "\n"
        "[[haybales]]\n"
        'name = "haybale-inline"\n'
        'min_version = "0.1.0"\n'
    )
    mf = parse_global_marketplace(f)
    assert len(mf.markets) == 1
    assert mf.markets[0].url == "https://aggregator.example/marketplace.toml"
    assert len(mf.stalls) == 1
    assert mf.stalls[0].blocked == ["haybale-untrusted"]
    assert len(mf.haybales) == 1
    assert mf.haybales[0].name == "haybale-inline"


@pytest.mark.unit
def test_parse_global_marketplace_malformed_toml_raises(tmp_path: Path) -> None:
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "marketplace.toml"
    f.write_text("this is = not valid TOML [[")
    with pytest.raises(MalformedMarketplaceError):
        parse_global_marketplace(f)


@pytest.mark.unit
def test_parse_project_marketplace_empty_returns_empty(tmp_path: Path) -> None:
    from haywire.core.marketstall.parsing import parse_project_marketplace

    f = tmp_path / "marketplace.toml"
    f.write_text("")
    pm = parse_project_marketplace(f)
    assert pm.heaps == []
    assert pm.caches == []


@pytest.mark.unit
def test_parse_project_marketplace_both_sections(tmp_path: Path) -> None:
    from haywire.core.marketstall.parsing import parse_project_marketplace

    f = tmp_path / "marketplace.toml"
    f.write_text(
        "[[heaps]]\n"
        'name = "haybale-my-project"\n'
        'path = "/abs/path/to/proj"\n'
        'label = "My Project"\n'
        "\n"
        "[[caches]]\n"
        'name = "haybale-foo"\n'
        'min_version = "0.1.0"\n'
        'via = "https://feed.example/marketstall.toml"\n'
        'last_seen = "2026-05-20T00:00:00Z"\n'
        "stale = false\n"
    )
    pm = parse_project_marketplace(f)
    assert len(pm.heaps) == 1
    assert pm.heaps[0]["name"] == "haybale-my-project"
    assert len(pm.caches) == 1
    assert pm.caches[0].via == "https://feed.example/marketstall.toml"
    assert pm.caches[0].stale is False


@pytest.mark.unit
def test_parse_project_marketplace_drops_global_only_sections(tmp_path: Path) -> None:
    """[[markets]] and [[stalls]] don't belong in a project file; silently dropped."""
    from haywire.core.marketstall.parsing import parse_project_marketplace

    f = tmp_path / "marketplace.toml"
    f.write_text('[[markets]]\nurl = "https://x.example/m.toml"\nignores = []\ndoubles = []\nblocked = []\n')
    pm = parse_project_marketplace(f)
    # No markets attribute exists on ProjectMarketplaceFile; the section is silently skipped.
    assert pm.heaps == []
    assert pm.caches == []


@pytest.mark.unit
def test_parse_marketstall_body_haybales_only() -> None:
    from haywire.core.marketstall.parsing import parse_marketstall_body

    body = '[[haybales]]\nname = "haybale-foo"\nmin_version = "0.1.0"\n'
    haybales = parse_marketstall_body(body)
    assert len(haybales) == 1
    assert haybales[0].name == "haybale-foo"


@pytest.mark.unit
def test_parse_marketstall_body_silently_drops_extra_sections() -> None:
    """A marketstall must not contain [[markets]] etc.; if it does, drop them silently per §2."""
    from haywire.core.marketstall.parsing import parse_marketstall_body

    body = (
        "[[markets]]\n"
        'url = "https://x.example/m.toml"\n'
        "ignores = []\n"
        "doubles = []\n"
        "blocked = []\n"
        "\n"
        "[[haybales]]\n"
        'name = "haybale-foo"\n'
        'min_version = "0.1.0"\n'
    )
    haybales = parse_marketstall_body(body)
    assert len(haybales) == 1
    assert haybales[0].name == "haybale-foo"


@pytest.mark.unit
def test_parse_marketstall_body_malformed_returns_empty() -> None:
    from haywire.core.marketstall.parsing import parse_marketstall_body

    assert parse_marketstall_body("not valid toml [[") == []


@pytest.mark.unit
def test_parse_remote_marketplace_body_collects_stalls_and_haybales() -> None:
    from haywire.core.marketstall.parsing import parse_remote_marketplace_body

    body = (
        "[[stalls]]\n"
        'url = "https://going-haywire.github.io/haywire/stalls/haybale-core.toml"\n'
        "ignores = []\n"
        "doubles = []\n"
        "blocked = []\n"
        "\n"
        "[[haybales]]\n"
        'name = "haybale-inline"\n'
        'min_version = "0.2.0"\n'
    )
    contents = parse_remote_marketplace_body(body)
    assert len(contents.stall_urls) == 1
    assert contents.stall_urls[0] == "https://going-haywire.github.io/haywire/stalls/haybale-core.toml"
    assert len(contents.haybales) == 1
    assert contents.haybales[0].name == "haybale-inline"


@pytest.mark.unit
def test_parse_remote_marketplace_body_ignores_nested_markets() -> None:
    """One-level-deep resolution per §8.1: [[markets]] in a remote marketplace are dropped."""
    from haywire.core.marketstall.parsing import parse_remote_marketplace_body

    body = (
        "[[markets]]\n"
        'url = "https://other-aggregator.example/marketplace.toml"\n'
        "ignores = []\n"
        "doubles = []\n"
        "blocked = []\n"
    )
    contents = parse_remote_marketplace_body(body)
    assert contents.stall_urls == []
    assert contents.haybales == []


@pytest.mark.unit
def test_parse_remote_marketplace_body_malformed_returns_empty() -> None:
    from haywire.core.marketstall.parsing import parse_remote_marketplace_body

    contents = parse_remote_marketplace_body("not valid toml [[")
    assert contents.stall_urls == []
    assert contents.haybales == []


@pytest.mark.unit
def test_serialize_global_marketplace_empty_returns_empty_string() -> None:
    from haywire.core.marketstall.parsing import serialize_global_marketplace
    from haywire.core.marketstall.types import MarketplaceFile

    assert serialize_global_marketplace(MarketplaceFile()) == ""


@pytest.mark.unit
def test_serialize_global_marketplace_emits_blocked_field() -> None:
    from haywire.core.marketstall.parsing import serialize_global_marketplace
    from haywire.core.marketstall.types import MarketplaceFile, Subscription

    mf = MarketplaceFile(
        stalls=[
            Subscription(
                url="https://alice.example/marketstall.toml",
                ignores=["haybale-skip"],
                blocked=["haybale-untrusted"],
            )
        ]
    )
    out = serialize_global_marketplace(mf)
    assert "[[stalls]]" in out
    assert "alice.example/marketstall.toml" in out
    assert "haybale-skip" in out
    assert "haybale-untrusted" in out
    assert "blocked" in out


@pytest.mark.unit
def test_serialize_global_marketplace_roundtrip(tmp_path: Path) -> None:
    from haywire.core.marketstall.parsing import (
        parse_global_marketplace,
        serialize_global_marketplace,
    )
    from haywire.core.marketstall.types import Haybale, MarketplaceFile, Subscription

    original = MarketplaceFile(
        markets=[Subscription(url="https://agg.example/marketplace.toml")],
        stalls=[
            Subscription(
                url="https://alice.example/marketstall.toml",
                ignores=["haybale-skip"],
                blocked=["haybale-untrusted"],
            )
        ],
        haybales=[Haybale(name="haybale-inline", min_version="0.1.0")],
    )

    f = tmp_path / "marketplace.toml"
    f.write_text(serialize_global_marketplace(original))
    reparsed = parse_global_marketplace(f)
    assert reparsed.markets[0].url == original.markets[0].url
    assert reparsed.stalls[0].blocked == original.stalls[0].blocked
    assert reparsed.haybales[0].name == "haybale-inline"


@pytest.mark.unit
def test_serialize_project_marketplace_roundtrip(tmp_path: Path) -> None:
    from haywire.core.marketstall.parsing import (
        parse_project_marketplace,
        serialize_project_marketplace,
    )
    from haywire.core.marketstall.types import Haybale, ProjectMarketplaceFile

    original = ProjectMarketplaceFile(
        heaps=[{"name": "haybale-x", "path": "/abs/path/x"}],
        caches=[
            Haybale(
                name="haybale-foo",
                min_version="0.1.0",
                via="https://feed.example/marketstall.toml",
                last_seen="2026-05-20T00:00:00Z",
                stale=False,
            )
        ],
    )

    f = tmp_path / "marketplace.toml"
    f.write_text(serialize_project_marketplace(original))
    reparsed = parse_project_marketplace(f)
    assert reparsed.heaps[0]["name"] == "haybale-x"
    assert reparsed.caches[0].via == "https://feed.example/marketstall.toml"
