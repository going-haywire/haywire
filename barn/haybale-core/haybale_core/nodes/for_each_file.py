"""For Each File — loop over the files of a folder."""

from pathlib import PurePosixPath
from typing import Optional

from haybale_core.file_listing import folder_root, list_files
from haywire.barn.builtin.progress import ProgressSettings, ProgressSpan, progress_field
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.settings import bag
from haywire.core.volumes import VolumePath

ON_ERROR = ("continue", "stop")


class ForEachProgress(ProgressSettings):
    """How far the loop is through the folder's files."""

    main = progress_field("Progress")


@node(
    label="For Each File",
    description="Runs the loop body once for each file in a folder that matches the pattern",
    menu="core/control/loops",
    search_tags=["loop", "for", "each", "file", "folder", "batch", "iterate", "glob"],
    node_type=NodeType.LOOPBACK,
)
class ForEachFileNode(BaseNode):
    """Runs the loop body once for each file in a folder that matches the pattern.

    - `Pattern`: one or more file-name patterns separated by `;`, such as
      `*.png;*.jpg`. Upper and lower case are not told apart; empty matches every file.
    - `Subfolders`: also go through every subfolder.
    - `Limit`: only the first files, in name order; 0 takes all of them.
    - `On Error`: when an iteration fails and the graph's *On Exception* setting is
      `branch`, `continue` goes on with the next file and `stop` ends the loop through
      `Stopped`. With `frame` or `run` the loop ends at the first failure, without
      `Completed` or `Stopped`.

    Files and folders whose names start with `.` are skipped, folders reached
    through a link are not entered, and a linked file pointing outside the folder
    is skipped. The list of files is taken when the loop starts.

    For each file the loop sets `Path`, `Subfolder` (its folder relative to `Folder`,
    empty at the top), `Stem` (its name without extension), `Extension` (such as
    `.png`), `Index` (from 0) and `Total`. `Path` remembers `Folder` as its base, so
    Split Path gives the same `Subfolder`. When the loop ends, `Failed` lists the
    files whose iteration failed. `Completed` runs when every file was gone through;
    `Stopped` runs when `Break` (wired from the loop body) or `On Error` = `stop`
    ended the loop early.

    Resume a batch by skipping files whose result is already saved:

    ```text
    For Each File → Path Exists? (Path = Output Path) → Missing → Save
    ```

    A folder that cannot be listed (its volume is not defined, it does not exist,
    or it is a file) is reported as an error.
    """

    progress = bag(ForEachProgress)

    def init(self) -> None:
        from haybale_core.types import ArrayType
        from haywire.barn.builtin.types import BOOL, EXEC, FILE_PATH, FOLDER_PATH, INT, STRING
        from haywire.barn.builtin.widgets import NumberWidget, SelectWidget

        self.add(EXEC.as_inlet("execute", label="Execute"))
        self.add(EXEC.as_inlet("break_loop", label="Break", description="Signal to stop loop"))
        self.add(FOLDER_PATH.as_inlet("folder", label="Folder"))
        self.add(STRING.as_inlet("pattern", label="Pattern", default="*"))
        self.add(BOOL.as_inlet("recursive", label="Subfolders", default=False))
        self.add(INT.as_inlet("limit", label="Limit", default=0, widget=NumberWidget.config()))
        self.add(
            STRING.as_inlet(
                "on_error",
                label="On Error",
                default="continue",
                widget=SelectWidget.config(properties={"options": list(ON_ERROR)}),
            )
        )

        self.add(EXEC.as_outlet("loop_body", label="Loop Body", needs_loopback=True))
        self.add(FILE_PATH.as_outlet("path", label="Path"))
        self.add(STRING.as_outlet("subdir", label="Subfolder"))
        self.add(STRING.as_outlet("stem", label="Stem"))
        self.add(STRING.as_outlet("extension", label="Extension"))
        self.add(INT.as_outlet("index", label="Index", default=0))
        self.add(INT.as_outlet("total", label="Total", default=0))
        self.add(ArrayType[FILE_PATH].as_outlet("failed", label="Failed"))

        # Completed outlet - executes when loop finishes
        self.add(EXEC.as_outlet("completed", label="Completed", description="Signal the loop completed"))

        # Stopped outlet - executes when Break ended the loop
        self.add(
            EXEC.as_outlet(
                "stopped",
                label="Stopped",
                description="Signal if the loop was interruted and was never completed",
            )
        )

    def post_init(self) -> None:
        self._folder: Optional[VolumePath] = None
        self._files: list[PurePosixPath] = []
        self._index = 0
        self._failed: list[VolumePath] = []
        self._failures_seen = 0
        self._span: Optional[ProgressSpan] = None

    def worker(self, context: ExecutionContext) -> Optional[str]:
        if context.control_pin == "execute":
            self._close()
            self._begin()
            return self._emit(context)
        if self._span is None:
            return None  # no loop open: a stray loopback return
        if len(context.failures) > self._failures_seen:
            self._failed.append(self._path(self._files[self._index]))
            if self.value("on_error") == "stop":
                return self._finish("stopped")
        if context.control_pin == "break_loop":
            return self._finish("stopped")
        self._index += 1
        return self._emit(context)

    def on_frame_end(self, context: ExecutionContext) -> None:
        """Close a loop the frame left open, as after a bail or a stop."""
        self._close()

    def _begin(self) -> None:
        folder: VolumePath = self.value("folder")
        root = folder_root(folder)
        files = list_files(root, self.value("pattern") or "", recursive=bool(self.value("recursive")))
        limit = int(self.value("limit") or 0)
        self._folder = folder
        self._files = files[:limit] if limit > 0 else files
        self._index = 0
        self._failed = []
        self._span = self.progress.busy("main", f"{len(self._files)} files")
        self._span.__enter__()

    def _emit(self, context: ExecutionContext) -> str:
        if self._index >= len(self._files):
            return self._finish("completed")
        relative = self._files[self._index]
        total = len(self._files)
        parent = str(relative.parent)
        self.out("path", self._path(relative))
        self.out("subdir", "" if parent == "." else parent)
        self.out("stem", relative.stem)
        self.out("extension", relative.suffix)
        self.out("index", self._index)
        self.out("total", total)
        assert self._span is not None
        self._span.step(self._index / total)
        self._failures_seen = len(context.failures)
        return "loop_body"

    def _finish(self, outlet: str) -> str:
        self.out("failed", list(self._failed))
        self._close()
        return outlet

    def _close(self) -> None:
        span, self._span = self._span, None
        if span is not None:
            span.__exit__(None, None, None)
        self._files = []
        self._folder = None

    def _path(self, relative: PurePosixPath) -> VolumePath:
        assert self._folder is not None
        base = [part for part in self._folder.relative.split("/") if part]
        return VolumePath(self._folder.volume, "/".join(base + list(relative.parts)), base="/".join(base))
