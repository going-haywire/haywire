"""Path Exists? — branch on whether a path is there."""

from haywire.api import (
    EXEC,
    PATH,
    BaseNode,
    ExecutionContext,
    NodeType,
    VolumePath,
    node,
    resolve_volume_path,
)


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
        self.add(EXEC.as_inlet("exec", label="Execute", description="Checks the path"))
        self.add(PATH.as_inlet("path", label="Path", description="File or folder to look for"))
        self.add(EXEC.as_outlet("exists", label="Exists", description="Runs when it is there"))
        self.add(EXEC.as_outlet("missing", label="Missing", description="Runs when it is not there"))

    def worker(self, context: ExecutionContext, path: VolumePath) -> str:
        return "exists" if resolve_volume_path(path).exists() else "missing"
