"""A pin must stay a NATIVE tag, and must keep looking exactly like a q-icon.

Two properties that fail silently in opposite directions, so both are pinned
here rather than left to a rendering check.

**Cost.** NiceGUI renders the whole page as ONE Vue component whose render
rebuilds a VNode for every element on every update, so the currency of studio
responsiveness is element count *and* what each element costs. `nicegui.js`
splits on the tag — ``isNativeTag(tag) ? tag : Vue.resolveComponent(tag)`` —
and a resolved component costs roughly 3x a native tag there. Pins are the
largest single population in a graph (one per port; 6,600 on the 300-node
fixture), so moving them off ``q-icon`` measured ~14% off the whole-page
update. Nothing about that is visible in a rendered card: put ``q-icon`` back
and the pin looks identical while every interaction in the studio gets slower.

**Fidelity.** The saving is only free because the markup is unchanged.
Quasar's own ``.q-icon`` rules supply the pin's box (``width``/``height: 1em``,
``content-box``) and ``.material-icons`` supplies the font, and the edge layer
reads ``getBoundingClientRect()`` off this element. Drop one of those classes
and pins keep rendering — at the wrong size, with edges landing off-centre.
"""

from __future__ import annotations

import pytest

from haywire.barn.builtin.types import FLOAT
from haywire.core.types import DataPort, FlowType, LayoutDirection, PortType
from haywire.ui.skin.pin_render import render_pin

pytestmark = pytest.mark.unit

_PIN_GUTTER = 20
_CARD_PADDING = 16
_PIN_PROTRUSION = 0


def _make_port(color: str = "#50b0ff") -> DataPort:
    return DataPort(
        registry_id="float",
        registry_key="haybale_core:type:float",
        label="F",
        id="p_inlet",
        type_cls=FLOAT,
        port_type=PortType.INLET,
        flow_type=FlowType.DATA,
        color=color,
    )


def _render(port):
    return render_pin(
        port,
        "node-1",
        layout=LayoutDirection.LEFT_TO_RIGHT,
        pin_gutter=_PIN_GUTTER,
        card_padding=_CARD_PADDING,
        pin_protrusion=_PIN_PROTRUSION,
    )


def test_pin_is_a_native_tag(nicegui_slot_context):
    """`i`, not `q-icon` — the whole point. See this module's docstring."""
    assert _render(_make_port()).tag == "i"


def test_pin_keeps_the_q_icon_markup(nicegui_slot_context):
    """Same classes, glyph and aria as the q-icon it replaced."""
    el = _render(_make_port())
    classes = set(el._classes)
    assert {"q-icon", "notranslate", "material-icons"} <= classes, (
        "Quasar's .q-icon supplies the pin's box and .material-icons its font; "
        f"missing from {sorted(classes)}"
    )
    assert {"port", "connection-pin", "zoom-pan-lod0"} <= classes
    # the glyph is a Material ligature carried as the element's text
    assert el._text
    assert el._props["aria-hidden"] == "true"


def test_size_and_hex_colour_become_inline_style(nicegui_slot_context):
    """`q-icon`'s size/color props mean nothing on a native tag."""
    el = _render(_make_port())
    assert el._style["font-size"] == f"{_PIN_GUTTER}px"
    assert el._style["color"] == "#50b0ff"
    # a leftover Quasar prop would be inert but misleading
    assert "size" not in el._props
    assert "color" not in el._props


def test_palette_colour_becomes_a_text_class(nicegui_slot_context):
    """Mirrors NiceGUI's TextColorElement: a palette name is a class, not a style."""
    el = _render(_make_port(color="primary"))
    assert "text-primary" in el._classes
    assert "color" not in el._style
