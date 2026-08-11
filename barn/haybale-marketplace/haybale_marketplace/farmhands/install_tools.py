"""marketplace_dry_run_install / marketplace_install_library / marketplace_uninstall_library."""

from __future__ import annotations

from haywire.core.farmhand import (
    Farmhand,
    FarmhandContext,
    FarmhandError,
    ToolAnnotations,
    farmhand,
)
from haywire.core.session.signals import LibraryCatalogChanged

from .catalog_tools import _library_manager, _progress_cb


@farmhand(
    label="Dry-run install",
    description="Resolve what an install would remove/upgrade, without installing (informational valve).",
    instructions="Resolve what installing install_spec would remove or upgrade, WITHOUT actually "
    "installing — a preview only, no changes to the venv. Run this before "
    "marketplace_install_library to see the blast radius. Returns the list of affected "
    "distributions; raises resolver_failed if resolution itself fails.",
    registry_id="dry_run_install",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True),
)
class MarketplaceDryRunInstallTool(Farmhand):
    async def run(self, ctx: FarmhandContext, install_spec: str) -> dict:
        try:
            affected = await _library_manager(ctx).dry_run(install_spec)
        except RuntimeError as exc:
            raise FarmhandError("resolver_failed", str(exc), ids={"install_spec": install_spec}) from exc
        return {
            "summary": f"Install of '{install_spec}' would touch {len(affected)} distributions.",
            "affected_distributions": affected,
        }


@farmhand(
    label="Install library",
    description="Install a library via uv pip (streams progress). Destructive: changes the venv. "
    "Run marketplace_dry_run_install first.",
    instructions="Install a library via uv pip (streams progress). DESTRUCTIVE: changes the "
    "venv. Run marketplace_dry_run_install first to preview what would be removed/upgraded. "
    "Raises install_failed with the underlying message on failure. On success, returns "
    "on_reload naming the follow-up action (e.g. whether a studio restart is needed) and "
    "broadcasts a catalog-changed signal.",
    registry_id="install_library",
    annotations=ToolAnnotations(destructive_hint=True, open_world_hint=True),
)
class MarketplaceInstallLibraryTool(Farmhand):
    async def run(self, ctx: FarmhandContext, install_spec: str) -> dict:
        manager = _library_manager(ctx)
        ok, message, hints = await manager.install(install_spec, _progress_cb(ctx))
        if not ok:
            raise FarmhandError("install_failed", message, ids={"install_spec": install_spec})
        ctx.broadcast(LibraryCatalogChanged())  # caller-owned signal, gap 5
        return {
            "summary": f"Installed '{install_spec}'. {message}",
            "on_reload": hints.action.value,
        }


@farmhand(
    label="Uninstall library",
    description="Uninstall an installed library via uv pip (streams progress). Destructive.",
    instructions="Uninstall an installed library by library_id via uv pip (streams progress). "
    "DESTRUCTIVE: changes the venv, and any graphs using this library's components will break. "
    "Raises uninstall_failed with the underlying message on failure. On success, returns "
    "on_reload naming the follow-up action and broadcasts a catalog-changed signal.",
    registry_id="uninstall_library",
    annotations=ToolAnnotations(destructive_hint=True),
)
class MarketplaceUninstallLibraryTool(Farmhand):
    async def run(self, ctx: FarmhandContext, library_id: str) -> dict:
        manager = _library_manager(ctx)
        ok, message, hints = await manager.uninstall_streaming(library_id, _progress_cb(ctx))
        if not ok:
            raise FarmhandError("uninstall_failed", message, ids={"library_id": library_id})
        ctx.broadcast(LibraryCatalogChanged())
        return {
            "summary": f"Uninstalled '{library_id}'. {message}",
            "on_reload": hints.action.value,
        }
