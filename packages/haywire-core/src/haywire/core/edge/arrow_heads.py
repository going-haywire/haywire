"""Arrow heads: the vocabulary of glyphs an edge can draw at either end.

One table is the single source for the canvas markers and the
``ArrowHeadWidget`` previews. Coordinates are in edge widths
(``markerUnits="strokeWidth"``): a head is drawn from its attach point at
x = 0, where the shortened edge ends, to its tip at x = ``inset``, which
touches the pin's edge. Every edge end stops at its pin's edge, and the canvas
shortens an end that has a head by a further ``inset × width``, so no head
overlaps its line. A head paints with ``context-stroke``, so it takes the
stroke of the edge that draws it.
"""

from __future__ import annotations

from dataclasses import dataclass

#: The value meaning "no head", as stored in a setting.
NO_HEAD = "none"

# Space around a glyph inside its marker viewport, in edge widths.
_PAD = 2
_HALF_HEIGHT = 4


@dataclass(frozen=True)
class ArrowHead:
    """One arrow head: its stored name, the label the picker shows, and its glyph.

    Attributes:
        name: The value a setting stores, such as ``"open"``.
        label: What the picker shows.
        common: Shown before the picker's "More" item.
        inset: The glyph's length in edge widths; the edge ends this far before the pin's edge.
        svg: The glyph's SVG children, painted with ``context-stroke``.
    """

    name: str
    label: str
    common: bool
    inset: float
    svg: str

    def to_payload(self) -> dict:
        """Return what the canvas needs to build this head's ``<marker>``."""
        width = self.inset + 2 * _PAD
        return {
            "name": self.name,
            "inset": self.inset,
            "svg": self.svg,
            "view_box": f"{-_PAD} {-_HALF_HEIGHT} {width} {2 * _HALF_HEIGHT}",
            "width": width,
            "height": 2 * _HALF_HEIGHT,
        }


def _fill(d: str) -> str:
    return f'<path d="{d}" fill="context-stroke"/>'


def _line(d: str) -> str:
    return f'<path d="{d}" fill="none" stroke="context-stroke" stroke-width="1" stroke-linejoin="round"/>'


def _disc(cx: float, r: float) -> str:
    return f'<circle cx="{cx}" cy="0" r="{r}" fill="context-stroke"/>'


def _ring(cx: float, r: float) -> str:
    return f'<circle cx="{cx}" cy="0" r="{r}" fill="none" stroke="context-stroke" stroke-width="1"/>'


_CROW = "M{x},0 L{tip},-3 M{x},0 L{tip},0 M{x},0 L{tip},3"

ARROW_HEADS: tuple[ArrowHead, ...] = (
    ArrowHead("arrow", "Arrow", True, 4.5, _fill("M0,-2.25 L4.5,0 L0,2.25 Z")),
    ArrowHead("sharp", "Sharp arrow", True, 4.0, _fill("M0,0 L-1.2,-2.5 L4,0 L-1.2,2.5 Z")),
    ArrowHead("open", "Open arrow", True, 4.0, _line("M0,-2.5 L3.5,0 L0,2.5 M0,0 L3.5,0")),
    ArrowHead("triangle", "Triangle", True, 5.0, _fill("M0,-3 L5,0 L0,3 Z")),
    ArrowHead("triangle_hollow", "Hollow triangle", False, 5.0, _line("M0.5,-2.7 L4.5,0 L0.5,2.7 Z")),
    ArrowHead("diamond", "Diamond", False, 6.0, _fill("M0,0 L3,-2.5 L6,0 L3,2.5 Z")),
    ArrowHead("diamond_hollow", "Hollow diamond", False, 6.0, _line("M0.5,0 L3,-2.1 L5.5,0 L3,2.1 Z")),
    ArrowHead("circle", "Circle", False, 4.5, _disc(2.25, 2.25)),
    ArrowHead("circle_hollow", "Hollow circle", False, 4.5, _ring(2.25, 1.75)),
    ArrowHead("bar", "Bar", False, 2.5, _line("M0,0 L2.5,0 M1,-3 L1,3")),
    ArrowHead("many", "Many", False, 4.0, _line(_CROW.format(x=0, tip=4))),
    ArrowHead(
        "one_or_many",
        "One or many",
        False,
        5.5,
        _line("M0,0 L5.5,0 M1,-3 L1,3 " + _CROW.format(x=1.5, tip=5.5)),
    ),
    ArrowHead("one_only", "Exactly one", False, 4.0, _line("M0,0 L4,0 M1,-3 L1,3 M2.5,-3 L2.5,3")),
    ArrowHead(
        "zero_or_many", "Zero or many", False, 7.5, _ring(1.75, 1.25) + _line(_CROW.format(x=3.5, tip=7.5))
    ),
    ArrowHead(
        "zero_or_one", "Zero or one", False, 6.0, _ring(1.75, 1.25) + _line("M3.5,0 L6,0 M4.75,-3 L4.75,3")
    ),
)

_BY_NAME = {head.name: head for head in ARROW_HEADS}


def get_arrow_head(name: str | None) -> ArrowHead | None:
    """Return the head called *name*; ``None`` for ``NO_HEAD``, ``None`` or an unknown name."""
    if name is None:
        return None
    return _BY_NAME.get(name)
