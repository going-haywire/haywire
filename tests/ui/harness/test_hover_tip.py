"""A pin's tooltip is drawn in the browser: hovering shows it without a server round trip."""

import pytest
from playwright.sync_api import Page, expect

from haywire.ui import hover_tip
from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled
from tests.ui.harness.test_edge_style_menu import _PATH, _STYLED
from tests.ui.harness.test_popup_outside_press import _empty_canvas_point

pytestmark = pytest.mark.ui

_TIP = ".hw-hover-tip"
_PIN = ".connection-pin[data-hw-tip]"


def _open(page: Page, harness) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    page.wait_for_selector(_STYLED)
    wait_for_canvas_settled(page)
    install_hover_tips(page)


def install_hover_tips(page: Page) -> None:
    """Add the hover-tip script to a harness page; AppShell installs it on studio pages."""
    page.add_script_tag(content=hover_tip._SCRIPT.removeprefix("<script>").removesuffix("</script>"))


def _hover_first_pin(page: Page) -> str:
    pin = page.locator(_PIN).first
    pin.hover()
    return pin.get_attribute("data-hw-tip") or ""


def test_hovering_a_pin_shows_its_label(page: Page, harness) -> None:
    _open(page, harness)

    label = _hover_first_pin(page)

    assert label
    expect(page.locator(_TIP)).to_be_visible()
    expect(page.locator(f"{_TIP} .text-weight-bold")).to_have_text(label)


def test_leaving_the_pin_hides_it(page: Page, harness) -> None:
    _open(page, harness)
    _hover_first_pin(page)
    expect(page.locator(_TIP)).to_be_visible()
    point = _empty_canvas_point(page)

    page.mouse.move(point["x"], point["y"])

    expect(page.locator(_TIP)).to_be_hidden()


def test_a_press_hides_it(page: Page, harness) -> None:
    _open(page, harness)
    _hover_first_pin(page)
    expect(page.locator(_TIP)).to_be_visible()

    page.mouse.down()
    page.mouse.up()

    expect(page.locator(_TIP)).to_be_hidden()


def test_no_pin_listens_for_hovers_on_the_server(page: Page, harness) -> None:
    """A server listener on an element is an entry in its ``events``; a pin has none for hovers."""
    _open(page, harness)

    hover_listeners = page.evaluate(
        """() => {
            const els = document.querySelector("#app")._vnode.component.proxy.elements;
            let pins = 0, listening = 0;
            for (const e of Object.values(els)) {
                if (!(e.class || []).includes("connection-pin")) continue;
                pins++;
                const hover = ev => ev.type === "mouseenter" || ev.type === "mouseleave";
                if ((e.events || []).some(hover)) listening++;
            }
            return { pins, listening };
        }"""
    )

    assert hover_listeners["pins"] > 0
    assert hover_listeners["listening"] == 0
