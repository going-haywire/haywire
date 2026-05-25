"""
ComponentSourceEditor — source code of the currently selected component.

Right-slot editor that mirrors ``context.active_component`` (a registry_key
string).  Works for any component type managed by a BaseRegistry subclass
(nodes, types, adapters, skins, widgets, editors, panels, settings, themes).

Editing model:

* On first keystroke the editor "pins" itself: subsequent
  ``active_component`` changes are ignored so the buffer is not blown
  away under the user's fingers.  Save and Discard both unpin.
* While pinned the editor subscribes to ``add_batch_event_subscriber`` on
  the resolved registry.  If the on-disk file changes and the new content
  differs from ``_original`` we surface a "file changed externally" banner
  with Reload-from-disk / Save-anyway actions.  When the change is just
  our own save echoing back (disk == _original) we ignore it.
"""

from __future__ import annotations

import inspect
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Optional

from nicegui import ui

from haywire.ui import elements as hui
from haywire.core.library.utils import (
    ADAPTER,
    EDITOR,
    NODE,
    PANEL,
    SETTING,
    SKIN,
    STATE,
    THEME,
    TYPE,
    WIDGET,
    get_registry_id_from_key,
)
from haywire.core.session.context import SessionContext
from haywire.core.session.handlers import redraw_on
from haywire.core.session.signals import Signal
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor

if TYPE_CHECKING:
    from haywire.core.registry.base import BaseRegistry
    from haywire.core.registry.lifecycle_event import LifeCycleEvent
    from nicegui.element import Element


logger = logging.getLogger(__name__)

# Maps the comp_type segment of a registry_key to the library_service getter.
_REGISTRY_GETTER = {
    NODE: "get_node_registry",
    WIDGET: "get_widget_registry",
    TYPE: "get_type_registry",
    ADAPTER: "get_adapter_registry",
    SKIN: "get_skin_registry",
    THEME: "get_theme_registry",
    SETTING: "get_settings_registry",
    STATE: "get_state_registry",
    PANEL: "get_panel_registry",
    EDITOR: "get_editor_registry",
}


@editor(
    label="Component Source",
    icon=hui.icon.node_source,
    default_slot="right",
    description="Source code of the currently selected component.",
)
class ComponentSourceEditor(BaseEditor):
    """Source viewer/editor that follows ``context.active_component``."""

    def __init__(self, wrapper) -> None:
        super().__init__(wrapper)
        # Buffer state
        self._content: str = ""
        self._original: str = ""
        self._pinned: bool = False
        self._conflict: bool = False

        # Resolved target (refreshed on every draw when not pinned)
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
        self._subscribed_registry: Optional["BaseRegistry"] = None
        self._subscribed_key: Optional[str] = None

    # ------------------------------------------------------------------
    # Event-bus subscriptions
    # ------------------------------------------------------------------

    @redraw_on(SessionContext.active_component)
    def _redraw_on_active_component(self, context: "SessionContext", event: Signal) -> None:
        if self._pinned:
            return
        self.wrapper.redraw()

    @redraw_on(SessionContext.active_workbench_theme_key)
    def _redraw_on_theme(self, context: "SessionContext", event: Signal) -> None:
        pass

    # ------------------------------------------------------------------
    # BaseEditor interface
    # ------------------------------------------------------------------

    def draw(self, context: "SessionContext", container: "Element") -> None:
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
        registry_key = context.active_component
        if not registry_key:
            self._cls = None
            self._path = None
            self._registry_key = None
            self._is_editable = False
            self._sync_subscription(context)
            return

        self._registry_key = registry_key
        self._cls = self._lookup_class(context, registry_key)

        if self._cls is not None:
            try:
                self._path = Path(inspect.getfile(self._cls))
            except (TypeError, OSError):
                self._path = None
        else:
            self._path = None

        self._is_editable = self._compute_is_editable(context)
        self._sync_subscription(context)

    def _lookup_class(self, context: "SessionContext", registry_key: str) -> Optional[type]:
        app = context.app
        if app is None:
            return None
        parts = registry_key.split(":", 2)
        if len(parts) != 3:
            return None
        _lib_id, comp_singular, _class_name = parts
        getter_name = _REGISTRY_GETTER.get(comp_singular)
        if getter_name is None:
            return None
        try:
            svc = app.library_service
            registry = getattr(svc, getter_name, lambda: None)()
            if registry is None:
                return None
            return registry.get(registry_key)
        except Exception as exc:
            logger.debug("lookup_class failed for %s: %s", registry_key, exc)
            return None

    def _compute_is_editable(self, context: "SessionContext") -> bool:
        from haybale_marketplace.state.library_manager_state import LibraryManagerState

        if not self._registry_key:
            return False
        manager_state = context.app_data.get(LibraryManagerState)
        manager = manager_state.manager if manager_state is not None else None
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
        if not context.active_component:
            hui.empty_state(
                "Select a component to view its source",
                icon=hui.icon.node_source,
            )
            return
        if self._cls is None or self._path is None:
            class_name = get_registry_id_from_key(context.active_component)
            hui.empty_state(
                f"No source file for {class_name}",
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
                    ui.button("", icon=hui.icon.save, on_click=self._save)
                    .props("flat dense size=sm")
                    .tooltip("Save changes to disk")
                )

    def _render_pin_banner(self) -> None:
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
    def _codemirror_theme(context: "SessionContext") -> Literal["vscodeLight", "vscodeDark"]:
        theme_key = context.active_workbench_theme_key or "dark"
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
        text = self._read_file(self._path)
        self._content = text
        self._original = text
        self._pinned = False
        self._conflict = False
        if self._editor is not None:
            self._editor.value = text
        self._refresh_chrome()

    def _reload_from_disk(self) -> None:
        self._discard()

    def _open_in_code_editor(self) -> None:
        if self._path is None:
            return
        wrapper = self.wrapper
        session = getattr(wrapper, "_session", None) if wrapper is not None else None
        if session is None:
            return
        from haybale_studio.editors.code_editor import CodeEditor
        from haywire.core.session.signals import Reveal

        session.context.active_file = self._path
        session.publish(
            Reveal(
                editor=CodeEditor,
                binding_id=str(self._path),
                label=self._path.name,
            )
        )

    # ------------------------------------------------------------------
    # Lifecycle subscription (external-change detection)
    #
    # Uses add_batch_event_subscriber on BaseRegistry — available on all
    # registry types.  The batch is filtered for the specific registry_key
    # this editor is currently displaying.
    # ------------------------------------------------------------------

    def _resolve_registry(self, context: "SessionContext") -> Optional["BaseRegistry"]:
        """Return the BaseRegistry that owns self._registry_key, or None."""
        if not self._registry_key:
            return None
        app = context.app
        if app is None:
            return None
        parts = self._registry_key.split(":", 2)
        if len(parts) != 3:
            return None
        _lib_id, comp_singular, _class_name = parts
        getter_name = _REGISTRY_GETTER.get(comp_singular)
        if getter_name is None:
            return None
        try:
            svc = app.library_service
            return getattr(svc, getter_name, lambda: None)()
        except Exception:
            return None

    def _sync_subscription(self, context: "SessionContext") -> None:
        target_key = self._registry_key if self._path is not None else None
        if target_key == self._subscribed_key:
            return
        self._unsubscribe_lifecycle()
        if target_key is None:
            return
        registry = self._resolve_registry(context)
        if registry is None:
            return
        try:
            registry.add_batch_event_subscriber(self._on_lifecycle_batch)
        except Exception as exc:
            logger.debug("subscribe failed for %s: %s", target_key, exc)
            return
        self._subscribed_registry = registry
        self._subscribed_key = target_key

    def _unsubscribe_lifecycle(self) -> None:
        if self._subscribed_registry is None:
            return
        try:
            self._subscribed_registry.remove_batch_event_subscriber(self._on_lifecycle_batch)
        except Exception as exc:
            logger.debug("unsubscribe failed: %s", exc)
        self._subscribed_registry = None
        self._subscribed_key = None

    def _on_lifecycle_batch(self, events: "list[LifeCycleEvent]") -> None:
        if self._path is None or self._subscribed_key is None:
            return
        # Only react if an event touches our watched key.
        if not any(e.matches_registry_key(self._subscribed_key) for e in events):
            return
        try:
            disk = self._read_file(self._path)
        except Exception:
            return
        if disk == self._original:
            return

        if not self._pinned:
            self._content = disk
            self._original = disk
            if self._editor is not None:
                self._editor.value = disk
            return

        self._original = disk
        self._conflict = True
        self._refresh_chrome()

    # ------------------------------------------------------------------
    # Chrome refresh
    # ------------------------------------------------------------------

    def _refresh_chrome(self) -> None:
        if self._pin_banner is not None:
            self._pin_banner.set_visibility(self._pinned)
        if self._conflict_banner is not None:
            self._conflict_banner.set_visibility(self._conflict)
