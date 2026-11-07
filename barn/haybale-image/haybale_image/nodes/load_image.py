"""Load Image — read an image file into an image."""

from pathlib import Path

from haywire.barn.builtin.field_text import fields_from_text
from haywire.barn.builtin.progress import ProgressSettings, progress_field
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.node.node_warning import NodeWarning
from haywire.core.settings import bag
from haywire.core.volumes import VolumePath, resolve

from haybale_image.io.codecs import read_image
from haybale_image.io.png_text import FIELDS_KEYWORD, read_text_chunk
from haybale_image.value import ImageValue

_FIELD_WARNING = "saved_fields"


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

    Fields that Save Image stored in a PNG come back on the image. A field whose type
    is not installed here is left out, with a warning on the node naming it.

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

        self.add(FILE_PATH.as_inlet("path", label="Path", description="Image file to read"))
        self.add(IMAGE.as_outlet("image", label="Image", description="The decoded image"))

    def worker(self, context: ExecutionContext, path: VolumePath) -> None:
        target = resolve(path)
        with self.progress.busy("main", "decoding"):
            image = self._with_saved_fields(read_image(target), target)
        self.out("image", image)
        return None

    def _with_saved_fields(self, image: ImageValue, target: Path) -> ImageValue:
        """Return ``image`` with the fields stored in the file at ``target``, warning about any left out."""
        with target.open("rb") as stream:
            text = read_text_chunk(stream, FIELDS_KEYWORD)
        fields, problems = ({}, []) if text is None else fields_from_text(text)
        warnings = [NodeWarning(problem, None, kind=_FIELD_WARNING) for problem in problems]
        self.wrapper.replace_warnings(_FIELD_WARNING, warnings)
        return image.with_fields(fields) if fields else image
