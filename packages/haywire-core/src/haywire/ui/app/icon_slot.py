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

from nicegui import ui

from haywire.ui.app.slot import EditorBinding, Slot
from haywire.ui.context_events import ContextChangedEvent, ContextChangeType


class IconSlot(Slot):
    """Icon-driven slot for the left and right shell slots.

    Notes:
        The bar area holds the fold-toggle button, a separator, and one icon
        button per binding. Clicking an icon fires ``switch_to`` and emits a
        ``WORKSPACE_CHANGED`` event via the session.
        The bar is never hidden by ``set_visible`` — only the area is — so
        the fold toggle remains available in both expanded and retracted
        states (matching the VS Code activity-bar idiom).
    """

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, parent: ui.element) -> None:
        """Build ``[bar | area]`` (or ``[area | bar]``) inside ``parent``."""
        with parent:
            wrapper = ui.row().classes("gap-0 no-wrap").style("height: 100%; overflow: hidden;")

        if self._bar_side == "left":
            with wrapper:
                self._render_bar_column()
                self._area_parent_box = self._create_content_box()
        else:
            with wrapper:
                self._area_parent_box = self._create_content_box()
                self._render_bar_column()

        self._render_area(self._area_parent_box)
        self._area_parent_box.set_visibility(self._visible)

    def _create_content_box(self) -> ui.element:
        """Create the slot's outer content box (width = slot_state.size, id for drag JS)."""
        size = getattr(self._slot_state, "size", 300) if self._slot_state is not None else 300
        border_style = (
            "border-right: 1px solid var(--hw-border);"
            if self._bar_side == "left"
            else "border-left: 1px solid var(--hw-border);"
        )
        col = (
            ui.column()
            .classes("gap-0")
            .style(
                f"width: {size}px; min-width: 150px; height: 100%; "
                "overflow: hidden; background: var(--hw-bg-page);" + border_style
            )
        )
        col._props["id"] = f"hw-slot-{self.name}"
        return col

    def _render_bar_column(self) -> None:
        """Render the icon bar (fold toggle + per-binding icon buttons)."""
        border_style = (
            "border-right: 1px solid var(--hw-border);"
            if self._bar_side == "left"
            else "border-left: 1px solid var(--hw-border);"
        )
        self._bar_container = (
            ui.column()
            .classes("items-center justify-start gap-1 py-2")
            .style(
                "width: 48px; min-width: 48px; height: 100%; "
                "background: var(--hw-bg-sidebar); " + border_style + " overflow: hidden;"
            )
        )
        with self._bar_container:
            self._render_bar_contents()

    def _render_bar_contents(self) -> None:
        """Re-entrant bar content renderer — call after clearing ``_bar_container``."""
        # Fold-toggle button (only rendered when the slot has bindings).
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

        # One icon button per binding, highlighting the active one.
        for binding in self._bindings:
            icon = binding.editor_cls.class_identity.icon
            label = binding.editor_cls.class_identity.label
            is_active = self._active is binding
            (
                ui.button(
                    icon=icon,
                    on_click=lambda _e=None, b=binding: self._on_icon_clicked(b),
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
        if self._bar_side == "left":
            return visible  # left slot: mirror icon while expanded
        return not visible  # right slot: mirror while retracted

    # ------------------------------------------------------------------
    # User actions
    # ------------------------------------------------------------------

    def _on_icon_clicked(self, binding: EditorBinding) -> None:
        """Switch to ``binding`` and broadcast WORKSPACE_CHANGED."""
        if not self.switch_to(binding.editor_key, binding.payload):
            return
        self._refresh_bar()
        self._session.notify_context_changed(
            ContextChangedEvent(change_type=ContextChangeType.WORKSPACE_CHANGED)
        )

    def _on_fold_toggle_clicked(self) -> None:
        """Flip the slot's area visibility."""
        self.set_visible(not self._visible)

    def set_visible(self, visible: bool) -> None:
        """Override: also refresh the fold button icon on transition."""
        transitioning = visible != self._visible
        super().set_visible(visible)
        if transitioning:
            self._refresh_bar()

    def _refresh_bar(self) -> None:
        """Clear and re-render the bar so active-icon highlight + fold icon stay in sync."""
        if self._bar_container is None:
            return
        self._bar_container.clear()
        with self._bar_container:
            self._render_bar_contents()
