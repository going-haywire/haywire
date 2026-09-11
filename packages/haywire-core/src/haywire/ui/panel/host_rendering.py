"""Host-side panel rendering for panel-aware hosts.

The ``PropertiesEditor`` and ``BaseContextMenuProvider`` both poll panels for
visibility, then instantiate, inject the actions host and draw the visible
ones, under one error boundary around panel-authored code. These verbs are
that shared contract; hosts own their own iteration:

  - :func:`visible_panels` — poll-filters a list down to the panels to show.
  - :func:`partition_panels` — the superset, ``(applies, disabled)``, for a
    host rendering a panel's inapplicable state through ``draw_disabled()``.
  - :func:`render_panel` — instantiates, injects the host, and draws one.
  - :func:`_poll_surface` — gates a surface once before querying its panels.

``_render_path``, the per-render surface ids, is where surface cycles are
enforced; registration only logs them.

The leaf counter is **not** declared here. ``flyout._leaves_drawn`` already
owns it: a ``SubmenuRow`` greys its anchor retroactively when its body drew
nothing, and that has to be the same number the popup-emptiness rule reads,
or a submenu full of leaf panels would grey itself. ``render_panel`` bumps
it; ``counting_leaves()`` below is the host-side reader.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Generator

from haywire.core.access import required_access
from haywire.core.errors.haywire_exception import HaywireException
from haywire.ui import elements as hui
from haywire.ui.elements.flyout import _leaves_drawn

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext
    from haywire.ui.panel.base import BasePanel
    from haywire.ui.panel.layout import PanelLayout
    from haywire.ui.surface import Surface

logger = logging.getLogger(__name__)


# Surface ids on the current render path. Per-render, not per-session: the
# same surface may legitimately appear twice side by side, but never nested
# inside itself. This is the cycle *enforcement* — registration only logs.
_render_path: ContextVar[tuple[str, ...]] = ContextVar("_render_path", default=())

# The panel class whose draw() is on the stack, so content can name the panel
# that drew it without being passed it. Set by render_panel; read through
# `drawing_panel()`. Nested panels report the innermost one.
_drawing_panel: ContextVar[type["BasePanel"] | None] = ContextVar("_drawing_panel", default=None)


def drawing_panel() -> "type[BasePanel] | None":
    """The panel class currently drawing, or None outside any panel's draw().

    None is an ordinary answer, not an error: settings are also rendered
    outside a panel (the UI harness renders a bag straight onto a page), and a
    caller that wants the panel's identity must degrade to offering nothing
    rather than assuming one is there.
    """
    return _drawing_panel.get()


@contextmanager
def render_path_extended(surface_id: str) -> Generator[None]:
    """Push ``surface_id`` onto the render path for the duration of the block."""
    token = _render_path.set(_render_path.get() + (surface_id,))
    try:
        yield
    finally:
        _render_path.reset(token)


@contextmanager
def counting_leaves() -> Generator[Callable[[], int]]:
    """Run a render with a fresh leaf counter; yields a reader for the total.

    Wraps ``flyout._leaves_drawn`` — the same counter ``SubmenuRow.__exit__``
    reads to decide whether to grey its anchor, one level down. A host opens
    a box (a popup) and this is that box's level.

    The reader stays valid inside the block only — the counter is reset on
    exit, so a host reads it before leaving (that is where the open-or-discard
    decision is made).
    """
    token = _leaves_drawn.set(0)
    try:
        yield _leaves_drawn.get
    finally:
        _leaves_drawn.reset(token)


def _guarded(
    fn: Callable[[], Any],
    *,
    panel_name: str,
    method_name: str,
) -> tuple[Any, HaywireException | None]:
    """Call fn(), returning (result, None) on success or (None, exception) on failure.

    The error boundary around panel-authored code. HaywireException instances
    are passed through unchanged; other exceptions are wrapped with context
    about the panel and method. The error is also logged. Private: hosts go
    through `visible_panels` / `render_panel`, not this directly.
    """
    try:
        return fn(), None
    except HaywireException as exc:
        logger.warning("Panel error in %s.%s: %s", panel_name, method_name, exc, exc_info=True)
        return None, exc
    except Exception as exc:
        wrapped = HaywireException(
            f"Panel {panel_name}.{method_name} raised {type(exc).__name__}: {exc}",
        )
        wrapped.__cause__ = exc
        logger.warning("Panel error in %s.%s: %s", panel_name, method_name, exc, exc_info=True)
        return None, wrapped


def _panel_name(panel_cls: type["BasePanel"]) -> str:
    """Best-effort display name; tolerates a non-class so the boundary can't crash."""
    return getattr(panel_cls, "__name__", repr(panel_cls))


def _accessible(panel_cls: type["BasePanel"], ctx: "SessionContext") -> bool:
    """Whether ``ctx``'s principal may see this panel at all.

    Checked *before* poll(), deliberately: a denied panel's poll() may read
    state the principal has no business touching, and running it would be doing
    work on behalf of someone not allowed to see the result.

    The missing-identity fallback lives in ``required_access`` (Slice 1), shared
    with the editor and Farmhand gates so all three cannot disagree about the
    rule.
    """
    return bool(ctx.can_access(required_access(panel_cls)))


def _poll_panel(panel_cls: type["BasePanel"], ctx: "SessionContext") -> bool:
    """Poll a single panel for visibility under the error boundary.

    Returns the panel's reported visibility, or ``False`` if poll() raised —
    a panel that errors while deciding visibility is treated as not-visible
    (and logged).
    """
    visible, err = _guarded(
        partial(panel_cls.poll, ctx),
        panel_name=_panel_name(panel_cls),
        method_name="poll",
    )
    return err is None and bool(visible)


def _poll_surface(surface: type["Surface"], context: "SessionContext") -> bool:
    """Poll a Surface under the same error boundary panels get.

    The surface-level twin of :func:`_poll_panel`, with the same false-on-raise
    rule. Deliberately *not* folded into :func:`visible_panels`: that function
    is shared by three hosts, takes no surface, and folding the gate in would
    both change its signature and poll the surface a second time on every
    nested render. Each host gates its own surface once, then filters panels.
    """
    applies, err = _guarded(
        partial(surface.poll, context),
        panel_name=getattr(surface, "__name__", repr(surface)),
        method_name="poll",
    )
    return err is None and bool(applies)


def _implements_draw_disabled(panel_cls: type["BasePanel"]) -> bool:
    """Whether ``panel_cls`` overrides ``draw_disabled`` rather than inheriting it.

    The default is a no-op, and a no-op must not count as "something drew" —
    otherwise every panel that polls false would keep a menu open around
    nothing, which is the opposite of the zero-migration guarantee. Compared
    against ``BasePanel``'s own function rather than probed by calling it,
    because calling has side effects by definition.
    """
    from haywire.ui.panel.base import BasePanel

    return getattr(panel_cls, "draw_disabled", None) is not BasePanel.draw_disabled


def partition_panels(
    panel_classes: list[type["BasePanel"]],
    context: "SessionContext",
) -> tuple[list[type["BasePanel"]], list[type["BasePanel"]]]:
    """Split ``panel_classes`` into ``(applies, disabled)``, both in order.

    A panel denied by ``access=`` is dropped from **both** lists — a greyed
    entry advertises what the principal may not have (ADR-0029). The rest
    split on ``poll()``: true lands in ``applies`` (rendered via ``draw()``),
    false in ``disabled`` (rendered via ``draw_disabled()``, whose default is
    a no-op, so a panel with no opinion still simply vanishes).

    Hosts render both lists interleaved in ``order`` — never
    applies-then-disabled, or a menu reshuffles as the selection changes.
    """
    applies: list[type["BasePanel"]] = []
    disabled: list[type["BasePanel"]] = []
    for cls in panel_classes:
        if not _accessible(cls, context):
            continue
        (applies if _poll_panel(cls, context) else disabled).append(cls)
    return applies, disabled


def visible_panels(
    panel_classes: list[type["BasePanel"]],
    context: "SessionContext",
) -> list[type["BasePanel"]]:
    """Poll-filter ``panel_classes`` down to the panels that apply, in order.

    The applicable half of :func:`partition_panels`, kept for hosts that want
    only that set. A panel is dropped when its ``access=`` tier is above the
    principal's, or when its poll() returns ``False`` — or raises, which is
    logged via the error boundary.

    Access is checked first, so a denied panel's poll() never runs.
    """
    return partition_panels(panel_classes, context)[0]


def render_panel(
    panel_cls: type["BasePanel"],
    context: "SessionContext",
    layout: "PanelLayout",
    *,
    actions_host: object | None = None,
    registry: Any = None,
    disabled: bool = False,
) -> bool:
    """Instantiate, inject the host, and draw one panel. Returns whether it drew.

    Assumes the panel's visibility is already decided, by
    :func:`partition_panels` or :func:`visible_panels`.

    A panel that raises is logged and renders an inline ``error_label`` into
    *layout* instead of crashing the host, and returns ``False``.

    Args:
        actions_host: Set on the instance as ``panel.actions``, the host whose
            verbs the panel calls. ``None`` when its surface declares no
            ``provides``.
        registry: Set as ``_hw_registry``, with ``layout.state_bag`` as
            ``_hw_state_bag`` — what a panel needs to render a surface of its
            own (see :meth:`BasePanel.render_surface`).
        disabled: Draw the panel's inapplicable state through
            ``draw_disabled()``. A panel inheriting that no-op is skipped and
            reports ``False``, so it never counts toward a menu opening.
    """

    # Callers are expected to filter through partition_panels() first, but
    # this is public API and a new host can reach it directly. Refusing here
    # makes the access rule a fact rather than a docstring request.
    if not _accessible(panel_cls, context):
        return False

    if disabled and not _implements_draw_disabled(panel_cls):
        return False

    method_name = "draw_disabled" if disabled else "draw"

    def _draw() -> None:
        instance = panel_cls()
        instance.actions = actions_host
        instance._hw_registry = registry
        instance._hw_state_bag = layout.state_bag
        # Publish which panel is drawing, so content rendered inside can name
        # it (see _drawing_panel). Reset in a finally: a panel that raises is
        # caught by _guarded just outside, and leaving a dead panel published
        # would misattribute whatever the error boundary renders next.
        token = _drawing_panel.set(panel_cls)
        try:
            getattr(instance, method_name)(context, layout)
        finally:
            _drawing_panel.reset(token)

    _, err = _guarded(_draw, panel_name=_panel_name(panel_cls), method_name=method_name)
    if err is not None:
        with layout.container:
            hui.error_label(f"Error: {err}")
        return False

    # A leaf that rendered — via either method — is what "something drew"
    # means for the popup-emptiness rule. A hosting panel is excluded because
    # a layout panel draws its arrangement whether or not anything lands in
    # it; only what a leaf put there is content (ADR-0029).
    # getattr-with-default twice: an undecorated BasePanel subclass has no
    # class_identity at all, and this is public API a caller can reach with
    # one. Such a panel declares no hosts, so it counts as a leaf.
    if not getattr(getattr(panel_cls, "class_identity", None), "hosts", ()):
        _leaves_drawn.set(_leaves_drawn.get() + 1)
    return True
