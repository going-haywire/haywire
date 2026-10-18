"""A stage canvas starts an edge drag only from an on-stage pin (canvas.vue).

The server refuses an off-stage edge on a stage canvas too; that is covered in
tests/ui/test_canvas_handlers/test_stage_visual_layer.py. These cover the
browser side: a pin without ``data-pin-on-stage`` starts nothing on stage, an
annotation pin connects. No shipped skin draws an off-stage pin on a stage, so
the first test plants one, as a skin that ignores ``on_stage`` would.
"""

import pytest
from playwright.sync_api import Page, expect

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled

_PROBES = ("a", "b")

pytestmark = pytest.mark.ui


def _open(page: Page, harness) -> dict[str, str]:
    goto_ready(page, f"{harness}/graph-stage-gate")
    page.wait_for_selector(".connection-pin", state="attached")
    wait_for_canvas_settled(page)
    return {name: page.inner_text(f'[data-testid="probe-{name}"]') for name in _PROBES}


def _pin_center(page: Page, node_id: str, pin_id: str) -> dict:
    return page.evaluate(
        """([node, pin]) => {
            const el = document.getElementById(`${pin}@${node}`);
            if (!el) throw new Error(`pin not found: ${pin}@${node}`);
            const r = el.getBoundingClientRect();
            return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
        }""",
        [node_id, pin_id],
    )


def _card_centre(page: Page, node_id: str, pin_id: str) -> tuple[float, float]:
    box = page.evaluate(
        """([node, pin]) => {
            const card = document.getElementById(`${pin}@${node}`).closest('.node-card');
            const c = card.getBoundingClientRect();
            return { x: c.left + c.width / 2, y: c.top + c.height / 2 };
        }""",
        [node_id, pin_id],
    )
    return box["x"], box["y"]


def test_a_pin_off_the_stage_wires_starts_no_drag_on_stage(page: Page, harness) -> None:
    ids = _open(page, harness)
    before = page.get_by_test_id("server-edges").inner_text()
    pos = page.evaluate(
        """([node, pin]) => {
            const src = document.getElementById(`${pin}@${node}`);
            const fake = src.cloneNode(true);
            fake.id = `fake@${node}`;
            fake.dataset.pinId = 'fake';
            delete fake.dataset.pinOnStage;
            fake.style.visibility = 'visible';
            src.parentElement.appendChild(fake);
            const r = fake.getBoundingClientRect();
            return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
        }""",
        [ids["a"], "right_0"],
    )

    page.mouse.move(*_card_centre(page, ids["a"], "right_0"))
    page.mouse.click(pos["x"], pos["y"])
    page.mouse.move(pos["x"] + 60, pos["y"] + 10)
    page.wait_for_timeout(300)

    assert page.locator(".graph-canvas.edge-dragging").count() == 0
    expect(page.get_by_test_id("server-edges")).to_have_text(before)


def test_an_annotation_pin_drag_connects_on_stage(page: Page, harness) -> None:
    ids = _open(page, harness)

    page.mouse.move(*_card_centre(page, ids["a"], "right_0"))
    start = _pin_center(page, ids["a"], "right_0")
    page.mouse.click(start["x"], start["y"])
    page.wait_for_selector(".graph-canvas.edge-dragging")
    end = _pin_center(page, ids["b"], "left_0")
    page.mouse.move(end["x"], end["y"])
    page.mouse.click(end["x"], end["y"])

    expect(page.get_by_test_id("server-edges")).to_contain_text(ids["a"])
