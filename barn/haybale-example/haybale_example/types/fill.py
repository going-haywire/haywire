"""FILL IType — a structured background fill, as a worked example.

A demonstration of a **compound BaseType with a custom widget**: a value with
several independently-edited parts, a non-trivial editor, and a rendering
method. Node authors wanting a structured type of their own can read this one
end to end — see ``FillDemoNode`` for it wired into a real card.

Why a type rather than a colour string: a fill has *structure* — a kind, an
angle, and N colour stops — and CSS for it is **generated from those fields**
rather than typed by a user. Nothing here ever concatenates free text into a
style attribute, so the value cannot carry a stray ``;`` out of its own
declaration and inject further CSS. A plain string field spelling
``linear-gradient(...)`` by hand can.

``to_css()`` is the whole point of the type: it is the only thing that turns a
FILL into CSS, and it is total — every reachable field combination yields a
valid ``background`` value, so a hand-edited graph cannot break a render.
"""

from dataclasses import asdict, dataclass, field
from typing import Any

from haywire.core.types import FlowType
from haywire.core.types import type as type_decorator
from haywire.core.types.base import BaseType

FILL_WIDGET = "haybale-example:widget:FillWidget"
"""The widget's registry key. Spelled out rather than imported from a shared
constants module: the type and its widget ship in the SAME library, so the key
is a local fact — and a library must not reach into haywire-core's key list."""

SOLID = "solid"
LINEAR = "linear"
RADIAL = "radial"
KINDS = (SOLID, LINEAR, RADIAL)
"""The three fill kinds. Deliberately closed: conic gradients and layered
(comma-separated) backgrounds double the editor's complexity for a case the
node-card look does not need."""

_DEFAULT_COLOR = "#1e1e1eff"
_FALLBACK_STOPS = [{"color": _DEFAULT_COLOR, "at": 0}, {"color": _DEFAULT_COLOR, "at": 100}]


def _clean_color(value: Any) -> str:
    """A colour safe to embed in a CSS declaration.

    The one place untrusted text could reach CSS. A colour is a bounded token —
    hex digits, ``rgb()``/``var()`` punctuation — so anything carrying ``;``,
    braces, or a comment sequence is rejected wholesale rather than escaped.
    """
    text = str(value or "").strip()
    if not text or any(ch in text for ch in ";{}\\") or "/*" in text:
        return _DEFAULT_COLOR
    return text


def _clean_stop(stop: Any, fallback_at: int) -> dict:
    """One ``{'color': str, 'at': int}`` stop, coerced into range."""
    if not isinstance(stop, dict):
        return {"color": _DEFAULT_COLOR, "at": fallback_at}
    try:
        at = max(0, min(int(stop.get("at", fallback_at)), 100))
    except (TypeError, ValueError):
        at = fallback_at
    return {"color": _clean_color(stop.get("color")), "at": at}


@type_decorator(
    flow_type=FlowType.DATA,
    label="Fill",
    description="Solid colour or gradient background",
    color="#f7b0ff",
    default={"kind": SOLID, "angle": 135, "stops": [{"color": _DEFAULT_COLOR, "at": 0}]},
    widget_key=FILL_WIDGET,
)
@dataclass
class FILL(BaseType):
    """A node card's background: a solid colour, or a linear/radial gradient.

    ``stops`` is a list of ``{'color': '#rrggbbaa', 'at': 0..100}``. ``kind``
    decides how many of them matter: ``solid`` reads only the first, the
    gradients read all of them. Keeping the full list across a kind switch is
    deliberate — flipping solid → linear → solid must not destroy the stops the
    user already picked.
    """

    kind: str = SOLID
    angle: int = 135
    """Degrees, ``linear`` only. 135 matches the CSS convention of a diagonal
    running top-left → bottom-right."""
    stops: list = field(default_factory=lambda: [{"color": _DEFAULT_COLOR, "at": 0}])

    def __init__(self, **kwargs: Any) -> None:
        """Build a fill from its parts, tolerating anything a hand edit left.

        Hand-written rather than dataclass-generated because the stop list
        needs sanitising on the way in: construction must never raise on a
        graph someone edited by hand, and ``to_css`` cleans what survives.
        """
        self.kind = kwargs.get("kind", SOLID)
        self.angle = kwargs.get("angle", 135)
        stops = kwargs.get("stops")
        # Copy dict stops, drop anything that is not one: construction must not
        # raise on a hand-edited graph, and to_css cleans what survives.
        self.stops = [dict(s) for s in stops if isinstance(s, dict)] if stops else []
        if not self.stops:
            self.stops = [{"color": _DEFAULT_COLOR, "at": 0}]

    # -- serialization -------------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "FILL":
        """Rebuild from stored JSON, tolerating anything a hand edit produced."""
        if not isinstance(data, dict):
            return cls()
        kind = data.get("kind", SOLID)
        if kind not in KINDS:
            kind = SOLID
        try:
            angle = int(data.get("angle", 135)) % 360
        except (TypeError, ValueError):
            angle = 135
        raw_stops = data.get("stops")
        if not isinstance(raw_stops, list) or not raw_stops:
            raw_stops = [{"color": _DEFAULT_COLOR, "at": 0}]
        stops = [_clean_stop(s, i * 100 // max(1, len(raw_stops) - 1)) for i, s in enumerate(raw_stops)]
        return cls(kind=kind, angle=angle, stops=stops)

    # -- rendering -----------------------------------------------------
    def to_css(self) -> str:
        """This fill as a CSS ``background`` value. Total — never raises.

        A gradient needs two stops to be a gradient; one is promoted to a flat
        run of that colour rather than emitting invalid CSS.
        """
        stops = [_clean_stop(s, 0) for s in self.stops] or list(_FALLBACK_STOPS)

        if self.kind not in (LINEAR, RADIAL):
            return stops[0]["color"]

        if len(stops) == 1:
            stops = [stops[0], {**stops[0], "at": 100}]

        rendered = ", ".join(f"{s['color']} {s['at']}%" for s in sorted(stops, key=lambda s: s["at"]))
        if self.kind == RADIAL:
            return f"radial-gradient(circle, {rendered})"
        try:
            angle = int(self.angle) % 360
        except (TypeError, ValueError):
            angle = 135
        return f"linear-gradient({angle}deg, {rendered})"
