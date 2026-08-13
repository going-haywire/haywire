"""Tests for LibraryManager.install / .uninstall_streaming returning PostInstallHints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from haywire.core.library.identity import LibraryIdentity, LibraryReloadAction
from haywire.ui.modals.install_progress_modal import PostInstallHints

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _identity(lib_id: str, *, on_reload: LibraryReloadAction = LibraryReloadAction.NONE) -> LibraryIdentity:
    return LibraryIdentity(
        label=lib_id,
        version="0.0.1",
        folder_path=f"/tmp/{lib_id}",
        module_name=lib_id,
        name=lib_id,
        on_reload=on_reload,
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
async def test_install_success_new_lib_refresh_propagates():
    """A fresh install of a library declaring REFRESH → hints carry REFRESH."""
    new_lib = _identity("graph_editor", on_reload=LibraryReloadAction.REFRESH)
    mgr, _ = _make_manager(libraries_before={}, libraries_after={"graph_editor": new_lib})

    with (
        patch.object(mgr, "dry_run", new=AsyncMock(return_value=[])),
        patch.object(mgr, "_run_uv_streaming", new=AsyncMock(return_value=(True, ""))),
        patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda fn: fn())),
    ):
        success, _msg, hints = await mgr.install("haybale-graph-editor", on_output=lambda _l: None)

    assert success is True
    assert hints.action is LibraryReloadAction.REFRESH


@pytest.mark.unit
async def test_install_failure_with_evicted_restart_lib_returns_restart_hint():
    """Per Q12.A: if eviction removed a RESTART library and then pip failed, the
    restart is still owed — the library is gone from the registry either way."""
    evicted = _identity("haybale_ext", on_reload=LibraryReloadAction.RESTART)
    mgr, _ = _make_manager(
        libraries_before={"haybale_ext": evicted}, libraries_after={"haybale_ext": evicted}
    )

    with (
        patch.object(mgr, "dry_run", new=AsyncMock(return_value=["haybale-ext"])),
        patch.object(mgr, "_run_uv_streaming", new=AsyncMock(return_value=(False, "pip exit 1"))),
    ):
        success, _msg, hints = await mgr.install("haybale-ext==2.0", on_output=lambda _l: None)

    assert success is False
    assert hints.action is LibraryReloadAction.RESTART


@pytest.mark.unit
async def test_install_upgrade_takes_the_heavier_of_new_and_evicted():
    """An upgrade combines the outgoing and incoming declarations; the heavier
    wins, because the old version's code is what is currently loaded."""
    old_v = _identity("haybale_x", on_reload=LibraryReloadAction.RESTART)
    new_v = _identity("haybale_x", on_reload=LibraryReloadAction.REFRESH)
    mgr, _ = _make_manager(libraries_before={"haybale_x": old_v}, libraries_after={"haybale_x": new_v})

    with (
        patch.object(mgr, "dry_run", new=AsyncMock(return_value=["haybale-x"])),
        patch.object(mgr, "_run_uv_streaming", new=AsyncMock(return_value=(True, ""))),
        patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda fn: fn())),
    ):
        success, _msg, hints = await mgr.install("haybale-x==2.0", on_output=lambda _l: None)

    assert success is True
    assert hints.action is LibraryReloadAction.RESTART


@pytest.mark.unit
async def test_eviction_alone_demands_nothing():
    """Hot-reload ejects the old modules and rebinds, so an upgrade that evicts a
    live library asks nothing of the user unless a library declared it.

    Inverts the former rule, which forced a restart on every eviction and so
    fired the affordance on routine upgrades.
    """
    old_v = _identity("haybale_y")
    new_v = _identity("haybale_y")
    mgr, _ = _make_manager(libraries_before={"haybale_y": old_v}, libraries_after={"haybale_y": new_v})

    with (
        patch.object(mgr, "dry_run", new=AsyncMock(return_value=["haybale-y"])),
        patch.object(mgr, "_run_uv_streaming", new=AsyncMock(return_value=(True, ""))),
        patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda fn: fn())),
    ):
        success, _msg, hints = await mgr.install("haybale-y==2.0", on_output=lambda _l: None)

    assert success is True
    assert hints.action is LibraryReloadAction.NONE


@pytest.mark.unit
async def test_install_unions_across_transitively_imported_libraries():
    """One install can import several libraries — the named package plus the
    haybale dependencies it pulls in. Any of them may escalate."""
    named = _identity("haybale_named")
    pulled = _identity("haybale_dep", on_reload=LibraryReloadAction.RESTART)
    mgr, _ = _make_manager(
        libraries_before={},
        libraries_after={"haybale_named": named, "haybale_dep": pulled},
    )

    with (
        patch.object(mgr, "dry_run", new=AsyncMock(return_value=[])),
        patch.object(mgr, "_run_uv_streaming", new=AsyncMock(return_value=(True, ""))),
        patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda fn: fn())),
    ):
        success, _msg, hints = await mgr.install("haybale-named", on_output=lambda _l: None)

    assert success is True
    assert hints.action is LibraryReloadAction.RESTART


@pytest.mark.unit
async def test_fresh_install_of_a_plain_library_demands_nothing():
    """Guards the affordance against firing on a routine install."""
    new_lib = _identity("brand_new")
    mgr, _ = _make_manager(libraries_before={}, libraries_after={"brand_new": new_lib})

    with (
        patch.object(mgr, "dry_run", new=AsyncMock(return_value=[])),
        patch.object(mgr, "_run_uv_streaming", new=AsyncMock(return_value=(True, ""))),
        patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda fn: fn())),
    ):
        success, _msg, hints = await mgr.install("brand-new", on_output=lambda _l: None)

    assert success is True
    assert hints.action is LibraryReloadAction.NONE


@pytest.mark.unit
@pytest.mark.parametrize("action", [LibraryReloadAction.REFRESH, LibraryReloadAction.RESTART])
async def test_uninstall_propagates_the_declaration_symmetrically(action: LibraryReloadAction):
    """The declaration is symmetric: what could not be hot-swapped in cannot be
    hot-swapped out either, so uninstall carries REFRESH as well as RESTART.

    Inverts the former rule, which dropped refresh on uninstall.
    """
    target = _identity("haybale_ext", on_reload=action)
    mgr, _ = _make_manager(libraries_before={"haybale_ext": target}, libraries_after={})

    with (
        patch.object(mgr, "_run_uv_streaming", new=AsyncMock(return_value=(True, ""))),
        patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda fn: fn())),
    ):
        success, _msg, hints = await mgr.uninstall_streaming("haybale_ext", on_output=lambda _l: None)

    assert success is True
    assert hints.action is action


@pytest.mark.unit
async def test_uninstall_with_no_declaration_returns_empty_hints():
    """Uninstalling a library that declared nothing → empty hints."""
    target = _identity("haybale_plain")
    mgr, _ = _make_manager(libraries_before={"haybale_plain": target}, libraries_after={})

    with (
        patch.object(mgr, "_run_uv_streaming", new=AsyncMock(return_value=(True, ""))),
        patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda fn: fn())),
    ):
        success, _msg, hints = await mgr.uninstall_streaming("haybale_plain", on_output=lambda _l: None)

    assert success is True
    assert hints == PostInstallHints()
