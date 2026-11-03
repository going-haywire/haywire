"""List Files — the files of a folder, as a list of paths."""

from haybale_core.file_listing import PATTERN_DESCRIPTION, folder_root, list_files
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.volumes import VolumePath


@node(
    label="List Files",
    description="Lists the files in a folder that match the pattern, each time it runs",
    menu="core/paths",
    search_tags=["list", "files", "folder", "glob", "batch", "array", "directory"],
    node_type=NodeType.CONTROL,
)
class ListFilesNode(BaseNode):
    """Lists the files in a folder that match the pattern, each time it runs.

    - `Pattern`: one or more file-name patterns separated by `;`, such as
      `*.png;*.jpg`. Upper and lower case are not told apart; empty matches every file.
    - `Subfolders`: also list the files of every subfolder.
    - `Limit`: only the first files, in name order; 0 takes all of them.

    `Files` holds the paths in name order and `Total` how many there are. Each path
    remembers `Folder` as its base, so Split Path can give its `Subfolder` below it.
    Files and folders whose names start with `.` are skipped, folders reached
    through a link are not entered, and a linked file pointing outside the folder
    is skipped.

    The folder is read again every time `Execute` runs, so files added meanwhile
    are found. Go through the list with Loop Array or Step Array:

    ```text
    List Files → Loop Array (Array = Files) → Load Image → Save Image
    ```

    A folder that cannot be listed (its volume is not defined, it does not exist,
    or it is a file) is reported as an error.
    """

    def init(self) -> None:
        from haybale_core.types import ArrayType
        from haywire.barn.builtin.types import BOOL, EXEC, FILE_PATH, FOLDER_PATH, INT, STRING
        from haywire.barn.builtin.widgets import NumberWidget

        self.add(EXEC.as_inlet("execute", label="Execute", description="Lists the folder's files again"))
        self.add(FOLDER_PATH.as_inlet("folder", label="Folder", description="Folder to list"))
        self.add(STRING.as_inlet("pattern", label="Pattern", default="*", description=PATTERN_DESCRIPTION))
        self.add(
            BOOL.as_inlet(
                "recursive",
                label="Subfolders",
                default=False,
                description="Also list the files of every subfolder",
            )
        )
        self.add(
            INT.as_inlet(
                "limit",
                label="Limit",
                default=0,
                widget=NumberWidget.config(),
                description="Only the first files, in name order; 0 takes all",
            )
        )

        self.add(EXEC.as_outlet("next", label="Next", description="Runs after the files are listed"))
        self.add(
            ArrayType[FILE_PATH].as_outlet(
                "files", label="Files", description="The matching files, in name order"
            )
        )
        self.add(INT.as_outlet("total", label="Total", default=0, description="Number of files found"))

    def worker(self, context: ExecutionContext) -> str:
        folder: VolumePath = self.value("folder")
        relatives = list_files(
            folder_root(folder), self.value("pattern") or "", recursive=bool(self.value("recursive"))
        )
        limit = int(self.value("limit") or 0)
        if limit > 0:
            relatives = relatives[:limit]
        base = [part for part in folder.relative.split("/") if part]
        files = [
            VolumePath(folder.volume, "/".join(base + list(r.parts)), base="/".join(base)) for r in relatives
        ]
        self.out("files", files)
        self.out("total", len(files))
        return "next"
