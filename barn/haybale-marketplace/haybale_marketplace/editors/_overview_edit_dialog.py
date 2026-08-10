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

``linked_libraries`` is the one exception to "no detection here", and it is a
narrow one: a Refresh button applies the same rule the share pipeline's
``apply_linked_registrations`` applies — union in what the source provably
imports, never remove, never ask. It is a fact, not an authored decision like a
pip dependency's version floor, which is why it needs no control beyond a
button. This does NOT extend to pip dependencies: ``[project] dependencies``
stays exclusively a ``haywire share`` concern (see marketplace-arch.md §6).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from nicegui import ui

from haywire.core.library.dep_detect import HaywireLibrarySource, find_module_dir
from haywire.core.library.haybale_toml import read_display, read_haybale_toml_lenient
from haywire.core.library.identity import LibraryReloadAction
from haywire.core.library.info import LibraryInfo
from haywire.core.publishing.drift.detect import detect_share_drift
from haywire.ui import elements as hui
from haywire.ui.components.popup import Popup
from haywire.ui.modals import info_modal

from haybale_marketplace.library_origin import is_project_library

if TYPE_CHECKING:
    from haybale_marketplace.library_manager import LibraryManager
    from haywire.core.session.context import SessionContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _RefreshResult:
    """Outcome of one Refresh click — never written to disk by this module."""

    added: list[str] = field(default_factory=list)
    """Detected entries that were not already declared."""
    merged: list[str] = field(default_factory=list)
    """`current` ∪ `added`, sorted — the value to stage. Never smaller than
    `current`: Refresh is union-only."""
    no_module_dir: bool = False
    """True when the library has no inspectable source — nothing to scan."""


def _refresh_linked_libraries(
    lib_dir: Path,
    *,
    current: list[str],
    libraries: HaywireLibrarySource,
) -> _RefreshResult:
    """Detect the library's imported haywire libraries and union them in.

    Pure — no writes. The rule is the share pipeline's, deliberately:
    ``apply_linked_registrations`` merges ``linked_missing`` into the declared
    list and drops nothing, because ``detect_deps`` emits a name only when the
    source imports it AND it resolves to an installed registered library. A
    declared entry the scan does not see is indistinguishable from a dynamic
    import it cannot see, so removal is never inferred — on any surface.

    ``lib_dir`` is the LIBRARY ROOT (the ``pyproject.toml`` directory), NOT the
    package dir: ``detect_share_drift`` reads ``lib_dir/pyproject.toml`` and
    finds the package itself via ``find_module_dir``.
    ``LibraryInfo.identity.folder_path`` is the *package* dir, so the caller
    passes its ``.parent`` — sound only for heap libraries, whose folder_path is
    provably ``barn/<lib>/<module>/``. See :func:`build_edit_dialog`.

    Only ``linked_missing`` is read. The pyproject-dependency fields on the
    returned ``DepDrift`` are deliberately ignored: pip-dependency authoring
    stays out of this dialog (see the module docstring).
    """
    if find_module_dir(lib_dir) is None:
        return _RefreshResult(no_module_dir=True)

    drift = detect_share_drift(lib_dir, libraries=libraries)
    current_set = set(current)
    added = sorted(n for n in drift.linked_missing if n not in current_set)
    return _RefreshResult(added=added, merged=sorted(current_set | set(added)), no_module_dir=False)


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
        # Version is not editable here — it's set by Share/publish (lockstep bump),
        # which overwrites this on the next publish regardless of what's typed here.
        ui.label(f"Version: {lib.identity.version or '0.1.0'} (set via Share/publish)").classes(
            "text-xs hw-text-dim"
        )
        # Still a label, not an input: the author has nothing to decide here.
        # Refresh applies the pipeline's own rule (union what is provably
        # imported, never remove), so the only affordance needed is the button.
        #
        # Heap-gated for the same reason `os` is — an installed wheel lives in
        # site-packages, where an edit is lost on the next reinstall. It is also
        # a correctness gate: detect_share_drift needs the LIBRARY ROOT, and
        # folder_path.parent only reaches it for heaps, whose folder_path is
        # provably barn/<lib>/<module>/ (exactly what is_project_library
        # checks). For a site-packages wheel the parent is site-packages itself.
        _is_heap = is_project_library(lib, marketplace_path)
        _pkg_dir = Path(lib.identity.folder_path)
        # Read the file, not lib.identity: identity carries the value loaded at
        # startup, so a previous save in this session would render stale.
        _linked: list[str] = list(read_haybale_toml_lenient(_pkg_dir).get("linked_libraries") or [])
        _linked_staged: list[str] = list(_linked)

        with ui.row().classes("items-center gap-2"):
            linked_label = ui.label().classes("text-xs hw-text-dim")

            def _render_linked() -> None:
                shown = ", ".join(_linked_staged) or "(none)"
                linked_label.set_text(f"Linked libraries: {shown}")

            _render_linked()

            if _is_heap:
                _lib_root = _pkg_dir.parent

                async def _do_refresh(m=manager, lib_root=_lib_root) -> None:
                    result = await asyncio.to_thread(
                        _refresh_linked_libraries,
                        lib_root,
                        current=list(_linked_staged),
                        libraries=m.registry,
                    )
                    if result.no_module_dir:
                        ui.notify("No inspectable source found — nothing to detect.", type="warning")
                        return
                    if not result.added:
                        ui.notify("Nothing new detected.", type="info")
                        return
                    _linked_staged[:] = result.merged
                    _render_linked()
                    ui.notify(
                        f"Added: {', '.join(result.added)}. Click Save Changes to write.",
                        type="positive",
                    )

                _refresh_button = ui.button(icon="refresh", on_click=_do_refresh).props("size=sm flat dense")
                if find_module_dir(_lib_root) is None:
                    _refresh_button.disable()
                    _refresh_button.tooltip("No inspectable source found for this library.")
                else:
                    _refresh_button.tooltip("Detect imported haywire libraries and add any missing.")

        label_input = hui.input_field(label="Label", value=display.label)
        desc_input = hui.input_field(label="Description", value=display.description)
        url_input = hui.input_field(label="Homepage URL", value=display.homepage_url)
        docs_url_input = hui.input_field(label="Documentation URL", value=display.documentation_url)
        issues_url_input = hui.input_field(label="Issues URL", value=display.issues_url)
        tags_input = hui.input_field(
            label="Tags (comma-separated)",
            value=", ".join(display.tags),
        )

        # Authors — positional, whole-value replace on save (like every other
        # field here except linked_libraries). `_author_rows` holds one
        # (row, name_input, url_input) triple per rendered row; add/remove
        # mutate the container directly, the same clear-and-redraw spirit
        # `_render_linked` above uses, but per-row rather than whole-list since
        # each row deletes independently.
        ui.label("Authors").classes("text-xs hw-text-dim")
        _author_rows: list[tuple[ui.row, ui.input, ui.input]] = []
        _authors_container = ui.column().classes("w-full gap-1")

        def _remove_author_row(row: ui.row) -> None:
            _author_rows[:] = [entry for entry in _author_rows if entry[0] is not row]
            row.delete()

        def _add_author_row(name: str = "", url: str = "") -> None:
            with _authors_container:
                with ui.row().classes("w-full items-center gap-2") as row:
                    name_in = hui.input_field(placeholder="Name", value=name).classes("flex-1")
                    url_in = hui.input_field(placeholder="URL (optional)", value=url).classes("flex-1")
                    hui.icon_action(
                        "close", tooltip="Remove author", on_click=lambda r=row: _remove_author_row(r)
                    )
            _author_rows.append((row, name_in, url_in))

        for _name, _url in display.authors:
            _add_author_row(_name, _url)

        with ui.row().classes("items-center"):
            ui.button("Add author", icon="add", on_click=lambda: _add_author_row()).props(
                "size=sm flat dense"
            )

        # OS multi-select. Editable for heaps — an installed wheel's file is in
        # site-packages, where an edit would be lost on the next reinstall.
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

        ui.label("Declare behavior for install, update, and uninstall alike:").classes("text-xs hw-text-dim")
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
            # A blank name with a filled url would otherwise be silently
            # dropped by write_haybale_fields (an author needs a name to be
            # one at all) — block the save instead of losing a typed URL.
            for _, name_in, url_in in _author_rows:
                if not name_in.value.strip() and url_in.value.strip():
                    ui.notify("An author needs a name to keep its URL.", type="negative")
                    return
            authors = [
                (name_in.value.strip(), url_in.value.strip())
                for _, name_in, url_in in _author_rows
                if name_in.value.strip()
            ]

            # Only the keys this dialog owns. write_haybale_fields edits in
            # place, so an omitted key is left alone rather than erased — which
            # is why [deprecated] survives a save untouched, and why an
            # unrefreshed linked_libraries is left exactly as the file has it.
            identity = {
                "label": label_input.value.strip(),
                "description": desc_input.value.strip(),
                "homepage_url": url_input.value.strip(),
                "documentation_url": docs_url_input.value.strip(),
                "issues_url": issues_url_input.value.strip(),
                "tags": [t.strip() for t in tags_input.value.split(",") if t.strip()],
                "on_reload": on_reload_select.value or LibraryReloadAction.NONE.value,
                "authors": authors,
            }
            # `os` only when its multi-select was rendered (heap libraries).
            if os_select is not None:
                identity["os"] = list(os_select.value or [])
            # linked_libraries only when Refresh actually changed it — an
            # untouched dialog must not rewrite a hand-authored list.
            if _linked_staged != _linked:
                identity["linked_libraries"] = list(_linked_staged)
            edit_popup.close()
            await on_save(identity)

        hui.dialog_actions(
            on_confirm=_save,
            on_cancel=edit_popup.close,
            confirm_label="Save Changes",
        )

    return edit_popup
