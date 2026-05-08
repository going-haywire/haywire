# packages/haywire-core/src/haywire/ui/panel/layout.py
"""PanelLayout — layout helper passed to BasePanel.draw()."""

from contextlib import contextmanager
from typing import Any, Callable

from haywire.ui import elements as hui


class PanelLayout:
    """
    Layout helper passed to panel draw() methods.

    Provides two usage modes:

    **Simple mode** — call helpers directly for common design-correct patterns::

        def draw(self, ctx, layout, actions):
            layout.section_label("FILES")
            layout.separator()
            layout.empty_state("Nothing selected", icon="folder_open")

    **Power mode** — use as a context manager to activate the container, then
    call ``hui.*`` functions directly for full design-system access::

        def draw(self, ctx, layout, actions):
            with layout:
                hui.section_label("ADVANCED")
                with layout.expansion_section("Node"):
                    hui.info_row("Key", node.registry_key)

    The optional ``expansion_state`` dict (passed at construction) is the
    persistence bag for ``expansion_section``. The owning editor typically
    holds it as an instance field so collapsed/expanded sections survive
    rebuilds without leaking into shared session state.

    All helper methods delegate to ``hui`` — they are convenience shortcuts,
    not a separate styling layer.
    """

    def __init__(self, container: Any, *, expansion_state: dict[str, bool] | None = None):
        self._container = container
        self._expansion_state = expansion_state

    @property
    def container(self) -> Any:
        """The underlying NiceGUI container element."""
        return self._container

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
        panel_key: str | None = None,
    ):
        """Collapsible section. Use as a context manager::

        with layout.expansion_section("Details", icon="info", panel_key="details"):
            hui.info_row("Key", node.registry_key)

        Persistence uses the layout's ``expansion_state`` dict (set at
        construction). Sections without a ``panel_key`` are not persisted.
        """
        with self._container:
            with hui.expansion_section(
                label,
                icon=icon,
                default_open=default_open,
                state=self._expansion_state,
                panel_key=panel_key,
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
