"""Tier-2 component doc drill on MarketplaceGetLibraryDocsTool: installed (wheel) vs
available (docs_url, via the shared fetch_doc cache)."""

from __future__ import annotations

import asyncio

import pytest

from haywire.core.farmhand import FarmhandContext
from haywire.core.library.kinds import doc_filename
from haywire.core.marketstall.types import Haybale

pytestmark = pytest.mark.integration


def run_tool(tool_cls, **kwargs):
    return asyncio.run(tool_cls().run(FarmhandContext(), **kwargs))


@pytest.fixture(autouse=True)
def _ambient(library_system, tmp_path):
    """Same ambient-workspace-root setup as tests/farmhand/test_baseline_tools.py."""
    from haywire.core.di import context as di_context

    previous = di_context._workspace_root
    di_context.set_workspace_root(str(tmp_path))
    yield
    di_context._workspace_root = previous


def test_installed_component_doc_read_from_wheel():
    """A component doc for an installed library is read from its module dir."""
    from pathlib import Path

    from haybale_marketplace.farmhands.catalog_tools import MarketplaceGetLibraryDocsTool
    from haywire.core.library.registry import LibraryRegistry

    ctx = FarmhandContext()
    registry = ctx.registry(LibraryRegistry)
    folder = registry.get_library_identity("testing").folder_path
    docs_dir = Path(folder) / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    key = "testing:node:drilldown_probe"
    doc_path = docs_dir / doc_filename(key)
    doc_path.write_text("# Resize\n\nports...", encoding="utf-8")
    try:
        result = run_tool(MarketplaceGetLibraryDocsTool, library="testing", component=key)
        assert "Resize" in result["text"]
        assert result["source"] == "installed"
    finally:
        doc_path.unlink()


@pytest.mark.anyio
async def test_available_component_doc_fetched_over_docs_path(tmp_path, monkeypatch):
    """A component doc for an available (not-installed) library is fetched via docs_path."""
    from haybale_marketplace.farmhands.catalog_tools import MarketplaceGetLibraryDocsTool
    from haybale_marketplace.state.marketplace_state import MarketplaceState
    from haywire.core.marketstall import cache as cache_mod

    class _Resp:
        def read(self):
            return b"# Remote Resize"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(cache_mod, "_urlopen", lambda url, *, timeout: _Resp())
    monkeypatch.setattr(cache_mod, "_default_cache_dir", lambda: tmp_path)

    pkg = Haybale(
        name="not_installed_lib",
        version="1.0.0",
        origin="https://github.com/me/repo",
        install_spec=("not_installed_lib @ git+https://github.com/me/repo.git@v1.0.0#subdirectory=barn/lib"),
        docs_path="barn/lib/haybale_lib",
    )
    monkeypatch.setattr(MarketplaceState, "get_project_haybales", lambda self: [pkg])

    result = await MarketplaceGetLibraryDocsTool().run(
        FarmhandContext(), library="not_installed_lib", component="lib:node:resize"
    )
    assert "Remote Resize" in result["text"]
    assert result["source"] == "available"
