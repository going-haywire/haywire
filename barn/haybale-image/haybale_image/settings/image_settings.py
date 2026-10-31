"""ImageSettings — library-wide defaults for saving images."""

from haywire.barn.builtin.types import BOOL, CHOICES, INT
from haywire.core.settings import LibrarySettings, setting, settings

TIFF_COMPRESSIONS = ("none", "lzw", "deflate")


@settings(namespace="image", label="Image", description="Defaults for saving images")
class ImageSettings(LibrarySettings):
    """Defaults for saving images; each Save Image node can override them."""

    jpeg_quality = setting[INT](
        95,
        label="JPEG quality",
        description="Quality of saved JPEG files, from 0 (smallest) to 100 (best)",
        min=0,
        max=100,
    )
    png_compression = setting[INT](
        3,
        label="PNG compression",
        description="Compression of saved PNG files, from 0 (fastest) to 9 (smallest); never loses detail",
        min=0,
        max=9,
    )
    webp_quality = setting[INT](
        90,
        label="WebP quality",
        description="Quality of saved WebP files, from 0 (smallest) to 100 (best)",
        min=0,
        max=100,
    )
    webp_lossless = setting[BOOL](
        False,
        label="WebP lossless",
        description="Save WebP files without losing detail; WebP quality is then ignored",
    )
    tiff_compression = setting[CHOICES](
        "lzw",
        label="TIFF compression",
        description="Compression of saved TIFF files; none of them loses detail",
        widget_config={"options": list(TIFF_COMPRESSIONS)},
    )
    avif_quality = setting[INT](
        80,
        label="AVIF quality",
        description="Quality of saved AVIF files, from 0 (smallest) to 100 (best)",
        min=0,
        max=100,
    )
