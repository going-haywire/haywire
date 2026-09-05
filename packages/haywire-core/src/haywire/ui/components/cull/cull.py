"""SPIKE — per-node culling wrapper.

Under evaluation, not yet a supported seam. See
``.insights/project_nicegui_component_vs_native_tag.md`` for the mechanism it
is testing: NiceGUI passes each element's children to Vue as a slot FUNCTION,
so a component that does not invoke its slot stops the page's full-tree render
walk from descending into that subtree.
"""

from nicegui import ui


class NodeCull(ui.element, component="cull.vue"):
    """Wraps one node's card so the client can withhold it from the render walk.

    Visibility is driven from JS through the ``_hwCull`` handle the component
    attaches to its own element — never from Python, because a pan would then
    cost one websocket message per node.
    """

    def __init__(self) -> None:
        super().__init__()
