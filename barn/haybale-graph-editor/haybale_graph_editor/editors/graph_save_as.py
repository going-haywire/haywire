"""Shared Save-As dialog for graph containers.

Both GraphEditor and HaystackEditor open the same save-as flow; they
differ only in the save callback. This module owns the common logic:
default-path computation, save_as_modal invocation, and the stacked
overwrite-confirm flow.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from nicegui import ui

from haywire.core.workspace import default_save_dir
from haywire.ui.modals import confirm_modal, save_as_modal

if TYPE_CHECKING:
    from haybale_graph_editor.protocols import GraphContainer


def _compute_initial_path(
    entry: "GraphContainer",
    workspace_root: Path,
) -> str:
    """Return a relative-to-workspace initial path string for the save-as modal."""
    if entry.path is not None:
        try:
            return str(entry.path.relative_to(workspace_root))
        except ValueError:
            return entry.path.name
    save_dir = default_save_dir(workspace_root)
    graph_name = getattr(entry.editor.graph, "name", None) or "untitled"
    safe_name = graph_name.lower().replace(" ", "_")
    try:
        rel_dir = save_dir.relative_to(workspace_root)
        return str(rel_dir / f"{safe_name}.haywire")
    except ValueError:
        return f"{safe_name}.haywire"


def open_graph_save_as_dialog(
    *,
    app,
    entry: "GraphContainer",
    save_fn: Callable[[Path], bool],
    on_success: Optional[Callable[[Path], None]] = None,
    initial_path: Optional[str] = None,
) -> None:
    """Open the Save-As modal for a graph entry.

    Args:
        app: The project app state (provides workspace_root).
        entry: The graph container to save.
        save_fn: Called with the chosen absolute path. Returns True on success.
            The caller is responsible for the actual save — this function only
            handles the dialog flow and the overwrite-confirm stacking.
        on_success: Optional callback fired with the resolved path after a
            successful save. Use this to update session state, emit signals, etc.
        initial_path: Pre-fill override (relative to workspace_root). When None
            the value is derived from entry.path or a sensible default for
            unnamed entries.
    """
    workspace_root = Path(getattr(app, "workspace_root", str(Path.home())))
    if initial_path is None:
        initial_path = _compute_initial_path(entry, workspace_root)

    def _do_save(save_path: Path) -> None:
        success = save_fn(save_path)
        if not success:
            ui.notify("Save failed — check the path and try again", type="negative")
            return
        ui.notify(f"Saved: {save_path.name}", type="positive", position="top-right")
        if on_success is not None:
            on_success(save_path)

    def _on_confirm(save_path: Path, raw_input: str) -> None:
        if save_path == entry.path:
            _do_save(save_path)
            return
        if save_path.exists():
            confirm_modal(
                title="Overwrite file?",
                message=f'"{save_path.name}" already exists. Overwrite it?',
                confirm_label="Overwrite",
                danger=True,
                on_confirm=lambda: _do_save(save_path),
                on_cancel=lambda: open_graph_save_as_dialog(
                    app=app,
                    entry=entry,
                    save_fn=save_fn,
                    on_success=on_success,
                    initial_path=raw_input,
                ),
            )
            return
        _do_save(save_path)

    save_as_modal(
        title="Save Graph As",
        workspace_root=workspace_root,
        initial_path=initial_path,
        suffixes=(".haywire",),
        on_confirm=_on_confirm,
    )
