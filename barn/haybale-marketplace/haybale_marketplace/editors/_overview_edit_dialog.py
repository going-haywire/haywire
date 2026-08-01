"""Edit-identity dialog and detect-dependencies flow for LibraryOverviewEditor."""

from __future__ import annotations

import logging
import toml
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Coroutine, Any

from nicegui import ui
from nicegui.elements.input import Input

from haywire.core.library.info import LibraryInfo
from haywire.ui import elements as hui
from haywire.ui.modals import info_modal

if TYPE_CHECKING:
    from haybale_marketplace.library_manager import LibraryManager
    from haywire.core.session.context import SessionContext

logger = logging.getLogger(__name__)


def is_project_library(lib: LibraryInfo, marketplace_path: str | None) -> bool:
    """Return True if lib is the local project library (lives under workspace/barn/)."""
    if not marketplace_path or not lib.identity.folder_path:
        return False
    workspace_root = Path(marketplace_path).parent.parent
    return Path(lib.identity.folder_path).is_relative_to(workspace_root / "barn")


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
        version_input = hui.input_field(label="Version", value=lib.identity.version or "0.1.0")
        desc_input = hui.input_field(label="Description", value=lib.identity.description)
        author_input = hui.input_field(label="Author", value=lib.identity.author)
        author_url_input = hui.input_field(label="Author URL", value=lib.identity.author_url)
        url_input = hui.input_field(label="URL", value=lib.identity.url)
        tags_input = hui.input_field(
            label="Tags (comma-separated)",
            value=", ".join(lib.identity.tags or []),
        )
        deps_input = hui.input_field(
            label="Dependencies (comma-separated)",
            value=", ".join(lib.identity.dependencies or []),
        )
        with deps_input.add_slot("append"):
            hui.icon_action(
                "manage_search",
                tooltip="Detect dependencies from source imports",
                size="sm",
                on_click=lambda d=deps_input, m=manager, ilib=lib, mp=marketplace_path: (
                    detect_dependencies(d, m, ilib, mp)
                ),
            )

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
                "version": version_input.value.strip().lstrip("vV"),
                "description": desc_input.value.strip(),
                "url": url_input.value.strip(),
                "author": author_input.value.strip(),
                "author_url": author_url_input.value.strip(),
                "tags": [t.strip() for t in tags_input.value.split(",") if t.strip()],
                "dependencies": [d.strip() for d in deps_input.value.split(",") if d.strip()],
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


def detect_dependencies(
    deps_input: Input,
    manager: "LibraryManager",
    lib: LibraryInfo,
    marketplace_path: str | None,
) -> None:
    """Scan the library source for imports, diff against declared deps, and offer Union or Replace.

    Opens a modal showing two diff sections — ``@library(dependencies=...)`` and
    ``pyproject.toml [project] dependencies`` — with additions, removals, and unchanged entries.

    **Union** merges detected into declared (no removals).
    **Replace** overwrites declared with detected entirely.

    The ``@library`` side is not persisted until the user clicks Save Changes in the Edit dialog.
    The ``pyproject.toml`` side is written to disk immediately on either action.
    """
    from haywire.core.library.dep_detect import (
        DetectedDeps,
        detect_deps,
        set_pyproject_dependencies,
    )
    from haywire.ui.modals import DiffSection, diff_modal
    from haywire_studio.packaging.share import union_pyproject_deps as _union_pyproject_deps

    if not marketplace_path or not lib.distribution_name:
        ui.notify("Cannot detect — no library on disk for this entry.", type="warning")
        return

    workspace_root = Path(marketplace_path).parent.parent
    lib_dir = workspace_root / "barn" / lib.distribution_name
    if not lib_dir.is_dir():
        ui.notify(f"Library directory not found: {lib_dir}", type="negative")
        return

    try:
        detected: DetectedDeps = detect_deps(lib_dir, libraries=manager.registry)
    except Exception as exc:
        logger.exception("detect_deps failed")
        ui.notify(f"Detect failed: {exc}", type="negative")
        return

    # Current @library deps — from the live input, not disk.
    current_decorator = [d.strip() for d in (deps_input.value or "").split(",") if d.strip()]

    # Current pyproject deps — from disk.
    pyproject_path = lib_dir / "pyproject.toml"
    try:
        pyproject_data = toml.loads(pyproject_path.read_text())
        current_pyproject = list(pyproject_data.get("project", {}).get("dependencies", []))
    except (OSError, toml.TomlDecodeError) as exc:
        ui.notify(f"Cannot read pyproject.toml: {exc}", type="negative")
        return

    detected_decorator = list(detected.library_decorator)
    detected_pyproject = list(detected.pyproject)

    cur_dec_set = set(current_decorator)
    det_dec_set = set(detected_decorator)
    cur_py_set = set(current_pyproject)
    det_py_set = set(detected_pyproject)

    decorator_section = DiffSection(
        title="@library(dependencies=...)",
        additions=sorted(det_dec_set - cur_dec_set),
        removals=sorted(cur_dec_set - det_dec_set),
        unchanged=sorted(cur_dec_set & det_dec_set),
        note=(
            f"Replace will remove {len(cur_dec_set - det_dec_set)} entr"
            f"{'y' if len(cur_dec_set - det_dec_set) == 1 else 'ies'}."
            if (cur_dec_set - det_dec_set)
            else ""
        ),
    )
    pyproject_section = DiffSection(
        title="pyproject.toml [project] dependencies",
        additions=sorted(det_py_set - cur_py_set),
        removals=sorted(cur_py_set - det_py_set),
        unchanged=sorted(cur_py_set & det_py_set),
        note=(
            f"Replace will remove {len(cur_py_set - det_py_set)} entr"
            f"{'y' if len(cur_py_set - det_py_set) == 1 else 'ies'}."
            if (cur_py_set - det_py_set)
            else ""
        ),
    )

    sections = [decorator_section, pyproject_section]
    if detected.unresolved:
        sections.append(
            DiffSection(
                title="Unresolved imports",
                additions=[],
                removals=[],
                unchanged=sorted(detected.unresolved),
                note=(
                    "These modules could not be mapped to a distribution. "
                    "Likely dynamic imports or missing installs — review manually."
                ),
            )
        )

    def _apply_union() -> None:
        new_decorator = sorted(cur_dec_set | det_dec_set)
        new_pyproject = _union_pyproject_deps(
            current=current_pyproject,
            detected=detected_pyproject,
            libraries=manager.registry,
        )
        deps_input.value = ", ".join(new_decorator)
        write_pyproject_deps(lib_dir, new_pyproject, set_pyproject_dependencies)

    def _apply_replace() -> None:
        new_decorator = sorted(det_dec_set)
        new_pyproject = sorted(det_py_set)
        deps_input.value = ", ".join(new_decorator)
        write_pyproject_deps(lib_dir, new_pyproject, set_pyproject_dependencies)

    diff_modal(
        title="Detected dependencies",
        sections=sections,
        primary_label="Union",
        on_primary=_apply_union,
        secondary_label="Replace",
        on_secondary=_apply_replace,
        empty_message=(
            "No changes detected — the @library decorator and pyproject.toml "
            "already reflect what the source imports."
        ),
    )


def write_pyproject_deps(lib_dir: Path, deps: list[str], setter: Callable[[Path, list[str]], None]) -> None:
    """Wrapper around set_pyproject_dependencies that surfaces UI feedback."""
    try:
        setter(lib_dir, deps)
        ui.notify(
            "pyproject.toml updated. Click Save Changes to persist the @library decorator.",
            type="info",
        )
    except Exception as exc:
        logger.exception("set_pyproject_dependencies failed")
        ui.notify(f"Failed to update pyproject.toml: {exc}", type="negative")
