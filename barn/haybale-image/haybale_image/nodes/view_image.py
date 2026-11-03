"""View Image — show an image on the node card."""

from typing import Any

from haywire.core.execution.execution_context import ExecutionContext
from haywire.barn.builtin.types import CHOICES, FLOAT
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.settings import NodeSettings, bag, setting
from haywire.core.types.enums import ShowWidgetStrategy

from haybale_image.value import ImageValue

VIEW_MODES = ("stream", "still")


class ViewerSettings(NodeSettings):
    """How the image shows: as a stream or a still, and how a click on a still enlarges it."""

    mode = setting[CHOICES](
        VIEW_MODES[1],
        label="Mode",
        description="stream for images that change often (a camera); still for large, rarely changing ones",
        widget_config={"options": list(VIEW_MODES)},
    )
    enlarge = setting[FLOAT](
        3.0,
        label="Enlarge view",
        description="How many times wider the view gets when a still image is clicked",
        min=1.0,
        max=8.0,
    )
    zoom = setting[FLOAT](
        1.0,
        label="Zoom image",
        description="How many times the enlarged view's width the image shows; 1 fits it",
        min=1.0,
        max=16.0,
    )


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
      image keeps its transparency.

    Click a still image to enlarge the view: it gets `Enlarge view` times wider and
    takes the image's shape, and the image shows `Zoom image` times the view's width
    (1 fits it). Drag inside it to move around the image; click again to go back.

    The view appears once `Image` is connected.

    ```text
    Load Image → View Image (Mode = still)
    ```
    """

    viewer = bag(ViewerSettings)

    def init(self) -> None:
        from haywire.barn.builtin.types import EXEC

        from haybale_image.types.image import IMAGE
        from haybale_image.widgets.image_viewer_widget import ImageViewerWidget

        self.add(EXEC.as_inlet("exec", label="Execute", description="Shows the image"))
        self.add(
            IMAGE.as_inlet(
                "image",
                label="Image",
                show_widget=ShowWidgetStrategy.WHEN_LINKED,
                widget=ImageViewerWidget.config(properties={"mode": VIEW_MODES[0]}),
                description="Image to show",
            )
        )
        self.add(EXEC.as_outlet("next", label="Next", description="Runs after showing"))
        self.add(IMAGE.as_outlet("image_out", label="Image Out", description="The same image, passed on"))

    def post_init(self) -> None:
        for name in ("mode", "enlarge", "zoom"):
            self.hb_on_viewer_changed(name, getattr(self.viewer, name), None)
        self.viewer._subscribe(self.hb_on_viewer_changed)

    def hb_on_viewer_changed(self, name: str, value: Any, old: Any) -> None:
        """Hand a viewer setting to the viewer, which is built again; an unknown mode shows a stream."""
        if name == "mode":
            self.ports["image"].set_widget_config("mode", value if value in VIEW_MODES else VIEW_MODES[0])
        elif name in ("enlarge", "zoom"):
            self.ports["image"].set_widget_config(name, float(value))

    def worker(self, context: ExecutionContext, image: ImageValue) -> str:
        self.out("image_out", image)
        return "next"
