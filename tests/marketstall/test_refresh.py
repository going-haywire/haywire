"""Refresh pipeline — conflict resolution filters and orchestrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from haywire.core.library.haybale import Haybale
from haywire.core.marketstall import cache as marketstall_cache


def _h(name: str, **kw) -> Haybale:
    """Test helper: build a Haybale with sensible defaults."""
    return Haybale(name=name, version=kw.pop("version", "0.1.0"), **kw)


@pytest.mark.unit
def test_preferred_sources_maps_name_to_the_chosen_url() -> None:
    from haywire.core.marketstall.refresh import preferred_sources
    from haywire.core.marketstall.types import MarketplaceFile, Subscription

    mf = MarketplaceFile(
        stalls=[
            Subscription(url="https://a.example/s.toml"),
            Subscription(url="https://b.example/s.toml", preference=["haybale-foo"]),
        ]
    )
    assert preferred_sources(mf) == {"haybale-foo": "https://b.example/s.toml"}


@pytest.mark.unit
def test_preferred_sources_is_empty_when_nobody_claims_anything() -> None:
    from haywire.core.marketstall.refresh import preferred_sources
    from haywire.core.marketstall.types import MarketplaceFile, Subscription

    mf = MarketplaceFile(stalls=[Subscription(url="https://a.example/s.toml")])
    assert preferred_sources(mf) == {}


@pytest.mark.unit
def test_preferred_sources_breaks_a_double_claim_by_file_order() -> None:
    """Only reachable by hand-editing; first in file order wins and the dedup
    step still reports the collision so the user can re-settle it."""
    from haywire.core.marketstall.refresh import preferred_sources
    from haywire.core.marketstall.types import MarketplaceFile, Subscription

    mf = MarketplaceFile(
        stalls=[
            Subscription(url="https://a.example/s.toml", preference=["haybale-foo"]),
            Subscription(url="https://b.example/s.toml", preference=["haybale-foo"]),
        ]
    )
    assert preferred_sources(mf) == {"haybale-foo": "https://a.example/s.toml"}


@pytest.mark.unit
def test_apply_blocked_filters_by_name() -> None:
    from haywire.core.marketstall.refresh import apply_blocked

    pkgs = [_h("haybale-a"), _h("haybale-untrusted"), _h("haybale-c")]
    out = apply_blocked(pkgs, ["haybale-untrusted"])
    assert [p.name for p in out] == ["haybale-a", "haybale-c"]


@pytest.mark.unit
def test_apply_blocked_empty_list_is_noop() -> None:
    from haywire.core.marketstall.refresh import apply_blocked

    pkgs = [_h("haybale-a")]
    assert apply_blocked(pkgs, []) == pkgs


@pytest.mark.unit
def test_apply_heaps_shadow_drops_collisions() -> None:
    """Spec §8.2: heaps always win — any candidate whose name matches a heap is dropped."""
    from haywire.core.marketstall.refresh import apply_heaps_shadow

    heaps = [{"name": "haybale-foo", "path": "/p"}, {"name": "haybale-bar", "path": "/p"}]
    candidates = [_h("haybale-foo"), _h("haybale-baz")]
    out = apply_heaps_shadow(heaps, candidates)
    assert [p.name for p in out] == ["haybale-baz"]


@pytest.mark.unit
def test_apply_heaps_shadow_empty_heaps_noop() -> None:
    from haywire.core.marketstall.refresh import apply_heaps_shadow

    candidates = [_h("haybale-foo")]
    assert apply_heaps_shadow([], candidates) == candidates


@pytest.mark.unit
def test_dedupe_without_preference_keeps_the_first_occurrence() -> None:
    from haywire.core.marketstall.refresh import dedupe_reporting_collisions

    candidates = [_h("haybale-foo", label="first"), _h("haybale-foo", label="second")]
    survivors, _ = dedupe_reporting_collisions(candidates)
    assert [h.label for h in survivors] == ["first"]


@pytest.mark.unit
def test_dedupe_preserves_distinct_names_in_order() -> None:
    from haywire.core.marketstall.refresh import dedupe_reporting_collisions

    survivors, _ = dedupe_reporting_collisions([_h("haybale-a"), _h("haybale-b"), _h("haybale-c")])
    assert [h.name for h in survivors] == ["haybale-a", "haybale-b", "haybale-c"]


@pytest.mark.unit
def test_dedupe_reports_the_loser_instead_of_dropping_it_silently() -> None:
    from haywire.core.marketstall.refresh import dedupe_reporting_collisions

    candidates = [
        _h("haybale-foo", version="2.1.0", via="https://a.example/s.toml"),
        _h("haybale-foo", version="2.3.0", via="https://b.example/s.toml"),
    ]
    survivors, collisions = dedupe_reporting_collisions(candidates)

    assert [h.version for h in survivors] == ["2.1.0"]
    assert len(collisions) == 1
    assert collisions[0].name == "haybale-foo"
    assert collisions[0].winner_url == "https://a.example/s.toml"
    assert collisions[0].winner_version == "2.1.0"
    assert collisions[0].losers == [("https://b.example/s.toml", "2.3.0")]
    assert collisions[0].source_count == 2


@pytest.mark.unit
def test_dedupe_reports_every_loser_in_drop_order() -> None:
    from haywire.core.marketstall.refresh import dedupe_reporting_collisions

    candidates = [
        _h("haybale-foo", version="1.0.0", via="https://a.example/s.toml"),
        _h("haybale-foo", version="2.0.0", via="https://b.example/s.toml"),
        _h("haybale-foo", version="3.0.0", via="https://c.example/s.toml"),
    ]
    _, collisions = dedupe_reporting_collisions(candidates)

    assert collisions[0].source_count == 3
    assert collisions[0].losers == [
        ("https://b.example/s.toml", "2.0.0"),
        ("https://c.example/s.toml", "3.0.0"),
    ]


@pytest.mark.unit
def test_dedupe_reports_nothing_when_names_are_distinct() -> None:
    from haywire.core.marketstall.refresh import dedupe_reporting_collisions

    survivors, collisions = dedupe_reporting_collisions([_h("haybale-a"), _h("haybale-b")])

    assert [h.name for h in survivors] == ["haybale-a", "haybale-b"]
    assert collisions == []


@pytest.mark.unit
def test_mark_stale_fresh_only_passes_through() -> None:
    from haywire.core.marketstall.refresh import mark_stale_against_previous

    fresh = [_h("haybale-a"), _h("haybale-b")]
    out = mark_stale_against_previous(fresh, previous=[])
    assert [p.name for p in out] == ["haybale-a", "haybale-b"]
    assert all(not p.stale for p in out)


@pytest.mark.unit
def test_mark_stale_drops_to_previous_only_marks_stale() -> None:
    """Entries in previous but not fresh become stale with a last_seen timestamp."""
    from haywire.core.marketstall.refresh import mark_stale_against_previous

    previous = [_h("haybale-gone")]
    fresh = [_h("haybale-still-here")]
    out = mark_stale_against_previous(fresh, previous=previous)
    by_name = {p.name: p for p in out}
    assert by_name["haybale-gone"].stale is True
    assert by_name["haybale-gone"].last_seen != ""
    assert by_name["haybale-still-here"].stale is False


@pytest.mark.unit
def test_mark_stale_preserves_existing_stale_timestamp() -> None:
    """An entry already stale in previous keeps its last_seen — don't bump on every refresh."""
    from haywire.core.marketstall.refresh import mark_stale_against_previous

    previous = [_h("haybale-old", stale=True, last_seen="2026-01-01T00:00:00Z")]
    out = mark_stale_against_previous([], previous=previous)
    assert len(out) == 1
    assert out[0].stale is True
    assert out[0].last_seen == "2026-01-01T00:00:00Z"


@pytest.mark.unit
def test_mark_stale_entries_in_both_use_fresh_data() -> None:
    """When an entry is in both fresh and previous, fresh wins (no stale flag carry-over)."""
    from haywire.core.marketstall.refresh import mark_stale_against_previous

    previous = [_h("haybale-foo", stale=True, last_seen="2026-01-01T00:00:00Z")]
    fresh = [_h("haybale-foo", label="back-fresh")]
    out = mark_stale_against_previous(fresh, previous=previous)
    assert len(out) == 1
    assert out[0].label == "back-fresh"
    assert out[0].stale is False


@pytest.mark.unit
def test_refresh_with_no_subscriptions_writes_empty_project(tmp_path: Path) -> None:
    from haywire.core.marketstall.refresh import refresh

    global_path = tmp_path / "global.toml"
    global_path.write_text("")
    project_path = tmp_path / "project.toml"

    report = refresh(global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c")
    assert report.sources_fetched == 0
    assert report.sources_from_cache == 0
    assert report.sources_unavailable == 0
    assert report.haybales_resolved == 0


@pytest.mark.unit
def test_refresh_fetches_stall_subscription(tmp_path: Path) -> None:
    from haywire.core.marketstall.refresh import refresh

    global_path = tmp_path / "global.toml"
    global_path.write_text(
        '[[stalls]]\nurl = "https://alice.example/marketstall.toml"\npreference = []\nblocked = []\n'
    )
    project_path = tmp_path / "project.toml"

    fake_body = '[[haybales]]\nname = "haybale-foo"\nversion = "0.1.0"\n'
    with patch.object(marketstall_cache, "_urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = fake_body.encode()
        report = refresh(global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c")

    assert report.sources_fetched == 1
    assert report.haybales_resolved == 1


@pytest.mark.unit
def test_refresh_falls_back_to_cache_when_unreachable(tmp_path: Path) -> None:
    from haywire.core.marketstall.cache import cache_write
    from haywire.core.marketstall.refresh import refresh

    cache_dir = tmp_path / "c"
    cache_write(
        "https://alice.example/marketstall.toml",
        '[[haybales]]\nname = "haybale-foo"\nversion = "0.1.0"\n',
        cache_dir=cache_dir,
    )

    global_path = tmp_path / "global.toml"
    global_path.write_text(
        '[[stalls]]\nurl = "https://alice.example/marketstall.toml"\npreference = []\nblocked = []\n'
    )
    project_path = tmp_path / "project.toml"

    with patch.object(marketstall_cache, "_urlopen", side_effect=OSError):
        report = refresh(global_path=global_path, project_path=project_path, cache_dir=cache_dir)

    assert report.sources_fetched == 0
    assert report.sources_from_cache == 1
    assert report.sources_unavailable == 0
    assert report.haybales_resolved == 1


@pytest.mark.unit
def test_refresh_unavailable_when_no_cache_no_network(tmp_path: Path) -> None:
    from haywire.core.marketstall.refresh import refresh

    global_path = tmp_path / "global.toml"
    global_path.write_text(
        '[[stalls]]\nurl = "https://gone.example/marketstall.toml"\npreference = []\nblocked = []\n'
    )
    project_path = tmp_path / "project.toml"

    with patch.object(marketstall_cache, "_urlopen", side_effect=OSError):
        report = refresh(global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c")

    assert report.sources_unavailable == 1
    assert "https://gone.example/marketstall.toml" in report.unavailable_urls


@pytest.mark.unit
def test_refresh_applies_blocked_per_subscription(tmp_path: Path) -> None:
    from haywire.core.marketstall.refresh import refresh

    global_path = tmp_path / "global.toml"
    global_path.write_text(
        "[[stalls]]\n"
        'url = "https://alice.example/marketstall.toml"\n'
        "preference = []\n"
        'blocked = ["haybale-untrusted"]\n'
    )
    project_path = tmp_path / "project.toml"

    fake_body = (
        "[[haybales]]\n"
        'name = "haybale-foo"\n'
        'version = "0.1.0"\n'
        "\n"
        "[[haybales]]\n"
        'name = "haybale-untrusted"\n'
        'version = "0.1.0"\n'
    )
    with patch.object(marketstall_cache, "_urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = fake_body.encode()
        report = refresh(global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c")

    assert report.haybales_resolved == 1


@pytest.mark.unit
def test_refresh_gcs_orphan_cache_files(tmp_path: Path) -> None:
    from haywire.core.marketstall.cache import cache_write
    from haywire.core.marketstall.refresh import refresh

    cache_dir = tmp_path / "c"
    cache_write("https://orphan.example/m.toml", "old", cache_dir=cache_dir)
    cache_write(
        "https://active.example/m.toml",
        '[[haybales]]\nname = "haybale-x"\nversion = "0.1.0"\n',
        cache_dir=cache_dir,
    )

    global_path = tmp_path / "global.toml"
    global_path.write_text(
        '[[stalls]]\nurl = "https://active.example/m.toml"\npreference = []\nblocked = []\n'
    )
    project_path = tmp_path / "project.toml"

    with patch.object(marketstall_cache, "_urlopen", side_effect=OSError):
        refresh(global_path=global_path, project_path=project_path, cache_dir=cache_dir)

    remaining = sorted(p.name for p in cache_dir.iterdir() if p.is_file())
    assert len(remaining) == 1  # orphan removed; active retained


@pytest.mark.unit
def test_refresh_one_level_deep_consumes_market_stalls(tmp_path: Path) -> None:
    """A [[markets]] subscription contributes [[stalls]] URLs and inline [[haybales]]."""
    from haywire.core.marketstall.refresh import refresh

    global_path = tmp_path / "global.toml"
    global_path.write_text(
        '[[markets]]\nurl = "https://aggregator.example/marketplace.toml"\npreference = []\nblocked = []\n'
    )
    project_path = tmp_path / "project.toml"

    aggregator_body = (
        "[[stalls]]\n"
        'url = "https://stall.example/marketstall.toml"\n'
        "preference = []\n"
        "blocked = []\n"
        "\n"
        "[[haybales]]\n"
        'name = "haybale-inline"\n'
        'version = "0.1.0"\n'
    )
    stall_body = '[[haybales]]\nname = "haybale-from-stall"\nversion = "0.1.0"\n'

    def fake_urlopen(url, *, timeout):
        from unittest.mock import MagicMock

        m = MagicMock()
        if "aggregator" in url:
            m.__enter__.return_value.read.return_value = aggregator_body.encode()
        else:
            m.__enter__.return_value.read.return_value = stall_body.encode()
        return m

    with patch.object(marketstall_cache, "_urlopen", side_effect=fake_urlopen):
        report = refresh(global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c")

    assert report.sources_fetched == 2  # aggregator + the stall it referenced
    assert report.haybales_resolved == 2  # haybale-inline + haybale-from-stall


@pytest.mark.unit
def test_refresh_stamps_via_on_cached_haybales(tmp_path: Path) -> None:
    """Every Haybale written to [[caches]] must carry `via` = its source URL.

    Without this, resolve_block_target() returns None and the first-install
    safety modal's Block button shows 'not from a subscription you can edit'
    even for haybales that came from an editable subscription.
    """
    from haywire.core.marketstall.parsing import parse_project_marketplace
    from haywire.core.marketstall.refresh import refresh

    stall_url = "https://alice.example/marketstall.toml"
    market_url = "https://aggregator.example/marketplace.toml"
    discovered_stall_url = "https://discovered.example/marketstall.toml"

    global_path = tmp_path / "global.toml"
    global_path.write_text(
        "[[stalls]]\n"
        f'url = "{stall_url}"\n'
        "preference = []\n"
        "blocked = []\n"
        "\n"
        "[[markets]]\n"
        f'url = "{market_url}"\n'
        "preference = []\n"
        "blocked = []\n"
    )
    project_path = tmp_path / "project.toml"

    stall_body = '[[haybales]]\nname = "haybale-from-direct-stall"\nversion = "0.1.0"\n'
    market_body = (
        "[[stalls]]\n"
        f'url = "{discovered_stall_url}"\n'
        "\n"
        "[[haybales]]\n"
        'name = "haybale-inline-in-market"\n'
        'version = "0.1.0"\n'
    )
    discovered_body = '[[haybales]]\nname = "haybale-from-discovered-stall"\nversion = "0.1.0"\n'

    def fake_urlopen(url, *, timeout):
        from unittest.mock import MagicMock

        m = MagicMock()
        if "aggregator" in url:
            body = market_body
        elif "discovered" in url:
            body = discovered_body
        else:
            body = stall_body
        m.__enter__.return_value.read.return_value = body.encode()
        return m

    with patch.object(marketstall_cache, "_urlopen", side_effect=fake_urlopen):
        refresh(global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c")

    pm = parse_project_marketplace(project_path)
    by_name = {h.name: h for h in pm.caches}

    assert by_name["haybale-from-direct-stall"].via == stall_url
    assert by_name["haybale-inline-in-market"].via == market_url
    assert by_name["haybale-from-discovered-stall"].via == discovered_stall_url


@pytest.mark.unit
def test_refresh_blocked_entry_disappears_from_caches(tmp_path: Path) -> None:
    """Blocking a haybale must remove it from [[caches]] on the next refresh —
    even when the source is unreachable (no fresh body, only the previous cache).

    Spec §3.1/§7.4/§8: blocked haybales are fully hidden, immediately. They
    must NOT be rescued by mark_stale_against_previous as stale=True survivors.
    """
    from haywire.core.marketstall.parsing import parse_project_marketplace
    from haywire.core.marketstall.refresh import refresh

    stall_url = "https://alice.example/marketstall.toml"
    stall_body = '[[haybales]]\nname = "haybale-foo"\nversion = "0.1.0"\n'

    # Step 1: initial refresh populates the cache with haybale-foo.
    global_path = tmp_path / "global.toml"
    global_path.write_text(f'[[stalls]]\nurl = "{stall_url}"\npreference = []\nblocked = []\n')
    project_path = tmp_path / "project.toml"
    cache_dir = tmp_path / "c"

    with patch.object(marketstall_cache, "_urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = stall_body.encode()
        refresh(global_path=global_path, project_path=project_path, cache_dir=cache_dir)

    pm = parse_project_marketplace(project_path)
    assert "haybale-foo" in {h.name for h in pm.caches}

    # Step 2: user blocks haybale-foo, then refreshes.
    global_path.write_text(f'[[stalls]]\nurl = "{stall_url}"\npreference = []\nblocked = ["haybale-foo"]\n')

    with patch.object(marketstall_cache, "_urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = stall_body.encode()
        refresh(global_path=global_path, project_path=project_path, cache_dir=cache_dir)

    pm = parse_project_marketplace(project_path)
    assert "haybale-foo" not in {h.name for h in pm.caches}, (
        "blocked haybale must disappear from caches, not survive as stale"
    )


# ──────────────────────────────────────────────────────────────────────────────
# _count_updates_available — RefreshReport.updates_available (spec §10.3)
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_count_updates_available_flags_installed_below_cache_min(monkeypatch) -> None:
    """An installed dist whose version is below the cache `version` counts
    as an available update (spec §10.3)."""
    import importlib.metadata as _meta

    from haywire.core.marketstall.refresh import _count_updates_available

    monkeypatch.setattr(_meta, "version", lambda dist: "0.1.0" if dist == "haybale-foo" else "0.0.0")
    cache = [_h("haybale-foo", version="0.5.0")]
    assert _count_updates_available(cache) == 1


@pytest.mark.unit
def test_count_updates_available_skips_equal_versions(monkeypatch) -> None:
    """installed == version is not an update — only strictly less."""
    import importlib.metadata as _meta

    from haywire.core.marketstall.refresh import _count_updates_available

    monkeypatch.setattr(_meta, "version", lambda dist: "0.5.0" if dist == "haybale-foo" else "0.0.0")
    cache = [_h("haybale-foo", version="0.5.0")]
    assert _count_updates_available(cache) == 0


@pytest.mark.unit
def test_count_updates_available_skips_uninstalled(monkeypatch) -> None:
    """A haybale not installed locally cannot be updated — skip silently."""
    import importlib.metadata as _meta

    from haywire.core.marketstall.refresh import _count_updates_available

    def _raise(dist):
        raise _meta.PackageNotFoundError(dist)

    monkeypatch.setattr(_meta, "version", _raise)
    cache = [_h("haybale-foo", version="0.5.0")]
    assert _count_updates_available(cache) == 0


@pytest.mark.unit
def test_count_updates_available_skips_stale_entries(monkeypatch) -> None:
    """Stale cache entries hold OLD version values from a previous refresh
    where the upstream wasn't reachable. Comparing against them would falsely
    report 'up-to-date' just because the user happened to install the same
    old version."""
    import importlib.metadata as _meta

    from haywire.core.marketstall.refresh import _count_updates_available

    monkeypatch.setattr(_meta, "version", lambda dist: "0.1.0" if dist == "haybale-foo" else "0.0.0")
    stale = _h("haybale-foo", version="0.5.0", stale=True)
    assert _count_updates_available([stale]) == 0


@pytest.mark.unit
def test_count_updates_available_handles_multiple(monkeypatch) -> None:
    """Counts across multiple entries — mix of out-of-date, current, and absent."""
    import importlib.metadata as _meta

    from haywire.core.marketstall.refresh import _count_updates_available

    versions = {"haybale-a": "0.1.0", "haybale-b": "0.5.0"}  # c is uninstalled

    def _ver(dist):
        if dist in versions:
            return versions[dist]
        raise _meta.PackageNotFoundError(dist)

    monkeypatch.setattr(_meta, "version", _ver)
    cache = [
        _h("haybale-a", version="0.5.0"),  # needs update
        _h("haybale-b", version="0.5.0"),  # current
        _h("haybale-c", version="0.5.0"),  # not installed
    ]
    assert _count_updates_available(cache) == 1


@pytest.mark.unit
def test_refresh_populates_updates_available_in_report(tmp_path: Path, monkeypatch) -> None:
    """End-to-end: refresh() must set RefreshReport.updates_available based on
    what the new caches contain."""
    import importlib.metadata as _meta

    from haywire.core.marketstall.refresh import refresh

    monkeypatch.setattr(_meta, "version", lambda dist: "0.1.0" if dist == "haybale-foo" else "0.0.0")

    stall_url = "https://alice.example/marketstall.toml"
    stall_body = '[[haybales]]\nname = "haybale-foo"\nversion = "0.5.0"\n'

    global_path = tmp_path / "global.toml"
    global_path.write_text(f'[[stalls]]\nurl = "{stall_url}"\npreference = []\nblocked = []\n')
    project_path = tmp_path / "project.toml"

    with patch.object(marketstall_cache, "_urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = stall_body.encode()
        report = refresh(global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c")

    assert report.updates_available == 1


@pytest.mark.unit
def test_refresh_evicts_doc_dir_for_dropped_library(tmp_path: Path) -> None:
    """A library absent from the resolved catalog loses its cached docs."""
    from haywire.core.marketstall.cache import docs_cache_dir
    from haywire.core.marketstall.refresh import refresh

    # Seed a doc cache for a library that will not be in any subscription.
    orphan = docs_cache_dir("ghost-lib", cache_dir=tmp_path)
    orphan.mkdir(parents=True)

    global_path = tmp_path / "marketplace.toml"
    global_path.write_text("")  # no subscriptions, no haybales
    project_path = tmp_path / "project.toml"

    refresh(global_path=global_path, project_path=project_path, cache_dir=tmp_path)

    assert not orphan.exists()  # ghost-lib evicted (not in resolved set)


@pytest.mark.unit
def test_malformed_caches_are_discarded_not_fatal(tmp_path):
    """[[caches]] are derived artifacts refetched on every refresh. A strict
    parser must not let a malformed cache block the refresh that heals it."""
    from haywire.core.marketstall.parsing import parse_project_marketplace

    project = tmp_path / "marketplace.toml"
    project.write_text('[[caches]]\nname = "haybale-foo"\n')  # no version

    pm = parse_project_marketplace(project)

    assert pm.caches == []


@pytest.mark.unit
def test_malformed_caches_do_not_discard_heaps(tmp_path):
    """Only [[caches]] are derived. [[heaps]] are user-authored and must survive."""
    from haywire.core.marketstall.parsing import parse_project_marketplace

    project = tmp_path / "marketplace.toml"
    project.write_text(
        '[[heaps]]\nname = "haybale-local"\npath = "barn/haybale-local"\n\n'
        '[[caches]]\nname = "haybale-foo"\n'
    )

    pm = parse_project_marketplace(project)

    assert pm.caches == []
    assert [h["name"] for h in pm.heaps] == ["haybale-local"]


# ── Three-phase pipeline: fetch_sources / resolve / apply ────────────────────
#
# The phase split exists so a UI can show what a refresh WOULD do before it
# does it, so the load-bearing property under test is that the first two
# phases leave the project file untouched.


def _stall_global(tmp_path: Path, url: str = "https://alice.example/marketstall.toml") -> Path:
    global_path = tmp_path / "global.toml"
    global_path.write_text(f'[[stalls]]\nurl = "{url}"\npreference = []\nblocked = []\n')
    return global_path


@pytest.mark.unit
def test_fetch_sources_writes_nothing(tmp_path: Path) -> None:
    from haywire.core.marketstall.refresh import fetch_sources

    global_path = _stall_global(tmp_path)
    project_path = tmp_path / "project.toml"

    fake_body = '[[haybales]]\nname = "haybale-foo"\nversion = "0.1.0"\n'
    with patch.object(marketstall_cache, "_urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = fake_body.encode()
        fetched = fetch_sources(global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c")

    assert not project_path.exists()
    assert fetched.sources_fetched == 1
    assert fetched.unavailable_urls == []


@pytest.mark.unit
def test_resolve_writes_nothing_and_reports_deltas(tmp_path: Path) -> None:
    from haywire.core.marketstall.refresh import fetch_sources, resolve

    global_path = _stall_global(tmp_path)
    project_path = tmp_path / "project.toml"

    fake_body = '[[haybales]]\nname = "haybale-foo"\nversion = "0.1.0"\n'
    with patch.object(marketstall_cache, "_urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = fake_body.encode()
        fetched = fetch_sources(global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c")

    resolved = resolve(fetched)

    assert not project_path.exists()
    assert resolved.resolved_count == 1
    assert resolved.newly_added == ["haybale-foo"]
    assert resolved.newly_stale == []


@pytest.mark.unit
def test_resolve_is_pure_and_repeatable(tmp_path: Path) -> None:
    """resolve() may be called repeatedly on one fetch without drift."""
    from haywire.core.marketstall.refresh import fetch_sources, resolve

    global_path = _stall_global(tmp_path)
    project_path = tmp_path / "project.toml"

    fake_body = '[[haybales]]\nname = "haybale-foo"\nversion = "0.1.0"\n'
    with patch.object(marketstall_cache, "_urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = fake_body.encode()
        fetched = fetch_sources(global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c")

    first = resolve(fetched)
    second = resolve(fetched)

    assert [h.name for h in first.haybales] == [h.name for h in second.haybales]
    assert first.newly_added == second.newly_added


@pytest.mark.unit
def test_apply_writes_project_file_and_returns_report(tmp_path: Path) -> None:
    from haywire.core.marketstall.parsing import parse_project_marketplace
    from haywire.core.marketstall.refresh import apply, fetch_sources, resolve

    global_path = _stall_global(tmp_path)
    project_path = tmp_path / "project.toml"

    fake_body = '[[haybales]]\nname = "haybale-foo"\nversion = "0.1.0"\n'
    with patch.object(marketstall_cache, "_urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = fake_body.encode()
        fetched = fetch_sources(global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c")

    report = apply(fetched, resolve(fetched), project_path=project_path, cache_dir=tmp_path / "c")

    assert project_path.exists()
    assert [h.name for h in parse_project_marketplace(project_path).caches] == ["haybale-foo"]
    assert report.haybales_resolved == 1
    assert report.sources_fetched == 1


@pytest.mark.unit
def test_phases_compose_to_same_report_as_refresh(tmp_path: Path) -> None:
    """The split must not change what refresh() reports."""
    from haywire.core.marketstall.refresh import apply, fetch_sources, refresh, resolve

    fake_body = '[[haybales]]\nname = "haybale-foo"\nversion = "0.1.0"\n'

    def _run_composed(root: Path):
        global_path = _stall_global(root)
        project_path = root / "project.toml"
        with patch.object(marketstall_cache, "_urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = fake_body.encode()
            fetched = fetch_sources(global_path=global_path, project_path=project_path, cache_dir=root / "c")
        return apply(fetched, resolve(fetched), project_path=project_path, cache_dir=root / "c")

    def _run_oneshot(root: Path):
        global_path = _stall_global(root)
        project_path = root / "project.toml"
        with patch.object(marketstall_cache, "_urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = fake_body.encode()
            return refresh(global_path=global_path, project_path=project_path, cache_dir=root / "c")

    split_dir = tmp_path / "split"
    split_dir.mkdir()
    oneshot_dir = tmp_path / "oneshot"
    oneshot_dir.mkdir()

    assert _run_composed(split_dir) == _run_oneshot(oneshot_dir)


@pytest.mark.unit
def test_fetch_sources_records_unavailable_without_writing(tmp_path: Path) -> None:
    from haywire.core.marketstall.refresh import fetch_sources, resolve
    from haywire.core.marketstall.types import RefreshOutcome

    global_path = _stall_global(tmp_path, "https://gone.example/marketstall.toml")
    project_path = tmp_path / "project.toml"

    with patch.object(marketstall_cache, "_urlopen", side_effect=OSError):
        fetched = fetch_sources(global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c")

    assert fetched.unavailable_urls == ["https://gone.example/marketstall.toml"]
    assert fetched.outcomes[0].outcome is RefreshOutcome.UNAVAILABLE
    assert fetched.outcomes[0].body is None
    assert not project_path.exists()
    # An unreachable source resolves to an empty catalog, not an exception.
    assert resolve(fetched).resolved_count == 0


@pytest.mark.unit
def test_resolve_marks_newly_stale_against_previous(tmp_path: Path) -> None:
    """A cached entry whose source no longer lists it shows up in newly_stale."""
    from haywire.core.marketstall.refresh import fetch_sources, resolve

    global_path = _stall_global(tmp_path)
    project_path = tmp_path / "project.toml"
    project_path.write_text('[[caches]]\nname = "haybale-gone"\nversion = "0.1.0"\n')

    fake_body = '[[haybales]]\nname = "haybale-foo"\nversion = "0.1.0"\n'
    with patch.object(marketstall_cache, "_urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = fake_body.encode()
        fetched = fetch_sources(global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c")

    resolved = resolve(fetched)

    assert resolved.newly_stale == ["haybale-gone"]
    assert resolved.newly_added == ["haybale-foo"]


# ---------------------------------------------------------------------------
# Cross-source collisions — the standing-conflict record
# ---------------------------------------------------------------------------


def _two_stall_global(tmp_path: Path, url_a: str, url_b: str) -> Path:
    global_path = tmp_path / "global.toml"
    global_path.write_text(
        f'[[stalls]]\nurl = "{url_a}"\npreference = []\nblocked = []\n'
        "\n"
        f'[[stalls]]\nurl = "{url_b}"\npreference = []\nblocked = []\n'
    )
    return global_path


def _collision_bodies(url_a: str):
    """Both stalls offer haybale-foo; A at 2.1.0 (older), B at 2.3.0 (newer)."""

    def fake_urlopen(url, *, timeout):
        from unittest.mock import MagicMock

        m = MagicMock()
        version = "2.1.0" if url == url_a else "2.3.0"
        body = f'[[haybales]]\nname = "haybale-foo"\nversion = "{version}"\n'
        m.__enter__.return_value.read.return_value = body.encode()
        return m

    return fake_urlopen


@pytest.mark.unit
def test_resolve_surfaces_a_cross_source_collision(tmp_path: Path) -> None:
    """Two stalls offering one name must produce a visible collision record.

    Before this, the loser was dropped with no prompt and no diagnostic — the
    catalog could not distinguish "one source offers this" from "two do and we
    picked by list position".
    """
    from haywire.core.marketstall.refresh import fetch_sources, resolve

    url_a, url_b = "https://a.example/s.toml", "https://b.example/s.toml"
    global_path = _two_stall_global(tmp_path, url_a, url_b)
    project_path = tmp_path / "project.toml"

    with patch.object(marketstall_cache, "_urlopen", side_effect=_collision_bodies(url_a)):
        fetched = fetch_sources(global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c")

    resolved = resolve(fetched)

    assert resolved.resolved_count == 1
    assert len(resolved.collisions) == 1
    collision = resolved.collisions[0]
    assert collision.name == "haybale-foo"
    assert collision.winner_url == url_a
    assert collision.winner_version == "2.1.0"
    assert collision.losers == [(url_b, "2.3.0")]


@pytest.mark.unit
def test_preference_picks_the_winner_regardless_of_subscription_order(tmp_path: Path) -> None:
    """The whole point of a positive preference: file order stops deciding.

    Without one, url_a wins because its [[stalls]] entry comes first.
    """
    from haywire.core.marketstall.parsing import parse_project_marketplace
    from haywire.core.marketstall.refresh import refresh

    url_a, url_b = "https://a.example/s.toml", "https://b.example/s.toml"
    global_path = tmp_path / "global.toml"
    global_path.write_text(
        f'[[stalls]]\nurl = "{url_a}"\npreference = []\nblocked = []\n'
        "\n"
        f'[[stalls]]\nurl = "{url_b}"\npreference = ["haybale-foo"]\nblocked = []\n'
    )
    project_path = tmp_path / "project.toml"

    with patch.object(marketstall_cache, "_urlopen", side_effect=_collision_bodies(url_a)):
        refresh(global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c")

    cached = parse_project_marketplace(project_path).caches
    assert [h.version for h in cached] == ["2.3.0"]
    assert cached[0].via == url_b


@pytest.mark.unit
def test_a_preference_still_reports_the_collision(tmp_path: Path) -> None:
    """Settling a collision does not hide it — the losers are still listed, so
    the resolved step can keep offering the other sources."""
    from haywire.core.marketstall.refresh import fetch_sources, resolve

    url_a, url_b = "https://a.example/s.toml", "https://b.example/s.toml"
    global_path = tmp_path / "global.toml"
    global_path.write_text(
        f'[[stalls]]\nurl = "{url_a}"\npreference = []\nblocked = []\n'
        "\n"
        f'[[stalls]]\nurl = "{url_b}"\npreference = ["haybale-foo"]\nblocked = []\n'
    )
    project_path = tmp_path / "project.toml"

    with patch.object(marketstall_cache, "_urlopen", side_effect=_collision_bodies(url_a)):
        fetched = fetch_sources(global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c")

    resolved = resolve(fetched)
    assert len(resolved.collisions) == 1
    assert resolved.collisions[0].winner_url == url_b
    assert resolved.collisions[0].losers == [(url_a, "2.1.0")]


@pytest.mark.unit
def test_a_preference_for_a_source_that_no_longer_offers_it_falls_back(tmp_path: Path) -> None:
    """A stale preference must not blank the entry — FCFS still yields a winner."""
    from haywire.core.marketstall.parsing import parse_project_marketplace
    from haywire.core.marketstall.refresh import refresh

    url_a, url_b = "https://a.example/s.toml", "https://b.example/s.toml"
    global_path = tmp_path / "global.toml"
    global_path.write_text(
        f'[[stalls]]\nurl = "{url_a}"\npreference = []\nblocked = []\n'
        "\n"
        f'[[stalls]]\nurl = "{url_b}"\npreference = ["haybale-foo"]\nblocked = []\n'
    )
    project_path = tmp_path / "project.toml"

    def only_a(url, *, timeout):
        from unittest.mock import MagicMock

        m = MagicMock()
        body = (
            '[[haybales]]\nname = "haybale-foo"\nversion = "2.1.0"\n'
            if url == url_a
            else '[[haybales]]\nname = "haybale-other"\nversion = "1.0.0"\n'
        )
        m.__enter__.return_value.read.return_value = body.encode()
        return m

    with patch.object(marketstall_cache, "_urlopen", side_effect=only_a):
        refresh(global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c")

    by_name = {h.name: h for h in parse_project_marketplace(project_path).caches}
    assert by_name["haybale-foo"].version == "2.1.0"
    assert by_name["haybale-foo"].via == url_a


@pytest.mark.unit
def test_refresh_never_writes_the_global_file(tmp_path: Path) -> None:
    """The global marketplace is user intent; only an explicit action edits it."""
    from haywire.core.marketstall.refresh import refresh

    url_a, url_b = "https://a.example/s.toml", "https://b.example/s.toml"
    global_path = _two_stall_global(tmp_path, url_a, url_b)
    project_path = tmp_path / "project.toml"
    before = global_path.read_text()

    with patch.object(marketstall_cache, "_urlopen", side_effect=_collision_bodies(url_a)):
        refresh(global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c")

    assert global_path.read_text() == before


@pytest.mark.unit
def test_preference_reaches_a_stall_discovered_through_a_market(tmp_path: Path) -> None:
    """A discovered stall is not subscribable, so its owner is the aggregator.

    Regression: the panel used to hand the discovered stall's own URL to
    record_preference, which matched no subscription — the click silently did
    nothing.
    """
    from haywire.core.marketstall.helpers import record_preference
    from haywire.core.marketstall.parsing import parse_project_marketplace
    from haywire.core.marketstall.refresh import fetch_sources, refresh, resolve

    rival = "file:///rival.toml"
    market = "https://agg.example/marketplace.toml"
    discovered = "https://agg.example/stalls/haybale-foo.toml"

    global_path = tmp_path / "global.toml"
    global_path.write_text(
        f'[[stalls]]\nurl = "{rival}"\npreference = []\nblocked = []\n'
        "\n"
        f'[[markets]]\nurl = "{market}"\npreference = []\nblocked = []\n'
    )
    project_path = tmp_path / "project.toml"

    def fake(url, *, timeout):
        from unittest.mock import MagicMock

        m = MagicMock()
        if url == market:
            body = f'[[stalls]]\nurl = "{discovered}"\n'
        elif url == discovered:
            body = '[[haybales]]\nname = "haybale-foo"\nversion = "0.1.0"\n'
        else:
            body = '[[haybales]]\nname = "haybale-foo"\nversion = "9.9.9"\n'
        m.__enter__.return_value.read.return_value = body.encode()
        return m

    with patch.object(marketstall_cache, "_urlopen", side_effect=fake):
        fetched = fetch_sources(global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c")
    collision = resolve(fetched).collisions[0]

    # Displayed as the stall it came from, but written against the aggregator.
    assert collision.losers == [(discovered, "0.1.0")]
    assert collision.loser_owners == [market]

    assert record_preference(global_path, source_url=market, haybale_name="haybale-foo") is True

    with patch.object(marketstall_cache, "_urlopen", side_effect=fake):
        refresh(global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c")

    cached = parse_project_marketplace(project_path).caches
    assert [h.version for h in cached] == ["0.1.0"]
    assert cached[0].via == discovered


@pytest.mark.unit
def test_record_preference_reports_when_no_subscription_can_own_it(tmp_path: Path) -> None:
    """False rather than a silent no-op, so the UI can say the click did nothing."""
    from haywire.core.marketstall.helpers import record_preference

    global_path = tmp_path / "global.toml"
    global_path.write_text("")

    assert record_preference(global_path, source_url="https://x.example/s.toml", haybale_name="hb") is False
