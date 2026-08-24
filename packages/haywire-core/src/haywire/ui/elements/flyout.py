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

Two more general primitives build on the same mechanics for callers that are
NOT ``ui.menu``-recursion-owning trees (``NodeMenuBuilder``'s case): panels that
are mutually blind and can't thread a shared ``siblings`` list themselves.

- ``SubmenuRow`` (``hui.submenu_row``) — a labelled row, styled independently of
  any enclosing ``QMenu``, that expands sideways into a flyout body. The sibling
  group it registers into, and the group it opens for its own body, are both
  read from and pushed onto an ambient ``ContextVar`` (``_flyout_siblings``), the
  same shape as this codebase's other ``ContextVar``-based render-path
  mechanisms. Callers push a group once (around a popup's content, or around a
  ``SubmenuRow``'s body); everything nested below just reads the ambient group
  and never learns it has siblings.
- ``FlyoutIcon`` (``hui.flyout``) — the bare icon-only face of the same anchor,
  for a toolbar/icon-row context menu rather than a labelled list.

Both are classes, not ``@contextmanager`` generators: a generator that is never
entered executes nothing, so a disabled, non-expanding ``SubmenuRow`` (which
never calls ``__enter__``) would draw no row at all if it were a generator. A
class draws its anchor in ``__init__`` and opens the flyout slot in
``__enter__``, serving both the bare-call and ``with`` shapes.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Generator, List

from nicegui import ui

from haywire.ui.elements.elements import MENU_ROW_ICON_CLASS, menu_row

# Above the context-menu popup card (z-index 7001); Quasar QMenu defaults to 6000.
#
# Deliberately no width here. A QMenu is already shrink-to-fit, so a flyout that
# stretches to the browser edge is never the menu's own sizing — it is an
# *inline-level* leaf inside it (a bare QBtn is `display: inline-flex`), which
# makes the menu's max-content the sum of every leaf on one line. Setting
# `width: max-content` / a max-width cap here only re-measures or truncates that
# same wrong number; the fix belongs on the leaf, and `hui.button` carries it.
FLYOUT_Z = "z-index: 7100"

# Flyout to the right of the anchor, cascading rightward for nested submenus.
# Quasar anchor/self points; a downward-opening variant would be
# `anchor="bottom start" self="top start"`.
FLYOUT_PROPS = 'anchor="top end" self="top start"'

# ANCHORING: a QMenu positions against, and opens on a click of, its PARENT
# element — not whatever element you pass to `open()`. So every flyout menu
# here is built *inside* its anchor (`with self._anchor:` / `with self._row:`).
# Built in the ambient slot instead, it anchored to whichever container the
# panel happened to draw into: measured, the selection toolbar's ⋯ flyout
# aligned to the top of the shared panel div rather than to the ⋯ button, a
# submenu opened level with the top of its popup rather than with its own row,
# and clicking the Copy button in the toolbar opened the ⋯ flyout.

# A fast diagonal mouse path across a sibling item would otherwise switch
# flyouts unintentionally (`.insights/feedback_nicegui_nested_menu_flyouts.md`
# "Known rough edge"). This delays the *open*, never the close — closing still
# happens synchronously via sibling-close / `auto-close`. Do NOT turn this into
# a close-timer; that machinery was removed for a reason (see the same file).
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


# The ambient sibling group for the current menu *level* (a popup or a flyout
# body — a visual box, not a surface). Mirrors the module-level ContextVar
# pattern used elsewhere in this codebase (e.g. `_render_path`): a container
# (a context-menu host, or `SubmenuRow.__enter__`) pushes a fresh group when it
# opens a box; everything drawn inside reads the ambient group via `.get()`
# without knowing it has siblings.
#
# No usable default: unlike `_leaves_drawn` (0 is a correct empty state), a
# `FlyoutSiblings` default would have to be a fresh list *per read*, and
# ContextVar defaults are a single shared object evaluated once at declaration
# time — a mutable default here would silently pool unrelated top-level rows
# into one shared sibling group. A row/icon constructed with nothing pushed
# means a caller forgot to open a box (the context-menu host, or an outer
# `SubmenuRow`/`FlyoutIcon`) — surface that as a clear error, not a quiet
# cross-wired default.
_flyout_siblings: ContextVar[FlyoutSiblings] = ContextVar("_flyout_siblings")


@contextmanager
def open_flyout_group() -> Generator[FlyoutSiblings]:
    """Push a fresh sibling group as the ambient level for everything drawn inside.

    This is the primitive a context-menu host wraps around a ``Popup``'s content
    — the container-owns-the-group half of the sibling-group contract
    (``SubmenuRow.__enter__`` is the other half, owning the group for its own
    flyout body). Panels rendered inside pass nothing and never learn they have
    siblings; only whoever opens the box calls this.

    Do **not** call this again directly inside a ``with hui.submenu_row(...)`` /
    ``with hui.flyout(...)`` body — their own ``__enter__`` already pushes a
    fresh group for that body. Pushing a second, unread group here would orphan
    everything drawn inside from the row's ``_child_flyouts``, breaking
    cascade-close for that whole branch. Call this only around a *box* that has
    no owning row of its own — a ``Popup``'s top-level content, or a ``ui.menu``
    opened directly.
    """
    child_siblings: FlyoutSiblings = []
    token = _flyout_siblings.set(child_siblings)
    try:
        yield child_siblings
    finally:
        _flyout_siblings.reset(token)


# "Did anything draw inside this body" — a minimal counter, ambient the same
# way as `_flyout_siblings`, that lets a hosting row grey itself retroactively
# once its body is fully drawn. Two things bump it:
#   1. A caller-drawn leaf (future `draw()` / `draw_disabled()` panel methods;
#      simulated directly by tests here) — this module does not itself decide
#      what counts as a leaf "drawing something".
#   2. Constructing a nested `SubmenuRow`/`FlyoutIcon` at this level, but ONLY
#      when the enclosing level is itself a flyout body (see `_in_flyout_body`
#      below) — a container whose body is *only* further nested rows, with no
#      direct leaf of its own, must not grey itself just because none of its
#      own leaves fired: its children existing at all is itself "something
#      drew" at this level, whether or not those children later grey
#      themselves. This fires for `enabled=False` rows too — a disabled
#      nested row still renders a real greyed row, it is not absent.
# Only a level where NEITHER happened -- no leaf and no nested row of any
# kind -- reads as truly empty and greys retroactively in `__exit__`.
_leaves_drawn: ContextVar[int] = ContextVar("_leaves_drawn", default=0)

# Whether the ambient `_leaves_drawn` counter belongs to a flyout BODY
# (`SubmenuRow`/`FlyoutIcon`'s own `__enter__`) rather than a host's top-level
# scope (`open_flyout_group()`, pushed once around a `Popup`'s content). Both
# push the same `_flyout_siblings` group shape, so without this there is no
# way to tell the two kinds of box apart from inside `__init__`.
#
# The distinction matters because a `SubmenuRow`/`FlyoutIcon` counting as
# "something drew" at its enclosing level is correct ONLY when that level is
# itself another row's body — that is the nested-container case above. A
# `SubmenuRow`/`FlyoutIcon` constructed directly in a host's top-level scope
# (e.g. a hosting panel like `GraphMorePanel` drawing `hui.flyout(...)`
# straight into its own `draw()`) is, at that scope, architecturally a
# container — exactly the category `render_panel` already excludes from the
# popup-emptiness count for hosting panels (`class_identity.hosts != ()`).
# Bumping the host's own counter there would make a popup whose only content
# is one empty flyout icon look non-empty, opening a popup around a single
# retroactively-greyed, useless control instead of not opening at all.
#
# `open_flyout_group()` does not set this to `True` (the default `False`
# already holds for it); only `SubmenuRow.__enter__`/`FlyoutIcon.__enter__` do.
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
def flyout_category(label: str, siblings: FlyoutSiblings, tooltip: str = "") -> Generator[FlyoutSiblings]:
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

    The look is **not** built here: it is one ``hui.menu_row``, so a submenu row
    and the leaf commands beside it are the same element by construction and
    cannot drift. ``flyout_category`` uses ``ui.menu_item``, whose look comes
    from an enclosing ``QMenu`` — fine for ``NodeMenuBuilder``, which always
    opens one, but a panel drawing into a ``Popup`` content column has no such
    ancestor; ``menu_row`` carries its own marker class and reads identically in
    both contexts. ``hw-flyout-row`` stays on top of it as the "this one
    expands" marker (what the retroactive greying and tests look for).
    """
    row = menu_row(label, icon=icon, enabled=enabled).classes(add="hw-flyout-row")
    with row:
        ui.icon("keyboard_arrow_right").classes(MENU_ROW_ICON_CLASS)
    return row


class FlyoutIcon:
    """``hui.flyout(icon, tooltip=...)`` — an icon-only anchor that opens a flyout.

    The icon-row counterpart of ``SubmenuRow``, for a toolbar/icon-row context
    menu (e.g. ``GraphToolBar``) rather than a labelled list. Registers into the
    ambient sibling group the same way ``SubmenuRow`` does, and pushes a fresh
    group for its own body on ``__enter__``.

    Like ``SubmenuRow``, ``__exit__`` decides retroactively whether the body
    drew anything and greys the icon anchor if it drew nothing at all — same
    ``_leaves_drawn`` counter, same ``opacity: 0.4; pointer-events: none``
    treatment, same reasoning (no user observes the anchor mid-construction).
    This is what makes an unextended ⋯ — a panel hosting an extension-point
    surface nobody has extended yet — read as unavailable rather than as a live
    control opening an empty box.

    Usage::

        with hui.flyout("image", tooltip="Image"):
            ...  # flyout body: leaves, or nested hui.submenu_row / hui.flyout
    """

    def __init__(self, icon: str, *, tooltip: str = "") -> None:
        self._anchor = ui.button(icon=icon).props("flat round dense size=sm")
        if tooltip:
            self._anchor.tooltip(tooltip)

        # Inside the anchor, not beside it: a QMenu positions against — and
        # opens on a click of — its PARENT element. Constructed in the ambient
        # slot it would anchor to whatever container the panel drew into (for
        # the toolbar, the one div every toolbar panel shares), so the flyout
        # aligned to that container and a click on any *other* button in it
        # opened this flyout. See the ANCHORING note at the top of this module.
        with self._anchor:
            self._menu = FlyoutMenu()
        self._menu.props(f"{FLYOUT_PROPS} auto-close").style(FLYOUT_Z)

        siblings = _flyout_siblings.get()
        siblings.append(self._menu)
        open_on_hover(self._anchor, self._menu, siblings)
        # This row itself is content having drawn at the ENCLOSING level (the
        # level that was ambient when this constructor ran, not the fresh
        # level this row pushes for its own body in __enter__) -- but only
        # when that enclosing level is itself a flyout body. See
        # SubmenuRow.__init__ and `_in_flyout_body` for the full rationale.
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


class SubmenuRow:
    """``hui.submenu_row(label, icon=None, enabled=True)`` — a row that expands sideways.

    ``enabled=False`` renders the greyed, non-expanding form (no flyout is
    created at all — a later stage's ``draw_disabled()`` calls this bare, never
    entering it): ``opacity: 0.4; pointer-events: none``, never a grey fill,
    following ``hui.icon_action``'s documented disabled-state rule.

    On construction, a row reads the ambient sibling group (``_flyout_siblings``)
    to register its own flyout into and wire sibling-close — it never receives a
    ``siblings`` list from its caller, and never learns it has siblings. On
    ``__enter__`` it pushes a *fresh* group for its own body, becoming the new
    ambient level (and the group is stashed as the menu's ``_child_flyouts`` for
    depth-first cascade-close).

    ``__exit__`` also decides, retroactively, whether the body drew anything:
    a body that drew nothing at all greys the anchor row after the fact (no
    user can observe the row mid-construction). A body where every leaf itself
    chose a disabled/greyed form still counts as "drew something" — only a
    body that drew *nothing* is regreyed here. Counting is delegated to the
    ambient ``_leaves_drawn`` counter, which real callers increment from inside
    the ``with`` block (this module does not decide what "drew" means).
    """

    def __init__(self, label: str, *, icon: str | None = None, enabled: bool = True) -> None:
        self._row = _anchor_row(label, icon, enabled)
        self._enabled = enabled
        self._menu: FlyoutMenu | None = None
        self._child: FlyoutSiblings = []
        self._token: Token[FlyoutSiblings] | None = None
        self._count_token: Token[int] | None = None
        self._body_token: Token[bool] | None = None

        # A row -- enabled or not -- is itself content having drawn at the
        # ENCLOSING level (the level ambient right now, before __enter__
        # pushes a fresh one for this row's own body) -- but only when that
        # enclosing level is itself a flyout body (`_in_flyout_body`), not a
        # host's top-level popup scope (see `_in_flyout_body`'s definition for
        # why). A container whose body consists entirely of nested
        # SubmenuRow/FlyoutIcon children (no direct leaf of its own) must not
        # grey itself just because none of ITS leaves fired -- its children
        # existing at all *is* the "drew something" signal for it. This must
        # fire for enabled=False too: a disabled nested row still renders a
        # real greyed row, it is not absent, so it still counts here.
        # (Contrast: the fresh counter this row resets to 0 in __enter__
        # tracks its OWN body, a separate level.)
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
