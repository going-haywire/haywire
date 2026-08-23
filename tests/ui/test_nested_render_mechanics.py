"""Proofs for the nested-render mechanics ADR-0029's surface model rests on.

Three framework behaviours the surface model assumes, none of which had coverage
and all of which were previously asserted from reading code:

1. A ``ContextVar`` scoped around a render survives NiceGUI's slot stack, so the
   render path and the leaf counter can be accumulated across nesting depth.
2. A closed ``ui.menu`` still *holds* its children server-side while rendering
   nothing to the client — the "built eagerly, lazy in the DOM" property that
   lets a hosting panel draw a flyout's panels during its own ``draw()``.
3. An element can be restyled *after* its children are built, which is what lets
   a submenu row grey itself once it knows its body drew nothing.

The implementations these support (``render_surface``, the leaf counter,
``SubmenuRow``) do not exist yet; these pin the mechanics they will be built on.
See ``docs/superpowers/plans/2026-08-23-surface-model.md``, Stage 0.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextvars import ContextVar

import pytest
from nicegui import ui
from nicegui.element import Element
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

_leaves_drawn: ContextVar[int] = ContextVar("_leaves_drawn", default=0)
_render_path: ContextVar[tuple[str, ...]] = ContextVar("_render_path", default=())


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests on the asyncio backend."""
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    """A NiceGUI ``User`` simulator without the user_plugin's main_file requirement."""
    async with user_simulation() as u:
        yield u


@pytest.mark.unit
@pytest.mark.anyio
async def test_contextvars_accumulate_across_nested_slots(user: User) -> None:
    """The counter and the render path both survive NiceGUI's slot stack.

    Element construction inside ``with`` blocks is synchronous on the calling
    task, so a ContextVar set by an outer host is visible to arbitrarily deep
    nested rendering and restores cleanly on the way out. If this were not true,
    the leaf counter would read zero for every nested panel and every menu would
    look empty — silently, since an empty menu is a legitimate outcome.
    """
    seen: dict[str, object] = {}

    def draw_leaf(label: str) -> None:
        ui.label(label)
        _leaves_drawn.set(_leaves_drawn.get() + 1)

    def render_surface(surface_id: str, depth: int) -> None:
        """Stand-in for the real thing: push the path, draw, recurse, pop."""
        token = _render_path.set((*_render_path.get(), surface_id))
        try:
            with ui.column():
                draw_leaf(f"leaf at {surface_id}")
                if depth > 0:
                    with ui.menu():  # a flyout: a new slot, a deeper level
                        render_surface(f"{surface_id}-child", depth - 1)
            seen[f"path@{surface_id}"] = _render_path.get()
        finally:
            _render_path.reset(token)

    @ui.page("/")
    def page() -> None:
        outer = _leaves_drawn.set(0)
        try:
            render_surface("root", depth=2)
            seen["leaves"] = _leaves_drawn.get()
        finally:
            _leaves_drawn.reset(outer)
        seen["after"] = _leaves_drawn.get()

    await user.open("/")

    # Three levels, one leaf each — counted through two nested slots.
    assert seen["leaves"] == 3
    # The path is depth-correct at each level, and unwinds.
    assert seen["path@root"] == ("root",)
    assert seen["path@root-child"] == ("root", "root-child")
    assert seen["path@root-child-child"] == ("root", "root-child", "root-child-child")
    # The outer scope is restored, so one render cannot bleed into the next.
    assert seen["after"] == 0
    assert _render_path.get() == ()


@pytest.mark.unit
@pytest.mark.anyio
async def test_closed_menu_holds_children_but_renders_nothing(user: User) -> None:
    """A flyout's panels exist server-side while the menu is closed.

    ``Menu._render_markdown`` returns ``''`` unless ``value`` is truthy, so a
    closed flyout contributes no client DOM — but its children are real elements
    on the server. That split is what makes eager building correct: panels are
    polled and drawn during the hosting panel's ``draw()``, on the render stack,
    inside the error boundary, and the client simply does not see them until the
    user hovers.
    """
    captured: dict[str, Element] = {}
    menus: dict[str, ui.menu] = {}

    @ui.page("/")
    def page() -> None:
        menu = ui.menu()
        with menu:
            captured["child"] = ui.label("a panel drew this into the flyout")
        menus["menu"] = menu

    await user.open("/")

    menu = menus["menu"]
    assert menu.value is False, "flyout should start closed"
    assert captured["child"] in menu.default_slot.children, "child not held server-side"
    assert menu._render_markdown() == "", "closed menu should contribute no client DOM"

    # Opening reveals the same children — nothing is rebuilt.
    menu.open()
    assert menu._render_markdown() != ""
    assert captured["child"] in menu.default_slot.children


@pytest.mark.unit
@pytest.mark.anyio
async def test_element_can_be_restyled_after_its_children_are_built(user: User) -> None:
    """A row can grey itself once it knows what landed inside it.

    ``SubmenuRow.__exit__`` decides the anchor's enabled state *after* the body
    has rendered, using the leaf counter. That requires mutating an element whose
    children already exist, and leaving those children untouched.
    """
    captured: dict[str, Element] = {}

    @ui.page("/")
    def page() -> None:
        with ui.row() as anchor:
            captured["child"] = ui.label("row label")
        # Body drew nothing worth keeping — grey the anchor retroactively.
        anchor.classes(add="hw-disabled").style("opacity: 0.4; pointer-events: none")
        captured["anchor"] = anchor

    await user.open("/")

    anchor = captured["anchor"]
    assert "hw-disabled" in anchor._classes
    assert anchor._style.get("opacity") == "0.4"
    assert anchor._style.get("pointer-events") == "none"
    # The child is untouched — greying the row must not restyle its contents.
    assert captured["child"]._classes == []
    assert captured["child"]._style == {}
