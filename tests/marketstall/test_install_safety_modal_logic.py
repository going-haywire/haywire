"""Install safety modal — integration logic + smoke import."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_install_safety_modal_is_importable() -> None:
    """The modal helper must be importable from haywire.ui.modals."""
    from haywire.ui.modals import install_safety_modal

    assert callable(install_safety_modal)


@pytest.mark.unit
def test_record_block_via_resolve_target(tmp_path) -> None:
    """End-to-end: resolve_block_target + record_block_on_source writes the block."""
    from haywire.core.marketstall import (
        add_stall_subscription_to_global,
        record_block_on_source,
        resolve_block_target,
        parse_global_marketplace,
    )

    global_path = tmp_path / "marketplace.toml"
    add_stall_subscription_to_global(global_path, "https://alice.example/marketstall.toml")

    via = "https://alice.example/marketstall.toml"  # direct subscription
    target = resolve_block_target(global_path, via)
    assert target is not None
    record_block_on_source(global_path, source_url=target, haybale_name="haybale-untrusted")

    mf = parse_global_marketplace(global_path)
    assert mf.stalls[0].blocked == ["haybale-untrusted"]


@pytest.mark.unit
def test_record_block_via_aggregator_fallback(tmp_path) -> None:
    """Transitive case: via doesn't match any subscription; fallback to aggregator."""
    from haywire.core.marketstall import (
        add_market_subscription_to_global,
        record_block_on_source,
        resolve_block_target,
        parse_global_marketplace,
    )

    global_path = tmp_path / "marketplace.toml"
    add_market_subscription_to_global(global_path, "https://agg.example/marketplace.toml")

    via = "https://going-haywire.github.io/haywire/stalls/haybale-foo.toml"  # discovered, not subscribed
    target = resolve_block_target(global_path, via)
    assert target == "https://agg.example/marketplace.toml"

    record_block_on_source(global_path, source_url=target, haybale_name="haybale-foo")

    mf = parse_global_marketplace(global_path)
    assert mf.markets[0].blocked == ["haybale-foo"]
