"""Output Path — compose a file path inside a folder's volume."""

from pathlib import PurePosixPath, PureWindowsPath

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.volumes import VolumePath

_FORBIDDEN = ("/", "\\", "\0")


@node(
    label="Output Path",
    description="Builds a file path from a folder, a subfolder, a name and an extension",
    menu="core/paths",
    search_tags=["path", "file", "output", "save", "folder", "name", "extension", "batch"],
    node_type=NodeType.DATA,
)
class OutputPathNode(BaseNode):
    """Builds a file path from a folder, a subfolder, a name and an extension.

    The result is `Folder / Subfolder / Name + Suffix + Extension`, in the same
    volume as `Folder`. Nothing is created on disk.

    - `Subfolder`: a relative path such as `a/b`; empty puts the file directly in `Folder`.
    - `Extension`: `png` and `.png` both work; empty gives a name without extension.

    Fed from For Each File's `Subfolder`, `Stem` and `Extension`, it mirrors the
    input folder's structure under another folder:

    ```
    For Each File.Subfolder → Subfolder
    For Each File.Stem      → Name        Suffix = "_x4"
    For Each File.Extension → Extension
    ```

    The node reports an error naming the part when a name is empty or contains
    `/` or `\\`, or when the subfolder is absolute or contains `..`.
    """

    def init(self) -> None:
        from haywire.barn.builtin.types import FILE_PATH, FOLDER_PATH, STRING

        self.add(FOLDER_PATH.as_inlet("folder", label="Folder"))
        self.add(STRING.as_inlet("subdir", label="Subfolder", default=""))
        self.add(STRING.as_inlet("stem", label="Name", default=""))
        self.add(STRING.as_inlet("suffix", label="Suffix", default=""))
        self.add(STRING.as_inlet("extension", label="Extension", default=""))
        self.add(FILE_PATH.as_outlet("path", label="Path"))

    def worker(
        self,
        context: ExecutionContext,
        folder: VolumePath,
        subdir: str = "",
        stem: str = "",
        suffix: str = "",
        extension: str = "",
    ) -> None:
        self.out("path", compose_output_path(folder, subdir, stem, suffix, extension))
        return None


def compose_output_path(
    folder: VolumePath, subdir: str, stem: str, suffix: str, extension: str
) -> VolumePath:
    """Return ``folder / subdir / stem + suffix + extension`` in ``folder``'s volume.

    Raises:
        ValueError: ``stem`` is empty; ``stem``, ``suffix`` or ``extension`` contains ``/``, ``\\``
            or a NUL byte; ``subdir`` is absolute or contains a ``..`` segment.
    """
    if not stem:
        raise ValueError("stem is empty")
    for part, value in (("stem", stem), ("suffix", suffix), ("extension", extension)):
        for char in _FORBIDDEN:
            if char in value:
                raise ValueError(f"{part} contains {char!r}")
    if PurePosixPath(subdir).is_absolute() or PureWindowsPath(subdir).drive:
        raise ValueError("subdir is absolute")
    if "\0" in subdir:
        raise ValueError("subdir contains '\\x00'")
    subdir_parts = [part for part in subdir.replace("\\", "/").split("/") if part]
    if ".." in subdir_parts:
        raise ValueError("subdir contains '..'")
    ext = extension.lstrip(".")
    name = stem + suffix + (f".{ext}" if ext else "")
    parts = [part for part in folder.relative.split("/") if part] + subdir_parts + [name]
    return VolumePath(folder.volume, "/".join(parts))
