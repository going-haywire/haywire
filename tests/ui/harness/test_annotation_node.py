"""The annotation node in a browser: centred pins on four sides, hover-only slots, drops, text edit."""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled

_PATH = "/graph-annotation"
_CANVAS = '.graph-canvas[data-testid="annotation-canvas"]'
_LINKED = 'path.hw-edge[data-edge-id*="[right_0]->"][data-edge-id*="[left_0]"]'

#: The outward direction vector of each card side.
_OUTWARD = {"top": (0, -1), "right": (1, 0), "bottom": (0, 1), "left": (-1, 0)}

pytestmark = [pytest.mark.ui, pytest.mark.browser]


def _open(page: Page, harness) -> dict[str, str]:
    goto_ready(page, f"{harness}{_PATH}")
    page.wait_for_selector(_LINKED, state="attached")
    wait_for_canvas_settled(page)
    return {name: page.inner_text(f'[data-testid="note-{name}"]') for name in "abcd"}


def _pin(node_id: str, pin_id: str) -> str:
    return f'.connection-pin[data-node-id="{node_id}"][data-pin-id="{pin_id}"]'


def _geometry(page: Page, node_id: str, pin_id: str) -> dict:
    """The pin's centre, its card's rect, its computed visibility and its direction vector."""
    return page.evaluate(
        """(sel) => {
            const pin = document.querySelector(sel);
            if (!pin) return null;
            const r = pin.getBoundingClientRect();
            const c = pin.closest('.node-card').getBoundingClientRect();
            return {
                x: r.left + r.width / 2, y: r.top + r.height / 2,
                card: { left: c.left, right: c.right, top: c.top, bottom: c.bottom },
                visibility: getComputedStyle(pin).visibility,
                dir: [Number(pin.dataset.pinDirX), Number(pin.dataset.pinDirY)],
            };
        }""",
        _pin(node_id, pin_id),
    )


def _card_centre(page: Page, node_id: str) -> tuple[float, float]:
    box = page.evaluate(
        """(sel) => {
            const c = document.querySelector(sel).closest('.node-card').getBoundingClientRect();
            return { x: c.left + c.width / 2, y: c.top + c.height / 2 };
        }""",
        _pin(node_id, "top_0"),
    )
    return box["x"], box["y"]


def _rects(page: Page, node_id: str) -> dict[str, dict[str, float]]:
    """Every pin's rect on the card, in the card's own unscaled px from its top-left corner.

    Undoing the card's scale keeps the rects comparable while the hover magnifier
    scales the card.
    """
    return page.evaluate(
        """(nodeId) => {
            const pins = [...document.querySelectorAll(`.connection-pin[data-node-id="${nodeId}"]`)];
            const card = pins[0].closest('.node-card');
            const c = card.getBoundingClientRect();
            const s = c.width / card.offsetWidth;
            return Object.fromEntries(pins.map(pin => {
                const r = pin.getBoundingClientRect();
                return [pin.dataset.pinId, {
                    left: (r.left - c.left) / s, top: (r.top - c.top) / s,
                    right: (r.right - c.left) / s, bottom: (r.bottom - c.top) / s,
                }];
            }));
        }""",
        node_id,
    )


def _start_drag(page: Page, node_id: str, pin_id: str) -> None:
    """Hover the card so its slots show, then click the pin to start an edge drag."""
    page.mouse.move(*_card_centre(page, node_id))
    g = _geometry(page, node_id, pin_id)
    assert g["visibility"] == "visible"
    page.mouse.click(g["x"], g["y"])
    page.wait_for_selector(f"{_CANVAS}.edge-dragging")


def _edge_ids(page: Page) -> list[str]:
    return page.evaluate(
        "() => [...new Set([...document.querySelectorAll('path.hw-edge[data-edge-id]')]"
        ".map(e => e.getAttribute('data-edge-id')))]"
    )


def test_pins_sit_on_their_sides(page: Page, harness) -> None:
    ids = _open(page, harness)
    for side, (dx, dy) in _OUTWARD.items():
        g = _geometry(page, ids["a"], f"{side}_0")
        assert g is not None, f"{side}_0 not rendered"
        assert g["dir"] == [dx, dy], f"{side}_0 points {g['dir']}"
        edge = g["card"][side]
        across = g["x"] if side in ("left", "right") else g["y"]
        assert abs(across - edge) <= 3, f"{side}_0 is {across - edge:.1f}px off its border"


def test_a_sides_pins_are_centred(page: Page, harness) -> None:
    ids = _open(page, harness)
    first, second, slot = (_geometry(page, ids["c"], f"right_{i}") for i in range(3))
    centre = (first["card"]["top"] + first["card"]["bottom"]) / 2
    assert abs((first["y"] + second["y"]) / 2 - centre) <= 1
    assert first["y"] < second["y"] < slot["y"]

    rects = _rects(page, ids["c"])
    for pin_id in ("right_0", "right_1"):
        a, b = rects[pin_id], rects["right_2"]
        assert a["bottom"] <= b["top"] or b["bottom"] <= a["top"], f"the slot overlaps {pin_id}"


def test_a_lone_slot_is_centred(page: Page, harness) -> None:
    ids = _open(page, harness)
    page.mouse.move(*_card_centre(page, ids["a"]))
    for side in _OUTWARD:
        g = _geometry(page, ids["a"], f"{side}_0")
        assert g["visibility"] == "visible"
        if side in ("left", "right"):
            along, centre = g["y"], (g["card"]["top"] + g["card"]["bottom"]) / 2
        else:
            along, centre = g["x"], (g["card"]["left"] + g["card"]["right"]) / 2
        assert abs(along - centre) <= 1, f"{side}_0 is {along - centre:.1f}px off its side's centre"


def test_hovering_does_not_move_pins(page: Page, harness) -> None:
    ids = _open(page, harness)
    page.mouse.move(5, 5)
    before = _rects(page, ids["c"])
    page.mouse.move(*_card_centre(page, ids["c"]))
    assert _geometry(page, ids["c"], "right_2")["visibility"] == "visible"
    after = _rects(page, ids["c"])
    assert after.keys() == before.keys()
    for pin_id, rect in before.items():
        for key, value in rect.items():
            assert abs(after[pin_id][key] - value) <= 0.5, f"{pin_id} moved: {rect} -> {after[pin_id]}"


def test_slots_are_hidden_until_hover(page: Page, harness) -> None:
    ids = _open(page, harness)
    page.mouse.move(5, 5)
    assert _geometry(page, ids["a"], "left_0")["visibility"] == "hidden"

    page.mouse.move(*_card_centre(page, ids["a"]))
    assert _geometry(page, ids["a"], "left_0")["visibility"] == "visible"
    assert _geometry(page, ids["b"], "left_0")["visibility"] == "hidden"


def test_slots_show_on_every_note_during_an_edge_drag(page: Page, harness) -> None:
    ids = _open(page, harness)
    _start_drag(page, ids["a"], "right_0")
    assert _geometry(page, ids["b"], "top_0")["visibility"] == "visible"

    page.keyboard.press("Escape")
    page.wait_for_selector(f"{_CANVAS}:not(.edge-dragging)")
    page.mouse.move(5, 5)
    assert _geometry(page, ids["b"], "top_0")["visibility"] == "hidden"


def test_a_hidden_slot_is_a_drop_candidate(page: Page, harness) -> None:
    ids = _open(page, harness)
    _start_drag(page, ids["a"], "right_0")
    target = _geometry(page, ids["b"], "left_0")
    page.mouse.move(target["x"] - 20, target["y"], steps=4)
    page.mouse.move(target["x"], target["y"], steps=2)
    slot = _pin(ids["b"], "left_0")
    page.wait_for_selector(f"{slot}.connection-valid, {slot}.connection-compatible", timeout=2000)


def test_a_drop_near_a_side_grows_the_slot_on_that_side(page: Page, harness) -> None:
    ids = _open(page, harness)

    _start_drag(page, ids["a"], "right_0")
    target = _geometry(page, ids["b"], "left_0")
    page.mouse.move(target["card"]["left"] - 30, target["y"], steps=4)
    page.mouse.move(target["card"]["left"] - 6, target["y"], steps=2)
    page.mouse.down()
    page.mouse.up()
    page.wait_for_selector(_pin(ids["b"], "left_1"), state="attached")
    assert f"{ids['a']}[right_0]->{ids['b']}[left_0]" in _edge_ids(page)

    wait_for_canvas_settled(page)
    _start_drag(page, ids["a"], "bottom_0")
    target = _geometry(page, ids["b"], "top_0")
    page.mouse.move(target["x"], target["card"]["top"] - 30, steps=4)
    page.mouse.move(target["x"], target["card"]["top"] - 6, steps=2)
    page.mouse.down()
    page.mouse.up()
    page.wait_for_selector(_pin(ids["b"], "top_1"), state="attached")
    assert f"{ids['a']}[bottom_0]->{ids['b']}[top_0]" in _edge_ids(page)


def test_double_click_opens_the_text_modal(page: Page, harness) -> None:
    ids = _open(page, harness)
    x, y = _card_centre(page, ids["a"])
    page.mouse.dblclick(x, y)
    area = page.wait_for_selector("textarea", timeout=3000)
    assert area is not None
    assert area.input_value() == "hello"
    area.fill("a\nb")
    page.get_by_role("button", name="OK").click()
    page.wait_for_function(
        """(sel) => {
            const card = document.querySelector(sel)?.closest('.node-card');
            return !!card && card.innerText.includes('a\\nb');
        }""",
        arg=_pin(ids["a"], "top_0"),
        timeout=5000,
    )


def test_an_annotation_edge_draws_and_edits_its_style(page: Page, harness) -> None:
    _open(page, harness)
    computed = "(sel, prop) => getComputedStyle(document.querySelector(sel))[prop]"
    assert "-arrow" in page.evaluate(f"([s, p]) => ({computed})(s, p)", [_LINKED, "markerEnd"])
    assert page.evaluate(f"([s, p]) => ({computed})(s, p)", [_LINKED, "markerStart"]) == "none"

    page.click('[data-testid="style-start-circle"]')
    page.wait_for_function(
        f"(s) => ({computed})(s, 'markerStart').includes('-circle')", arg=_LINKED, timeout=5000
    )
    page.click('[data-testid="style-color-red"]')
    page.wait_for_function(
        f"(s) => ({computed})(s, 'stroke') === 'rgb(255, 0, 0)'", arg=_LINKED, timeout=5000
    )


def test_control_pins_draw_only_when_switched_on(page: Page, harness) -> None:
    ids = _open(page, harness)
    assert page.query_selector(_pin(ids["a"], "exec")) is None
    page.click('[data-testid="show-control"]')
    page.wait_for_selector(_pin(ids["a"], "exec"), timeout=5000)
    page.wait_for_selector(_pin(ids["a"], "done"), timeout=5000)
