"""DEPTH_BUFFER: a metric depth buffer."""

from haywire.api import CARRIER, type as type_decorator

from haybale_image.value import DepthValue


@type_decorator(
    label="Depth Buffer",
    description="A depth buffer, one value per pixel in millimetres.",
    color="#00838f",
    default={"value": {}},
    hidden=False,
)
class DEPTH_BUFFER(CARRIER):
    """A depth buffer: one value per pixel, in millimetres.

    It is not an image, so it does not connect to image inlets. Use a node to turn it
    into something viewable. The value is never saved with the graph.
    """

    element_type_cls = DepthValue

    @classmethod
    def empty_value(cls) -> DepthValue:
        """Return a 0×0 depth buffer."""
        return DepthValue.empty()
