"""Tests for LibraryManager.dry_run() and _parse_dry_run_removals()."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_manager():
    from haybale_marketplace.library_manager import LibraryManager

    registry = MagicMock()
    registry._library_distribution_names = {}
    registry._library_install_types = {}
    registry._library_sources = {}
    return LibraryManager(library_registry=registry)


@pytest.mark.unit
def test_parse_dry_run_removals_extracts_minus_lines():
    """_parse_dry_run_removals must return normalised dist names from ' - name==ver' lines."""
    mgr = _make_manager()
    output = (
        "Resolved 68 packages in 912ms\n"
        "Would uninstall 2 packages\n"
        " - haybale-core==0.0.5\n"
        " + haybale-core==0.0.6\n"
        " - haybale-visiongraph==0.0.5\n"
        " + haybale-visiongraph==0.0.6\n"
    )
    result = mgr._parse_dry_run_removals(output)
    assert result == ["haybale-core", "haybale-visiongraph"]


@pytest.mark.unit
def test_parse_dry_run_removals_no_changes():
    """_parse_dry_run_removals must return empty list for 'Would make no changes'."""
    mgr = _make_manager()
    output = "Resolved 12 packages in 120ms\nWould make no changes\n"
    result = mgr._parse_dry_run_removals(output)
    assert result == []


@pytest.mark.unit
def test_parse_dry_run_removals_empty_output():
    """_parse_dry_run_removals must return empty list for empty output."""
    mgr = _make_manager()
    assert mgr._parse_dry_run_removals("") == []


@pytest.mark.unit
async def test_dry_run_returns_removals_list():
    """dry_run() must call uv with --dry-run and return parsed removal names."""
    mgr = _make_manager()

    async def fake_run(args, on_output):
        # Simulate uv output for a dry-run that would upgrade haybale-core
        on_output(" - haybale-core==0.0.5")
        on_output(" + haybale-core==0.0.6")
        return True, ""

    with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
        result = await mgr.dry_run("haybale-visiongraph")

    assert result == ["haybale-core"]


@pytest.mark.unit
async def test_dry_run_already_satisfied_returns_empty():
    """dry_run() must return [] when uv reports no changes needed."""
    mgr = _make_manager()

    async def fake_run(args, on_output):
        on_output("Would make no changes")
        return True, ""

    with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
        result = await mgr.dry_run("haybale-visiongraph==0.0.6")

    assert result == []


@pytest.mark.unit
async def test_dry_run_resolver_error_raises():
    """dry_run() must raise RuntimeError when uv exits non-zero."""
    mgr = _make_manager()

    async def fake_run(args, on_output):
        return False, "error: no solution found"

    with patch.object(mgr, "_run_uv_streaming", side_effect=fake_run):
        with pytest.raises(RuntimeError, match="Dependency resolution failed"):
            await mgr.dry_run("haybale-bad-pkg")
