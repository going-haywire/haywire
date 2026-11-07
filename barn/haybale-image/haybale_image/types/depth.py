"""DEPTH: a metric depth map."""

from haywire.barn.builtin.types import CARRIER
from haywire.core.types import type as type_decorator

from haybale_image.value import DepthValue


@type_decorator(
    label="Depth",
    description="A depth map, one value per pixel in millimetres.",
    color="#00838f",
    default={"value": {}},
    hidden=False,
)
class DEPTH(CARRIER):
    """A depth map: one value per pixel, in millimetres.

    It is not an image, so it does not connect to image inlets. Use a node to turn it
    into something viewable. The value is never saved with the graph.
    """

    element_type_cls = DepthValue

    @classmethod
    def empty_value(cls) -> DepthValue:
        """Return a 0×0 depth map."""
        return DepthValue.empty()
