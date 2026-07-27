"""Widget fixtures for the declared-size-box feature (browser test support).

All three render the SAME oversized replaced element — a 1280x720 ``<img>``,
standing in for the real case, a video frame viewer — and differ only in what
they declare. Without a declaration such content becomes the node's size floor
and the resize gadget cannot shrink the node past it.

Backs ``tests/ui/harness/test_widget_size_box.py``. An ``<img>`` (SVG data URI,
so the fixture needs no asset and no stream) rather than a sized ``div``: the
bug is specific to *replaced* elements, whose natural size wins over
``width``/``max-width`` during intrinsic sizing, and whose aspect ratio drives
the proportional growth that must survive the fix.
"""

from typing import Any

from nicegui import ui

from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget

# Matches a 720p frame — the case that motivated the feature.
CONTENT_WIDTH = 1280
CONTENT_HEIGHT = 720

# The box a widget claims when nothing constrains it. 16:9, small enough that a
# floor measurement can never be confused with the content size.
BOX_WIDTH = 160
BOX_HEIGHT = 90

_FRAME = (
    "data:image/svg+xml;utf8,"
    f"<svg xmlns='http://www.w3.org/2000/svg' width='{CONTENT_WIDTH}' height='{CONTENT_HEIGHT}'>"
    "<rect width='100%' height='100%' fill='%231a1a1a'/></svg>"
)


def _frame_image() -> Any:
    """A replaced element at 1280x720 natural size, scaled like the real viewer."""
    return ui.html(
        f"<img src=\"{_FRAME}\" data-testid='oversized-content' "
        "style='width: 100%; height: 100%; max-width: 100%; max-height: 100%; "
        "object-fit: contain; display: block;'>"
    ).style("width: 100%; display: block;")


@widget(description="Oversized content that sizes from its contents (no declared box)")
class OversizedContentWidget(BaseWidget):
    """Control fixture: content votes on the node's size floor, as stock widgets do."""

    def build(self) -> Any:
        with ui.element("div").style("width: 100%;") as root:
            _frame_image()
        return root


@widget(
    description="Oversized content behind a declared width; height follows the content's aspect",
    min_width=BOX_WIDTH,
)
class AspectBoxWidget(BaseWidget):
    """Width declared, height content-driven — inline-axis containment only."""

    def build(self) -> Any:
        with ui.element("div").style("width: 100%;") as root:
            _frame_image()
        return root


@widget(
    description="Oversized content behind a fully declared box",
    min_width=BOX_WIDTH,
    min_height=BOX_HEIGHT,
)
class FixedBoxWidget(BaseWidget):
    """Both axes declared — the content never votes on either."""

    def build(self) -> Any:
        with ui.element("div").style("width: 100%; height: 100%;") as root:
            _frame_image()
        return root
