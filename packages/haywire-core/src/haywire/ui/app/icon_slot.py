"""
IconSlot — the Slot subclass for left / right slots.

Renders a horizontal row with a narrow vertical bar (48px) of icon buttons on
one side and the area ``ui.tab_panels`` on the other.

Collapse/expand follows the VS Code activity-bar idiom: clicking the active
icon collapses the area; clicking any icon while collapsed re-expands it
(switching to that editor). There is no separate fold-toggle button.
``set_visible`` hides only the area — the icon bar always stays rendered, so
the icons remain clickable to re-expand a collapsed slot.

The side the bar renders on is configured via the ``bar_place`` constructor
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
        The bar holds one icon button per wrapper. Clicking an icon switches
        to it (``switch_to`` → ``on_focus`` via ``Slot._activate``); clicking
        the active icon collapses the area, and clicking any icon while
        collapsed re-expands it — the VS Code activity-bar idiom, handled in
        :meth:`_on_icon_clicked`. A programmatic :meth:`reveal` into a
        collapsed icon slot auto-expands it (see :attr:`_expands_on_reveal`).
        The bar is never hidden by ``set_visible`` — only the area is — so the
        icons stay clickable in both expanded and collapsed states.
    """

    # Reveal into a collapsed icon slot should pop it open so the user sees
    # the editor they triggered (TabSlot leaves this False — its area is never
    # collapsed by an icon-click gesture).
    _expands_on_reveal: ClassVar[bool] = True

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

        Renders a vertical ``ui.tabs`` — one ``ui.tab`` per wrapper. Quasar
        owns the active indicator (free transition animation; the indicator
        strip sits on the inner edge of the tabs container, which is the
        area-facing side by virtue of the row layout in :meth:`render`).

        There is no fold-toggle button: collapse/expand is driven by clicking
        the icons themselves (VS Code activity-bar idiom). Clicking the active
        icon collapses the area; clicking any icon while collapsed re-expands
        it. The per-tab ``click`` handler carries this — ``ui.tabs`` ``on_change``
        does not fire when the already-active tab is re-clicked, so it can't
        detect the collapse gesture on its own.
        """
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

        # No ``on_change`` handler: the per-tab ``click`` below is the sole
        # driver of switch / collapse / expand. Wiring ``on_change`` too would
        # race the click — q-tabs updates its value (firing on_change →
        # switch_to) *before* the click handler runs, so the click handler
        # would then see the just-switched tab as the active one and collapse
        # the slot on a plain cross-tab click. Quasar still moves its own
        # visual ``value`` on click; the next ``_refresh_bar`` re-syncs the
        # highlight to the true active editor (``tabs.value = active_tab``).
        tabs = (
            ui.tabs().props(tab_props).classes("w-full hw-icon-bar-tabs").style("background: transparent;")
        )
        active_tab = None
        with tabs:
            for wrapper in renderable:
                # ui.tab defaults label to `name` when label is None; pass
                # label="" so the binding_id doesn't render as text under
                # the icon. The editor draws its own icon (and tooltip) via
                # render_tab_into; the slot owns only the tab shell, the
                # active indicator, and the dirty marker.
                tab = ui.tab(name=wrapper.editor_binding_id, label="")
                # Per-tab click drives switch / collapse / expand. Fires on
                # every click — including a re-click of the already-active
                # icon (the fold gesture), which a tabs ``on_change`` would
                # swallow.
                tab.on("click", lambda _e, bid=wrapper.editor_binding_id: self._on_icon_clicked(bid))
                with tab:
                    # Slot-owned chrome: dirty marker — a small corner dot,
                    # rendered for every editor including custom overrides.
                    if wrapper.state is not None and wrapper.state.is_dirty:
                        ui.icon("circle").classes("hw-tab-dirty").style(
                            "position: absolute; top: 4px; right: 4px; font-size: 8px; "
                            "color: var(--hw-text-body);"
                        )
                    # Editor-owned interior: icon (+ tooltip) by default.
                    wrapper.render_tab_into(orientation="vertical")
                if wrapper is active_wrapper:
                    active_tab = tab
        if active_tab is not None:
            tabs.value = active_tab

    # ------------------------------------------------------------------
    # User actions
    # ------------------------------------------------------------------

    def _on_icon_clicked(self, tab_id: str) -> None:
        """VS Code-style icon click: switch, collapse, or re-expand.

        The sole click handler for the icon bar — there is no tabs
        ``on_change`` to race against, so ``self.active_binding_id`` is read
        before this method mutates it via ``switch_to``.

        Decision table (``tab_id`` is the clicked icon's binding id):

        * Slot **collapsed** → expand; if the clicked icon isn't already the
          active one, switch to it first. (Any icon re-opens the slot.)
        * Slot **expanded** and the clicked icon **is** the active one →
          collapse the slot (the fold gesture).
        * Slot **expanded** and a **different** icon clicked → switch to it,
          staying open.

        ``switch_to`` runs ``editor.on_focus`` via ``Slot._activate``, so no
        separate context notification is needed. The bar is refreshed so the
        active highlight (and, when collapsing, any visibility-derived chrome)
        stays in sync.
        """
        key, binding_id = EditorWrapper.split_id(tab_id)

        if not self._visible:
            if self.active_binding_id != tab_id:
                self.switch_to(key, binding_id)
            self.set_visible(True)
            self._refresh_bar()
            return

        if self.active_binding_id == tab_id:
            self.set_visible(False)
            return

        self.switch_to(key, binding_id)
        self._refresh_bar()
