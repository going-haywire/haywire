"""Save Image — write an image to a file in a volume."""

from pathlib import Path, PurePosixPath
from typing import Any, Optional

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.settings import NodeSettings, UiState, bag, shadow
from haywire.core.volumes import VolumePath, resolve

from haybale_image.io.codecs import EncodeOptions, encode_image
from haybale_image.io.formats import FORMAT_BY_EXTENSION, Format, format_for
from haybale_image.io.placement import IfExists, atomic_write, claim_target
from haybale_image.settings.image_settings import ImageSettings
from haybale_image.value import ImageValue

DEPTH_CHOICES = ("source", "8", "16", "32")

# Format → name of the node's settings group for it; formats without options have none.
_BAG_BY_FORMAT: dict[Format, str] = {
    Format.PNG: "png",
    Format.JPEG: "jpeg",
    Format.WEBP: "webp",
    Format.TIFF: "tiff",
    Format.AVIF: "avif",
}


class PngSaveSettings(NodeSettings):
    """PNG options of one Save Image node."""

    compression = shadow(ImageSettings.png_compression)


class JpegSaveSettings(NodeSettings):
    """JPEG options of one Save Image node."""

    quality = shadow(ImageSettings.jpeg_quality)


class WebpSaveSettings(NodeSettings):
    """WebP options of one Save Image node."""

    quality = shadow(ImageSettings.webp_quality)
    lossless = shadow(ImageSettings.webp_lossless)


class TiffSaveSettings(NodeSettings):
    """TIFF options of one Save Image node."""

    compression = shadow(ImageSettings.tiff_compression)


class AvifSaveSettings(NodeSettings):
    """AVIF options of one Save Image node."""

    quality = shadow(ImageSettings.avif_quality)


@node(
    label="Save Image",
    description="Writes an image to a file in a volume, in the format its extension names",
    menu="image/io",
    search_tags=["image", "save", "write", "export", "file", "png", "jpg", "tiff", "webp"],
    node_type=NodeType.CONTROL,
)
class SaveImageNode(BaseNode):
    """Writes `Image` to the file at `Path`, in the format its extension names.

    Known extensions: `.png`, `.jpg`/`.jpeg`, `.webp`, `.tif`/`.tiff`, `.bmp`, `.gif`,
    `.tga`, `.avif`. The file appears complete or not at all; a half-written file is
    never left behind.

    - `If Exists`: what to do when the file is already there. `overwrite` replaces
      it, `skip` keeps it and writes nothing, `unique-suffix` saves beside it as
      `name_1.png`, `name_2.png`, and so on.
    - `Depth`: `source` keeps the image's own bit depth; `8`, `16` and `32` (float)
      ask for that depth. A format that cannot store it gets the deepest it can
      (JPEG is always 8-bit, PNG at most 16-bit). 16-bit and float saves drop the
      image's ICC profile and EXIF block.

    `Saved` is the file that now holds the image: the suffixed name for
    `unique-suffix`, and the existing file for `skip`.

    The quality and compression settings default to the library's *Image* settings;
    change them here for this node only. Only the settings of the format `Path` names
    are shown.

    The folder must already exist; add Create Folder before Save Image to make it.
    An empty image, an unknown extension and a volume that is not defined on this
    machine are reported as errors.

    ```text
    For Each File → Load Image → … → Save Image (Path = Output Path)
    ```
    """

    png = bag(PngSaveSettings)
    jpeg = bag(JpegSaveSettings)
    webp = bag(WebpSaveSettings)
    tiff = bag(TiffSaveSettings)
    avif = bag(AvifSaveSettings)

    def init(self) -> None:
        from haywire.barn.builtin.types import EXEC, FILE_PATH, STRING
        from haywire.barn.builtin.widgets import PathWidget, SelectWidget

        from haybale_image.types.image import IMAGE

        self.add(EXEC.as_inlet("exec", label="Execute"))
        self.add(IMAGE.as_inlet("image", label="Image"))
        self.add(
            FILE_PATH.as_inlet(
                "path",
                label="Path",
                widget=PathWidget.config(
                    properties={"mode": "save", "extensions": list(FORMAT_BY_EXTENSION)}
                ),
                on_change="hb_on_path_changed",
            )
        )
        self.add(
            STRING.as_config(
                "if_exists",
                default=IfExists.OVERWRITE.value,
                label="If Exists",
                widget=SelectWidget.config(properties={"options": [m.value for m in IfExists]}),
            )
        )
        self.add(
            STRING.as_config(
                "depth",
                default="source",
                label="Depth",
                widget=SelectWidget.config(properties={"options": list(DEPTH_CHOICES)}),
            )
        )
        self.add(EXEC.as_outlet("next", label="Next"))
        self.add(FILE_PATH.as_outlet("saved", label="Saved"))

    def post_init(self) -> None:
        self._shown_format: Optional[Format] = None  # None: every format's settings are shown
        self.hb_refresh_format_bags(self.value("path"))

    def hb_on_path_changed(self, port: Any, value: Any) -> None:
        self.hb_refresh_format_bags(value)

    def hb_refresh_format_bags(self, path: Optional[VolumePath]) -> None:
        """Show only the settings of the format ``path``'s extension names.

        A path with no or an unknown extension, or ``None``, shows every format's
        settings. Does nothing when the shown format is already the one ``path`` names.
        """
        fmt = _format_or_none(path)
        if fmt == self._shown_format:
            return
        self._shown_format = fmt
        for bag_fmt, name in _BAG_BY_FORMAT.items():
            visible = fmt is None or fmt is bag_fmt
            getattr(self, name)._set_ui_state_all(UiState.NORMAL if visible else UiState.HIDDEN)

    def worker(
        self,
        context: ExecutionContext,
        image: ImageValue,
        path: VolumePath,
        if_exists: str,
        depth: str,
    ) -> str:
        self.hb_refresh_format_bags(path)
        if image.is_empty:
            raise ValueError("image is empty")
        target = resolve(path)
        fmt = format_for(target)
        policy = IfExists(if_exists)
        claimed = claim_target(target, policy)
        if claimed is None:
            self.out("saved", path)
            return "next"
        atomic_write(
            claimed,
            encode_image(image, fmt, self._encode_options(depth)),
            placeholder=policy is IfExists.UNIQUE_SUFFIX,
        )
        self.out("saved", _sibling(path, claimed))
        return "next"

    def _encode_options(self, depth: str) -> EncodeOptions:
        return EncodeOptions(
            depth=None if depth == "source" else int(depth),
            jpeg_quality=self.jpeg.quality,
            png_compression=self.png.compression,
            webp_quality=self.webp.quality,
            webp_lossless=self.webp.lossless,
            tiff_compression=self.tiff.compression,
            avif_quality=self.avif.quality,
        )


def _format_or_none(path: Optional[VolumePath]) -> Optional[Format]:
    """The format ``path``'s extension names, or ``None`` for no path or no known extension."""
    if path is None:
        return None
    try:
        return format_for(Path(path.relative))
    except ValueError:
        return None


def _sibling(path: VolumePath, claimed: Path) -> VolumePath:
    """``path`` with its file name replaced by ``claimed``'s."""
    if claimed.name == PurePosixPath(path.relative).name:
        return path
    return VolumePath(path.volume, str(PurePosixPath(path.relative).with_name(claimed.name)))
