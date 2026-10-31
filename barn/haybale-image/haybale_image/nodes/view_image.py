"""View Image — show an image on the node card."""

from typing import Any

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.types.enums import ShowWidgetStrategy

from haybale_image.value import ImageValue

VIEW_MODES = ("stream", "still")


@node(
    label="View Image",
    description="Shows an image on the node, as a live stream or as a still picture",
    menu="image",
    search_tags=["image", "view", "show", "preview", "display", "viewer", "stream"],
    node_type=NodeType.CONTROL,
)
class ViewImageNode(BaseNode):
    """Shows `Image` on the node and passes it on to `Image Out`.

    - `Mode`: `stream` for images that change many times a second, such as a camera;
      `still` for large images that change rarely, such as a loaded file. A still
      image keeps its transparency; click it to see it at its natural size (1:1),
      and click again to fit it.

    The view appears once `Image` is connected.

    ```text
    Load Image → View Image (Mode = still)
    ```
    """

    def init(self) -> None:
        from haywire.barn.builtin.types import EXEC, STRING
        from haywire.barn.builtin.widgets import SelectWidget

        from haybale_image.types.image import IMAGE
        from haybale_image.widgets.image_viewer_widget import ImageViewerWidget

        self.add(EXEC.as_inlet("exec", label="Execute"))
        self.add(
            IMAGE.as_inlet(
                "image",
                label="Image",
                show_widget=ShowWidgetStrategy.WHEN_LINKED,
                widget=ImageViewerWidget.config(properties={"mode": VIEW_MODES[0]}),
            )
        )
        self.add(
            STRING.as_config(
                "mode",
                default=VIEW_MODES[0],
                label="Mode",
                widget=SelectWidget.config(properties={"options": list(VIEW_MODES)}),
                on_change="hb_on_mode_changed",
            )
        )
        self.add(EXEC.as_outlet("next", label="Next"))
        self.add(IMAGE.as_outlet("image_out", label="Image Out"))

    def post_init(self) -> None:
        self.hb_apply_mode(self.value("mode"))

    def hb_on_mode_changed(self, port: Any, value: Any) -> None:
        self.hb_apply_mode(value)

    def hb_apply_mode(self, mode: Any) -> None:
        """Rebuild the viewer for ``mode``; an unknown mode shows a stream."""
        mode = mode if mode in VIEW_MODES else VIEW_MODES[0]
        self.ports["image"].set_widget_config("mode", mode)

    def worker(self, context: ExecutionContext, image: ImageValue) -> str:
        self.out("image_out", image)
        return "next"
