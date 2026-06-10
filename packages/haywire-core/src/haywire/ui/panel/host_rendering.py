"""Host-side panel rendering for panel-aware hosts.

Two hosts render panels: the PropertiesEditor (persistent display panels)
and BaseContextMenuProvider (ephemeral context-menu panels). Both run the
same steps — poll each panel for visibility, then instantiate, inject the
actions host, and draw the visible ones — and both need the same error
boundary around panel-authored code.

`_guarded` is that boundary: it invokes a panel's poll() or draw() and
returns ``(result, exception)`` instead of letting the exception escape.
Hosts don't call it directly — they use the intention-revealing verbs built
on top of it:

  - `visible_panels` — poll-filters a list down to the panels to show.
  - `render_panel` — instantiates, injects the host, and draws one panel.

Both hosts share those, so the rendering contract lives in one place. The
hosts own their own iteration (the editor wraps each panel in an expansion
section; the context menu gates popup-open on whether any panel is visible).
"""

from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING, Any, Callable

from haywire.core.errors.haywire_exception import HaywireException
from haywire.ui import elements as hui

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext
    from haywire.ui.panel.base import BasePanel
    from haywire.ui.panel.layout import PanelLayout

logger = logging.getLogger(__name__)


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


def visible_panels(
    panel_classes: list[type["BasePanel"]],
    context: "SessionContext",
) -> list[type["BasePanel"]]:
    """Poll-filter ``panel_classes`` down to the panels to show, in order.

    The single visibility gate shared by both hosts. A panel whose poll()
    returns ``False`` — or raises — is dropped (raises are logged via the
    error boundary). Hosts use this to decide what to mount, and the
    context-menu host to decide whether to open at all.
    """
    return [cls for cls in panel_classes if _poll_panel(cls, context)]


def render_panel(
    panel_cls: type["BasePanel"],
    context: "SessionContext",
    layout: "PanelLayout",
    *,
    actions_host: object | None = None,
) -> bool:
    """Instantiate, inject the host, and draw one panel. Returns whether it drew.

    ``actions_host`` is set on the instance as ``panel.actions`` — the host
    for action panels, ``None`` for display panels (which leaves it at the
    ``BasePanel.actions`` default). draw() runs under the error boundary, so
    a panel that raises is logged and an inline ``error_label`` is rendered
    into ``layout`` rather than crashing the host; the call then returns
    ``False``.

    Callers poll-filter first via :func:`visible_panels`, so this assumes the
    panel is already known visible.
    """

    def _draw() -> None:
        instance = panel_cls()
        instance.actions = actions_host
        instance.draw(context, layout)

    _, err = _guarded(_draw, panel_name=_panel_name(panel_cls), method_name="draw")
    if err is None:
        return True
    with layout.container:
        hui.error_label(f"Error: {err}")
    return False
