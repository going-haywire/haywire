"""fetch_overview routes through the shared doc cache instead of raw urllib."""

from __future__ import annotations

import pytest

from haywire.core.marketstall import cache as cache_mod
from haywire.core.marketstall.cache import docs_cache_dir
from haywire.core.marketstall.types import Haybale


@pytest.mark.anyio
async def test_fetch_overview_writes_to_docs_cache(tmp_path, monkeypatch):
    from haybale_marketplace.state.marketplace_state import MarketplaceState

    class _Resp:
        def read(self):
            return b"# OVERVIEW"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(cache_mod, "_urlopen", lambda url, *, timeout: _Resp())

    pkg = Haybale(name="lib", min_version="1.0.0", docs_url="https://raw.example.com/lib/module/")
    state = MarketplaceState.__new__(MarketplaceState)  # avoid full DI init
    text = await state.fetch_overview(pkg, cache_dir=tmp_path)
    assert text == "# OVERVIEW"
    assert docs_cache_dir("lib", cache_dir=tmp_path).is_dir()
