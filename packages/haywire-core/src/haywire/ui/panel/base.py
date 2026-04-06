# packages/haywire-core/src/haywire/ui/panel/base.py
"""
Abstract base class and layout helper for Haywire panels.
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import TYPE_CHECKING, ClassVar, Any, Callable

from haywire.ui import elements as hui
from .identity import PanelIdentity

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


class PanelLayout:
    """
    Layout helper passed to panel draw() methods.

    Provides two usage modes:

    **Simple mode** — call helpers directly for common design-correct patterns::

        def draw(self, context, layout):
            layout.section_label("FILES")
            layout.separator()
            layout.empty_state("Nothing selected", icon="folder_open")

    **Power mode** — use as a context manager to activate the container, then
    call ``hui.*`` functions directly for full design-system access::

        def draw(self, context, layout):
            with layout:
                hui.section_label("ADVANCED")
                with hui.expansion_section("Node", context=context):
                    hui.info_row("Key", node.registry_key)

    All helper methods delegate to ``hui`` — they are convenience shortcuts,
    not a separate styling layer.
    """

    def __init__(self, container: Any):
        self._container = container

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self):
        self._container.__enter__()
        return self

    def __exit__(self, *args):
        return self._container.__exit__(*args)

    # ── Helpers (delegate to hui) ─────────────────────────────────────────────

    def panel_header(self, title: str, *, icon: str | None = None):
        """Slim header bar with title, optional icon, and space for action buttons.

        Use as a context manager to add action buttons::

            with layout.panel_header("Files", icon="folder"):
                hui.icon_action("refresh", on_click=self._refresh)
        """
        with self._container:
            return hui.panel_header(title, icon=icon)

    def section_label(self, text: str) -> Any:
        """Uppercase tracking label that separates groups within a panel."""
        with self._container:
            return hui.section_label(text)

    def separator(self) -> None:
        """Plain themed horizontal rule."""
        with self._container:
            hui.separator()

    def section_divider(self, text: str | None = None) -> None:
        """Visual break between sections, with optional label."""
        with self._container:
            hui.section_divider(text)

    def empty_state(self, message: str, *, icon: str = "folder_open", hint: str | None = None) -> Any:
        """Centred placeholder for panels with no content."""
        with self._container:
            return hui.empty_state(message, icon=icon, hint=hint)

    def error_label(self, text: str) -> Any:
        """Error message label using ``--hw-danger``."""
        with self._container:
            return hui.error_label(text)

    def warning_label(self, text: str) -> Any:
        """Warning message label using ``--hw-warning``."""
        with self._container:
            return hui.warning_label(text)

    def icon_action(self, icon: str, *, tooltip: str | None = None, on_click: Callable | None = None) -> Any:
        """Minimal icon-only action button."""
        with self._container:
            return hui.icon_action(icon, tooltip=tooltip, on_click=on_click)

    @contextmanager
    def expansion_section(
        self,
        label: str,
        *,
        icon: str | None = None,
        default_open: bool = True,
        context: "SessionContext | None" = None,
        panel_key: str | None = None,
    ):
        """Collapsible section. Use as a context manager::

        with layout.expansion_section("Details", icon="info", context=ctx):
            hui.info_row("Key", node.registry_key)
        """
        with self._container:
            with hui.expansion_section(
                label, icon=icon, default_open=default_open, context=context, panel_key=panel_key
            ) as exp:
                yield exp

    def label(self, text: str) -> Any:
        """Body-tier text label using ``--hw-text-body``."""
        with self._container:
            return hui.label(text)

    def button(self, text: str, *, icon: str | None = None, on_click: Callable | None = None) -> Any:
        """A flat labelled action button, optionally with a leading icon."""
        with self._container:
            return hui.button(text, icon=icon, on_click=on_click)


class BasePanel(ABC):
    """
    Abstract base class for all panels.

    A panel is a collapsible section that appears inside an editor,
    filtered by context. Panels are the primary extension point for
    library developers to add custom UI.

    Class attributes (set by @panel decorator via class_identity):
        - class_identity.registry_key: Unique registry key.
        - class_identity.editor_keys: Which editor types this panel belongs to (list).
        - class_identity.context: Context filter string.
        - class_identity.label: Display label shown in the panel header.
        - class_identity.icon: Optional Material icon.
        - class_identity.order: Sort priority (lower = higher in the list).
        - class_identity.default_open: Whether the panel starts expanded.

    Lifecycle:
        1. Editor receives ContextChangedEvent.
        2. Editor queries PanelRegistry for panels matching its editor_key.
        3. For each panel, editor calls poll(context).
        4. If poll() returns True, editor calls draw(context, layout).
        5. If poll() returns False, panel is hidden.
    """

    class_identity: ClassVar[PanelIdentity]

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        """
        Determine if this panel should be visible given the current context.

        Called every time the context changes. Should be fast — avoid
        expensive computation here.

        Args:
            context: Current session context.

        Returns:
            True if the panel should be shown, False to hide it.
        """
        return True

    @abstractmethod
    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        """
        Render the panel contents.

        Called when poll() returns True and the panel needs to display.
        Use the layout helper to add widgets and UI elements.

        Args:
            context: Current session context.
            layout: PanelLayout helper for building the UI.
        """
        ...

    def on_context_changed(self, context: "SessionContext", layout: PanelLayout) -> None:
        """
        Optional incremental update when context changes without full redraw.

        Override for panels that can update in-place rather than fully
        re-rendering. If not overridden, the editor will clear and re-call draw().
        """
        pass
