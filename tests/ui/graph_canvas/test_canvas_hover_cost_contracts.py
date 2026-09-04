"""Two rules in canvas.vue that keep a hover crossing cheap.

Both are one-token changes that look harmless, cost nothing at rest, and only
show up as a framerate collapse while the user is doing something else. Neither
can be caught by rendering a card, so they are checked against the source —
the same posture ADR 0032 takes with its source-inspection test over in-repo
skins.

They were found together, wiring an edge on a 300-node graph: the move handler
rewrites pin classes on every mousemove, `transition: all` turned each rewrite
into a bundle of transitions, and `transitionstart` BUBBLES, so those arrived
at the node card's own listener — which cannot tell them from the magnifier's
and answers each with `_scheduleEdgeUpdates`, i.e. seven whole-edge-map sweeps
for a pin glow.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

_CANVAS = (
    Path(__file__).resolve().parents[3] / "packages/haywire-core/src/haywire/ui/components/graph/canvas.vue"
)


@pytest.fixture(scope="module")
def source() -> str:
    assert _CANVAS.exists(), f"canvas.vue not found at {_CANVAS}"
    return _CANVAS.read_text(encoding="utf-8")


def test_connection_pin_never_transitions_all(source: str) -> None:
    """`transition: all` on a pin animates every computed change it receives.

    The edge-drag move handler rewrites pin classes constantly while a wire is
    open, so `all` turns each rewrite into a bundle of transitions instead of
    the one or two properties the rules below it actually animate.
    """
    block = re.search(r"\.connection-pin\s*\{(.*?)\}", source, re.S)
    assert block, "no `.connection-pin` rule found in canvas.vue"
    transition = re.search(r"transition\s*:\s*([^;]+);", block.group(1))
    assert transition, "`.connection-pin` declares no transition — check this rule still exists"
    value = transition.group(1)
    assert not re.match(r"\s*all\b", value), (
        f"`.connection-pin` uses `transition: {value.strip()}`. Name the "
        f"properties instead: with a wire open, pin classes are rewritten on "
        f"every mousemove, and `all` makes each rewrite a bundle of transitions "
        f"whose transitionstart events bubble to the node card."
    )


def test_the_card_transitionstart_listener_filters_by_target(source: str) -> None:
    """The card's listener must ignore transitions from its descendants.

    `transitionstart` bubbles, and a card is full of elements that animate
    `transform` — every `.connection-pin` does, on hover and on
    connection-valid/compatible. Without a target check each one reaches
    `_scheduleEdgeUpdates`, which is one edge-map sweep plus six more on timers.
    """
    listener = re.search(r"addEventListener\(\s*['\"]transitionstart['\"].*?\n(.{0,400})", source, re.S)
    assert listener, "no `transitionstart` listener found in canvas.vue"
    assert re.search(r"\.target\s*!==", listener.group(1)), (
        "the transitionstart listener does not compare `.target` against the "
        "element it is bound to. Without that, a pin's hover transition — which "
        "bubbles — triggers a full _scheduleEdgeUpdates (7 edge-map sweeps) for "
        "a cosmetic effect."
    )
