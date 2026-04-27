"""
NodeSourceEditor — source code of the currently selected graph node.

Right-slot, REQUIRED editor that mirrors a slice of session state
(``context.active_node``). Behaves as a viewer when the owning library
is not EDITABLE; opens up to a full save-capable editor when it is.

Editing model:

* On first keystroke the editor "pins" itself: subsequent
  ``SELECTION_CHANGED`` events are ignored so the buffer is not blown
  away under the user's fingers. Save and Discard both unpin.
* While pinned the editor subscribes to ``LifeCycleEvent`` on the
  node's registry_key. If the on-disk file changes (someone else
  saves it, hot reload, etc.) and the new content differs from
  ``_original`` we surface a "file changed externally" banner with
  Reload-from-disk / Save-anyway actions. When the change is just
  our own save echoing back (disk == _original) we ignore it.
"""

from __future__ import annotations

import inspect
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.context_signals import SelectionMoved, ThemeMoved
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor

if TYPE_CHECKING:
    from haywire.core.registry.lifecycle_event import LifeCycleEvent
    from haywire.ui.context import SessionContext
    from haywire.ui.context_signals import ContextSignal
    from nicegui.element import Element


logger = logging.getLogger(__name__)


@editor(
    label="Node Source",
    icon=hui.icon.node_source,
    default_slot="right",
    description="Source code of the currently selected graph node.",
)
class NodeSourceEditor(BaseEditor):
    """Source viewer/editor that follows ``context.active_node``."""

    _RELEVANT_SIGNALS = (SelectionMoved, ThemeMoved)

    def __init__(self) -> None:
        # Buffer state
        self._content: str = ""
        self._original: str = ""
        self._pinned: bool = False
        self._conflict: bool = False  # external change detected, pending resolution

        # Resolved target (refreshed on every draw)
        self._cls: Optional[type] = None
        self._path: Optional[Path] = None
        self._registry_key: Optional[str] = None
        self._is_editable: bool = False

        # UI handles (nullable; reset in cleanup)
        self._editor: Optional[ui.codemirror] = None
        self._save_button: Optional[ui.button] = None
        self._path_label: Optional[ui.label] = None
        self._readonly_badge: Optional[ui.element] = None
        self._pin_banner: Optional[ui.element] = None
        self._conflict_banner: Optional[ui.element] = None

        # Lifecycle subscription bookkeeping
        self._lifecycle_node_factory = None
        self._lifecycle_registry_key: Optional[str] = None

    # ------------------------------------------------------------------
    # BaseEditor interface
    # ------------------------------------------------------------------

    def poll(self, context: "SessionContext", signal: "ContextSignal") -> bool:
        # While the user is editing, freeze the buffer against selection
        # churn. Theme changes still redraw so CodeMirror picks up the
        # new colors — but theme changes are expected to be rare and the
        # redraw happily reads the already-dirty _content out of self.
        if self._pinned and isinstance(signal, SelectionMoved):
            return False
        return isinstance(signal, self._RELEVANT_SIGNALS)

    def draw(self, context: "SessionContext", container: "Element") -> None:
        # If we're not pinned, reload from active_node. If we are pinned,
        # keep the existing buffer and just rebuild the chrome (theme
        # change path).
        if not self._pinned:
            self._resolve_target(context)
            self._read_buffer()
            self._conflict = False

        with container:
            self._render(context)

    def cleanup(self) -> None:
        self._unsubscribe_lifecycle()
        self._editor = None
        self._save_button = None
        self._path_label = None
        self._readonly_badge = None
        self._pin_banner = None
        self._conflict_banner = None

    # ------------------------------------------------------------------
    # Target resolution
    # ------------------------------------------------------------------

    def _resolve_target(self, context: "SessionContext") -> None:
        node = context.active_node
        if node is None:
            self._cls = None
            self._path = None
            self._registry_key = None
            self._is_editable = False
            self._sync_subscription(context)
            return

        self._registry_key = node.registry_key

        # Class lookup goes through node_factory — public API and
        # survives hot reload (NodeWrapper.node may not be instantiable
        # if the node has an import error).
        cls = None
        app = context.app
        if app is not None and self._registry_key:
            factory = getattr(app, "node_factory", None)
            if factory is not None:
                try:
                    cls, _err = factory.get_node(self._registry_key)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.debug("get_node failed for %s: %s", self._registry_key, exc)
                    cls = None
        self._cls = cls

        # Path resolution
        if cls is not None:
            try:
                self._path = Path(inspect.getfile(cls))
            except (TypeError, OSError):
                self._path = None
        else:
            self._path = None

        self._is_editable = self._compute_is_editable(context)
        self._sync_subscription(context)

    def _compute_is_editable(self, context: "SessionContext") -> bool:
        if not self._registry_key:
            return False
        app = context.app
        if app is None:
            return False
        manager = getattr(app, "library_manager", None)
        if manager is None:
            return False
        lib_id = self._registry_key.split(":", 1)[0]
        lib = manager.get_installed_library(lib_id)
        if lib is None:
            return False
        install_type = getattr(lib, "install_type", None)
        if install_type is None:
            return False
        return (
            install_type.name == "EDITABLE" if hasattr(install_type, "name") else install_type == "EDITABLE"
        )

    def _read_buffer(self) -> None:
        text = self._read_file(self._path)
        self._content = text
        self._original = text

    @staticmethod
    def _read_file(path: Optional[Path]) -> str:
        if path is None or not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self, context: "SessionContext") -> None:
        # Empty / error states short-circuit the editor chrome.
        if context.active_node is None:
            hui.empty_state(
                "Select a node to view its source",
                icon=hui.icon.node_info,
            )
            return
        if self._cls is None or self._path is None:
            hui.empty_state(
                "This node has no source file",
                icon=hui.icon.empty_binary,
                hint="(dynamically generated or missing class)",
            )
            return
        if not self._path.exists():
            hui.empty_state(
                f"Source file not found: {self._path}",
                icon=hui.icon.warning,
            )
            return

        with ui.column().classes("w-full h-full gap-0"):
            self._render_header()
            self._render_pin_banner()
            self._render_conflict_banner()
            self._render_editor(context)

    def _render_header(self) -> None:
        with (
            ui.row()
            .classes("w-full items-center px-3 gap-2 flex-shrink-0 border-b")
            .style("min-height: 32px; background: var(--hw-bg-surface);")
        ):
            (
                ui.button(icon="arrow_back", on_click=self._open_in_code_editor)
                .props("flat dense round size=sm")
                .tooltip("Open in editor")
            )
            ui.icon(hui.icon.node_source, size="14px").classes("hw-text-dim")
            label_text = str(self._path) if self._path is not None else "—"
            self._path_label = ui.label(label_text).classes(
                "text-xs hw-text-muted truncate font-mono flex-1"
            )

            if not self._is_editable:
                self._readonly_badge = (
                    ui.label("Read-only")
                    .classes("text-xs hw-text-dim")
                    .style("padding: 1px 6px; border: 1px solid var(--hw-border); border-radius: 3px;")
                )
            else:
                self._readonly_badge = None
                self._save_button = (
                    ui.button(
                        "",
                        icon=hui.icon.save,
                        on_click=self._save,
                    )
                    .props("flat dense size=sm")
                    .tooltip("Save changes to disk")
                )

    def _render_pin_banner(self) -> None:
        # Always rendered; visibility toggled by _pinned. Avoids a full
        # redraw when the user starts or stops editing.
        with (
            ui.row()
            .classes("w-full items-center px-3 gap-2 flex-shrink-0")
            .style(
                "min-height: 26px; background: var(--hw-bg-surface);"
                " border-bottom: 1px solid var(--hw-border);"
            )
        ) as banner:
            self._pin_banner = banner
            name = self._path.name if self._path else "buffer"
            ui.label(f"• editing {name}").classes("text-xs hw-text-muted flex-1")
            ui.button("Discard", on_click=self._discard).props("flat dense size=sm").tooltip(
                "Drop edits and follow the current selection again"
            )
        banner.set_visibility(self._pinned)

    def _render_conflict_banner(self) -> None:
        with (
            ui.row()
            .classes("w-full items-center px-3 gap-2 flex-shrink-0")
            .style(
                "min-height: 26px; background: var(--hw-bg-warning, #5a3a00);"
                " border-bottom: 1px solid var(--hw-border);"
            )
        ) as banner:
            self._conflict_banner = banner
            ui.icon(hui.icon.warning, size="14px").classes("hw-text-dim")
            ui.label("File changed on disk").classes("text-xs flex-1")
            ui.button("Reload from disk", on_click=self._reload_from_disk).props("flat dense size=sm")
            ui.button("Save anyway", on_click=self._save).props("flat dense size=sm")
        banner.set_visibility(self._conflict)

    def _render_editor(self, context: "SessionContext") -> None:
        # .hw-cm-isolate prevents .hw-panel * CSS from cascading into
        # CodeMirror's token spans — same isolation the other source
        # views use (see app_shell.py).
        with (
            ui.element("div")
            .classes("hw-cm-isolate")
            .style("flex: 1; min-height: 0; width: 100%; display: flex;")
        ):
            on_change = self._on_text_changed if self._is_editable else None
            self._editor = ui.codemirror(
                value=self._content,
                language="Python",
                theme=self._codemirror_theme(context),
                on_change=on_change,
            ).style("flex: 1; min-height: 0; width: 100%; height: 100%;")

    @staticmethod
    def _codemirror_theme(context: "SessionContext") -> str:
        theme_key = getattr(context, "active_workbench_theme_key", "core:theme:workbench:haywire-dark")
        return "vscodeLight" if "light" in theme_key else "vscodeDark"

    # ------------------------------------------------------------------
    # Editing flow
    # ------------------------------------------------------------------

    def _on_text_changed(self, event) -> None:
        new_value = getattr(event, "value", None)
        if not isinstance(new_value, str):
            return
        self._content = new_value
        if not self._pinned and self._content != self._original:
            self._pinned = True
            self._refresh_chrome()

    def _save(self) -> None:
        if self._path is None:
            return
        try:
            self._path.write_text(self._content, encoding="utf-8")
        except OSError as exc:
            ui.notify(f"Save failed: {exc}", type="negative")
            return
        self._original = self._content
        self._pinned = False
        self._conflict = False
        self._refresh_chrome()
        ui.notify(f"Saved {self._path.name}", type="positive")

    def _discard(self) -> None:
        # Re-read the file fresh — disk is the source of truth.
        text = self._read_file(self._path)
        self._content = text
        self._original = text
        self._pinned = False
        self._conflict = False
        # Replace the codemirror buffer in place rather than triggering
        # a full redraw, so we don't wipe other UI handles.
        if self._editor is not None:
            self._editor.value = text
        self._refresh_chrome()

    def _reload_from_disk(self) -> None:
        # Same as discard — the disk has the canonical content.
        self._discard()

    def _open_in_code_editor(self) -> None:
        """Reveal the same file in the main-slot CodeEditor."""
        if self._path is None:
            return
        wrapper = self.wrapper
        session = getattr(wrapper, "_session", None) if wrapper is not None else None
        if session is None:
            return
        # Lazy import to keep the editor decorator chain identical to
        # how file_browser does it.
        from haybale_studio.editors.code_editor import CodeEditor

        from haywire.ui.context_signals import ActiveFileMoved, RevealRequest

        session.context.active_file = self._path
        session.signal(ActiveFileMoved())
        session.reveal(
            RevealRequest(
                editor=CodeEditor,
                payload=str(self._path),
                label=self._path.name,
            )
        )

    # ------------------------------------------------------------------
    # Lifecycle subscription (external-change detection)
    #
    # Subscription is bound to "the file this editor is showing", not
    # to edit mode. _resolve_target calls _sync_subscription on every
    # redraw to (re)attach the callback when the active node — and
    # therefore the watched registry_key — changes.
    # ------------------------------------------------------------------

    def _sync_subscription(self, context: "SessionContext") -> None:
        target_key = self._registry_key if self._path is not None else None
        if target_key == self._lifecycle_registry_key:
            return  # already on the right key (or both None)
        self._unsubscribe_lifecycle()
        if target_key is None:
            return
        factory = getattr(context.app, "node_factory", None) if context.app is not None else None
        if factory is None:
            return
        try:
            factory.add_event_subscriber(target_key, self._on_lifecycle_event)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("subscribe failed for %s: %s", target_key, exc)
            return
        self._lifecycle_node_factory = factory
        self._lifecycle_registry_key = target_key

    def _unsubscribe_lifecycle(self) -> None:
        if self._lifecycle_node_factory is None or self._lifecycle_registry_key is None:
            return
        try:
            self._lifecycle_node_factory.remove_event_subscriber(
                self._lifecycle_registry_key, self._on_lifecycle_event
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("unsubscribe failed: %s", exc)
        self._lifecycle_node_factory = None
        self._lifecycle_registry_key = None

    def _on_lifecycle_event(self, event: "LifeCycleEvent") -> None:
        # Re-read the file. If unchanged from _original, it's our own
        # save echoing back (or a class-only reload that didn't touch
        # the source text) — ignore. Otherwise:
        #   - not pinned → silently refresh the buffer (passive viewer)
        #   - pinned     → surface the conflict banner
        if self._path is None:
            return
        try:
            disk = self._read_file(self._path)
        except Exception:  # pragma: no cover - defensive
            return
        if disk == self._original:
            return

        if not self._pinned:
            self._content = disk
            self._original = disk
            if self._editor is not None:
                self._editor.value = disk
            return

        # Pinned: real conflict. Update _original so a subsequent
        # self-save doesn't re-trigger the banner.
        self._original = disk
        self._conflict = True
        self._refresh_chrome()

    # ------------------------------------------------------------------
    # Chrome refresh — toggle banner visibility without touching the
    # codemirror buffer (preserves cursor + scroll position).
    # ------------------------------------------------------------------

    def _refresh_chrome(self) -> None:
        if self._pin_banner is not None:
            self._pin_banner.set_visibility(self._pinned)
        if self._conflict_banner is not None:
            self._conflict_banner.set_visibility(self._conflict)
