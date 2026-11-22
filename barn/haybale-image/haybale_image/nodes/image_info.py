"""Image Info — size, channel layout and bit depth of an image."""

from __future__ import annotations

from haybale_image.value.image_value import ImageValue
from haywire.api import INT, STRING, BaseNode, ExecutionContext, NodeType, node


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
        from haybale_image.types.image import IMAGE

        self.add(IMAGE.as_inlet("image", label="Image", description="Image to describe"))
        self.add(INT.as_outlet("width", label="Width", description="Width in pixels"))
        self.add(INT.as_outlet("height", label="Height", description="Height in pixels"))
        self.add(STRING.as_outlet("layout", label="Layout", description="Channels: gray, rgb or rgba"))
        self.add(
            INT.as_outlet(
                "depth", label="Depth", description="Bits per channel of the source file, such as 8 or 16"
            )
        )

    def worker(self, context: ExecutionContext, image: ImageValue) -> None:
        self.out("width", image.width)
        self.out("height", image.height)
        self.out("layout", str(image.layout))
        self.out("depth", image.source_depth)
        return None
