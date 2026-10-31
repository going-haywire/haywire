"""Layout adapters: any image to a gray, RGB or RGBA image."""

from typing_extensions import override

from haywire.core.adapter.base import BaseAdapter, adapter

from haybale_image.types.image import IMAGE, IMAGE_GRAY, IMAGE_RGB, IMAGE_RGBA
from haybale_image.value import ImageValue, Layout, convert_layout


def _sample(layout: Layout) -> ImageValue:
    import numpy as np

    channels = {Layout.GRAY: (), Layout.RGB: (3,), Layout.RGBA: (4,)}[layout]
    return ImageValue.from_array(np.zeros((2, 2, *channels), dtype=np.uint8))


@adapter(description="Convert an image to gray", converts_from=IMAGE, converts_to=IMAGE_GRAY)
class ImageToGrayAdapter(BaseAdapter):
    """Convert an image to one gray channel (luma of the colour channels)."""

    @override
    def convert(self, value: ImageValue) -> ImageValue:
        return convert_layout(value, Layout.GRAY)

    def get_test_value(self) -> ImageValue:
        return _sample(Layout.RGB)


@adapter(description="Convert an image to RGB", converts_from=IMAGE, converts_to=IMAGE_RGB)
class ImageToRgbAdapter(BaseAdapter):
    """Convert an image to three colour channels, dropping transparency or repeating gray."""

    @override
    def convert(self, value: ImageValue) -> ImageValue:
        return convert_layout(value, Layout.RGB)

    def get_test_value(self) -> ImageValue:
        return _sample(Layout.GRAY)


@adapter(description="Convert an image to RGBA", converts_from=IMAGE, converts_to=IMAGE_RGBA)
class ImageToRgbaAdapter(BaseAdapter):
    """Convert an image to colour plus transparency, fully opaque when it had none."""

    @override
    def convert(self, value: ImageValue) -> ImageValue:
        return convert_layout(value, Layout.RGBA)

    def get_test_value(self) -> ImageValue:
        return _sample(Layout.RGB)
