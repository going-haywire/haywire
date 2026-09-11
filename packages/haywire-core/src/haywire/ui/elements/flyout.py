"""Nested-flyout menu mechanics.

A flyout is a submenu that opens on hover of its anchor and cascades to the
right, raised above the context-menu popup. One open path exists at a time:
opening a flyout closes its siblings and their descendants. Keeping that
machinery here is what stops hierarchical hover menus from drifting apart —
it is fragile under NiceGUI 3.x, which drops closed-menu DOM and whose
``auto-close`` does not fire when the mouse moves to a sibling category (see
``.insights/feedback_nicegui_nested_menu_flyouts.md``).

Callers own their domain recursion and leaf rendering. A tree that owns its
own ``ui.menu`` recursion threads an explicit sibling group::

    siblings: FlyoutSiblings = []
    with hui.flyout_category("📁 filter", siblings) as child_siblings:
        # leaves here; recurse for subcategories with `child_siblings`
        ...

Callers that cannot thread one — mutually blind panels — use ``SubmenuRow``
(``hui.submenu_row``), a labelled row expanding sideways into a flyout body,
or ``FlyoutIcon`` (``hui.flyout``), its icon-only face for a toolbar. Both
read and push the ambient ``_flyout_siblings`` context var, so a caller pushes
a group once around a popup's content and everything nested below finds it.

Both are classes rather than ``@contextmanager`` generators, so a disabled
``SubmenuRow`` that is never entered still draws its row.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Generator, List, Literal

from nicegui import ui

from haywire.ui.elements.elements import MENU_ROW_ICON_CLASS, menu_row

# One rung above Quasar's interaction tier, which QMenu hardcodes at 6000: a
# flyout is a QMenu inside another QMenu, so without this the child wins only
# on portal insertion order. The literal is the fallback for pages rendered
# without the shell's CSS (previews, tests).
#
# No width: a flyout stretching to the browser edge is an inline-level leaf
# inside it, not the menu's sizing, and the fix belongs on the leaf —
# `hui.button` carries it.
FLYOUT_Z = "z-index: var(--hw-z-menu-over-menu, 6001)"

# Flyout to the right of the anchor, cascading rightward for nested submenus.
FLYOUT_PROPS = 'anchor="top end" self="top start"'

# Where a dropdown panel sits relative to its icon (`hui.dropdown`), named for
# where the panel lands the way `text-align` is, not the direction it travels.
# Neither this nor `direction` is a promise: Quasar flips a panel that would
# leave the viewport, keeping alignment. Use `direction` to want up while down
# still fits, such as a toolbar along a panel's bottom edge.
DROPDOWN_ALIGNMENTS: dict[str, tuple[str, str]] = {  # (anchor, self) horizontal
    # panel's left edge on the icon's left edge — it grows rightward
    "left": ("start", "start"),
    # panel's right edge on the icon's right edge — it grows leftward
    "right": ("end", "end"),
    # panel centred on the icon — it grows both ways
    "center": ("middle", "middle"),
}

DROPDOWN_DIRECTIONS: dict[str, tuple[str, str]] = {  # (anchor, self) vertical
    # panel's top edge on the icon's bottom edge — it hangs below
    "down": ("bottom", "top"),
    # panel's bottom edge on the icon's top edge — it stands above
    "up": ("top", "bottom"),
}

DropdownAlign = Literal["left", "right", "center"]
DropdownDirection = Literal["down", "up"]


def dropdown_props(*, align: DropdownAlign = "left", direction: DropdownDirection = "down") -> str:
    """The Quasar ``anchor``/``self`` props for one dropdown placement.

    Composed from the two tables above rather than looked up in a table of
    pairs: the axes are independent, so a caller that asks for a new alignment
    gets it in both directions for free, and neither table can gain an entry
    the other lacks.
    """
    if align not in DROPDOWN_ALIGNMENTS:
        raise ValueError(
            f"hui.dropdown(align={align!r}) — expected one of {', '.join(sorted(DROPDOWN_ALIGNMENTS))}"
        )
    if direction not in DROPDOWN_DIRECTIONS:
        raise ValueError(
            f"hui.dropdown(direction={direction!r}) — expected one of "
            f"{', '.join(sorted(DROPDOWN_DIRECTIONS))}"
        )
    anchor_v, self_v = DROPDOWN_DIRECTIONS[direction]
    anchor_h, self_h = DROPDOWN_ALIGNMENTS[align]
    return f'anchor="{anchor_v} {anchor_h}" self="{self_v} {self_h}"'


# The default placement, kept as a name of its own because it is what every
# dropdown gets that does not ask.
DROPDOWN_PROPS = dropdown_props()

# A QMenu positions against, and opens on a click of, its parent element, not
# whatever is passed to `open()`. So every flyout is built inside its anchor
# (`with self._anchor:` / `with self._row:`); built in the ambient slot it
# anchors to whichever container the panel drew into, and a click anywhere in
# that container opens it.

# Guards against a fast diagonal mouse path across a sibling item switching
# flyouts. Delays the open only — closing stays synchronous through
# sibling-close and `auto-close`. A close-timer breaks under 3.x's dropped
# DOM (`.insights/feedback_nicegui_nested_menu_flyouts.md`).
FLYOUT_OPEN_DELAY_S = 0.12

_DISABLED_STYLE = "opacity: 0.4; pointer-events: none"


class FlyoutMenu(ui.menu):
    """A ``ui.menu`` that tracks its child flyouts for depth-first cascade-close.

    ``_child_flyouts`` is the one-level-deeper sibling group opened beneath this
    flyout; ``close_flyout`` walks it to dismiss descendants before closing self.
    """

    def __init__(self, *, value: bool = False) -> None:
        super().__init__(value=value)
        self._child_flyouts: FlyoutSiblings = []


# A sibling group: the open-flyout set for one menu level. Opening any member
# closes the others (and their descendants), leaving one open path from the root.
FlyoutSiblings = List[FlyoutMenu]


# The ambient sibling group for the current menu level — a popup or a flyout
# body, a visual box rather than a surface. A container pushes a fresh group
# when it opens a box; everything drawn inside reads it without knowing it has
# siblings.
#
# No default, so a row constructed with nothing pushed raises instead of
# silently pooling unrelated rows into one shared group: a ContextVar default
# is one object evaluated once, never a fresh list per read.
_flyout_siblings: ContextVar[FlyoutSiblings] = ContextVar("_flyout_siblings")


@contextmanager
def open_flyout_group() -> Generator[FlyoutSiblings]:
    """Push a fresh sibling group as the ambient level for everything drawn inside.

    Call it around a box with no owning row: a ``Popup``'s top-level content,
    or a ``ui.menu`` opened directly. Panels rendered inside pass nothing.

    Never call it inside a ``hui.submenu_row`` or ``hui.flyout`` body, whose
    ``__enter__`` pushes its own group — a second group there orphans
    everything inside from the row's ``_child_flyouts`` and breaks
    cascade-close for that branch.
    """
    child_siblings: FlyoutSiblings = []
    token = _flyout_siblings.set(child_siblings)
    try:
        yield child_siblings
    finally:
        _flyout_siblings.reset(token)


# "Did anything draw inside this body", so a hosting row can grey itself
# retroactively in `__exit__`. Two things bump it: a caller-drawn leaf, and
# constructing a nested row or icon — the latter only when the enclosing level
# is itself a flyout body (`_in_flyout_body`). A disabled nested row counts:
# it still renders. A level where neither happened reads as empty.
_leaves_drawn: ContextVar[int] = ContextVar("_leaves_drawn", default=0)

# Whether the ambient `_leaves_drawn` belongs to a flyout body rather than a
# host's top-level scope. Both push the same sibling-group shape, so nothing
# else tells the two boxes apart from inside `__init__`.
#
# A row drawn straight into a host's own `draw()` is a container at that
# scope, the category `render_panel` already excludes from popup-emptiness
# counting. Bumping the host's counter there makes a popup whose only content
# is one empty flyout icon look non-empty, so it opens around a single greyed
# control instead of not opening.
#
# Only `SubmenuRow.__enter__`/`FlyoutIcon.__enter__` set it True.
_in_flyout_body: ContextVar[bool] = ContextVar("_in_flyout_body", default=False)


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


def close_flyout(submenu: FlyoutMenu) -> None:
    """Close ``submenu`` and any open descendant flyouts (depth-first)."""
    for child in submenu._child_flyouts:
        close_flyout(child)
    submenu.close()


def open_on_hover(anchor: ui.element, submenu: FlyoutMenu, siblings: FlyoutSiblings) -> None:
    """Open ``submenu`` after a short hover delay on ``anchor``, closing siblings.

    Quasar's QMenu opens on its anchor's *click*, not hover, so we open it
    explicitly on ``mouseenter``. Each open first closes the other flyouts in its
    ``siblings`` group (and their open descendants), leaving exactly one open path
    from the root at a time. Closing on click-away is left to ``auto-close``,
    which avoids the close-timer machinery that broke under NiceGUI 3.x.

    The open itself is gated behind ``FLYOUT_OPEN_DELAY_S``: a fast diagonal
    mouse path across a sibling item would otherwise open-then-immediately-close
    it. The delay is cancelled on ``mouseleave`` before it fires — this is an
    *open* debounce, not a close-timer: once a submenu is open, closing it is
    still purely sibling-close / ``auto-close``, synchronous, no timers involved.
    The pending timer is parented to ``anchor`` so it is torn down with it if the
    anchor's slot is cleared before the delay elapses
    (``.insights/feedback_nicegui_async.md``, "a ui.timer can outlive the slot it
    was created in").
    """
    pending: dict[str, ui.timer] = {}

    def open_and_close_siblings() -> None:
        pending.pop("timer", None)
        for other in siblings:
            if other is not submenu:
                close_flyout(other)
        submenu.open()

    def schedule_open() -> None:
        cancel_pending()
        with anchor:
            pending["timer"] = ui.timer(FLYOUT_OPEN_DELAY_S, open_and_close_siblings, once=True)

    def cancel_pending() -> None:
        timer = pending.pop("timer", None)
        if timer is not None:
            timer.cancel()
            timer.delete()

    anchor.on("mouseenter", schedule_open)
    anchor.on("mouseleave", cancel_pending)


@contextmanager
def flyout_category(
    label: str, siblings: FlyoutSiblings, tooltip: str = "", *, dense: bool = True
) -> Generator[FlyoutSiblings]:
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

    ``dense`` sets the anchor's Quasar density, and must match the density of the
    *sibling* items it lines up with — a ``dense`` q-item has smaller padding, so
    an anchor that disagrees with the plain ``menu_item``s above it sits visibly
    shorter than the rest of the menu. It defaults True for ``NodeMenuBuilder``,
    whose own leaves are dense; a settings row's menu, whose Reset/Promote items
    are not, passes ``dense=False``. The caller cannot fix this after the fact:
    the anchor is internal and only the child sibling group is yielded.
    """
    # `white-space: nowrap` on the item, not the QMenu: a flyout Quasar flips
    # leftward shrink-to-fits the smaller space, and the label is a real
    # `ItemSection` child free to wrap. Pinning it keeps the natural width.
    anchor_props = "dense" if dense else ""
    with ui.menu_item(label, auto_close=False).props(anchor_props).style("white-space: nowrap") as item:
        if tooltip:
            menu_item_tooltip(item, tooltip)
        with ui.item_section().props("side"):
            ui.icon("keyboard_arrow_right")

        submenu = FlyoutMenu()
        submenu.props(f"{FLYOUT_PROPS} auto-close").style(FLYOUT_Z)
        # Child flyouts form their own sibling group, one level deeper.
        child_siblings: FlyoutSiblings = []
        with submenu:
            yield child_siblings

        submenu._child_flyouts = child_siblings
        siblings.append(submenu)
        open_on_hover(item, submenu, siblings)


def _anchor_row(label: str, icon: str | None, enabled: bool) -> ui.row:
    """A ``hui.menu_row`` plus the sideways affordance — a row that expands.

    Built on ``menu_row`` rather than ``ui.menu_item``, whose look needs an
    enclosing ``QMenu`` a panel drawing into a ``Popup`` column does not have.
    Carries ``hw-flyout-row``, the marker retroactive greying and tests look
    for.
    """
    row = menu_row(label, icon=icon, enabled=enabled).classes(add="hw-flyout-row")
    with row:
        ui.icon("keyboard_arrow_right").classes(MENU_ROW_ICON_CLASS)
    return row


class FlyoutIcon:
    """``hui.flyout(icon, tooltip=...)`` — an icon-only anchor that opens a flyout.

    The icon-row counterpart of ``SubmenuRow``, for a toolbar rather than a
    labelled list. Registers into the ambient sibling group and pushes a fresh
    one for its own body on ``__enter__``.

    If the body draws nothing, ``__exit__`` greys the anchor and makes it
    unclickable, so an unextended ⋯ reads as unavailable instead of opening an
    empty box.

    Usage::

        with hui.flyout("image", tooltip="Image"):
            ...  # flyout body: leaves, or nested hui.submenu_row / hui.flyout
    """

    # Overridden by DropdownIcon — the only two things that differ between a
    # sideways command flyout and a downward content dropdown.
    def _menu_props(self) -> str:
        return f"{FLYOUT_PROPS} auto-close"

    def _wire_trigger(self, siblings: FlyoutSiblings) -> None:
        open_on_hover(self._anchor, self._menu, siblings)

    def __init__(self, icon: str, *, tooltip: str = "") -> None:
        self._anchor = ui.button(icon=icon).props("flat round dense size=sm")
        if tooltip:
            self._anchor.tooltip(tooltip)

        # Inside the anchor, not beside it: a QMenu positions against, and
        # opens on a click of, its parent element. See the anchoring note above.
        with self._anchor:
            self._menu = FlyoutMenu()
        self._menu.props(self._menu_props()).style(FLYOUT_Z)

        siblings = _flyout_siblings.get()
        siblings.append(self._menu)
        self._wire_trigger(siblings)
        # This row counts as content drawn at the enclosing level — the one
        # ambient here, not the level __enter__ pushes — when that level is
        # itself a flyout body. See `_in_flyout_body`.
        if _in_flyout_body.get():
            _leaves_drawn.set(_leaves_drawn.get() + 1)

        self._child: FlyoutSiblings = []
        self._token: Token[FlyoutSiblings] | None = None
        self._count_token: Token[int] | None = None
        self._body_token: Token[bool] | None = None

    def __enter__(self) -> "FlyoutIcon":
        self._child = []
        self._token = _flyout_siblings.set(self._child)  # body is a new level
        self._count_token = _leaves_drawn.set(0)
        self._body_token = _in_flyout_body.set(True)
        self._menu.__enter__()
        return self

    def __exit__(self, *exc: object) -> None:
        self._menu.__exit__(*exc)
        assert self._token is not None
        assert self._count_token is not None
        assert self._body_token is not None
        drew_anything = _leaves_drawn.get() > 0
        _flyout_siblings.reset(self._token)
        _leaves_drawn.reset(self._count_token)
        _in_flyout_body.reset(self._body_token)
        self._menu._child_flyouts = self._child

        if not drew_anything:
            self._anchor.classes(add="hw-disabled").style(_DISABLED_STYLE)


# A popup opened inside a dropdown is its own Quasar portal at the default
# z-6000, behind the dropdown that spawned it. It teleports to <body>, beyond
# the reach of any CSS descendant rule, so the lift is stamped on the element
# as it is built — one rung above the dropdown, so stacking never depends on
# portal insertion order.
_NESTED_POPUP_Z = "z-index: calc(var(--hw-z-menu-over-menu, 6001) + 1)"


def _lift_nested_popups(body: ui.element) -> None:
    """Raise every popup-spawning control drawn inside a dropdown body.

    A dropdown panel is a ``QMenu`` one rung above Quasar's interaction tier,
    so a select's option list, a colour picker or a row menu inside it opens
    on the bare tier, underneath the panel that spawned it. One more rung
    clears it. A menu inside a ``Popup`` needs none of this — a popup sits
    below the tier.

    Applies to the whole body, since it is often a hosted surface whose
    widgets the factory builds, where no caller could pass a flag.
    """
    for element in body.descendants():
        # ContextMenu is a sibling of Menu, not a subclass, so testing only
        # ui.menu misses every row menu.
        if isinstance(element, (ui.menu, ui.context_menu)):
            element.style(_NESTED_POPUP_Z)
        elif isinstance(element, ui.select):
            element.props(f'popup-content-style="{_NESTED_POPUP_Z}"')


def close_siblings_on_open(submenu: FlyoutMenu, siblings: FlyoutSiblings) -> None:
    """Keep the one-open-path rule for a menu Quasar opens by itself.

    A ``QMenu`` built inside its anchor already toggles on a click of it, so a
    click-triggered dropdown needs only the sibling-close half of
    :func:`open_on_hover`, hung off Quasar's ``show`` event. Adding an
    explicit ``open()`` fights Quasar's toggle and sticks the menu open on the
    second click.
    """

    def _close_others() -> None:
        for other in siblings:
            if other is not submenu:
                close_flyout(other)

    submenu.on("show", _close_others)


class DropdownIcon(FlyoutIcon):
    """``hui.dropdown(icon, tooltip=...)`` — an icon that opens a panel below it.

    Same anchor, same sibling group, same cascade-close and same retroactive
    greying as ``hui.flyout``; three deliberate differences, because what
    hangs off it is **content**, not commands:

    - **Opens above or below the icon rather than beside it** — the shape a
      toolbar wants for a group of fields. Two independent axes, so two
      parameters (see :func:`dropdown_props`):

      ``align`` picks the horizontal edges: ``"left"`` (the default) puts the
      panel's left edge on the icon's so it grows rightward, ``"right"`` grows
      leftward from the icon's right edge, ``"center"`` centres it. A wide
      panel under a toolbar's last icon wants ``"right"``, one under a middle
      icon usually ``"center"``.

      ``direction`` picks the vertical side: ``"down"`` (the default) hangs
      the panel below the icon, ``"up"`` stands it above. Reach for ``"up"``
      only when up is what you want while down would still fit — a toolbar
      along a panel's bottom edge, a status-bar control. Quasar flips a panel
      that would leave the viewport, so neither parameter is a promise: never
      lay out content assuming the panel is where you asked.
    - **Click, not hover**, through Quasar's own anchor-click toggle (see
      :func:`close_siblings_on_open`).
    - **No ``auto-close``**, which dismisses on any click inside, so the first
      click into a field would close the panel. A dropdown closes on
      click-away, or when a sibling flyout opens.

    Everything drawn inside must be a panel for the emptiness rule to work:
    ``__exit__`` greys the icon when nothing bumped the leaf counter, and only
    ``render_panel`` bumps it. Render a hosted surface here (the ADR-0029
    shape) rather than fields drawn straight into the body, or an
    otherwise-fine dropdown greys itself.

    Usage::

        with hui.dropdown(hui.icon.theme, tooltip="Appearance"):
            self.render_surface(NodeAppearance, ctx)

        with hui.dropdown("tune", tooltip="Filters", align="right"):
            self.render_surface(FilterPanel, ctx)   # last icon in a toolbar

        with hui.dropdown("palette", align="center", direction="up"):
            self.render_surface(Swatches, ctx)      # toolbar along a bottom edge
    """

    def __init__(
        self,
        icon: str,
        *,
        tooltip: str = "",
        align: DropdownAlign = "left",
        direction: DropdownDirection = "down",
    ) -> None:
        # Validated here, at construction, so a typo is an error where it was
        # written rather than a panel that opens somewhere surprising.
        self._props_str = dropdown_props(align=align, direction=direction)
        self._align = align
        self._direction = direction
        super().__init__(icon, tooltip=tooltip)

    def _menu_props(self) -> str:
        return self._props_str

    def _wire_trigger(self, siblings: FlyoutSiblings) -> None:
        close_siblings_on_open(self._menu, siblings)

    def __exit__(self, *exc: object) -> None:
        _lift_nested_popups(self._menu)
        super().__exit__(*exc)


class SubmenuRow:
    """``hui.submenu_row(label, icon=None, enabled=True)`` — a row that expands sideways.

    ``enabled=False`` renders the greyed, non-expanding form and creates no
    flyout, so it may be called bare and never entered.

    A row reads the ambient sibling group to register its own flyout into; it
    never takes a ``siblings`` list from its caller. ``__enter__`` pushes a
    fresh group for its body, which becomes the menu's ``_child_flyouts`` for
    cascade-close.

    ``__exit__`` greys the anchor row if the body drew nothing at all. A body
    whose leaves all drew themselves greyed still counts as having drawn.
    Callers do the counting, by bumping ``_leaves_drawn`` inside the block.
    """

    def __init__(self, label: str, *, icon: str | None = None, enabled: bool = True) -> None:
        self._row = _anchor_row(label, icon, enabled)
        self._enabled = enabled
        self._menu: FlyoutMenu | None = None
        self._child: FlyoutSiblings = []
        self._token: Token[FlyoutSiblings] | None = None
        self._count_token: Token[int] | None = None
        self._body_token: Token[bool] | None = None

        # A row, enabled or not, counts as content drawn at the enclosing
        # level when that level is itself a flyout body — so a container whose
        # body is only nested rows does not grey itself. Distinct from the
        # counter __enter__ resets for this row's own body.
        if _in_flyout_body.get():
            _leaves_drawn.set(_leaves_drawn.get() + 1)

        if not enabled:
            return

        with self._row:  # inside the anchor — see the module's ANCHORING note
            self._menu = FlyoutMenu()
        self._menu.props(f"{FLYOUT_PROPS} auto-close").style(FLYOUT_Z)

        siblings = _flyout_siblings.get()  # ambient: this level's group
        siblings.append(self._menu)
        open_on_hover(self._row, self._menu, siblings)

    def __enter__(self) -> "SubmenuRow":
        if self._menu is None:
            raise RuntimeError("a disabled SubmenuRow (enabled=False) has no body to enter")
        self._child = []
        self._token = _flyout_siblings.set(self._child)  # body is a new level
        self._count_token = _leaves_drawn.set(0)
        self._body_token = _in_flyout_body.set(True)
        self._menu.__enter__()
        return self

    def __exit__(self, *exc: object) -> None:
        assert self._menu is not None
        self._menu.__exit__(*exc)
        assert self._token is not None
        assert self._count_token is not None
        assert self._body_token is not None
        drew_anything = _leaves_drawn.get() > 0
        _flyout_siblings.reset(self._token)
        _leaves_drawn.reset(self._count_token)
        _in_flyout_body.reset(self._body_token)
        self._menu._child_flyouts = self._child

        if not drew_anything:
            self._row.classes(add="hw-disabled").style(_DISABLED_STYLE)
