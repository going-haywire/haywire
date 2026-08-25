"""FillDemoNode — a compound BaseType with a custom widget, wired end to end.

Exists to exercise :class:`FILL` in a real node card rather than only in unit
tests: the config port renders the FillWidget, and the outlet hands the fill's
generated CSS to anything downstream.

Read this alongside ``types/fill.py`` (the type) and ``widgets/fill_widget.py``
(its editor) when building a structured type of your own.
"""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType

from haybale_example.types.fill import FILL


@node(
    label="Fill Demo",
    search_tags=["fill", "gradient", "colour", "color", "css", "example"],
    menu="examples/appearance",
    node_type=NodeType.DATA,
)
class FillDemoNode(BaseNode):
    """Edits a solid/linear/radial fill and outputs it as a CSS value."""

    def init(self):
        from haywire.barn.builtin.types import STRING

        # A CONFIG port: the fill is authored on the card, not fed by an edge.
        # FILL carries its own widget_key, so no `widget=` is needed here — the
        # FillWidget is chosen by the type.
        self.add(FILL.as_config(id="fill", label="Fill"))

        self.add(STRING.as_outlet(id="css", label="CSS"))

    def worker(self, context: ExecutionContext, fill: FILL) -> str | None:
        # to_css() is total: every reachable field combination yields a valid
        # `background` value, so this needs no guarding.
        self.out("css", fill.to_css())
        return None
