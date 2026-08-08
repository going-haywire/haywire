"""Edit-identity dialog for LibraryOverviewEditor.

Identity only. Both of the fields this dialog once wrote and no longer does —
the package name and the dependency list — moved out for the same reason: they
need a flow that can sequence several writes and validate between them. Rename
runs from the CLI with studio stopped; dependencies are authored by
``haywire share``, whose steps each own disjoint entries in
``[project] dependencies``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Coroutine

import toml
from nicegui import ui

from haywire.core.library.identity import LibraryReloadAction
from haywire.core.library.info import LibraryInfo
from haywire.ui import elements as hui
from haywire.ui.modals import info_modal

from haybale_marketplace.library_origin import is_project_library

if TYPE_CHECKING:
    from haybale_marketplace.library_manager import LibraryManager
    from haywire.core.session.context import SessionContext

logger = logging.getLogger(__name__)


def read_os_from_pyproject(lib: LibraryInfo, marketplace_path: str | None) -> list[str]:
    """Read the heap's current [tool.haywire].os values. Empty list if unset or non-heap."""
    if not is_project_library(lib, marketplace_path):
        return []
    if not lib.identity.folder_path:
        return []
    # lib.identity.folder_path is the MODULE path (e.g. workspace/barn/haybale-foo/haybale_foo).
    # The pyproject.toml lives in its parent.
    pyproject = Path(lib.identity.folder_path).parent / "pyproject.toml"
    if not pyproject.is_file():
        return []
    try:
        data = toml.loads(pyproject.read_text())
    except Exception:
        return []
    os_decl = data.get("tool", {}).get("haywire", {}).get("os", [])
    return [v for v in os_decl if isinstance(v, str)]


def build_edit_dialog(
    lib: LibraryInfo,
    marketplace_path: str | None,
    manager: "LibraryManager",
    context: "SessionContext",
    on_save: Callable[[dict], Coroutine[Any, Any, None]],
) -> "ui.dialog":
    """Build the Edit dialog — all identity fields immediately editable.

    The package name is read-only. To rename a library use the CLI:
    ``uv run haywire rename haybale-<name> <new-name>`` with studio stopped.

    ``on_save`` is an async callable that receives the identity dict and
    performs the actual save + rebuild (stays in the editor class).
    """
    old_name_part = (
        lib.distribution_name.removeprefix("haybale-") if lib.distribution_name else lib.identity.id
    )

    with ui.dialog() as edit_dialog, hui.dialog_card("w-[480px]"):
        ui.label("Edit Library").classes("text-base font-medium hw-text-body")
        ui.label(f"haybale-{old_name_part}").classes("text-xs hw-text-muted font-mono")
        hui.separator()

        hui.section_label("Identity")
        label_input = hui.input_field(label="Label", value=lib.identity.label)
        # Version is not editable here — it's set by Share/publish (lockstep bump),
        # which overwrites this on the next publish regardless of what's typed here.
        ui.label(f"Version: {lib.identity.version or '0.1.0'} (set via Share/publish)").classes(
            "text-xs hw-text-dim"
        )
        desc_input = hui.input_field(label="Description", value=lib.identity.description)
        author_input = hui.input_field(label="Author", value=lib.identity.author)
        author_url_input = hui.input_field(label="Author URL", value=lib.identity.author_url)
        url_input = hui.input_field(label="URL", value=lib.identity.url)
        tags_input = hui.input_field(
            label="Tags (comma-separated)",
            value=", ".join(lib.identity.tags or []),
        )
        # Dependencies are authored by `haywire share`, not here. Three steps of
        # the publish flow write this list — the framework floor, removals, and
        # additions — each owning disjoint entries so none can clobber another's.
        # A second writer with no such discipline is how the framework floor got
        # silently rewritten in the first place.
        ui.label(
            f"Dependencies: {', '.join(lib.identity.dependencies or []) or '(none)'} (set via Share/publish)"
        ).classes("text-xs hw-text-dim")

        hui.separator()

        hui.section_label("Reload requirement")
        ui.label("Declare behavior for install, update, and uninstall alike.").classes("text-xs hw-text-dim")
        on_reload_select = hui.select_field(
            options={
                LibraryReloadAction.NONE.value: "No special action — library is hot-reloadable",
                LibraryReloadAction.REFRESH.value: (
                    "Reload the page — registers Vue components or JS resources"
                ),
                LibraryReloadAction.RESTART.value: (
                    "Restart the Studio — C-extension modules, import-time global mutation"
                ),
            },
            value=lib.identity.on_reload.value,
        ).classes("w-full")

        # OS multi-select. Visible only for heaps (writable pyproject.toml).
        _is_heap = is_project_library(lib, marketplace_path)
        current_os = read_os_from_pyproject(lib, marketplace_path) if _is_heap else []
        os_select = None
        if _is_heap:
            os_select = (
                hui.select_field(
                    options={"macos": "macOS", "windows": "Windows", "linux": "Linux"},
                    value=current_os,
                    multiple=True,
                    label="Supported OS (leave empty = all platforms)",
                )
                .classes("w-full")
                .props("use-chips")
            )
        else:
            # Installed wheels: read-only display of any os declaration.
            marketplace_pkg = getattr(context, "active_marketplace_pkg", None)
            wheel_os = list(getattr(marketplace_pkg, "os", []) or []) if marketplace_pkg else []
            if wheel_os:
                ui.label(f"Supported OS (read-only): {', '.join(wheel_os)}").classes("text-xs hw-text-dim")

        hui.separator()

        hui.section_label("Package Name")
        name_input = hui.input_field(value=old_name_part).props("readonly")
        with name_input.add_slot("prepend"):
            ui.label("haybale-").classes("text-sm font-mono hw-text-muted")
        _cur = f"haybale-{old_name_part}"
        with name_input.add_slot("append"):
            hui.icon_action(
                "info",
                tooltip="How to rename",
                size="sm",
                on_click=lambda c=_cur: info_modal(
                    title="Renaming a library",
                    icon="info",
                    message=(
                        "Renaming happens from the command line, with studio stopped:\n"
                        "\n"
                        "1.  Quit studio\n"
                        f"2.  uv run haywire rename {c} <new-name>\n"
                        "3.  Restart studio\n"
                    ),
                    detail=(
                        "The reason is rename rewrites installed packages and runs "
                        "`uv sync`, which isn't safe while studio is running."
                    ),
                ),
            )

        async def _save():
            identity = {
                "label": label_input.value.strip(),
                "description": desc_input.value.strip(),
                "url": url_input.value.strip(),
                "author": author_input.value.strip(),
                "author_url": author_url_input.value.strip(),
                "tags": [t.strip() for t in tags_input.value.split(",") if t.strip()],
                # Passed through untouched: this dialog no longer authors
                # dependencies, but the identity dict is written wholesale, so
                # omitting the key would erase the declaration.
                "dependencies": list(lib.identity.dependencies or []),
                "on_reload": on_reload_select.value or LibraryReloadAction.NONE.value,
            }
            # Include `os` only if the multi-select was rendered (heap libraries).
            if os_select is not None:
                identity["os"] = list(os_select.value or [])
            edit_dialog.close()
            await on_save(identity)

        hui.dialog_actions(
            on_confirm=_save,
            on_cancel=edit_dialog.close,
            confirm_label="Save Changes",
        )

    return edit_dialog
