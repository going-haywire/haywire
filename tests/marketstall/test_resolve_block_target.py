"""resolve_block_target — pick the right subscription URL for Block."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
def test_resolve_block_target_returns_stall_for_direct(tmp_path: Path) -> None:
    """When via matches a [[stalls]] URL, block goes on that stall."""
    from haywire.core.marketstall import (
        add_stall_subscription_to_global,
        resolve_block_target,
    )

    global_path = tmp_path / "marketplace.toml"
    add_stall_subscription_to_global(global_path, "https://alice.example/marketstall.toml")

    target = resolve_block_target(global_path, "https://alice.example/marketstall.toml")
    assert target == "https://alice.example/marketstall.toml"


@pytest.mark.unit
def test_resolve_block_target_returns_market_for_direct_market(tmp_path: Path) -> None:
    """If via somehow matches a [[markets]] entry directly, block goes there."""
    from haywire.core.marketstall import (
        add_market_subscription_to_global,
        resolve_block_target,
    )

    global_path = tmp_path / "marketplace.toml"
    add_market_subscription_to_global(global_path, "https://agg.example/marketplace.toml")

    target = resolve_block_target(global_path, "https://agg.example/marketplace.toml")
    assert target == "https://agg.example/marketplace.toml"


@pytest.mark.unit
def test_resolve_block_target_falls_back_to_aggregator_for_transitive(tmp_path: Path) -> None:
    """Transitive: via is a discovered stall, not a direct subscription.
    Fallback to the aggregator's [[markets]] URL (the only one the user controls)."""
    from haywire.core.marketstall import (
        add_market_subscription_to_global,
        resolve_block_target,
    )

    global_path = tmp_path / "marketplace.toml"
    add_market_subscription_to_global(global_path, "https://agg.example/marketplace.toml")

    # via is a stall the user didn't directly subscribe to.
    target = resolve_block_target(
        global_path, "https://going-haywire.github.io/haywire/stalls/haybale-foo.toml"
    )
    assert target == "https://agg.example/marketplace.toml"


@pytest.mark.unit
def test_resolve_block_target_returns_none_when_no_subscriptions(tmp_path: Path) -> None:
    """With no [[markets]] or [[stalls]] entries, no block can be recorded."""
    from haywire.core.marketstall import resolve_block_target

    global_path = tmp_path / "marketplace.toml"
    # Don't write anything — file is missing.

    target = resolve_block_target(global_path, "https://x.example/stall.toml")
    assert target is None


@pytest.mark.unit
def test_resolve_block_target_returns_none_for_empty_via(tmp_path: Path) -> None:
    """Empty via (inline haybale from global file) returns None."""
    from haywire.core.marketstall import (
        add_market_subscription_to_global,
        resolve_block_target,
    )

    global_path = tmp_path / "marketplace.toml"
    add_market_subscription_to_global(global_path, "https://agg.example/marketplace.toml")

    target = resolve_block_target(global_path, "")
    assert target is None


@pytest.mark.unit
def test_resolve_block_target_prefers_direct_stall_over_aggregator(tmp_path: Path) -> None:
    """Direct stall subscription wins over fallback to aggregator."""
    from haywire.core.marketstall import (
        add_market_subscription_to_global,
        add_stall_subscription_to_global,
        resolve_block_target,
    )

    global_path = tmp_path / "marketplace.toml"
    add_market_subscription_to_global(global_path, "https://agg.example/marketplace.toml")
    add_stall_subscription_to_global(global_path, "https://alice.example/marketstall.toml")

    target = resolve_block_target(global_path, "https://alice.example/marketstall.toml")
    assert target == "https://alice.example/marketstall.toml"
