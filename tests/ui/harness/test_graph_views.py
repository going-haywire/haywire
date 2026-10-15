"""A level's Patch and Stage views, switched in a real browser.

Drives the ``/graph-views`` harness route: a real ``GraphEditor`` level with two linked annotation
nodes on the stage. Both views hold those two nodes, with the same page-global pin ids, so the
switch is only correct if the hidden canvas's DOM is detached and the shown one measures its own
pins. Asserted in a browser because the edge geometry and the keep-alive behaviour are the
layout engine's and Quasar's.
"""

import time

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled
from tests.ui.harness.pin_edge import PIN_EDGE_JS

pytestmark = pytest.mark.ui

#: A view's worst endpoint may sit this many screen px further from its pin's edge than the
#: first patch draw's worst does. An arrow head stops a few px short of the pin, so that first draw,
#: not zero, is the reference; a wrong measurement is tens of px out.
_SLACK_PX = 4.0

#: The arrow head's own inset, the most the reference draw may be off.
_MAX_BASELINE_PX = 12.0

#: Edge paths of the one canvas in the DOM (the other view's tree is detached), hit areas excluded.
_PATH_COUNT = """
() => Array.from(
    document.querySelectorAll('.graph-canvas .connection-svg path[data-edge-id]')
).filter(p => !p.id.endsWith('_hitarea')).length
"""

_ENDPOINTS_VS_PINS = (
    """
() => {%s
    const out = [];
    document.querySelectorAll('.graph-canvas .connection-svg path[data-edge-id]').forEach(p => {
        if (p.id.endsWith('_hitarea')) return;
        const ctm = p.getScreenCTM();
        if (!ctm) return;
        const m = /^(.*)\\[(.*)\\]->(.*)\\[(.*)\\]$/.exec(p.id);
        if (!m) return;
        const at = (len) => {
            const q = p.getPointAtLength(len);
            return { x: q.x * ctm.a + q.y * ctm.c + ctm.e, y: q.x * ctm.b + q.y * ctm.d + ctm.f };
        };
        const outlet = document.getElementById(`${m[2]}@${m[1]}`);
        const inlet = document.getElementById(`${m[4]}@${m[3]}`);
        out.push({
            start: at(0),
            end: at(p.getTotalLength()),
            outlet: outlet ? pinEdge(outlet, ctm) : null,
            inlet: inlet ? pinEdge(inlet, ctm) : null,
        });
    });
    return out;
}
"""
    % PIN_EDGE_JS
)

# Several elements of one card carry its id, so count distinct ids.
_NODE_COUNT = (
    "() => new Set(Array.from(document.querySelectorAll('.graph-canvas [data-node-id]'))"
    ".map(e => e.dataset.nodeId)).size"
)


def _errors(page: Page) -> list[float]:
    """Distance in screen px between each drawn endpoint and the edge of the pin it joins."""
    errors: list[float] = []
    for row in page.evaluate(_ENDPOINTS_VS_PINS):
        for drawn, pin in ((row["start"], row["outlet"]), (row["end"], row["inlet"])):
            assert pin is not None, "an edge's pin is not in the DOM"
            errors.append(((drawn["x"] - pin["x"]) ** 2 + (drawn["y"] - pin["y"]) ** 2) ** 0.5)
    return errors


def _wait_on_pins(page: Page, edges: int, limit: float, timeout_s: float = 8.0) -> list[float]:
    """Poll until ``edges`` edges are drawn and every endpoint sits on its pin, or the budget runs out."""
    deadline = time.monotonic() + timeout_s
    while True:
        drawn = page.evaluate(_PATH_COUNT)
        errors = _errors(page) if drawn == edges else []
        if (errors and max(errors) < limit) or time.monotonic() > deadline:
            return errors
        page.wait_for_timeout(100)


def _show(page: Page, view: str, nodes: int, edges: int, limit: float) -> list[float]:
    """Click the header switch for ``view`` and wait for its nodes and edges, on their pins."""
    page.get_by_role("button", name=view.capitalize(), exact=True).click()
    page.wait_for_function(f"() => ({_NODE_COUNT})() === {nodes}", timeout=10_000)
    page.wait_for_function("() => document.querySelectorAll('.graph-canvas').length === 1", timeout=10_000)
    wait_for_canvas_settled(page)
    return _wait_on_pins(page, edges, limit)


def _baseline(page: Page) -> float:
    """The worst endpoint error of the patch's first draw, plus the slack: the limit for every later draw."""
    errors = _wait_on_pins(page, 2, _MAX_BASELINE_PX)
    assert errors, "no edges drawn"
    assert max(errors) < _MAX_BASELINE_PX, errors
    return max(errors) + _SLACK_PX


def test_switching_views_redraws_each_views_edges_on_their_own_pins(page: Page, harness):
    goto_ready(page, f"{harness}/graph-views")
    page.wait_for_function(f"() => ({_NODE_COUNT})() === 4", timeout=10_000)
    wait_for_canvas_settled(page)
    limit = _baseline(page)

    # Stamp a patch card; if the patch is re-rendered on the way back, the stamp is gone.
    stamped = page.evaluate(
        "() => { const el = document.querySelector('.graph-canvas [data-node-id]');"
        " el.setAttribute('data-marker', '1'); return el.dataset.nodeId; }"
    )

    for _ in range(2):
        stage_errors = _show(page, "stage", nodes=2, edges=2, limit=limit)
        assert stage_errors, "the stage drew no edges"
        assert max(stage_errors) < limit, f"stage: {max(stage_errors):.1f}px from a pin"

        patch_errors = _show(page, "patch", nodes=4, edges=2, limit=limit)
        assert patch_errors, "the patch drew no edges"
        assert max(patch_errors) < limit, f"patch: {max(patch_errors):.1f}px from a pin"
        survivor = page.evaluate(
            "(id) => { const el = document.querySelector('.graph-canvas [data-marker]');"
            " return el && el.dataset.nodeId === id; }",
            stamped,
        )
        assert survivor, "the patch card was re-rendered: its marker did not survive the round trip"


def test_a_level_opens_on_the_stage_when_asked(page: Page, harness):
    goto_ready(page, f"{harness}/graph-views?view=stage")
    page.wait_for_function(f"() => ({_NODE_COUNT})() === 2", timeout=10_000)
    wait_for_canvas_settled(page)
    limit = _baseline(page)

    patch_errors = _show(page, "patch", nodes=4, edges=2, limit=limit)
    assert patch_errors, "no edges drawn"
    assert max(patch_errors) < limit, patch_errors


def test_the_header_switch_styles_the_active_view_apart(page: Page, harness):
    goto_ready(page, f"{harness}/graph-views")
    wait_for_canvas_settled(page)
    patch = page.get_by_role("button", name="Patch", exact=True)
    stage = page.get_by_role("button", name="Stage", exact=True)
    style = "(el) => { const s = getComputedStyle(el); return [s.color, s.backgroundColor, s.boxShadow]; }"

    assert patch.get_attribute("aria-pressed") == "true"
    assert stage.get_attribute("aria-pressed") == "false"
    assert patch.evaluate(style) != stage.evaluate(style)

    stage.click()
    page.wait_for_function(
        "() => [...document.querySelectorAll('button')].some("
        "b => b.textContent.trim() === 'Stage' && b.getAttribute('aria-pressed') === 'true')"
    )
    assert patch.get_attribute("aria-pressed") == "false"
    assert patch.evaluate(style) != stage.evaluate(style)


_CARD_POSITIONS = """
() => {
    const out = {};
    document.querySelectorAll('.graph-canvas [data-node-id]').forEach(el => {
        if (el.style.left && el.style.top) {
            out[el.dataset.nodeId] = [parseFloat(el.style.left), parseFloat(el.style.top)];
        }
    });
    return out;
}
"""

#: A stage canvas lays its nodes out from this canvas offset (``STAGE.origin``).
_STAGE_ORIGIN = 200.0


def test_a_hidden_stage_follows_membership_moves_and_deletes(page: Page, harness):
    import json

    goto_ready(page, f"{harness}/graph-views")
    page.wait_for_function(f"() => ({_NODE_COUNT})() === 4", timeout=10_000)
    wait_for_canvas_settled(page)
    limit = _baseline(page)
    # Mount the stage once, then hide it again behind the patch.
    _show(page, "stage", nodes=2, edges=2, limit=limit)
    _show(page, "patch", nodes=4, edges=2, limit=limit)

    # With the stage hidden: add a node to it, link it, move one stage node, delete another.
    patch_before = page.evaluate(_CARD_POSITIONS)
    page.get_by_test_id("views-mutate").click()
    page.wait_for_function(
        "() => document.querySelector('[data-testid=\"views-expected\"]').textContent.length > 0",
        timeout=10_000,
    )
    expected = json.loads(page.get_by_test_id("views-expected").text_content() or "{}")
    assert len(expected) == 2, expected

    # The patch keeps its own layout: a stage move must not reach the patch's cards.
    page.wait_for_function(f"() => ({_NODE_COUNT})() === 3", timeout=10_000)
    patch_after = page.evaluate(_CARD_POSITIONS)
    assert patch_after == {k: v for k, v in patch_before.items() if k in patch_after}, patch_after

    errors = _show(page, "stage", nodes=2, edges=1, limit=limit)
    assert errors, "the stage drew no edge"
    assert max(errors) < limit, f"stage: {max(errors):.1f}px from a pin"

    shown = page.evaluate(_CARD_POSITIONS)
    assert set(shown) == set(expected), (shown, expected)
    for node_id, (sx, sy) in expected.items():
        assert shown[node_id] == pytest.approx([sx + _STAGE_ORIGIN, sy + _STAGE_ORIGIN], abs=1.0), node_id


_CARD_IDS = (
    "() => [...new Set(Array.from(document.querySelectorAll('.graph-canvas [data-node-id]'))"
    ".map(e => e.dataset.nodeId))]"
)

_SELECTED_CARDS = """
() => [...new Set(Array.from(document.querySelectorAll('.graph-canvas .node-selected'))
    .map(e => e.dataset.nodeId))].sort()
"""


def _card_ids(page: Page) -> list[str]:
    return sorted(page.evaluate(_CARD_IDS))


def _click_card(page: Page, node_id: str, *, shift: bool = False) -> None:
    box = page.locator(f'.graph-canvas [data-node-id="{node_id}"] .ui-node-slot').first.bounding_box()
    assert box is not None, node_id
    if shift:
        page.keyboard.down("Shift")
    page.mouse.click(box["x"] + 30, box["y"] + 14)
    if shift:
        page.keyboard.up("Shift")


def _wait_selected(page: Page, expected: list[str]) -> None:
    page.wait_for_function(
        "(ids) => JSON.stringify((" + _SELECTED_CARDS.strip() + ")()) === JSON.stringify(ids)",
        arg=sorted(expected),
        timeout=10_000,
    )


def test_the_selection_carries_across_patch_and_stage(page: Page, harness):
    goto_ready(page, f"{harness}/graph-views")
    page.wait_for_function(f"() => ({_NODE_COUNT})() === 4", timeout=10_000)
    wait_for_canvas_settled(page)
    limit = _baseline(page)
    patch_ids = _card_ids(page)
    _show(page, "stage", nodes=2, edges=2, limit=limit)
    stage_ids = _card_ids(page)
    _show(page, "patch", nodes=4, edges=2, limit=limit)
    on_stage, off_stage = stage_ids[0], next(n for n in patch_ids if n not in stage_ids)
    positions = page.evaluate(_CARD_POSITIONS)

    # A node shown in both views, plus one that only the patch shows.
    _click_card(page, on_stage)
    _click_card(page, off_stage, shift=True)
    _wait_selected(page, [on_stage, off_stage])

    _show(page, "stage", nodes=2, edges=2, limit=limit)
    _wait_selected(page, [on_stage])

    # Selecting the other stage node on the stage replaces the selection.
    other = stage_ids[1]
    _click_card(page, other)
    _wait_selected(page, [other])

    _show(page, "patch", nodes=4, edges=2, limit=limit)
    _wait_selected(page, [other])
    assert page.evaluate(_CARD_POSITIONS) == positions, "a selection change moved a patch card"


_CARD_SIZES = """
() => {
    const out = {};
    document.querySelectorAll('.graph-canvas .ui-node-slot').forEach(el => {
        const host = el.closest('[data-node-id]');
        if (host) out[host.dataset.nodeId] = [el.offsetWidth, el.offsetHeight];
    });
    return out;
}
"""


def test_a_stage_resize_leaves_the_patch_card_alone(page: Page, harness):
    goto_ready(page, f"{harness}/graph-views")
    page.wait_for_function(f"() => ({_NODE_COUNT})() === 4", timeout=10_000)
    wait_for_canvas_settled(page)
    limit = _baseline(page)
    _show(page, "stage", nodes=2, edges=2, limit=limit)
    stage_ids = _card_ids(page)
    _show(page, "patch", nodes=4, edges=2, limit=limit)
    patch_sizes = page.evaluate(_CARD_SIZES)
    patch_positions = page.evaluate(_CARD_POSITIONS)

    node = stage_ids[0]
    _show(page, "stage", nodes=2, edges=2, limit=limit)
    wait_for_canvas_settled(page)
    stage_size = page.evaluate(_CARD_SIZES)[node]
    _click_card(page, node)
    _wait_selected(page, [node])
    grip = page.locator('.hw-resize-grip[data-handle="right"]')
    grip.wait_for()
    wait_for_canvas_settled(page)
    box = grip.bounding_box()
    assert box is not None
    # Grab near the grip's top, not its centre: a node's output pin straddles the right border at
    # mid-height, and a pin under the cursor takes the gesture from the grip (a connection drag,
    # not a resize). Which node `stage_ids[0]` is varies per run (random ids), so the mid-point
    # hit a pin about half the time.
    gx, gy = box["x"] + box["width"] / 2, box["y"] + 8
    page.mouse.move(gx, gy)
    page.mouse.down()
    page.mouse.move(gx + 80, gy, steps=8)
    page.mouse.up()
    page.wait_for_function(
        "([nid, w]) => {"
        ' const s = document.querySelector(`.graph-canvas [data-node-id="${nid}"] .ui-node-slot`);'
        " return s && s.offsetWidth > w + 20; }",
        arg=[node, stage_size[0]],
        timeout=10_000,
    )
    resized = page.evaluate(_CARD_SIZES)[node]

    _show(page, "patch", nodes=4, edges=2, limit=limit)
    _wait_selected(page, [node])
    assert page.evaluate(_CARD_SIZES) == patch_sizes, "a stage resize changed a patch card's size"
    assert page.evaluate(_CARD_POSITIONS) == patch_positions, "a stage resize moved a patch card"

    _show(page, "stage", nodes=2, edges=2, limit=limit)
    assert page.evaluate(_CARD_SIZES)[node] == pytest.approx(resized, abs=1.5)
