"""canvas.vue ``_wiresMatch`` mirrors ``wires_match`` in core/types/wire.py.

The canvas decides in the browser whether two pins may link, from their
``data-pin-wire`` keys, so the rule is checked on the live component.
"""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled

_PATH = "/graph-connect"

pytestmark = pytest.mark.ui

_CALL = """(args) => {
    // The page is one Vue app; walk its vnode tree to the component that owns _wiresMatch.
    // Relies on Vue internals (__vue_app__._container, vnode fields); a Vue upgrade may break it.
    const stack = [document.querySelector('#app').__vue_app__._container._vnode];
    while (stack.length) {
        const vnode = stack.pop();
        if (!vnode) continue;
        const proxy = vnode.component && vnode.component.proxy;
        if (proxy && typeof proxy._wiresMatch === 'function') return proxy._wiresMatch(args[0], args[1]);
        if (vnode.component) stack.push(vnode.component.subTree);
        if (Array.isArray(vnode.children)) stack.push(...vnode.children);
        if (vnode.dynamicChildren) stack.push(...vnode.dynamicChildren);
    }
    throw new Error('canvas component not reachable');
}"""


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("a", "a", True),
        ("a", "b", False),
        ("*", "a", True),
        ("a", "*", True),
        ("*", "*", False),
        (None, "a", False),
        ("", "a", False),
    ],
)
def test_wires_match_rule(page: Page, harness, a, b, expected):
    goto_ready(page, f"{harness}{_PATH}")
    page.wait_for_selector("[data-node-id]")
    wait_for_canvas_settled(page)

    assert page.evaluate(_CALL, [a, b]) is expected
