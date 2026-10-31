"""Resolve Path — the location of a path on this machine."""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.volumes import VolumePath, resolve


@node(
    label="Resolve Path",
    description="Gives the absolute location of a path on this machine, as text",
    menu="core/paths",
    search_tags=["path", "resolve", "absolute", "location", "file", "folder", "volume"],
    node_type=NodeType.DATA,
)
class ResolvePathNode(BaseNode):
    """Gives the absolute location of a path on this machine, as text.

    Use it to hand a path to something outside the graph, or to see where a file
    is. The result differs between machines, so keep paths as paths inside the
    graph. A path wired straight to a text inlet arrives as `volume name:path`
    instead, the same on every machine.

    The file or folder need not exist. A path whose volume is not defined here,
    or that leads outside its volume, is reported as an error.
    """

    def init(self) -> None:
        from haywire.barn.builtin.types import PATH, STRING

        self.add(PATH.as_inlet("path", label="Path"))
        self.add(
            STRING.as_outlet(
                "resolved", label="Resolved", description="absolute location of a path on this machine"
            )
        )

    def worker(self, context: ExecutionContext, path: VolumePath) -> None:
        self.out("resolved", str(resolve(path)))
        return None
