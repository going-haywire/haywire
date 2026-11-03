"""Split Path — take a file path apart into its volume, base, subfolder, stem and extension."""

from pathlib import PurePosixPath
from typing import Any

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.volumes import VolumePath, VolumeError, resolve

#: The outlets a new node shows; the rest start hidden.
SHOWN = ("folder", "stem", "extension")


@node(
    label="Split Path",
    description="Splits a path into its volume, base, subfolder, stem and extension",
    menu="core/paths",
    search_tags=["path", "split", "folder", "parent", "name", "stem", "extension", "volume", "base"],
    node_type=NodeType.DATA,
)
class SplitPathNode(BaseNode):
    """Splits a path into its volume, base, subfolder, stem and extension.

    A path is read as

    ```text
    <volume>/<base>/<sub>/<stem><ext>
    ```

    `<base>` is the folder a path was listed from: List Files and For Each File
    give every path their `Folder` as its base. `<sub>` is the rest of the folder
    below it, empty unless `Subfolders` was on. A path typed in by hand has no
    base, so `<sub>` is its whole folder.

    | Outlet | Kind | Holds |
    |---|---|---|
    | `Volume` | path | `<volume>` |
    | `Base` | path | `<volume>/<base>` |
    | `Parent` | path | `<volume>/<base>/<sub>` |
    | `Basefolder` | text | `<base>` |
    | `Subfolder` | text | `<sub>` |
    | `Folder` | text | `<base>/<sub>` |
    | `Stem` | text | `<stem>` |
    | `Extension` | text | `<ext>`, such as `.png`; empty when there is none |
    | `Name` | text | `<stem><ext>` |
    | `Base on Disk` | text | where `<volume>/<base>` is on this machine |
    | `Parent on Disk` | text | where `<volume>/<base>/<sub>` is on this machine |
    | `Path on Disk` | text | where the file is on this machine |

    A new node shows `Folder`, `Stem` and `Extension`; show the others from the
    Ports panel. Only connected outlets are worked out; connecting one makes the
    node run again. The `on Disk` outlets
    differ between machines, and are empty when the volume is not defined here.
    Nothing is read from disk.

    Rebuild a listed file in another folder, keeping its subfolders:

    ```text
    For Each File.Path → Split Path
    Split Path.Subfolder → Output Path.Subfolder
    Split Path.Stem      → Output Path.Stem        Suffix = "_x4"
    Split Path.Extension → Output Path.Extension
    ```
    """

    def init(self) -> None:
        from haywire.barn.builtin.types import FOLDER_PATH, PATH, STRING

        self.add(PATH.as_inlet("path", label="Path", description="Path to split"))
        outlets = (
            (FOLDER_PATH, "volume", "Volume", "The volume's root folder: <volume>"),
            (FOLDER_PATH, "base", "Base", "The folder the path was listed from: <volume>/<base>"),
            (FOLDER_PATH, "parent", "Parent", "The folder the file is in: <volume>/<base>/<sub>"),
            (STRING, "base_folder", "Basefolder", "<base>, inside the volume"),
            (STRING, "subfolder", "Subfolder", "<sub>, inside the base"),
            (STRING, "folder", "Folder", "<base>/<sub>, inside the volume"),
            (STRING, "stem", "Stem", "<stem>, the file name without extension"),
            (STRING, "extension", "Extension", "<ext>, with the dot"),
            (STRING, "name", "Name", "<stem><ext>, the file name"),
            (STRING, "base_on_disk", "Base on Disk", "Where <volume>/<base> is on this machine"),
            (STRING, "parent_on_disk", "Parent on Disk", "Where <volume>/<base>/<sub> is on this machine"),
            (STRING, "path_on_disk", "Path on Disk", "Where the file is on this machine"),
        )
        for type_cls, port_id, label, description in outlets:
            self.add(
                type_cls.as_outlet(
                    port_id,
                    label=label,
                    description=description,
                    hidden=port_id not in SHOWN,
                    on_connect="_on_outlet_connected",
                )
            )

    def _on_outlet_connected(self, port: Any, edge: Any) -> None:
        """An outlet connected for the first time has no value yet: work it out on the next run."""
        self.run_again()

    def worker(self, context: ExecutionContext, path: VolumePath) -> None:
        relative = PurePosixPath(path.relative)
        folder = _folder_of(relative)
        subpath = path.subpath
        base = path.relative[: len(path.relative) - len(subpath)].rstrip("/")
        compute = {
            "volume": lambda: VolumePath(path.volume, ""),
            "base": lambda: VolumePath(path.volume, base),
            "parent": lambda: VolumePath(path.volume, folder),
            "base_folder": lambda: base,
            "subfolder": lambda: _folder_of(PurePosixPath(subpath)),
            "folder": lambda: folder,
            "stem": lambda: relative.stem,
            "extension": lambda: relative.suffix,
            "name": lambda: relative.name,
            "base_on_disk": lambda: _on_disk(VolumePath(path.volume, base)),
            "parent_on_disk": lambda: _on_disk(VolumePath(path.volume, folder)),
            "path_on_disk": lambda: _on_disk(path),
        }
        for port_id, value in compute.items():
            if self.ports[port_id].is_linked():
                self.out(port_id, value())
        return None


def _folder_of(relative: PurePosixPath) -> str:
    parent = str(relative.parent)
    return "" if parent == "." else parent


def _on_disk(path: VolumePath) -> str:
    try:
        return str(resolve(path))
    except VolumeError:
        return ""
