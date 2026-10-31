"""Image Viewer widget — shows an IMAGE port's value as a live stream or a still picture."""

from typing import Any

from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget

from haybale_image.value import ImageValue
from haybale_image.viewer.backend import ImageViewer, StillBackend, StreamingBackend


@widget(
    description="Shows an image, as a live stream or as a still picture",
    # Width only: the image's natural size stops flooring the node, and its aspect
    # ratio still sets the height as the node widens. See haywire.ui.widget.sizing.
    min_width=160,
)
class ImageViewerWidget(BaseWidget):
    """Shows the port's image.

    Properties (`ImageViewerWidget.config(properties={...})`):

    - `mode`: `stream` (default) sends every image as JPEG, for images that change
      many times a second; `still` sends the image as PNG only when the view asks for
      it, for large images that change rarely. Click a still image to see it at its
      natural size (1:1) and scroll it; click again to fit it.
    - `quality`: JPEG quality in `stream` mode, 0 to 100 (default `80`).
    - `frame_width`: CSS width of a border around the view (default `0`, none).
    - `frame_color`: CSS color of that border (default `var(--hw-border)`).

    `stream` shows nothing until the view is open, and RGBA images lose their
    transparency. `still` keeps transparency and shows 8 bits per channel.

    ```python
    self.add(IMAGE.as_inlet(
        "image",
        widget=ImageViewerWidget.config(properties={"mode": "still"}),
    ))
    ```
    """

    def __init__(self, port: Any) -> None:
        super().__init__(port)
        self._backend: StreamingBackend | StillBackend | None = None
        self._viewer: ImageViewer | None = None

    def build(self) -> Any:
        props = self._config.get("properties", {})
        if self._backend is None:
            if props.get("mode", "stream") == "still":
                self._backend = StillBackend()
            else:
                self._backend = StreamingBackend(quality=props.get("quality", 80))
        frame_width = props.get("frame_width", "0")
        frame_color = props.get("frame_color", "var(--hw-border)")
        # flex: 1 grows into the size the host node gives; min-height: 0 lets it shrink again.
        self._viewer = ImageViewer(self._backend).style(
            f"width: 100%; flex: 1; min-width: 0; min-height: 0; border: {frame_width} solid {frame_color};"
        )
        return self._viewer

    def on_model_changed(self, value: Any) -> None:
        # Floor-only widget: owns sync entirely, does not call super(). Runs on worker threads.
        image = getattr(value, "value", value)
        if not isinstance(image, ImageValue):
            return
        backend = self._backend
        if isinstance(backend, StreamingBackend):
            backend.stream(image)
        elif isinstance(backend, StillBackend):
            version = backend.show(image)
            viewer = self._viewer  # local: _on_cleanup on the loop may clear it meanwhile
            if viewer is not None:
                viewer.set_version(0 if image.is_empty else version)

    def _on_cleanup(self) -> None:
        if self._backend is not None:
            self._backend.cleanup()
            self._backend = None
        self._viewer = None
