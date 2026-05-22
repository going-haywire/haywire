"""Provenance label derivation for the Library Browser — spec §7.4."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_provenance_label_for_direct_stall_subscription() -> None:
    """Haybale fetched from a [[stalls]] subscription shows 'from {host}'."""
    from haybale_studio.editors.library_browser_editor import derive_provenance_label
    from haywire.core.marketstall import Haybale, MarketplaceFile, Subscription

    haybale = Haybale(
        name="haybale-foo",
        min_version="0.1.0",
        via="https://alice.example/marketstall.toml",
    )
    mf = MarketplaceFile(stalls=[Subscription(url="https://alice.example/marketstall.toml")])

    label = derive_provenance_label(haybale, mf)
    assert label is not None
    assert "from" in label.lower()
    assert "alice.example" in label


@pytest.mark.unit
def test_provenance_label_for_transitive_via_market() -> None:
    """Haybale via [[markets]] (not directly in [[stalls]]) shows 'via {host}'."""
    from haybale_studio.editors.library_browser_editor import derive_provenance_label
    from haywire.core.marketstall import Haybale, MarketplaceFile, Subscription

    # User subscribed to an aggregator; haybale arrived via the aggregator's listed stall.
    haybale = Haybale(
        name="haybale-foo",
        min_version="0.1.0",
        via="https://going-haywire.github.io/haywire/stalls/haybale-foo.toml",
    )
    mf = MarketplaceFile(
        markets=[Subscription(url="https://going-haywire.github.io/haywire/marketplace.toml")],
        # No matching [[stalls]] entry for the haybale's via URL.
    )

    label = derive_provenance_label(haybale, mf)
    assert label is not None
    assert "via" in label.lower()
    assert "going-haywire.github.io" in label


@pytest.mark.unit
def test_provenance_label_empty_via_returns_none() -> None:
    """A haybale with no `via` (e.g. inline in global file) returns None."""
    from haybale_studio.editors.library_browser_editor import derive_provenance_label
    from haywire.core.marketstall import Haybale, MarketplaceFile

    haybale = Haybale(name="haybale-foo", min_version="0.1.0", via="")
    mf = MarketplaceFile()

    assert derive_provenance_label(haybale, mf) is None


@pytest.mark.unit
def test_provenance_label_strips_user_paths_from_file_urls() -> None:
    """For file:// pasted-block subscriptions, the label uses 'pasted' instead of a path."""
    from haybale_studio.editors.library_browser_editor import derive_provenance_label
    from haywire.core.marketstall import Haybale, MarketplaceFile, Subscription

    haybale = Haybale(
        name="haybale-foo",
        min_version="0.1.0",
        via="file:///Users/me/.haywire/db/haybale-marketplace/stalls/haybale-foo.toml",
    )
    mf = MarketplaceFile(
        stalls=[Subscription(url="file:///Users/me/.haywire/db/haybale-marketplace/stalls/haybale-foo.toml")]
    )

    label = derive_provenance_label(haybale, mf)
    assert label is not None
    assert "pasted" in label.lower()
