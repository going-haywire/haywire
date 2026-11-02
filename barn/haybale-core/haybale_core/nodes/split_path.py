"""Split Path — take a file path apart into its volume, base, subfolder, stem and extension."""

from pathlib import PurePosixPath

from haywire.barn.builtin.types import FOLDER_PATH, STRING
from haywire.barn.builtin.widgets import SimpleLabelWidget
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.settings import NodeSettings, Promotable, UiState, bag, setting
from haywire.core.types.enums import PortType
from haywire.core.volumes import VolumePath, VolumeError, resolve

_NO_PATH = {"value": {"volume": "", "relative": ""}}

#: What a text part shows while it is not promoted.
NOT_EVALUATED = "<promote to evaluate>"

#: What a promoted text part shows until the node runs.
READY = "<ready>"

_PATH_PARTS = ("volume", "base", "parent")


def _path_part(label: str, description: str, order: int) -> "setting":
    return setting[FOLDER_PATH](
        _NO_PATH,
        label=label,
        description=description,
        order=order,
        widget=SimpleLabelWidget.config(),
        ui_state=UiState.HIDE_WIDGET,
        promotable=Promotable.OUTLET,
    )


def _text_part(label: str, description: str, order: int, *, outlet: bool = False) -> "setting":
    return setting[STRING](
        READY if outlet else NOT_EVALUATED,
        label=label,
        description=description,
        order=order,
        widget=SimpleLabelWidget.config(),
        promotable=Promotable.OUTLET | Promotable.CONFIG,
        promote_default=PortType.OUTLET if outlet else None,
    )


class SplitPathParts(NodeSettings):
    """The parts of the incoming path; promote the ones you need to outlets or card rows."""

    volume = _path_part("Volume", "The volume's root folder: <volume>", 0)
    base = _path_part("Base", "The folder the path was listed from: <volume>/<base>", 1)
    parent = _path_part("Parent", "The folder the file is in: <volume>/<base>/<sub>", 2)
    base_folder = _text_part("Basefolder", "<base>, inside the volume", 3)
    subfolder = _text_part("Subfolder", "<sub>, inside the base", 4)
    folder = _text_part("Folder", "<base>/<sub>, inside the volume", 5, outlet=True)
    stem = _text_part("Stem", "<stem>, the file name without extension", 6, outlet=True)
    extension = _text_part("Extension", "<ext>, with the dot", 7, outlet=True)
    name = _text_part("Name", "<stem><ext>, the file name", 8)
    base_on_disk = _text_part("Base on Disk", "Where <volume>/<base> is on this machine", 9)
    parent_on_disk = _text_part("Parent on Disk", "Where <volume>/<base>/<sub> is on this machine", 10)
    path_on_disk = _text_part("Path on Disk", "Where the file is on this machine", 11)


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

    Every part is a setting. Promote the ones you need to an outlet, or to a row
    on the card to look at them while the graph runs. Only promoted parts are
    worked out; the others show `<promote to evaluate>`. A promoted part shows
    `<ready>` until the node runs. The parts that are paths can only become
    outlets, and show no value in the properties.

    | Part | Kind | Holds |
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

    `Folder`, `Stem` and `Extension` are outlets on a new node. The `on Disk` parts
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

    parts = bag(SplitPathParts)

    def init(self) -> None:
        from haywire.barn.builtin.types import PATH

        self.add(PATH.as_inlet("path", label="Path"))

    def post_init(self) -> None:
        self.parts._subscribe_promotion(self._on_promotion)

    def _on_promotion(self, name: str, direction: PortType | None) -> None:
        """Fill a newly promoted part on the next run; a demoted one shows the placeholder again."""
        if direction is not None:
            self.run_again()
        if name not in _PATH_PARTS:
            setattr(self.parts, name, NOT_EVALUATED if direction is None else READY)

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
        parts = self.parts
        for part, value in compute.items():
            if parts._is_promoted(part):
                setattr(parts, part, value())
        return None


def _folder_of(relative: PurePosixPath) -> str:
    parent = str(relative.parent)
    return "" if parent == "." else parent


def _on_disk(path: VolumePath) -> str:
    try:
        return str(resolve(path))
    except VolumeError:
        return ""
