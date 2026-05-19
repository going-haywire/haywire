"""Tests for MarketplaceEntry, including the cache-shape fields added in Plan E."""

from __future__ import annotations

import pytest

from haywire.core.marketplace import MarketplaceEntry


@pytest.mark.unit
def test_marketplace_entry_has_cache_shape_fields() -> None:
    """Plan E adds via, last_seen, and stale fields for the project-cache shape."""
    entry = MarketplaceEntry(
        name="haybale-foo",
        min_version="0.0.1",
        via="https://example.com/marketstall.toml",
        last_seen="2026-05-19T12:00:00Z",
        stale=True,
    )
    assert entry.via == "https://example.com/marketstall.toml"
    assert entry.last_seen == "2026-05-19T12:00:00Z"
    assert entry.stale is True


@pytest.mark.unit
def test_marketplace_entry_cache_fields_default_falsy() -> None:
    entry = MarketplaceEntry(name="haybale-foo", min_version="0.0.1")
    assert entry.via == ""
    assert entry.last_seen == ""
    assert entry.stale is False


@pytest.mark.unit
def test_to_dict_omits_falsy_cache_fields() -> None:
    """The existing 'skip empty/default' to_dict() rule must apply to the new fields too,
    so Plan B's generator and Plan D's share --save output don't gain via/last_seen/stale keys."""
    entry = MarketplaceEntry(name="haybale-foo", min_version="0.0.1")
    d = entry.to_dict()
    assert "via" not in d
    assert "last_seen" not in d
    assert "stale" not in d


@pytest.mark.unit
def test_to_dict_includes_via_when_set() -> None:
    entry = MarketplaceEntry(
        name="haybale-foo",
        min_version="0.0.1",
        via="https://example.com/marketstall.toml",
    )
    d = entry.to_dict()
    assert d.get("via") == "https://example.com/marketstall.toml"


@pytest.mark.unit
def test_to_dict_includes_stale_true_but_omits_stale_false() -> None:
    """stale=True must serialize; stale=False is the default and is omitted."""
    stale_entry = MarketplaceEntry(name="haybale-foo", min_version="0.0.1", stale=True)
    fresh_entry = MarketplaceEntry(name="haybale-foo", min_version="0.0.1", stale=False)
    assert stale_entry.to_dict().get("stale") is True
    assert "stale" not in fresh_entry.to_dict()
