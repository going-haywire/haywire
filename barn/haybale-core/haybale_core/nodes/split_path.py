"""Split Path — take a file path apart into its volume, folder, name and extension."""

from pathlib import PurePosixPath

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.volumes import VolumePath


@node(
    label="Split Path",
    description="Splits a path into its volume, folder, name and extension",
    menu="core/paths",
    search_tags=["path", "split", "folder", "parent", "name", "stem", "extension", "volume"],
    node_type=NodeType.DATA,
)
class SplitPathNode(BaseNode):
    """Splits a path into its volume, folder, name and extension.

    Nothing is read from disk. For `a/b/x.png` in a volume:

    - `Volume`: the volume's root folder.
    - `Folder`: `a/b`, empty when the file is directly in the volume.
    - `Name`: `x`.
    - `Extension`: `.png`, including the dot; empty when there is none.
    - `Parent`: the folder `a/b` as a folder path.

    `Folder`, `Name` and `Extension` fit Output Path's `Subfolder`, `Name` and
    `Extension`, so a path can be rebuilt with a changed suffix or in another folder:

    ```
    Split Path.Folder    → Output Path.Subfolder
    Split Path.Name      → Output Path.Name        Suffix = "_x4"
    Split Path.Extension → Output Path.Extension
    ```
    """

    def init(self) -> None:
        from haywire.barn.builtin.types import FOLDER_PATH, PATH, STRING

        self.add(PATH.as_inlet("path", label="Path"))
        self.add(FOLDER_PATH.as_outlet("volume", label="Volume"))
        self.add(STRING.as_outlet("folder", label="Folder"))
        self.add(STRING.as_outlet("stem", label="Name"))
        self.add(STRING.as_outlet("extension", label="Extension"))
        self.add(FOLDER_PATH.as_outlet("parent", label="Parent"))

    def worker(self, context: ExecutionContext, path: VolumePath) -> None:
        relative = PurePosixPath(path.relative)
        parent = str(relative.parent)
        folder = "" if parent == "." else parent
        self.out("volume", VolumePath(path.volume, ""))
        self.out("folder", folder)
        self.out("stem", relative.stem)
        self.out("extension", relative.suffix)
        self.out("parent", VolumePath(path.volume, folder))
        return None
