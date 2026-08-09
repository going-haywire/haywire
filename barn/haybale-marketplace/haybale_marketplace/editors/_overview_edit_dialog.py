"""Edit-metadata dialog for LibraryOverviewEditor.

Writes ``haybale.toml`` and nothing else — no ``uv sync``, no module eviction,
no restart. The runtime reads that file at the point of use, so the next render
shows the change.

What this dialog deliberately cannot write, and why:

* ``name`` / ``id`` — immutable. They key every saved graph's node references
  and every consumer's ``install_spec``. Renaming runs from the CLI with studio
  stopped, because it rewrites installed packages and runs ``uv sync``.
* ``version`` / ``origin`` — the share wizard writes these from facts it
  observes (the lockstep bump, the git remote), and would overwrite anything
  typed here on the next publish.
* ``[deprecated]`` — retiring a library is rare and deliberate, so it is
  hand-edited in the file rather than given a control that invites a stray
  click.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from nicegui import ui

from haywire.core.library.haybale_toml import read_display, read_haybale_toml_lenient
from haywire.core.library.identity import LibraryReloadAction
from haywire.core.library.info import LibraryInfo
from haywire.ui import elements as hui
from haywire.ui.components.popup import Popup
from haywire.ui.modals import info_modal

from haybale_marketplace.library_origin import is_project_library

if TYPE_CHECKING:
    from haybale_marketplace.library_manager import LibraryManager
    from haywire.core.session.context import SessionContext

logger = logging.getLogger(__name__)


def build_edit_dialog(
    lib: LibraryInfo,
    marketplace_path: str | None,
    manager: "LibraryManager",
    context: "SessionContext",
    on_save: Callable[[dict], Coroutine[Any, Any, None]],
) -> Popup:
    """Build the Edit dialog — all identity fields immediately editable.

    The package name is read-only. To rename a library use the CLI:
    ``uv run haywire rename haybale-<name> <new-name>`` with studio stopped.

    ``on_save`` is an async callable that receives the identity dict and
    performs the actual save + rebuild (stays in the editor class).

    Built on ``Popup`` rather than ``ui.dialog()`` — the identity form has
    grown past what a fixed-height Quasar dialog can show without squishing
    content unreadably; ``Popup``'s card caps at ``90vh`` and scrolls.
    """
    old_name_part = (
        lib.distribution_name.removeprefix("haybale-") if lib.distribution_name else lib.identity.id
    )

    edit_popup = Popup(
        title=f"Edit Library — haybale-{old_name_part}",
        width="480px",
        closable=True,
        backdrop_click_close=False,
        escape_close=True,
    )
    # Read the file, not the identity: the identity carries only what the
    # runtime needs, and reading it here would show pre-edit values for
    # anything a previous save changed.
    display = read_display(Path(lib.identity.folder_path))

    with edit_popup:
        hui.section_label("Identity")
        label_input = hui.input_field(label="Label", value=display.label)
        # Version is not editable here — it's set by Share/publish (lockstep bump),
        # which overwrites this on the next publish regardless of what's typed here.
        ui.label(f"Version: {lib.identity.version or '0.1.0'} (set via Share/publish)").classes(
            "text-xs hw-text-dim"
        )
        # linked_libraries is maintained by `haywire share`'s drift detector,
        # which can prove what a library actually imports.
        ui.label(
            f"Linked libraries: {', '.join(lib.identity.linked_libraries or []) or '(none)'}"
            " (maintained by Share)"
        ).classes("text-xs hw-text-dim")

        desc_input = hui.input_field(label="Description", value=display.description)
        url_input = hui.input_field(label="Homepage URL", value=display.homepage_url)
        docs_url_input = hui.input_field(label="Documentation URL", value=display.documentation_url)
        issues_url_input = hui.input_field(label="Issues URL", value=display.issues_url)
        tags_input = hui.input_field(
            label="Tags (comma-separated)",
            value=", ".join(display.tags),
        )

        # OS multi-select. Editable for heaps — an installed wheel's file is in
        # site-packages, where an edit would be lost on the next reinstall.
        _is_heap = is_project_library(lib, marketplace_path)
        current_os = list(read_haybale_toml_lenient(Path(lib.identity.folder_path)).get("os") or [])
        os_select = None
        if _is_heap:
            os_select = (
                hui.select_field(
                    options={"macos": "macOS", "windows": "Windows", "linux": "Linux"},
                    value=current_os,
                    multiple=True,
                    label="Supported OS (leave empty = all platforms)",
                    in_popup=True,
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
            value=lib.identity.on_reload,
            in_popup=True,
        ).classes("w-full")

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
            # Only the keys this dialog owns. write_haybale_fields edits in
            # place, so an omitted key is left alone rather than erased — which
            # is why linked_libraries and [deprecated] survive a save untouched.
            identity = {
                "label": label_input.value.strip(),
                "description": desc_input.value.strip(),
                "homepage_url": url_input.value.strip(),
                "documentation_url": docs_url_input.value.strip(),
                "issues_url": issues_url_input.value.strip(),
                "tags": [t.strip() for t in tags_input.value.split(",") if t.strip()],
                "on_reload": on_reload_select.value or LibraryReloadAction.NONE.value,
            }
            # `os` only when the multi-select was rendered (heap libraries).
            if os_select is not None:
                identity["os"] = list(os_select.value or [])
            edit_popup.close()
            await on_save(identity)

        hui.dialog_actions(
            on_confirm=_save,
            on_cancel=edit_popup.close,
            confirm_label="Save Changes",
        )

    return edit_popup
