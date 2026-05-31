"""HTTP cache with tri-state outcomes.

Cache lives at ~/.haywire/cache/<url-hash>.toml. No TTL: entries are valid
until overwritten by a successful fetch. GC removes orphans (cache files
whose URL no longer corresponds to an active subscription) at end of refresh.

`cache_dir` parameter on every function: defaults to ~/.haywire/cache; tests
override to use tmp_path. Keeps the production code testable without
monkey-patching Path.home().
"""

from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.request
from pathlib import Path

from haywire.core.marketstall.errors import RemoteFetchError
from haywire.core.marketstall.types import FetchResult, RefreshOutcome

_URL_HASH_LEN = 16


def _default_cache_dir() -> Path:
    """Production cache directory: ~/.haywire/cache."""
    return Path.home() / ".haywire" / "cache"


def _url_hash(url: str) -> str:
    """Short hex hash of a URL, used as the cache filename stem."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:_URL_HASH_LEN]


def _cache_path(url: str, *, cache_dir: Path | None = None) -> Path:
    cache_dir = cache_dir if cache_dir is not None else _default_cache_dir()
    return cache_dir / f"{_url_hash(url)}.toml"


def cache_write(url: str, body: str, *, cache_dir: Path | None = None) -> None:
    """Cache a successful HTTP response; overwrites any previous entry."""
    path = _cache_path(url, cache_dir=cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def cache_read(url: str, *, cache_dir: Path | None = None) -> tuple[str | None, float | None]:
    """Return (body, age_in_seconds) for a URL, or (None, None) if no cache."""
    path = _cache_path(url, cache_dir=cache_dir)
    if not path.is_file():
        return None, None
    body = path.read_text(encoding="utf-8")
    age = time.time() - path.stat().st_mtime
    return body, age


def _urlopen(url: str, *, timeout: float):
    """Wrapped urllib.request.urlopen — separate function for ease of patching in tests."""
    return urllib.request.urlopen(url, timeout=timeout)


def fetch_with_cache_fallback(
    url: str,
    *,
    timeout: float = 5.0,
    cache_dir: Path | None = None,
) -> FetchResult:
    """Fetch a URL. On success: cache + return FRESH. On failure: try cache → CACHE_FALLBACK.

    Raises RemoteFetchError only when the URL fails AND no cache exists.
    Never returns UNAVAILABLE — the orchestrator converts the exception into
    that outcome at the call site.
    """
    try:
        with _urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
        cache_write(url, body, cache_dir=cache_dir)
        return FetchResult(body=body, outcome=RefreshOutcome.FRESH, cache_age=None)
    except (OSError, urllib.error.URLError):
        cached, age = cache_read(url, cache_dir=cache_dir)
        if cached is not None:
            return FetchResult(body=cached, outcome=RefreshOutcome.CACHE_FALLBACK, cache_age=age)
        raise RemoteFetchError(f"failed to fetch {url} and no cache available") from None


def gc_orphans(active_urls: set[str], *, cache_dir: Path | None = None) -> int:
    """Delete cache files whose URL is not in `active_urls`. Returns count deleted.

    At end of refresh, drop orphaned <url-hash>.toml files.
    Resolves URLs to their hashes; deletes any cache file whose stem doesn't
    match any active subscription. Missing cache dir returns 0 (nothing to GC).
    """
    cache_dir = cache_dir if cache_dir is not None else _default_cache_dir()
    if not cache_dir.is_dir():
        return 0

    active_hashes = {_url_hash(url) for url in active_urls}
    deleted = 0
    for path in cache_dir.iterdir():
        if not path.is_file() or path.suffix != ".toml":
            continue
        if path.stem not in active_hashes:
            path.unlink()
            deleted += 1
    return deleted
