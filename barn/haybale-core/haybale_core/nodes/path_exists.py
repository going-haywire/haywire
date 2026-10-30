"""Path Exists? — branch on whether a path is there."""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.volumes import VolumePath, resolve


@node(
    label="Path Exists?",
    description="Continues on Exists or Missing, depending on whether a file or folder is there",
    menu="core/control/branch",
    search_tags=["path", "exists", "missing", "file", "folder", "skip", "resume", "branch"],
    node_type=NodeType.CONTROL,
)
class PathExistsNode(BaseNode):
    """Continues on `Exists` or `Missing`, depending on whether a file or folder is there.

    Any file or folder at the path counts as there. A path that cannot be found on
    this machine at all, because its volume is not defined or the path leads outside
    its volume, is reported as an error.

    Resume a batch by skipping files whose result is already saved:

    ```
    For Each File → Path Exists? (Path = Output Path) → Missing → Save
    ```
    """

    def init(self) -> None:
        from haywire.barn.builtin.types import EXEC, PATH

        self.add(EXEC.as_inlet("exec", label="Execute"))
        self.add(PATH.as_inlet("path", label="Path"))
        self.add(EXEC.as_outlet("exists", label="Exists"))
        self.add(EXEC.as_outlet("missing", label="Missing"))

    def worker(self, context: ExecutionContext, path: VolumePath) -> str:
        return "exists" if resolve(path).exists() else "missing"
