"""Stamping a widget's declared size box onto its rendered container.

A widget declares the box it claims when nothing constrains it via
``@widget(min_width=..., min_height=...)``. This module carries that declaration
from the widget instance to the DOM, where ``canvas.vue`` turns it into CSS size
containment.

Why containment. A node's size floor is not computed anywhere in Haywire — the
resize gadget writes a ``min-width``/``min-height`` onto the host slot and reads
back ``offsetWidth``/``offsetHeight`` (canvas.vue ``onResizeGripDown``), so the
floor is whatever CSS intrinsic sizing produces: the max-content size of the
card subtree. A widget holding an ``<img>`` therefore floors its node at the
image's *natural pixel size* — percentages (``width: 100%``, ``max-width: 100%``)
resolve to ``auto`` during intrinsic sizing and cannot cap it. ``contain: size``
plus ``contain-intrinsic-size`` replaces the content's vote with the declared
box, so the node shrinks to the box while the widget still grows into a larger
card.

The declaration reaches the DOM as CSS custom properties plus a marker class,
so the whole CSS contract stays in one place (``canvas.vue``) next to the
``.widget-container`` rules it interacts with. Both are ``class`` and ``style``,
the two things a Quasar field keeps on its root (it moves every other attribute
to an inner element), so the box reaches a widget whose root is a ``ui.select``
or ``ui.input`` as well as a plain element.
"""

from __future__ import annotations

import logging

from nicegui.element import Element

from .interface import IWidget

logger = logging.getLogger(__name__)

# Marker classes read by the canvas.vue CSS contract.
BOX_CLASS = "hw-widget-box"  # both axes declared -> contain: size
INLINE_BOX_CLASS = "hw-widget-inline-box"  # width only -> contain: inline-size
MAX_HEIGHT_CLASS = "hw-widget-max-height"

# Custom properties the marker rules read.
MIN_WIDTH_VAR = "--hw-widget-min-width"
MIN_HEIGHT_VAR = "--hw-widget-min-height"
MAX_HEIGHT_VAR = "--hw-widget-max-height"


def stamp_size_declaration(element: Element | None, widget: IWidget) -> None:
    """Stamp ``widget``'s declared size box onto its rendered root ``element``.

    No-op for a widget that declares nothing, so content-driven sizing stays the
    default. The marker is a class on ``element``: a widget that later calls
    ``classes(replace=...)`` on its own root removes it.

    Which axes are declared picks the containment mode, and the two modes suit
    genuinely different content:

    - ``min_width`` alone — inline-axis containment. The width stops coming from
      content (the floor drops), while the height still does. For content with
      an intrinsic aspect ratio (an image, a video frame) that is what keeps the
      widget growing *proportionally* as the node gets wider, which full
      containment would flatten into a fixed-height box.
    - ``min_width`` + ``min_height`` — both axes contained. The content never
      votes on either. For content with no useful aspect ratio, or that should
      scroll/clip inside a fixed box.
    - ``min_height`` alone — not expressible: CSS has ``contain: inline-size``
      but no block-axis equivalent. Logged and ignored.
    """
    if element is None:
        return  # a widget whose render failed has no root to stamp

    min_width = widget.min_width
    min_height = widget.min_height
    max_height = widget.max_height

    decls: list[str] = []

    if min_width is not None:
        decls.append(f"{MIN_WIDTH_VAR}: {min_width}px")
        if min_height is not None:
            decls.append(f"{MIN_HEIGHT_VAR}: {min_height}px")
            element.classes(add=BOX_CLASS)
        else:
            element.classes(add=INLINE_BOX_CLASS)
    elif min_height is not None:
        logger.warning(
            "Widget %s declares min_height without min_width. CSS can contain the "
            "inline axis alone but not the block axis, so the declaration is ignored "
            "— declare min_width too for a fully contained box.",
            type(widget).__name__,
        )

    if max_height is not None:
        decls.append(f"{MAX_HEIGHT_VAR}: {max_height}px")
        element.classes(add=MAX_HEIGHT_CLASS)

    if decls:
        # add (not replace) — the widget's own build() styling stays intact.
        element.style("; ".join(decls))
