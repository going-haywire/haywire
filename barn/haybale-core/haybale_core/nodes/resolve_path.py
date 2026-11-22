"""Resolve Path — the location of a path on this machine."""

from __future__ import annotations

from haywire.api import (
    PATH,
    STRING,
    BaseNode,
    ExecutionContext,
    NodeType,
    VolumePath,
    node,
    resolve_volume_path,
)


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
        self.add(PATH.as_inlet("path", label="Path", description="Path to resolve"))
        self.add(
            STRING.as_outlet(
                "resolved", label="Resolved", description="Absolute location of the path on this machine"
            )
        )

    def worker(self, context: ExecutionContext, path: VolumePath) -> None:
        self.out("resolved", str(resolve_volume_path(path)))
        return None
