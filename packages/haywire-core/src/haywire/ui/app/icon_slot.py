"""
IconSlot — the Slot subclass for left / right slots.

Renders a horizontal row with a narrow vertical bar (48px) of icon buttons on
one side and the area ``ui.tab_panels`` on the other. The bar includes an
optional fold toggle at the top that flips the slot's area visibility via
``set_visible`` — the slot wrapper and bar stay rendered so the fold control
remains reachable when the area is hidden.

The side the bar renders on is configured via the ``bar_side`` constructor
arg: ``"left"`` places the bar before the area (used by the left slot);
``"right"`` places it after (right slot / ContextBar).
"""

from __future__ import annotations

from typing import ClassVar, Literal

from nicegui import ui

from haywire.ui.app.slot import Slot
from haywire.ui.editor.wrapper import EditorWrapper


class IconSlot(Slot):
    """Icon-driven slot for the left and right shell slots.

    Notes:
        The bar area holds the fold-toggle button, a separator, and one icon
        button per wrapper. Clicking an icon fires ``switch_to`` and emits a
        ``WORKSPACE_CHANGED`` event via the session.
        The bar is never hidden by ``set_visible`` — only the area is — so
        the fold toggle remains available in both expanded and retracted
        states (matching the VS Code activity-bar idiom).
    """

    _ORIENTATION: ClassVar[Literal["horizontal", "vertical"]] = "horizontal"

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, parent: ui.element) -> None:
        """Build ``[bar | area]`` (or ``[area | bar]``) inside ``parent``."""
        with parent:
            row = ui.row().classes("gap-0 no-wrap").style("height: 100%; overflow: hidden;")

        if self._bar_place == "left":
            with row:
                self._render_bar_column()
                self._area_parent_box = self._create_content_box()
        else:
            with row:
                self._area_parent_box = self._create_content_box()
                self._render_bar_column()

        self._render_area_contents(self._area_parent_box)
        self._area_parent_box.set_visibility(self._visible)

    def _render_bar_contents(self) -> None:
        """Re-entrant bar content renderer — call after clearing ``_bar_container``.

        Layout (top → bottom):
            1. Fold-toggle button (plain ``ui.button``, sits outside the tabs
               so its click doesn't enter the q-tabs active-state machinery).
            2. Separator.
            3. ``ui.tabs`` (vertical) — one ``ui.tab`` per wrapper. Quasar
               owns the active indicator (free transition animation; the
               indicator strip sits on the inner edge of the tabs container,
               which is the area-facing side by virtue of the row layout
               in :meth:`render`).
        """
        # Fold-toggle button (only rendered when the slot has wrappers).
        if self._bindings:
            fold_icon = self._fold_icon_for_visible(self._visible)
            btn = (
                ui.button(icon=fold_icon, on_click=self._on_fold_toggle_clicked)
                .props("flat round dense size=sm")
                .tooltip(f"Toggle {self.name} slot")
            )
            # Mirror the original visual: left=login+mirror-when-visible; right=login+mirror-when-hidden.
            if self._mirror_fold_icon(self._visible):
                btn.style("transform: scaleX(-1);")
            self._fold_button = btn
            ui.separator().classes("w-full opacity-20")

        # Filter to wrappers with a registered editor class — we use
        # binding_id as the tab value for stable per-(key, binding_id) routing.
        renderable = [w for w in self._bindings if w.editor_cls is not None]
        if not renderable:
            return

        # Indicator side: q-tabs in vertical mode places the indicator on
        # the inner edge of the active tab. Quasar's `switch-indicator`
        # prop flips it to the opposite edge. The bar's area-facing side
        # is the side OPPOSITE its placement — left-slot bar has its area
        # on the right, so the indicator should be on the right edge of
        # the tabs container (no `switch-indicator` needed since q-tabs
        # in vertical mode defaults to the right edge for left-aligned
        # tabs). For a right-slot bar we flip with `switch-indicator`.
        active_wrapper = self._active if self._active in renderable else renderable[0]
        tab_props = "vertical no-caps inline-label align=center"
        if self._bar_place == "right":
            tab_props += " switch-indicator"

        tabs = (
            ui.tabs(on_change=self._on_tab_change)
            .props(tab_props)
            .classes("w-full hw-icon-bar-tabs")
            .style("background: transparent;")
        )
        active_tab = None
        with tabs:
            for wrapper in renderable:
                icon = wrapper.editor_cls.class_identity.icon  # type: ignore[union-attr]
                tooltip = wrapper.editor_cls.class_identity.label  # type: ignore[union-attr]
                # ui.tab defaults label to `name` when label is None; pass
                # label="" so the binding_id doesn't render as text under
                # the icon. The hover tooltip carries the human-readable
                # editor label instead.
                tab = ui.tab(name=wrapper.editor_binding_id, label="", icon=icon).tooltip(tooltip)
                if wrapper is active_wrapper:
                    active_tab = tab
        if active_tab is not None:
            tabs.value = active_tab

    def _fold_icon_for_visible(self, visible: bool) -> str:
        return "login" if visible else "logout"

    def _mirror_fold_icon(self, visible: bool) -> bool:
        """Whether to apply scaleX(-1) to the fold icon, matching the original UX."""
        if self._bar_place == "left":
            return visible  # left slot: mirror icon while expanded
        return not visible  # right slot: mirror while retracted

    # ------------------------------------------------------------------
    # User actions
    # ------------------------------------------------------------------

    def _on_tab_change(self, e) -> None:
        """Handle q-tabs value change: resolve binding_id → wrapper, switch.

        NiceGUI's ``ui.tabs`` passes a :class:`ValueChangeEventArguments`
        whose ``value`` is the tab's ``name`` string (the
        ``_value_to_model_value`` hook in ``Tabs`` normalises Tab elements
        to their name). Tests may also pass a raw Tab element — we accept
        either by extracting ``._props['name']`` when present.

        ``slot.switch_to`` already calls ``editor.on_focus`` via
        ``Slot._activate``, so no separate context notification is needed.
        """
        value = e.value if hasattr(e, "value") else e
        if value is None:
            return
        tab_id = value if isinstance(value, str) else getattr(value, "_props", {}).get("name")
        if not tab_id:
            return
        key, binding_id = EditorWrapper.split_id(tab_id)
        self.switch_to(key, binding_id)

    def _on_fold_toggle_clicked(self) -> None:
        """Flip the slot's area visibility."""
        self.set_visible(not self._visible)
