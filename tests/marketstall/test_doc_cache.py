"""Doc-body cache primitives: docs_cache_dir, fetch_doc, gc_doc_dirs."""

from __future__ import annotations

from haywire.core.marketstall import cache as cache_mod
from haywire.core.marketstall.cache import docs_cache_dir, fetch_doc, gc_doc_dirs


def test_docs_cache_dir_partitions_by_library(tmp_path):
    d = docs_cache_dir("haybale-image", cache_dir=tmp_path)
    assert d == tmp_path / "docs" / "haybale-image"


def test_fetch_doc_caches_then_serves_from_cache(tmp_path, monkeypatch):
    calls = {"n": 0}

    class _Resp:
        def __init__(self, body):
            self._body = body

        def read(self):
            return self._body.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(url, *, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            return _Resp("# Docs")
        raise OSError("network down")

    monkeypatch.setattr(cache_mod, "_urlopen", fake_urlopen)

    # First call: FRESH, writes cache.
    assert fetch_doc("http://x/OVERVIEW.md", "lib", cache_dir=tmp_path) == "# Docs"
    # Second call: network fails, but cache serves the body.
    assert fetch_doc("http://x/OVERVIEW.md", "lib", cache_dir=tmp_path) == "# Docs"
    assert (docs_cache_dir("lib", cache_dir=tmp_path)).is_dir()


def test_fetch_doc_returns_none_when_unreachable_and_uncached(tmp_path, monkeypatch):
    def fake_urlopen(url, *, timeout):
        raise OSError("network down")

    monkeypatch.setattr(cache_mod, "_urlopen", fake_urlopen)
    assert fetch_doc("http://x/OVERVIEW.md", "lib", cache_dir=tmp_path) is None


def test_gc_doc_dirs_removes_only_inactive_libraries(tmp_path):
    (tmp_path / "docs" / "keep").mkdir(parents=True)
    (tmp_path / "docs" / "drop").mkdir(parents=True)
    removed = gc_doc_dirs({"keep"}, cache_dir=tmp_path)
    assert removed == 1
    assert (tmp_path / "docs" / "keep").is_dir()
    assert not (tmp_path / "docs" / "drop").exists()


def test_gc_doc_dirs_missing_dir_is_zero(tmp_path):
    assert gc_doc_dirs({"anything"}, cache_dir=tmp_path) == 0
