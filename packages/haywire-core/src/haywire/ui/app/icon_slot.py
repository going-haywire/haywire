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
        """Re-entrant bar content renderer — call after clearing ``_bar_container``."""
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

        # One icon button per wrapper, highlighting the active one.
        for wrapper in self._bindings:
            icon = wrapper.editor_cls.class_identity.icon
            label = wrapper.editor_cls.class_identity.label
            is_active = self._active is wrapper
            (
                ui.button(
                    icon=icon,
                    on_click=lambda _e=None, w=wrapper: self._on_icon_clicked(w),
                )
                .classes(self._button_classes(is_active))
                .props("flat round")
                .tooltip(label)
            )

    @staticmethod
    def _button_classes(is_active: bool) -> str:
        base = "hw-shell-toolbar-btn w-10 h-10"
        return f"{base} hw-shell-toolbar-btn-active" if is_active else base

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

    def _on_icon_clicked(self, wrapper: EditorWrapper) -> None:
        """Switch to ``wrapper``.

        ``slot.switch_to`` already calls ``editor.on_focus`` via
        ``Slot._activate`` (slot.py:499-505), so no separate context
        notification is needed.
        """
        if not self.switch_to(wrapper.editor_key, wrapper.payload):
            return
        self._refresh_bar()

    def _on_fold_toggle_clicked(self) -> None:
        """Flip the slot's area visibility."""
        self.set_visible(not self._visible)
