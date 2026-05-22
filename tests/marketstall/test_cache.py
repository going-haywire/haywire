"""HTTP cache — spec §7.3 (tri-state, no TTL, GC of orphans)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from haywire.core.marketstall.errors import RemoteFetchError
from haywire.core.marketstall.types import RefreshOutcome


@pytest.mark.unit
def test_cache_write_and_read_roundtrip(tmp_path: Path) -> None:
    from haywire.core.marketstall.cache import cache_read, cache_write

    cache_dir = tmp_path / "cache"
    cache_write("https://x.example/m.toml", "body-text", cache_dir=cache_dir)
    body, age = cache_read("https://x.example/m.toml", cache_dir=cache_dir)
    assert body == "body-text"
    assert age is not None
    assert age >= 0


@pytest.mark.unit
def test_cache_read_missing_returns_none(tmp_path: Path) -> None:
    from haywire.core.marketstall.cache import cache_read

    body, age = cache_read("https://x.example/missing.toml", cache_dir=tmp_path)
    assert body is None
    assert age is None


@pytest.mark.unit
def test_url_hash_is_stable() -> None:
    from haywire.core.marketstall.cache import _url_hash

    h1 = _url_hash("https://x.example/m.toml")
    h2 = _url_hash("https://x.example/m.toml")
    assert h1 == h2
    assert h1 != _url_hash("https://y.example/m.toml")


@pytest.mark.unit
def test_fetch_with_cache_fallback_fresh(tmp_path: Path) -> None:
    from haywire.core.marketstall.cache import fetch_with_cache_fallback

    with patch("haywire.core.marketstall.cache._urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = b"fresh-body"
        result = fetch_with_cache_fallback("https://x.example/m.toml", cache_dir=tmp_path / "cache")
    assert result.body == "fresh-body"
    assert result.outcome is RefreshOutcome.FRESH
    assert result.cache_age is None


@pytest.mark.unit
def test_fetch_with_cache_fallback_uses_cache_on_failure(tmp_path: Path) -> None:
    from haywire.core.marketstall.cache import cache_write, fetch_with_cache_fallback

    cache_dir = tmp_path / "cache"
    cache_write("https://x.example/m.toml", "cached-body", cache_dir=cache_dir)

    with patch("haywire.core.marketstall.cache._urlopen", side_effect=OSError("network down")):
        result = fetch_with_cache_fallback("https://x.example/m.toml", cache_dir=cache_dir)
    assert result.body == "cached-body"
    assert result.outcome is RefreshOutcome.CACHE_FALLBACK
    assert result.cache_age is not None


@pytest.mark.unit
def test_fetch_with_cache_fallback_raises_when_no_cache(tmp_path: Path) -> None:
    from haywire.core.marketstall.cache import fetch_with_cache_fallback

    with patch("haywire.core.marketstall.cache._urlopen", side_effect=OSError("network down")):
        with pytest.raises(RemoteFetchError):
            fetch_with_cache_fallback("https://x.example/m.toml", cache_dir=tmp_path / "cache")


@pytest.mark.unit
def test_gc_orphans_keeps_active_urls(tmp_path: Path) -> None:
    from haywire.core.marketstall.cache import cache_write, gc_orphans

    cache_dir = tmp_path / "cache"
    cache_write("https://active.example/m.toml", "a", cache_dir=cache_dir)
    cache_write("https://orphan.example/m.toml", "o", cache_dir=cache_dir)

    deleted = gc_orphans({"https://active.example/m.toml"}, cache_dir=cache_dir)

    files = sorted(p.name for p in cache_dir.iterdir())
    assert len(files) == 1  # only the active one remains
    assert deleted == 1


@pytest.mark.unit
def test_gc_orphans_no_op_when_all_active(tmp_path: Path) -> None:
    from haywire.core.marketstall.cache import cache_write, gc_orphans

    cache_dir = tmp_path / "cache"
    cache_write("https://x.example/m.toml", "body", cache_dir=cache_dir)
    deleted = gc_orphans({"https://x.example/m.toml"}, cache_dir=cache_dir)
    assert deleted == 0


@pytest.mark.unit
def test_gc_orphans_handles_missing_cache_dir(tmp_path: Path) -> None:
    from haywire.core.marketstall.cache import gc_orphans

    deleted = gc_orphans({"https://x.example/m.toml"}, cache_dir=tmp_path / "no-cache")
    assert deleted == 0
