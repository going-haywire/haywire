"""The rail skin seats its pins on the card edge and renders root ghost pins.

Geometry is measured against the card's own box, so a change to the pin gutter
or the card padding does not move the assertion.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready

pytestmark = pytest.mark.browser

#: Distance a pin centre may sit from the card edge. The filled `add_circle`
#: glyph draws inset within its em-box, so a slot reads further in than a
#: `circle` pin at the same offset.
_TOLERANCE = 12


def _pins(page: Page) -> list[dict]:
    """Every pin on every boundary node, with its inset from the card edge."""
    return page.evaluate(
        """() => [...document.querySelectorAll('[data-node-id]')].flatMap(n => {
            const card = n.querySelector('.node-card');
            if (!card) return [];
            const c = card.getBoundingClientRect();
            return [...n.querySelectorAll('.connection-pin')].map(p => {
                const r = p.getBoundingClientRect();
                const cx = r.left + r.width / 2;
                return {
                    node: n.id,
                    pin: p.dataset.pinId,
                    flow: p.dataset.pinFlowType,
                    inset: p.dataset.pinDir === 'inlet' ? cx - c.left : c.right - cx,
                };
            });
        })"""
    )


def test_every_pin_sits_on_the_card_edge(page: Page, harness) -> None:
    goto_ready(page, f"{harness}/graph-boundary")
    pins = _pins(page)
    assert pins, "the boundary nodes rendered no pins"

    for row in pins:
        assert abs(row["inset"]) <= _TOLERANCE, (
            f"{row['pin']} on {row['node']} sits {row['inset']:.1f}px from the card edge, not on it"
        )


def test_both_boundary_nodes_render_a_root_ghost_pin(page: Page, harness) -> None:
    """An edge whose port is removed falls back to the ghost, so it stays on the card."""
    goto_ready(page, f"{harness}/graph-boundary")

    ghosts = {(r["node"], r["pin"]) for r in _pins(page) if r["flow"] == "ghost"}

    assert any(pin == "root_out" for _node, pin in ghosts), "the Subgraph Input has no outlet ghost"
    assert any(pin == "root_in" for _node, pin in ghosts), "the Subgraph Output has no inlet ghost"


def test_a_ghost_pin_sits_on_the_edge_like_a_real_pin(page: Page, harness) -> None:
    goto_ready(page, f"{harness}/graph-boundary")

    for row in _pins(page):
        if row["flow"] == "ghost":
            assert abs(row["inset"]) <= 2, f"ghost {row['pin']} sits {row['inset']:.1f}px from the card edge"


def test_the_growing_slot_renders_a_pin(page: Page, harness) -> None:
    goto_ready(page, f"{harness}/graph-boundary")

    slots = [r for r in _pins(page) if r["pin"].startswith("slot_")]

    assert len(slots) == 2, f"expected one growing slot per boundary node, got {slots}"
