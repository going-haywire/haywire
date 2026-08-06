"""Shared helpers for baseline tools: pagination, kind maps, target-library resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from haywire.core.farmhand import FarmhandContext, FarmhandError
from haywire.core.library.kinds import KIND_FOLDERS, kind_registry_map  # noqa: F401
from haywire.core.library.registry import LibraryRegistry


def page(items: list, limit: int, offset: int) -> tuple[list, int]:
    return items[offset : offset + limit], len(items)


def resolve_component_class(ctx: FarmhandContext, registry_key: str) -> Any:
    parts = registry_key.split(":")
    if len(parts) != 3 or parts[1] not in kind_registry_map():
        raise FarmhandError(
            "bad_registry_key",
            f"Registry keys look like '{{lib_id}}:{{kind}}:{{name}}' with kind one of "
            f"{sorted(kind_registry_map())}; got '{registry_key}'.",
            ids={"registry_key": registry_key},
        )
    registry: Any = ctx.registry(kind_registry_map()[parts[1]])
    cls = registry.get(registry_key)
    if cls is None:
        raise FarmhandError(
            "component_not_found",
            f"No component registered under '{registry_key}'.",
            ids={"registry_key": registry_key},
        )
    return cls


def project_writable_libraries(ctx: FarmhandContext) -> list[str]:
    """Libraries Farmhand may author into: the EDITABLE (pip ``-e``) installs.

    Uses ``InstallType.is_editable()`` — the SAME authority the source editor's
    read-only badge consults (ComponentSourceEditor._compute_is_editable) — so the
    UI "Edit" button and this write gate can never disagree. An editable install
    IS the developer's on-disk source (that is the point of ``-e``), and the
    framework hot-reloads it; Farmhand may write it regardless of whether its path
    sits under the current workspace root. REGULAR (site-packages, immutable) and
    FOLDER (framework-owned builtin) are excluded.

    Deliberately broader than LibraryOrigin.PROJECT_LOCAL (haybale_marketplace's
    "is this literally under this workspace's barn/" classification): any
    editable install anywhere satisfies Farmhand's actual need
    ("can I write this source"), including a symlinked-in editable install of
    someone else's library. Renamed from project_local_libraries, which implied
    the narrower origin-axis meaning it never actually had — see
    internals/handoff/library-origin-and-required-classification.md.
    """
    registry = ctx.registry(LibraryRegistry)
    result = []
    for lib_id in registry.list_names():
        install_type = registry.get_library_install_type(lib_id)
        if install_type is not None and install_type.is_editable():
            result.append(lib_id)
    return sorted(result)


def resolve_target_library(ctx: FarmhandContext, library: str | None) -> str:
    locals_ = project_writable_libraries(ctx)
    if library is not None:
        if library not in locals_:
            raise FarmhandError(
                "not_project_library",
                f"'{library}' is not a project-local library (project-local: {locals_ or 'none'}). "
                f"Farmhand writes source only into project-local libraries.",
                ids={"library": library},
            )
        return library
    if not locals_:
        raise FarmhandError(
            "no_project_library",
            "No project-local library exists in this workspace — create one with 'haywire init'.",
        )
    if len(locals_) > 1:
        raise FarmhandError(
            "ambiguous_project_library",
            f"Several project-local libraries exist; pass library= explicitly: {locals_}.",
        )
    return locals_[0]


def library_folder(ctx: FarmhandContext, lib_id: str) -> Path:
    registry = ctx.registry(LibraryRegistry)
    identity = registry.get_library_identity(lib_id)
    return Path(identity.folder_path)
