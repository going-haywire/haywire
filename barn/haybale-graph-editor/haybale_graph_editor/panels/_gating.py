# barn/haybale-graph-editor/haybale_graph_editor/panels/graph/toolbar/_gating.py
"""Shared ``poll`` predicates for the floating-toolbar panels.

Both answer a question about locked nodes, and they are **not**
interchangeable — they read different selection axes, and using the wrong one
is a bug the UI hides rather than reports:

============================  ==========================  =======================
                              :func:`locked_bag`          :func:`selection_has_locked`
============================  ==========================  =======================
Axis                          Active (the one subject)    Selection (any size)
Returns                       the props bag, or ``None``  ``bool``
Selection-size rule           exactly one, else ``None``  none
Answers                       "which node do I edit?"     "is a lock in the way?"
============================  ==========================  =======================

The distinction is worth a module of its own because collapsing it has already
cost once: Delete and Collapse were first gated on ``locked_bag``, inheriting
its "exactly one node" rule, which hid them from **every** multi-selection —
locked or not — and quietly removed the delete button from ordinary batch work.
A verb that applies to a whole selection must gate on
:func:`selection_has_locked`; only a single-subject affordance (the Lock
toggle, the Appearance dropdown) may use :func:`locked_bag`.

See the **Selection axis** and **Active axis** glossary entries for the wider
model these follow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.core.session.context import SessionContext

from ..state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.node.properties import NodeProperties
    from haywire.core.session.context import SessionContext


def locked_bag(ctx: "SessionContext") -> "NodeProperties | None":
    """The props bag of the single node in play, or ``None``.

    ``None`` whenever there is not exactly ONE node selected: the Active axis
    is cleared by any bulk selection, so ``active_node`` alone already encodes
    "a single node is the subject" — but the selection size is checked too,
    since a lone active node inside a larger selection would otherwise offer a
    button that acts on only part of what the user can see selected.

    Also ``None`` for a wrapper whose node has not been built (or was cleaned
    up): ``NodeWrapper.node`` RAISES rather than returning ``None`` there, and
    a toolbar button is not the place to surface that.

    Callers decide what to do with the bag — read ``locked`` to render a state,
    write it to toggle, or treat ``None`` as "this affordance does not apply".
    """
    edit = ctx.data[EditState]
    if len(edit.selected_nodes) != 1:
        return None
    wrapper = edit.active_node
    if wrapper is None:
        return None
    try:
        return wrapper.node.props
    except RuntimeError:
        return None


def selection_has_locked(ctx: "SessionContext") -> bool:
    """True when ANY selected node is locked.

    The gate for verbs a lock refuses (delete, collapse), at any selection
    size. Deliberately carries no size rule of its own — see the module
    docstring for what happens when it borrows :func:`locked_bag`'s.

    In practice only ever true for a lone locked node, since ``canvas.vue``
    keeps locked nodes out of multi-selections entirely. Written as "any"
    regardless, so the gate stays correct on its own terms rather than on that
    invariant continuing to hold.
    """
    edit = ctx.data[EditState]
    graph = edit.active_graph
    if graph is None:
        return False
    for node_id in edit.selected_nodes:
        wrapper = graph.get_node_wrapper(node_id)
        if wrapper is None:
            continue
        if wrapper.node.props.locked:
            return True
    return False


def is_reroute_node(ctx: "SessionContext") -> bool:
    """True when the selection's primary node is a reroute node.

    The primary node is the one whose card is on show, and the one that
    receives the context menu. It is not necessarily the only node in the
    selection, but it is the one that matters for this command.
    """
    wrapper = ctx.data[EditState].active_node
    if wrapper is None:
        return False
    return wrapper.node.behavior.is_reroute_node
