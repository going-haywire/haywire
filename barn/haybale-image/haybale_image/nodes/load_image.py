"""Load Image — read an image file into an image."""

from haywire.barn.builtin.progress import ProgressSettings, progress_field
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.settings import bag
from haywire.core.volumes import VolumePath, resolve

from haybale_image.io.codecs import read_image


class LoadProgress(ProgressSettings):
    """Reading and decoding the file."""

    main = progress_field("Loading")


@node(
    label="Load Image",
    description="Reads an image file from a volume",
    menu="image/io",
    search_tags=["image", "load", "open", "read", "file", "png", "jpg", "tiff", "import"],
    node_type=NodeType.DATA,
)
class LoadImageNode(BaseNode):
    """Reads an image file from a volume into an `Image`.

    Gray files stay gray, files with transparency become RGBA and everything else
    is RGB. The camera's rotation (EXIF orientation) is applied to the pixels on
    load, because OpenCV's reader ignores it.
    16-bit and float files are read at full precision; see Image Info's `Depth`.

    The Loading bar shows while the file is read and decoded.

    The node reports an error naming the file when it is missing or is not an
    image, and when `Path` leads to a volume that is not defined on this machine.

    ```
    For Each File → Load Image → Image Info
    ```
    """

    progress = bag(LoadProgress)

    def init(self) -> None:
        from haywire.barn.builtin.types import FILE_PATH

        from haybale_image.types.image import IMAGE

        self.add(FILE_PATH.as_inlet("path", label="Path"))
        self.add(IMAGE.as_outlet("image", label="Image"))

    def worker(self, context: ExecutionContext, path: VolumePath) -> None:
        target = resolve(path)
        with self.progress.busy("main", "decoding"):
            image = read_image(target)
        self.out("image", image)
        return None
