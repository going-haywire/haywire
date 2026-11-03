"""Create Folder — make a folder, and any folders above it, inside a volume."""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.volumes import VolumePath, resolve
from haywire.core.volumes.keys import volume_name


@node(
    label="Create Folder",
    description="Creates a folder inside a volume, including any folders above it",
    menu="core/paths",
    search_tags=["folder", "create", "mkdir", "directory", "output", "batch"],
    node_type=NodeType.CONTROL,
)
class CreateFolderNode(BaseNode):
    """Creates a folder inside a volume, including any folders above it.

    A folder that already exists is left as it is. `Folder` passes `Path` on, so
    the next node can use it.

    The volume's own location must already exist: a volume whose drive is not
    mounted is reported as an error and nothing is created. An error is also
    reported when the path leads outside its volume or a file is in the way.

    Save Image does not create folders; create the output folder first:

    ```
    Output Path.Parent → Create Folder → Save Image
    ```
    """

    def init(self) -> None:
        from haywire.barn.builtin.types import EXEC, FOLDER_PATH

        self.add(EXEC.as_inlet("exec", label="Execute", description="Creates the folder"))
        self.add(FOLDER_PATH.as_inlet("path", label="Path", description="Folder to create"))
        self.add(EXEC.as_outlet("next", label="Next", description="Runs once the folder exists"))
        self.add(FOLDER_PATH.as_outlet("folder", label="Folder", description="The folder, now created"))

    def worker(self, context: ExecutionContext, path: VolumePath) -> str:
        target = resolve(path)
        root = resolve(VolumePath(path.volume, ""))
        if not root.exists():
            raise FileNotFoundError(f"volume '{volume_name(path.volume)}' location {root} does not exist")
        target.mkdir(parents=True, exist_ok=True)
        self.out("folder", path)
        return "next"
