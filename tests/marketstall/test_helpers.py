"""Helpers for adding/removing marketplace entries — spec §14."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
def test_add_market_subscription_creates_file_if_missing(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import add_market_subscription_to_global
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "marketplace.toml"
    add_market_subscription_to_global(f, "https://x.example/marketplace.toml")
    mf = parse_global_marketplace(f)
    assert len(mf.markets) == 1
    assert mf.markets[0].url == "https://x.example/marketplace.toml"


@pytest.mark.unit
def test_add_market_subscription_is_idempotent(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import add_market_subscription_to_global
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "marketplace.toml"
    add_market_subscription_to_global(f, "https://x.example/m.toml")
    add_market_subscription_to_global(f, "https://x.example/m.toml")
    mf = parse_global_marketplace(f)
    assert len(mf.markets) == 1


@pytest.mark.unit
def test_add_stall_subscription_creates_file_if_missing(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import add_stall_subscription_to_global
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "marketplace.toml"
    add_stall_subscription_to_global(f, "https://alice.example/marketstall.toml")
    mf = parse_global_marketplace(f)
    assert len(mf.stalls) == 1
    assert mf.stalls[0].blocked == []  # new field defaults to empty


@pytest.mark.unit
def test_add_stall_subscription_preserves_existing_sections(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import (
        add_market_subscription_to_global,
        add_stall_subscription_to_global,
    )
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "marketplace.toml"
    add_market_subscription_to_global(f, "https://m.example/m.toml")
    add_stall_subscription_to_global(f, "https://s.example/s.toml")
    mf = parse_global_marketplace(f)
    assert len(mf.markets) == 1
    assert len(mf.stalls) == 1


@pytest.mark.unit
def test_add_heap_to_project_creates_file(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import add_heap_to_project
    from haywire.core.marketstall.parsing import parse_project_marketplace

    f = tmp_path / "project.toml"
    add_heap_to_project(f, name="haybale-my-project", path=Path("/abs/path"), label="My Project")
    pm = parse_project_marketplace(f)
    assert len(pm.heaps) == 1
    assert pm.heaps[0]["name"] == "haybale-my-project"
    assert pm.heaps[0]["path"] == "/abs/path"
    assert pm.heaps[0]["label"] == "My Project"


@pytest.mark.unit
def test_add_heap_to_project_raises_on_duplicate(tmp_path: Path) -> None:
    from haywire.core.marketstall.errors import DuplicateHeapNameError
    from haywire.core.marketstall.helpers import add_heap_to_project

    f = tmp_path / "project.toml"
    add_heap_to_project(f, name="haybale-x", path=Path("/p1"))
    with pytest.raises(DuplicateHeapNameError):
        add_heap_to_project(f, name="haybale-x", path=Path("/p2"))


@pytest.mark.unit
def test_remove_stale_haybale_removes_entry(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import remove_stale_haybale_from_project
    from haywire.core.marketstall.parsing import (
        parse_project_marketplace,
        serialize_project_marketplace,
    )
    from haywire.core.marketstall.types import Haybale, ProjectMarketplaceFile

    f = tmp_path / "project.toml"
    pm = ProjectMarketplaceFile(caches=[Haybale(name="haybale-gone", min_version="0.1.0", stale=True)])
    f.write_text(serialize_project_marketplace(pm))

    removed = remove_stale_haybale_from_project(f, name="haybale-gone")
    assert removed is True

    reparsed = parse_project_marketplace(f)
    assert reparsed.caches == []


@pytest.mark.unit
def test_remove_stale_haybale_refuses_non_stale(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import remove_stale_haybale_from_project
    from haywire.core.marketstall.parsing import serialize_project_marketplace
    from haywire.core.marketstall.types import Haybale, ProjectMarketplaceFile

    f = tmp_path / "project.toml"
    pm = ProjectMarketplaceFile(caches=[Haybale(name="haybale-foo", min_version="0.1.0", stale=False)])
    f.write_text(serialize_project_marketplace(pm))

    with pytest.raises(ValueError, match="non-stale"):
        remove_stale_haybale_from_project(f, name="haybale-foo")


@pytest.mark.unit
def test_remove_stale_haybale_returns_false_when_not_found(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import remove_stale_haybale_from_project

    f = tmp_path / "project.toml"
    f.write_text("")
    assert remove_stale_haybale_from_project(f, name="haybale-missing") is False


@pytest.mark.unit
def test_record_ignore_appends_to_subscription(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import (
        add_stall_subscription_to_global,
        record_ignore_on_source,
    )
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "marketplace.toml"
    add_stall_subscription_to_global(f, "https://alice.example/marketstall.toml")
    record_ignore_on_source(
        f, source_url="https://alice.example/marketstall.toml", haybale_name="haybale-mesh"
    )

    mf = parse_global_marketplace(f)
    assert mf.stalls[0].ignores == ["haybale-mesh"]


@pytest.mark.unit
def test_record_ignore_is_idempotent(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import (
        add_stall_subscription_to_global,
        record_ignore_on_source,
    )
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "marketplace.toml"
    add_stall_subscription_to_global(f, "https://alice.example/marketstall.toml")
    record_ignore_on_source(
        f, source_url="https://alice.example/marketstall.toml", haybale_name="haybale-mesh"
    )
    record_ignore_on_source(
        f, source_url="https://alice.example/marketstall.toml", haybale_name="haybale-mesh"
    )

    mf = parse_global_marketplace(f)
    assert mf.stalls[0].ignores == ["haybale-mesh"]


@pytest.mark.unit
def test_record_block_appends_to_subscription(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import (
        add_stall_subscription_to_global,
        record_block_on_source,
    )
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "marketplace.toml"
    add_stall_subscription_to_global(f, "https://alice.example/marketstall.toml")
    record_block_on_source(
        f,
        source_url="https://alice.example/marketstall.toml",
        haybale_name="haybale-untrusted",
    )

    mf = parse_global_marketplace(f)
    assert mf.stalls[0].blocked == ["haybale-untrusted"]


@pytest.mark.unit
def test_record_block_works_on_market_subscription(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import (
        add_market_subscription_to_global,
        record_block_on_source,
    )
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "marketplace.toml"
    add_market_subscription_to_global(f, "https://agg.example/marketplace.toml")
    record_block_on_source(
        f,
        source_url="https://agg.example/marketplace.toml",
        haybale_name="haybale-spam",
    )

    mf = parse_global_marketplace(f)
    assert mf.markets[0].blocked == ["haybale-spam"]


@pytest.mark.unit
def test_detect_subscription_conflicts_finds_name_collisions() -> None:
    from haywire.core.marketstall.helpers import detect_subscription_conflicts
    from haywire.core.marketstall.types import Haybale

    existing = [
        Haybale(name="haybale-foo", min_version="0.1.0", source_origin="https://a.example/m.toml"),
        Haybale(name="haybale-bar", min_version="0.1.0", source_origin="https://a.example/m.toml"),
    ]
    new = [
        Haybale(name="haybale-foo", min_version="0.2.0", source_origin="https://b.example/m.toml"),
        Haybale(name="haybale-new", min_version="0.1.0", source_origin="https://b.example/m.toml"),
    ]
    conflicts = detect_subscription_conflicts(existing, new)
    assert len(conflicts) == 1
    assert conflicts[0].name == "haybale-foo"
    assert conflicts[0].existing_source == "https://a.example/m.toml"
    assert conflicts[0].new_source == "https://b.example/m.toml"


@pytest.mark.unit
def test_detect_subscription_conflicts_no_collisions() -> None:
    from haywire.core.marketstall.helpers import detect_subscription_conflicts
    from haywire.core.marketstall.types import Haybale

    existing = [Haybale(name="haybale-a", min_version="0.1.0")]
    new = [Haybale(name="haybale-b", min_version="0.1.0")]
    assert detect_subscription_conflicts(existing, new) == []
