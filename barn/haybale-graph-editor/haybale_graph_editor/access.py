# barn/haybale-graph-editor/haybale_graph_editor/access.py
"""The canvas lock rule, and the write gates that enforce it where a value is written.

A locked canvas caps a session's effective tier at operate. ``NodeWriteGate``
and ``GraphWriteGate`` carry the rule to a widget (``BaseWidget.write_gate``)
or a settings form (``render_settings(gate=...)``), which ask it at every write.
"""

from typing import TYPE_CHECKING, Callable

from haywire.core.access import AccessTier

from .state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.node.node_wrapper import NodeWrapper
    from haywire.core.session.context import SessionContext


def allows(can_access: Callable[[AccessTier], bool], locked: bool, required: AccessTier) -> bool:
    """Return whether ``required`` is allowed, given the session's real tier and the canvas lock.

    ``can_access`` answers for the session's real tier. A locked canvas also
    refuses anything above operate.
    """
    if not can_access(required):
        return False
    return not locked or AccessTier.OPERATE.satisfies(required)


def can_edit_graph(ctx: "SessionContext") -> bool:
    """Return whether ``ctx`` may edit the graph on screen, lock included."""
    return allows(ctx.can_access, ctx.data[EditState].active_locked, AccessTier.EDIT)


def session_allows(ctx: "SessionContext") -> Callable[[AccessTier], bool]:
    """Return ``allows`` bound to ``ctx``'s real tier and the lock of the level it has on screen.

    The lock is read at each call, so a gate built on it follows the lock.
    """
    return lambda required: allows(ctx.can_access, ctx.data[EditState].active_locked, required)


class NodeWriteGate:
    """A write gate for a node's values: refuses below ``required``, marks the graph unsaved after a write.

    Args:
        allows_fn: Answers whether the session may do what a tier asks, as
            ``GraphCanvasManager.allows`` or ``session_allows(ctx)`` does.
            Asked at every write.

    Example::

        # A node card's widget: operate is enough, a locked canvas included.
        widget.write_gate = NodeWriteGate(AccessTier.OPERATE, manager.allows, wrapper)
        # A form in the properties editor: needs edit, which a lock refuses.
        render_settings(ctx, bag, gate=NodeWriteGate(AccessTier.EDIT, session_allows(ctx), wrapper))
    """

    def __init__(
        self, required: AccessTier, allows_fn: Callable[[AccessTier], bool], wrapper: "NodeWrapper"
    ) -> None:
        self._required = required
        self._allows_fn = allows_fn
        self._wrapper = wrapper

    def allows(self) -> bool:
        """Return whether ``allows_fn`` allows the required tier now."""
        return self._allows_fn(self._required)

    def written(self) -> None:
        """Mark the node's value edited. See ``NodeWrapper.mark_value_edited``."""
        self._wrapper.mark_value_edited()


class GraphWriteGate:
    """A write gate that refuses below ``required`` and marks nothing after a write.

    For a form whose writes do not mark the graph unsaved, or mark it
    themselves: graph settings and metadata, and a connection's style (which
    reports ``EDGE_STYLE_CHANGED``).

    Args:
        allows_fn: Answers whether the session may do what a tier asks, as
            ``GraphCanvasManager.allows`` or ``session_allows(ctx)`` does.
            Asked at every write.

    Example::

        render_settings(ctx, graph.props, gate=GraphWriteGate(AccessTier.EDIT, session_allows(ctx)))
    """

    def __init__(self, required: AccessTier, allows_fn: Callable[[AccessTier], bool]) -> None:
        self._required = required
        self._allows_fn = allows_fn

    def allows(self) -> bool:
        """Return whether ``allows_fn`` allows the required tier now."""
        return self._allows_fn(self._required)

    def written(self) -> None:
        """Do nothing."""
