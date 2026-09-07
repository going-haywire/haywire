# barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/component_rows.py
"""Shared bits for the "Edit…" submenus on the pin and selection menus.

Both menus answer the same question about different subjects — *which
components produced what I am looking at, and where is their code* — so the
row, the key resolution and the reveal live here rather than twice.

These rows are deliberately **not** gated on ``ctx.developer_mode``. They
point at ordinary registry components (a data type, a widget, a node, a skin,
a theme), which is the same ungated navigation the create-node menu performs
on right-click and what the Component Docs/Source editors exist to follow.
The ``developer_mode`` gate in core's settings rows covers a different thing:
which *panel class* or *settings class* drew a row — the studio's own
internals. A node's skin is the user's own vocabulary; "what does this skin
do" is a normal question.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from haywire.ui import elements as hui

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


def identity_of(cls: object | None) -> Any | None:
    """The ``class_identity`` stamped on *cls* at registration, or None.

    Absent on an unregistered class (a test double, a dynamically built type),
    which is a miss rather than an error: the caller draws no row. ``None`` in
    is ``None`` out, so callers can pass a lookup that legitimately found
    nothing without each repeating the guard.
    """
    if cls is None:
        return None
    return getattr(cls, "class_identity", None)


def key_and_label(identity: Any | None, fallback: str = "") -> tuple[str, str]:
    """Split an identity into ``(registry_key, display label)``.

    An identity with no ``registry_key`` yields ``("", ...)`` — falsy, so the
    caller skips the row rather than drawing one that opens nothing.
    """
    if identity is None:
        return "", ""
    key = getattr(identity, "registry_key", "") or ""
    label = getattr(identity, "label", "") or fallback or key
    return key, label


def reveal_component(ctx: "SessionContext", registry_key: str) -> None:
    """Show ``registry_key``'s source, popping the CONTEXT slot open.

    Publishes ``RevealComponentSource`` rather than only assigning
    ``ctx.active_component``. The assignment alone updates the source/docs
    editors in place, which is enough for the create-node menu (the user is
    already looking at that surface) but not from a canvas right-click: with
    the CONTEXT slot collapsed it would silently update content nobody can
    see. The reveal is what expands a collapsed slot
    (``IconSlot._expands_on_reveal``); ``ComponentSourceEditor`` sets
    ``active_component`` itself in its ``@reveal_on`` hook, before the reveal.

    Fire-and-forget, like every other reveal: with no source viewer installed
    nothing answers, which is a working configuration rather than an error.
    """
    from haywire.core.signals import RevealComponentSource

    ctx.session.publish(RevealComponentSource(registry_key=registry_key))


def component_row(ctx: "SessionContext", label: str, key: str, icon: str) -> bool:
    """Draw one "open this component's source" row. Returns whether it drew.

    The return value is what lets a hosting ``hui.submenu_row`` grey itself
    when every row inside declined — a body that draws nothing greys its
    anchor retroactively (see ``SubmenuRow.__exit__``), so callers need only
    report honestly.
    """
    if not key:
        return False
    hui.menu_row(
        label,
        icon=icon,
        tooltip=f"Open the source of {key}",
        on_click=lambda: reveal_component(ctx, key),
    )
    return True
