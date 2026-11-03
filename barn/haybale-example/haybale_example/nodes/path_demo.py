"""PathDemoNode — one inlet per path type, each resolved to an absolute path on this machine.

Exists to show the path picker on a real card: a plain `PATH`, a `FILE_PATH`, a
`FILE_PATH` limited to images, a `FOLDER_PATH`, and a `FILE_PATH` in save mode.
"""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.volumes import VolumeError, VolumePath, resolve


@node(
    label="Path Demo",
    description="Picks files and folders inside volumes and shows where they are on this machine.",
    search_tags=["path", "file", "folder", "volume", "picker", "example"],
    menu="examples/paths",
    node_type=NodeType.DATA,
)
class PathDemoNode(BaseNode):
    """Picks files and folders inside volumes and shows where they are on this machine.

    Each inlet stores a volume and a path inside it, never an absolute path, so
    the graph works on any machine that has the same volumes. Each `… resolved`
    outlet gives the absolute path on this machine, or nothing when the path
    cannot be resolved; `problems` says why, one line per inlet.

    - `Path`: any file or folder.
    - `File`: an existing file.
    - `Image`: a file, with the browser showing only PNG and JPEG files.
    - `Folder`: a folder.
    - `Save to`: a folder plus a file name typed in the browser.

    Volumes are added and moved in the Volumes editor.
    """

    PATH_PORTS = ("path", "file", "image", "folder", "save_to")

    def init(self):
        from haywire.barn.builtin.types import FILE_PATH, FOLDER_PATH, PATH, STRING
        from haywire.barn.builtin.widgets import PathWidget

        self.add(PATH.as_inlet(id="path", label="Path", description="A file or a folder"))
        self.add(FILE_PATH.as_inlet(id="file", label="File", description="An existing file"))
        self.add(
            FILE_PATH.as_inlet(
                id="image",
                label="Image",
                description="A PNG or JPEG file",
                widget=PathWidget.config(properties={"extensions": [".png", ".jpg", ".jpeg"]}),
            )
        )
        self.add(FOLDER_PATH.as_inlet(id="folder", label="Folder", description="A folder"))
        self.add(
            FILE_PATH.as_inlet(
                id="save_to",
                label="Save to",
                description="A file to save to; it need not exist yet",
                widget=PathWidget.config(properties={"mode": "save"}),
            )
        )

        for port_id in self.PATH_PORTS:
            label = self.ports[port_id].label
            self.add(
                STRING.as_outlet(
                    id=f"{port_id}_resolved",
                    label=f"{label} resolved",
                    description=f"Where {label} is on this machine",
                )
            )
        self.add(
            STRING.as_outlet(
                id="problems",
                label="Problems",
                description="Why an inlet could not be resolved, one line each",
            )
        )

    def worker(
        self,
        context: ExecutionContext,
        path: VolumePath,
        file: VolumePath,
        image: VolumePath,
        folder: VolumePath,
        save_to: VolumePath,
    ) -> str | None:
        problems: list[str] = []
        for port_id, value in zip(self.PATH_PORTS, (path, file, image, folder, save_to), strict=True):
            try:
                resolved = str(resolve(value))
            except VolumeError as exc:
                resolved = ""
                problems.append(f"{port_id}: {exc}")
            self.out(f"{port_id}_resolved", resolved)
        self.out("problems", "\n".join(problems))
        return None
