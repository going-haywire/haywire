"""HTTP cache with tri-state outcomes.

Cache lives at ~/.haywire/cache/<url-hash>.toml. Entries never expire: they are
valid until overwritten by a successful fetch, or collected by
:func:`gc_orphans` / :func:`gc_doc_dirs`.

Every function takes ``cache_dir``, defaulting to ~/.haywire/cache.
"""

from __future__ import annotations

import hashlib
import shutil
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
    """Wrap ``urllib.request.urlopen`` as a single patch point."""
    return urllib.request.urlopen(url, timeout=timeout)


def fetch_with_cache_fallback(
    url: str,
    *,
    timeout: float = 5.0,
    cache_dir: Path | None = None,
) -> FetchResult:
    """Fetch a URL, caching the body on success and falling back to the cache on failure.

    Returns ``FRESH`` on success (the cache is overwritten) and
    ``CACHE_FALLBACK`` when the fetch failed but a cached body exists. Never
    returns ``UNAVAILABLE``.

    Raises:
        RemoteFetchError: The URL failed and no cache exists.
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


def docs_cache_dir(library: str, *, cache_dir: Path | None = None) -> Path:
    """Per-library partition of the doc-body cache: <cache>/docs/<library>/.

    :func:`gc_orphans` scans only top-level files, so these directories survive
    it; :func:`gc_doc_dirs` collects them instead.
    """
    base = cache_dir if cache_dir is not None else _default_cache_dir()
    return base / "docs" / library


def fetch_doc(
    url: str,
    library: str,
    *,
    timeout: float = 6.0,
    cache_dir: Path | None = None,
) -> str | None:
    """Fetch a documentation URL through the shared cache-with-fallback.

    Returns the body, fresh or from cache, or ``None`` when the URL fails and
    no cache exists.
    """
    try:
        result = fetch_with_cache_fallback(
            url, timeout=timeout, cache_dir=docs_cache_dir(library, cache_dir=cache_dir)
        )
    except RemoteFetchError:
        return None
    return result.body


def gc_doc_dirs(active_libraries: set[str], *, cache_dir: Path | None = None) -> int:
    """Delete <cache>/docs/<library>/ for libraries not in ``active_libraries``.

    Returns the number of directories removed; 0 when the docs directory does
    not exist.
    """
    base = (cache_dir if cache_dir is not None else _default_cache_dir()) / "docs"
    if not base.is_dir():
        return 0
    removed = 0
    for child in base.iterdir():
        if child.is_dir() and child.name not in active_libraries:
            shutil.rmtree(child)
            removed += 1
    return removed


def gc_orphans(active_urls: set[str], *, cache_dir: Path | None = None) -> int:
    """Delete top-level <url-hash>.toml cache files whose URL is not in ``active_urls``.

    Returns the number deleted; 0 when the cache directory does not exist.
    Subdirectories are left alone (see :func:`docs_cache_dir`).
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
