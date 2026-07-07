"""Nested-flyout menu mechanics.

A **flyout menu** is a nested context-menu submenu that opens *on hover* of its
anchor item and cascades to the right, raised above the context-menu popup. Only
one open path from the root exists at a time: opening one flyout closes its
siblings (same-level group) and their open descendants.

The hover-open / sibling-close behaviour is fragile under NiceGUI 3.x's render
model (see ``.insights/feedback_nicegui_nested_menu_flyouts.md``): ``auto-close``
dismisses a flyout on selection or click-away but NOT when the mouse moves to a
*sibling* category, and 3.x drops closed-menu DOM, so close-timers break. This
module is the single home for that machinery, so callers that build hierarchical
hover menus (the add-node menu) share one behaviour and can never drift.

Callers keep their own domain recursion and leaf rendering; this module owns only
the mechanics. The typical pattern::

    siblings: FlyoutSiblings = []
    with hui.flyout_category("📁 filter", siblings) as child_siblings:
        # render leaves here (plain ui.menu_item), and recurse for
        # subcategories passing `child_siblings` as their sibling group.
        ...
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, List

from nicegui import ui

# Above the context-menu popup card (z-index 7001); Quasar QMenu defaults to 6000.
FLYOUT_Z = "z-index: 7100"

# Flyout to the right of the anchor, cascading rightward for nested submenus.
FLYOUT_PROPS = 'anchor="top end" self="top start"'

# A sibling group: the open-flyout set for one menu level. Opening any member
# closes the others (and their descendants), leaving one open path from the root.
FlyoutSiblings = List[ui.menu]


def menu_item_tooltip(item: ui.menu_item, text: str) -> None:
    """Attach a hover tooltip to a ``ui.menu_item`` (Quasar ``QItem``).

    A bare ``ui.tooltip`` child does not fire on a ``QItem`` inside a ``QMenu`` —
    the menu swallows the hover event — so the tooltip must be shown/hidden
    explicitly on the item's ``mouseenter``/``mouseleave`` (same pattern the
    add-node menu uses for node descriptions).
    """
    with item:
        tip = ui.tooltip(text).classes("text-xs").props("no-parent-event")
    item.on("mouseenter", lambda _: tip.run_method("show"))
    item.on("mouseleave", lambda _: tip.run_method("hide"))


def close_flyout(submenu: ui.menu) -> None:
    """Close ``submenu`` and any open descendant flyouts (depth-first)."""
    for child in getattr(submenu, "_child_flyouts", ()):
        close_flyout(child)
    submenu.close()


def open_on_hover(anchor: ui.menu_item, submenu: ui.menu, siblings: FlyoutSiblings) -> None:
    """Open ``submenu`` on hover of ``anchor``, closing its sibling flyouts.

    Quasar's QMenu opens on its anchor's *click*, not hover, so we open it
    explicitly on ``mouseenter``. Each open first closes the other flyouts in its
    ``siblings`` group (and their open descendants), leaving exactly one open path
    from the root at a time. Closing on click-away is left to ``auto-close``,
    which avoids the close-timer machinery that broke under NiceGUI 3.x.
    """

    def open_and_close_siblings() -> None:
        for other in siblings:
            if other is not submenu:
                close_flyout(other)
        submenu.open()

    anchor.on("mouseenter", open_and_close_siblings)


@contextmanager
def flyout_category(label: str, siblings: FlyoutSiblings, tooltip: str = "") -> Iterator[FlyoutSiblings]:
    """Render one hover-opening category flyout and yield its child sibling group.

    Creates a ``ui.menu_item`` anchor (with a right-arrow affordance) whose nested
    ``ui.menu`` flyout opens on hover, registering it into ``siblings`` and wiring
    the sibling-close behaviour. Inside the ``with`` block the flyout is the active
    NiceGUI slot, so callers render its contents (leaf ``ui.menu_item``s,
    separators) directly; subcategories recurse by calling ``flyout_category``
    again, passing the *yielded* child sibling group as their ``siblings``.

    ``tooltip``, when non-empty, is attached to the *anchor row* (not the flyout
    body) so hovering the category shows its help text — the caller can't reach the
    internal anchor, so the primitive wires it.
    """
    with ui.menu_item(label, auto_close=False).props("dense") as item:
        if tooltip:
            menu_item_tooltip(item, tooltip)
        with ui.item_section().props("side"):
            ui.icon("keyboard_arrow_right")

        submenu = ui.menu().props(f"{FLYOUT_PROPS} auto-close").style(FLYOUT_Z)
        # Child flyouts form their own sibling group, one level deeper.
        child_siblings: FlyoutSiblings = []
        with submenu:
            yield child_siblings

        submenu._child_flyouts = child_siblings  # type: ignore[attr-defined]
        siblings.append(submenu)
        open_on_hover(item, submenu, siblings)
