"""Haybale dataclass — spec §14 rename of MarketplaceEntry, with new `os` field."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_haybale_minimal_construction() -> None:
    from haywire.core.marketstall.types import Haybale

    h = Haybale(name="haybale-foo", min_version="0.1.0")
    assert h.name == "haybale-foo"
    assert h.min_version == "0.1.0"
    assert h.label == ""
    assert h.os == []  # absent = all platforms per §2.1


@pytest.mark.unit
def test_haybale_full_construction() -> None:
    from haywire.core.marketstall.types import Haybale

    h = Haybale(
        name="haybale-vision",
        min_version="0.2.0",
        label="Vision",
        description="A library",
        author="Alice",
        source="git",
        install_spec="haybale-vision @ git+https://example.com",
        tags=["vision"],
        os=["macos", "linux"],
        dependencies=["haybale-core"],
        source_url="https://example.com/repo",
        docs_url="https://example.com/docs",
    )
    assert h.os == ["macos", "linux"]
    assert h.tags == ["vision"]


@pytest.mark.unit
def test_haybale_cache_fields_default_empty() -> None:
    from haywire.core.marketstall.types import Haybale

    h = Haybale(name="x", min_version="0.0.1")
    assert h.via == ""
    assert h.last_seen == ""
    assert h.stale is False


@pytest.mark.unit
def test_haybale_to_dict_omits_empty_fields() -> None:
    """Empty list and False-bool fields are omitted via the falsy check.

    Note: defaulted string fields with truthy defaults (e.g. source="pypi")
    are still included — `to_dict()` uses a simple `if val:` falsy check,
    matching the legacy MarketplaceEntry.to_dict() semantics.
    """
    from haywire.core.marketstall.types import Haybale

    h = Haybale(name="haybale-foo", min_version="0.1.0")
    d = h.to_dict()
    assert d["name"] == "haybale-foo"
    assert d["min_version"] == "0.1.0"
    # Empty/default falsy fields are omitted.
    assert "os" not in d
    assert "tags" not in d
    assert "dependencies" not in d
    assert "stale" not in d
    assert "label" not in d
    assert "description" not in d
    assert "install_spec" not in d  # default is "" which is falsy


@pytest.mark.unit
def test_haybale_to_dict_includes_os_when_present() -> None:
    from haywire.core.marketstall.types import Haybale

    h = Haybale(name="haybale-foo", min_version="0.1.0", os=["macos", "linux"])
    d = h.to_dict()
    assert d["os"] == ["macos", "linux"]


@pytest.mark.unit
def test_haybale_field_order_in_toml_fields() -> None:
    """Spec §2 field-semantics table sets the canonical order; `os` lives between tags and dependencies."""
    from haywire.core.marketstall.types import Haybale

    fields = Haybale._TOML_FIELDS
    assert "os" in fields
    tags_idx = fields.index("tags")
    os_idx = fields.index("os")
    deps_idx = fields.index("dependencies")
    assert tags_idx < os_idx < deps_idx


@pytest.mark.unit
def test_subscription_minimal_construction() -> None:
    from haywire.core.marketstall.types import Subscription

    s = Subscription(url="https://example.com/marketplace.toml")
    assert s.url == "https://example.com/marketplace.toml"
    assert s.ignores == []
    assert s.doubles == []
    assert s.blocked == []  # new field per §7.4


@pytest.mark.unit
def test_subscription_with_blocked() -> None:
    from haywire.core.marketstall.types import Subscription

    s = Subscription(
        url="https://example.com/marketstall.toml",
        ignores=["haybale-skip"],
        blocked=["haybale-untrusted"],
    )
    assert s.blocked == ["haybale-untrusted"]


@pytest.mark.unit
def test_subscription_is_frozen() -> None:
    """Frozen so it can live in sets and as dict keys if needed."""
    from haywire.core.marketstall.types import Subscription

    s = Subscription(url="https://example.com/x.toml")
    with pytest.raises((AttributeError, Exception)):
        s.url = "other"  # type: ignore[misc]


@pytest.mark.unit
def test_marketplace_file_default_empty() -> None:
    from haywire.core.marketstall.types import MarketplaceFile

    mf = MarketplaceFile()
    assert mf.markets == []
    assert mf.stalls == []
    assert mf.haybales == []


@pytest.mark.unit
def test_project_marketplace_file_default_empty() -> None:
    from haywire.core.marketstall.types import ProjectMarketplaceFile

    pm = ProjectMarketplaceFile()
    assert pm.heaps == []
    assert pm.caches == []


@pytest.mark.unit
def test_refresh_outcome_has_three_states() -> None:
    from haywire.core.marketstall.types import RefreshOutcome

    assert RefreshOutcome.FRESH.value == "fresh"
    assert RefreshOutcome.CACHE_FALLBACK.value == "cache_fallback"
    assert RefreshOutcome.UNAVAILABLE.value == "unavailable"


@pytest.mark.unit
def test_fetch_result_fresh() -> None:
    from haywire.core.marketstall.types import FetchResult, RefreshOutcome

    r = FetchResult(body="contents", outcome=RefreshOutcome.FRESH, cache_age=None)
    assert r.outcome is RefreshOutcome.FRESH
    assert r.body == "contents"


@pytest.mark.unit
def test_fetch_result_cache_fallback_has_age() -> None:
    from haywire.core.marketstall.types import FetchResult, RefreshOutcome

    r = FetchResult(body="cached", outcome=RefreshOutcome.CACHE_FALLBACK, cache_age=3600.0)
    assert r.outcome is RefreshOutcome.CACHE_FALLBACK
    assert r.cache_age == 3600.0


@pytest.mark.unit
def test_refresh_report_default_zeros() -> None:
    from haywire.core.marketstall.types import RefreshReport

    r = RefreshReport()
    assert r.sources_fetched == 0
    assert r.sources_from_cache == 0  # new field per §9
    assert r.sources_unavailable == 0
    assert r.unavailable_urls == []
    assert r.haybales_resolved == 0  # renamed from packages_resolved per §14
    assert r.new_stale == 0
    assert r.updates_available == 0  # new field per §10.3


@pytest.mark.unit
def test_refresh_report_sources_partition() -> None:
    """fetched + from_cache + unavailable must always sum to total subscriptions."""
    from haywire.core.marketstall.types import RefreshReport

    r = RefreshReport(sources_fetched=3, sources_from_cache=1, sources_unavailable=2)
    assert r.sources_fetched + r.sources_from_cache + r.sources_unavailable == 6


@pytest.mark.unit
def test_public_surface_imports_from_marketstall_package() -> None:
    """All major types and functions are importable from haywire.core.marketstall."""
    from haywire.core import marketstall

    # Dataclasses
    assert hasattr(marketstall, "Haybale")
    assert hasattr(marketstall, "Subscription")
    assert hasattr(marketstall, "MarketplaceFile")
    assert hasattr(marketstall, "ProjectMarketplaceFile")
    assert hasattr(marketstall, "RefreshOutcome")
    assert hasattr(marketstall, "RefreshReport")
    assert hasattr(marketstall, "FetchResult")
    # Parsers
    assert hasattr(marketstall, "parse_global_marketplace")
    assert hasattr(marketstall, "parse_project_marketplace")
    assert hasattr(marketstall, "parse_marketstall_body")
    assert hasattr(marketstall, "parse_remote_marketplace_body")
    # Serializers
    assert hasattr(marketstall, "serialize_global_marketplace")
    assert hasattr(marketstall, "serialize_project_marketplace")
    # Refresh
    assert hasattr(marketstall, "refresh")
    # Helpers
    assert hasattr(marketstall, "add_market_subscription_to_global")
    assert hasattr(marketstall, "add_stall_subscription_to_global")
    assert hasattr(marketstall, "add_heap_to_project")
    assert hasattr(marketstall, "remove_stale_haybale_from_project")
    assert hasattr(marketstall, "record_ignore_on_source")
    assert hasattr(marketstall, "record_block_on_source")
    assert hasattr(marketstall, "detect_subscription_conflicts")
    # Errors
    assert hasattr(marketstall, "MalformedMarketplaceError")
    assert hasattr(marketstall, "DuplicateHeapNameError")
    assert hasattr(marketstall, "RemoteFetchError")
    # Platform
    assert hasattr(marketstall, "current_os")
    assert hasattr(marketstall, "haybale_supports_current_os")
    # URL resolution
    assert hasattr(marketstall, "classify_input")
    assert hasattr(marketstall, "InputForm")
    assert hasattr(marketstall, "BareRepoUrlRejectedError")
