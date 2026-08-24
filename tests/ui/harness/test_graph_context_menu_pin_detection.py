"""Pin detection is structural (canvas.vue's ``handleContextMenu``), not skin-owned.

``render_pin`` emits ``data-pin-id`` on every pin from every skin, so the
canvas's context-menu router treats any element carrying it (and no
``data-hw-menu-surface-id`` ancestor) as a pin — regardless of which skin
drew it — and opens ``PinMenu``. This is checked BEFORE the node branch,
since a pin sits inside a node's DOM and would otherwise be swallowed by it
(canvas.vue, "Structural: a pin"). Uses ``/graph-connect``'s fixture (real
nodes with real pins, full GraphCanvasManager wiring) since it already
exposes ``.connection-pin`` elements — see ``test_graph_connect.py``.
"""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready

_URL = "http://localhost:8090/graph-connect"

pytestmark = pytest.mark.ui


def _pin_center(page: Page, id_fragment: str) -> dict:
    return page.evaluate(
        """(frag) => {
            const pin = [...document.querySelectorAll('.connection-pin')]
                .find(e => e.id.includes(frag));
            if (!pin) throw new Error('pin not found: ' + frag);
            const r = pin.getBoundingClientRect();
            return { x: r.left + r.width/2, y: r.top + r.height/2 };
        }""",
        id_fragment,
    )


def _node_body_center(page: Page, id_fragment: str) -> dict:
    """Screen-space center of a node's own card body (not a pin) — the safe
    right-click target for asserting the pin branch does not swallow nodes."""
    return page.evaluate(
        """(frag) => {
            const node = [...document.querySelectorAll('[data-node-id]')]
                .find(e => e.id.includes(frag) || e.getAttribute('data-node-id').includes(frag));
            if (!node) throw new Error('node not found: ' + frag);
            const card = node.querySelector('.node-card') || node;
            const r = card.getBoundingClientRect();
            return { x: r.left + r.width * 0.5, y: r.top + r.height * 0.5 };
        }""",
        id_fragment,
    )


def _open(page: Page) -> None:
    goto_ready(page, _URL)
    page.wait_for_selector("[data-node-id]")
    page.wait_for_selector(".connection-pin")
    page.wait_for_timeout(1200)  # let the graph sync + center


def test_right_click_on_a_pin_opens_the_pin_menu(page: Page, harness):
    """A right-click on an element carrying data-pin-id (and no
    data-hw-menu-surface-id) opens PinMenu — proven by PortInfoMenuPanel's
    section_label(port.id), which is only ever drawn on that surface."""
    _open(page)
    pos = _pin_center(page, "exec@TestBeginPlay")

    page.mouse.click(pos["x"], pos["y"], button="right")
    page.wait_for_timeout(400)

    # PortInfoMenuPanel draws hui.section_label(port.id) directly into the
    # popup — visible as soon as PinMenu opens, no submenu navigation needed.
    assert page.get_by_text("exec", exact=False).count() > 0, (
        "right-clicking a pin should open PinMenu (Port Info panel shows the port id)"
    )
    # The selection menu's distinguishing content must NOT be present —
    # proves the pin branch, not the node/selection branch, was taken.
    assert page.get_by_text("Copy Node", exact=False).count() == 0
    assert page.get_by_text("Copy Selection", exact=False).count() == 0


def test_right_click_on_a_node_body_still_opens_the_selection_menu(page: Page, harness):
    """A right-click on the node body (not a pin) still opens the selection
    menu — the pin branch (checked first, since a pin sits inside a node)
    must not swallow the node case."""
    _open(page)
    pos = _node_body_center(page, "TestBeginPlay")

    page.mouse.click(pos["x"], pos["y"], button="right")
    page.wait_for_timeout(400)

    assert page.get_by_text("Copy", exact=False).count() > 0, (
        "right-clicking a node body should open the selection menu (Copy Selection panel)"
    )
