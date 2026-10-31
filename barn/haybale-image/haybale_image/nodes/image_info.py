"""Image Info — size, channel layout and bit depth of an image."""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node

from haybale_image.value.image_value import ImageValue


@node(
    label="Image Info",
    description="Reports the width, height, channel layout and bit depth of an image",
    menu="image",
    search_tags=["image", "info", "size", "width", "height", "layout", "depth", "channels"],
    node_type=NodeType.DATA,
)
class ImageInfoNode(BaseNode):
    """Reports the width, height, channel layout and bit depth of an `Image`.

    - `Width`, `Height`: size in pixels.
    - `Layout`: `gray`, `rgb` or `rgba`.
    - `Depth`: bits per channel of the file the image was read from (8, 16 or 32).
    """

    def init(self) -> None:
        from haywire.barn.builtin.types import INT, STRING

        from haybale_image.types.image import IMAGE

        self.add(IMAGE.as_inlet("image", label="Image"))
        self.add(INT.as_outlet("width", label="Width"))
        self.add(INT.as_outlet("height", label="Height"))
        self.add(STRING.as_outlet("layout", label="Layout"))
        self.add(INT.as_outlet("depth", label="Depth"))

    def worker(self, context: ExecutionContext, image: ImageValue) -> None:
        self.out("width", image.width)
        self.out("height", image.height)
        self.out("layout", str(image.layout))
        self.out("depth", image.source_depth)
        return None
