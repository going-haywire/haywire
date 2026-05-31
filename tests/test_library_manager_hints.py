"""Tests for LibraryManager.install / .uninstall_streaming returning PostInstallHints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from haywire.core.library.identity import LibraryIdentity
from haywire.ui.modals.install_progress_modal import PostInstallHints

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _identity(lib_id: str, *, needs_refresh: bool = False, needs_restart: bool = False) -> LibraryIdentity:
    return LibraryIdentity(
        label=lib_id,
        version="0.0.1",
        description="",
        url="",
        help_url="",
        author="",
        author_url="",
        folder_path=f"/tmp/{lib_id}",
        module_name=lib_id,
        id=lib_id,
        needs_refresh=needs_refresh,
        needs_restart=needs_restart,
    )


def _make_manager(*, libraries_before: dict, libraries_after: dict):
    """Build a LibraryManager whose registry returns `libraries_before` until
    scan_for_libraries() is called, after which it returns `libraries_after`.
    """
    from haybale_marketplace.library_manager import LibraryManager
    from haywire.core.library.install_type import InstallType

    registry = MagicMock()
    state = {"libs": dict(libraries_before)}

    registry.list_names.side_effect = lambda: list(state["libs"].keys())

    def _get_identity(lid: str) -> LibraryIdentity:
        if lid not in state["libs"]:
            raise KeyError(lid)
        return state["libs"][lid]

    registry.get_library_identity.side_effect = _get_identity
    registry.get_library_install_type.return_value = InstallType.REGULAR
    registry.find_library_by_distribution_name.side_effect = lambda dn: dn.replace("-", "_")
    registry.get_library_distribution_name.side_effect = lambda lid: lid.replace("_", "-")

    def _scan() -> None:
        state["libs"] = dict(libraries_after)

    registry.scan_for_libraries.side_effect = _scan
    registry.enable_all_libraries.return_value = None

    def _remove(lid: str) -> bool:
        state["libs"].pop(lid, None)
        return True

    registry.remove_library.side_effect = _remove
    registry.disable_library.return_value = None

    mgr = LibraryManager(library_registry=registry)
    return mgr, registry


@pytest.mark.unit
async def test_install_success_no_flags_returns_empty_hints():
    """A fresh install of a library declaring neither flag → empty hints."""
    new_lib = _identity("new_lib")
    mgr, _ = _make_manager(libraries_before={}, libraries_after={"new_lib": new_lib})

    with (
        patch.object(mgr, "dry_run", new=AsyncMock(return_value=[])),
        patch.object(mgr, "_run_uv_streaming", new=AsyncMock(return_value=(True, ""))),
        patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda fn: fn())),
    ):
        success, _msg, hints = await mgr.install("new-lib", on_output=lambda _l: None)

    assert success is True
    assert hints == PostInstallHints()


@pytest.mark.unit
async def test_install_success_new_lib_needs_refresh_propagates():
    """A fresh install of a library declaring needs_refresh=True → hints.needs_refresh=True."""
    new_lib = _identity("graph_editor", needs_refresh=True)
    mgr, _ = _make_manager(libraries_before={}, libraries_after={"graph_editor": new_lib})

    with (
        patch.object(mgr, "dry_run", new=AsyncMock(return_value=[])),
        patch.object(mgr, "_run_uv_streaming", new=AsyncMock(return_value=(True, ""))),
        patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda fn: fn())),
    ):
        success, _msg, hints = await mgr.install("haybale-graph-editor", on_output=lambda _l: None)

    assert success is True
    assert hints.needs_refresh is True
    assert hints.needs_restart is False


@pytest.mark.unit
async def test_install_failure_with_evicted_restart_lib_returns_restart_hint():
    """Per Q12.A: if eviction removed a needs_restart library and then pip failed,
    hints.needs_restart must be True."""
    evicted = _identity("haybale_ext", needs_restart=True)
    mgr, _ = _make_manager(
        libraries_before={"haybale_ext": evicted}, libraries_after={"haybale_ext": evicted}
    )

    with (
        patch.object(mgr, "dry_run", new=AsyncMock(return_value=["haybale-ext"])),
        patch.object(mgr, "_run_uv_streaming", new=AsyncMock(return_value=(False, "pip exit 1"))),
    ):
        success, _msg, hints = await mgr.install("haybale-ext==2.0", on_output=lambda _l: None)

    assert success is False
    assert hints.needs_refresh is False  # failure never sets refresh
    assert hints.needs_restart is True


@pytest.mark.unit
async def test_install_upgrade_unions_new_and_evicted_flags():
    """Per Q6.A: install hints = OR over (newly-imported + evicted) for restart;
    OR over (newly-imported only) for refresh."""
    old_v = _identity("haybale_x", needs_restart=True, needs_refresh=False)
    new_v = _identity("haybale_x", needs_restart=False, needs_refresh=True)
    mgr, _ = _make_manager(libraries_before={"haybale_x": old_v}, libraries_after={"haybale_x": new_v})

    with (
        patch.object(mgr, "dry_run", new=AsyncMock(return_value=["haybale-x"])),
        patch.object(mgr, "_run_uv_streaming", new=AsyncMock(return_value=(True, ""))),
        patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda fn: fn())),
    ):
        success, _msg, hints = await mgr.install("haybale-x==2.0", on_output=lambda _l: None)

    assert success is True
    # refresh: True (new version declares it)
    assert hints.needs_refresh is True
    # restart: True (old version declared it; OR'd in from evicted set)
    assert hints.needs_restart is True


@pytest.mark.unit
async def test_uninstall_propagates_needs_restart_only():
    """Per Q5/B: uninstall hints.needs_refresh is always False; needs_restart
    comes from the removed library."""
    target = _identity("haybale_ext", needs_restart=True, needs_refresh=True)
    mgr, _ = _make_manager(libraries_before={"haybale_ext": target}, libraries_after={})

    with (
        patch.object(mgr, "_run_uv_streaming", new=AsyncMock(return_value=(True, ""))),
        patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda fn: fn())),
    ):
        success, _msg, hints = await mgr.uninstall_streaming("haybale_ext", on_output=lambda _l: None)

    assert success is True
    assert hints.needs_refresh is False  # uninstall never sets refresh
    assert hints.needs_restart is True


@pytest.mark.unit
async def test_uninstall_with_no_restart_flag_returns_empty_hints():
    """Uninstalling a library that didn't declare needs_restart → empty hints."""
    target = _identity("haybale_plain")
    mgr, _ = _make_manager(libraries_before={"haybale_plain": target}, libraries_after={})

    with (
        patch.object(mgr, "_run_uv_streaming", new=AsyncMock(return_value=(True, ""))),
        patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda fn: fn())),
    ):
        success, _msg, hints = await mgr.uninstall_streaming("haybale_plain", on_output=lambda _l: None)

    assert success is True
    assert hints == PostInstallHints()
