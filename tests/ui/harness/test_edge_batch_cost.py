"""A graph's edges must reach the client in a message count independent of N.

Opening a graph used to emit one websocket message per edge — ``UIEdge`` synced
itself from its own constructor, so 672 edges meant 672 ``run_method`` frames.
Nothing about the drawing was slow: the whole client-side edge chain measured
384 ms across those 672 messages. The cost was the messages themselves, which
run roughly 0.15 ms per mounted node each whatever they carry, making a graph
open O(nodes x edges). Measured on a 128-node/672-edge graph: 18.9 s for the
edges to appear, against 161 ms once they arrived in a single message. A
256-node/1344-edge graph went from 60.9 s to 8.8 s.

Counting messages rather than timing the open, for the same reason as
``test_edge_drag_cost.py``: a timing threshold on this canvas flakes — four runs
of one identical 128-node config measured 17.2 s, 18.3 s, 18.9 s and 27.2 s —
while the regression signature here is exact. The count either stays flat as the
edge count grows, or it tracks it.

Two sizes, deliberately. A single size can only assert "few messages", which a
per-edge emitter passes on any small fixture; it takes a second size to assert
the thing that actually matters, that the count does not scale.
"""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready

_URL = "http://localhost:8090/graph-edge-batch"

pytestmark = pytest.mark.ui

#: Edge counts to compare. Far enough apart that a per-edge emitter cannot
#: land on the same count twice, small enough that the page still builds fast.
_FEW = 4
_MANY = 32

#: Counts every websocket frame carrying edges, under either sync event, so a
#: revert to per-edge emission is caught rather than missed because the event
#: name changed.
#:
#: Registered ONCE and re-run by the browser on each navigation — which is both
#: how the counter gets in before the page's own websocket opens, and how it
#: resets between the two loads. Registering it per navigation instead stacks
#: the wrappers, and the second load then counts every frame twice.
COUNTER = """
(() => {
  window.__edgeMsgs = 0;
  const Orig = window.WebSocket;
  window.WebSocket = function (...a) {
    const ws = new Orig(...a);
    ws.addEventListener('message', (ev) => {
      const d = ev.data;
      if (typeof d !== 'string') return;
      if (d.indexOf('syncAllEdges') !== -1 || d.indexOf('syncEdgeAddition') !== -1) {
        window.__edgeMsgs++;
      }
    }, true);
    return ws;
  };
  window.WebSocket.prototype = Orig.prototype;
  Object.assign(window.WebSocket, Orig);
})();
"""


def _open_and_count(page: Page, edges: int) -> int:
    """Load the fixture with `edges` edges; return the edge messages it took."""
    goto_ready(page, f"{_URL}?edges={edges}")
    page.wait_for_selector("[data-node-id]")
    page.wait_for_function(
        """(n) => {
            const svg = document.getElementById('connection-svg');
            if (!svg) return false;
            // Two paths per edge: the visible stroke and its hit area.
            return svg.querySelectorAll('path[data-edge-id]').length >= n * 2;
        }""",
        arg=edges,
    )
    return page.evaluate("() => window.__edgeMsgs")


def test_edge_sync_message_count_does_not_grow_with_edge_count(page: Page, harness) -> None:
    page.add_init_script(COUNTER)

    few = _open_and_count(page, _FEW)
    many = _open_and_count(page, _MANY)

    assert few > 0, "no edge sync message was seen at all — the fixture drew no edges"

    # The invariant is a CONSTANT number of messages, not merely a small one:
    # a per-edge emitter reports _FEW and _MANY here.
    assert many == few, (
        f"{many} edge sync messages for {_MANY} edges, but {few} for {_FEW}. "
        f"The message count is tracking the edge count, which is the per-edge "
        f"emit this batching replaced — it made a 128-node/672-edge graph take "
        f"18.9 s to draw its edges instead of 161 ms. Edges added in one "
        f"validation pass must go out in a single SyncAllEdgesEvent "
        f"(VisualLayerHandlers.on_validated)."
    )

    # A second guard on the absolute number: `many == few` also holds if some
    # future change emitted a fixed but silly number of messages per open.
    assert many <= 2, (
        f"{many} edge sync messages to open a {_MANY}-edge graph. One pass "
        f"should emit one batched event; more than a couple means edges are "
        f"being synced in several passes."
    )
