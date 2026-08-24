# tests/ui/panel/test_render_surface.py
"""Direct tests for ``BasePanel.render_surface`` — the nesting call.

No file exercised this method directly before: coverage of its guard clauses
(declared-in-hosts, re-entry, surface gate, host-satisfies-provides, render)
previously came only transitively, through higher-level hosts like
``SessionContextMenuProvider`` and ``SelectionToolbarProvider``. Each guard is
a decision that fails silently if it regresses (ADR-0029), so this file pins
each one directly against a real ``PanelRegistry`` and real ``@panel``-
decorated classes, mounted via the same ``render_panel`` a host uses and
rendered on a real NiceGUI page — ``render_surface`` builds a real
``PanelLayout``/``ui.element`` and calls ``hui.error_label``, so a
MagicMock-only harness would not exercise the actual rendering path.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from types import SimpleNamespace
from typing import Protocol, runtime_checkable
from unittest.mock import MagicMock

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.core.library.identity import LibraryIdentity
from haywire.ui.panel import BasePanel, PanelRegistry, panel
from haywire.ui.panel.host_rendering import render_panel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.surface import Surface


_FAKE_LIBRARY_IDENTITY = LibraryIdentity(
    label="fake",
    version="0.1",
    folder_path="/tmp/fake",
    module_name="fake",
    name="fake",
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


def _make_ctx():
    """A stand-in SessionContext. None of these tests' surfaces/panels read
    ctx.data, so a bare namespace with a MagicMock data bag is enough.
    can_access always grants — access tiers are not what these tests probe."""
    return SimpleNamespace(
        data=MagicMock(), app=MagicMock(), session_id="t", can_access=lambda required: True
    )


def _mount_hosting_panel(hosting_cls, registry: PanelRegistry) -> PanelLayout:
    """Mount ``hosting_cls`` (a real @panel-decorated BasePanel with a
    non-empty hosts=) through render_panel, exactly as a host does — this is
    what puts a live ``_hw_registry`` on the instance so its own
    render_surface() calls resolve against ``registry``."""
    layout = PanelLayout(ui.column())
    render_panel(hosting_cls, _make_ctx(), layout, registry=registry)
    return layout


# ---------------------------------------------------------------------------
# 1. Declared? — rendering a surface not named in hosts=
# ---------------------------------------------------------------------------


class _UndeclaredSurface(Surface):
    id = "render_surface_test_undeclared_surface"


class _NoHostsSurface(Surface):
    id = "render_surface_test_no_hosts_surface"


@panel(
    surface=_NoHostsSurface,
    label="Sneaky",
    registry_id="rstest_sneaky_panel",
)
class _SneakyPanel(BasePanel):
    """Declares no hosts= at all, but tries to render one anyway — an
    authoring error render_surface must catch, not the registry."""

    def draw(self, ctx, layout):
        with layout:
            self.render_surface(_UndeclaredSurface, ctx)


@pytest.mark.unit
@pytest.mark.anyio
async def test_render_surface_of_a_surface_not_in_hosts_renders_error_and_draws_nothing(
    user: User,
) -> None:
    target_drew: list[bool] = []

    @panel(surface=_UndeclaredSurface, label="Ghost", registry_id="rstest_ghost_panel")
    class _GhostPanel(BasePanel):
        def draw(self, ctx, layout):
            target_drew.append(True)

    registry = PanelRegistry()
    registry._register_class(_SneakyPanel, _FAKE_LIBRARY_IDENTITY)
    registry._register_class(_GhostPanel, _FAKE_LIBRARY_IDENTITY)

    @ui.page("/")
    def page() -> None:
        _mount_hosting_panel(_SneakyPanel, registry)

    await user.open("/")

    # The target surface's own panel never drew.
    assert target_drew == []
    # An inline error rendered instead.
    user.find(kind=ui.label, content="does not declare hosts")


# ---------------------------------------------------------------------------
# 2. Re-entry guard — a surface rendering itself, one hop down
# ---------------------------------------------------------------------------


class _SelfHostingSurface(Surface):
    id = "render_surface_test_self_hosting_surface"


@pytest.mark.unit
@pytest.mark.anyio
async def test_render_surface_reentry_into_the_same_surface_renders_one_error_and_terminates(
    user: User,
) -> None:
    """render_surface's re-entry guard is the cycle *enforcement* (registration
    only logs — see test_panel_redraw_union.py for that half). A panel on
    _SelfHostingSurface that hosts _SelfHostingSurface again must not recurse
    unboundedly: the outermost mount (via render_panel, not render_surface)
    pushes nothing onto _render_path, so the panel's own first
    render_surface() call legitimately opens _SelfHostingSurface one level
    down (this is "the same surface twice side by side", explicitly allowed
    per host_rendering.py's _render_path docstring) — but that second
    instance's OWN render_surface() call closes the loop and the guard stops
    it there. Two draws happen, never a third."""
    draw_count: list[bool] = []

    @panel(
        surface=_SelfHostingSurface,
        hosts=(_SelfHostingSurface,),
        label="Recursive",
        registry_id="rstest_recursive_panel",
    )
    class _RecursivePanel(BasePanel):
        def draw(self, ctx, layout):
            draw_count.append(True)
            with layout:
                self.render_surface(_SelfHostingSurface, ctx)

    registry = PanelRegistry()
    registry._register_class(_RecursivePanel, _FAKE_LIBRARY_IDENTITY)

    @ui.page("/")
    def page() -> None:
        _mount_hosting_panel(_RecursivePanel, registry)

    await user.open("/")

    # Terminates rather than recursing forever: exactly two draws (the outer
    # mount, then the one nested level the empty starting path permits), and
    # the third attempt is refused with an inline error.
    assert draw_count == [True, True]
    user.find(kind=ui.label, content="already being rendered")


# ---------------------------------------------------------------------------
# 3. Host — piped, never inferred (member-less Protocol)
# ---------------------------------------------------------------------------


@runtime_checkable
class _MemberlessProtocol(Protocol):
    """No members at all — isinstance() against this is True for every
    object, including None. This is the case the first draft broke on: a
    structural check cannot distinguish 'implements this' from 'happens to
    satisfy a Protocol with nothing to check'."""


class _PipedSurface(Surface):
    id = "render_surface_test_piped_surface"
    provides = _MemberlessProtocol


class _PipedChildSurface(Surface):
    id = "render_surface_test_piped_child_surface"
    provides = _MemberlessProtocol


@pytest.mark.unit
@pytest.mark.anyio
async def test_host_pipe_carries_self_actions_by_default(user: User) -> None:
    """The pipe case: a layout-only panel's self.actions (received from ITS
    OWN host) is what a nested surface's panels receive — never the piping
    panel instance itself, even though it structurally satisfies a
    member-less Protocol."""
    captured_actions: list[object] = []

    @panel(surface=_PipedChildSurface, label="Reader", registry_id="rstest_piped_reader_panel")
    class _ReaderPanel(BasePanel):
        def draw(self, ctx, layout):
            captured_actions.append(self.actions)

    @panel(
        surface=_PipedSurface,
        hosts=(_PipedChildSurface,),
        label="Piping2",
        registry_id="rstest_piping_panel_2",
    )
    class _PipingPanel2(BasePanel):
        def draw(self, ctx, layout):
            with layout:
                self.render_surface(_PipedChildSurface, ctx)

    registry = PanelRegistry()
    registry._register_class(_PipingPanel2, _FAKE_LIBRARY_IDENTITY)
    registry._register_class(_ReaderPanel, _FAKE_LIBRARY_IDENTITY)

    outer_host = object()

    @ui.page("/")
    def page() -> None:
        layout = PanelLayout(ui.column())
        render_panel(_PipingPanel2, _make_ctx(), layout, actions_host=outer_host, registry=registry)

    await user.open("/")

    # self.actions piped down is the OUTER host, never the _PipingPanel2
    # instance — proving the host is piped, not inferred from structural
    # satisfaction of the (member-less, universally-satisfied) Protocol.
    assert captured_actions == [outer_host]
    assert captured_actions[0] is not None
    assert not isinstance(captured_actions[0], _PipingPanel2)


# ---------------------------------------------------------------------------
# 4. Host — must satisfy the target surface's provides
# ---------------------------------------------------------------------------


@runtime_checkable
class _RequiresVerbProtocol(Protocol):
    def required_verb(self) -> None: ...


class _RequiresVerbSurface(Surface):
    id = "render_surface_test_requires_verb_surface"
    provides = _RequiresVerbProtocol


@panel(surface=_RequiresVerbSurface, label="NeedsVerb", registry_id="rstest_needs_verb_panel")
class _NeedsVerbPanel(BasePanel):
    def draw(self, ctx, layout):
        pass


@pytest.mark.unit
@pytest.mark.anyio
async def test_render_surface_errors_when_the_chosen_host_does_not_satisfy_provides(
    user: User,
) -> None:
    target_drew: list[bool] = []

    @panel(
        surface=_RequiresVerbSurface,
        label="NeedsVerbSpy",
        registry_id="rstest_needs_verb_spy_panel",
    )
    class _SpyPanel(BasePanel):
        def draw(self, ctx, layout):
            target_drew.append(True)

    @panel(
        surface=_PipedSurface,
        hosts=(_RequiresVerbSurface,),
        label="BadHostPanel",
        registry_id="rstest_bad_host_panel",
    )
    class _BadHostPanel(BasePanel):
        def draw(self, ctx, layout):
            with layout:
                # self.actions is None (no host injected) — does not satisfy
                # _RequiresVerbProtocol.
                self.render_surface(_RequiresVerbSurface, ctx)

    registry = PanelRegistry()
    registry._register_class(_BadHostPanel, _FAKE_LIBRARY_IDENTITY)
    registry._register_class(_SpyPanel, _FAKE_LIBRARY_IDENTITY)

    @ui.page("/")
    def page() -> None:
        _mount_hosting_panel(_BadHostPanel, registry)

    await user.open("/")

    assert target_drew == []
    user.find(kind=ui.label, content="does not satisfy")


@pytest.mark.unit
@pytest.mark.anyio
async def test_render_surface_succeeds_when_the_chosen_host_satisfies_provides(user: User) -> None:
    target_drew: list[bool] = []

    class _GoodHost:
        def required_verb(self) -> None: ...

    @panel(
        surface=_RequiresVerbSurface,
        label="NeedsVerbSpy2",
        registry_id="rstest_needs_verb_spy_panel_2",
    )
    class _SpyPanel2(BasePanel):
        def draw(self, ctx, layout):
            target_drew.append(True)

    @panel(
        surface=_PipedSurface,
        hosts=(_RequiresVerbSurface,),
        label="GoodHostPanel",
        registry_id="rstest_good_host_panel",
    )
    class _GoodHostPanel(BasePanel):
        def draw(self, ctx, layout):
            with layout:
                self.render_surface(_RequiresVerbSurface, ctx, actions=_GoodHost())

    registry = PanelRegistry()
    registry._register_class(_GoodHostPanel, _FAKE_LIBRARY_IDENTITY)
    registry._register_class(_SpyPanel2, _FAKE_LIBRARY_IDENTITY)

    @ui.page("/")
    def page() -> None:
        _mount_hosting_panel(_GoodHostPanel, registry)

    await user.open("/")

    assert target_drew == [True]


# ---------------------------------------------------------------------------
# Emptiness after nesting: the inverse — a leaf two levels down is enough
# ---------------------------------------------------------------------------


class _InverseEmptinessLevelOne(Surface):
    id = "render_surface_test_inverse_emptiness_level_one"


class _InverseEmptinessLevelTwo(Surface):
    id = "render_surface_test_inverse_emptiness_level_two"


class _InverseEmptinessRoot(Surface):
    id = "render_surface_test_inverse_emptiness_root"


@pytest.mark.unit
@pytest.mark.anyio
async def test_leaf_two_levels_down_is_enough_to_open_the_menu(user: User) -> None:
    """The counterpart to ``test_a_tree_that_draws_nothing_deletes_the_popup``
    (tests/ui/test_canvas_handlers/test_session_context_menu_provider.py): a
    root holding only a hosting panel, whose hosted surface holds only ANOTHER
    hosting panel, whose hosted surface finally holds one real leaf that polls
    true — is enough for the leaf counter to register non-zero. Two levels of
    pure layout panels must not by themselves make the tree read as empty.
    Uses ``counting_leaves()`` directly (the same counter the popup-emptiness
    decision reads) rather than a host, since no host in-tree nests exactly
    two hop levels of pure layout the way this needs to isolate the case."""
    from haywire.ui.panel.host_rendering import counting_leaves

    leaf_drew: list[bool] = []

    @panel(
        surface=_InverseEmptinessLevelTwo,
        label="Leaf",
        registry_id="rstest_inverse_emptiness_leaf",
    )
    class _LeafPanel(BasePanel):
        def draw(self, ctx, layout):
            with layout:
                leaf_drew.append(True)

    @panel(
        surface=_InverseEmptinessLevelOne,
        hosts=(_InverseEmptinessLevelTwo,),
        label="Level1Host",
        registry_id="rstest_inverse_emptiness_level1",
    )
    class _Level1HostPanel(BasePanel):
        def draw(self, ctx, layout):
            with layout:
                self.render_surface(_InverseEmptinessLevelTwo, ctx)

    @panel(
        surface=_InverseEmptinessRoot,
        hosts=(_InverseEmptinessLevelOne,),
        label="Level0Host",
        registry_id="rstest_inverse_emptiness_level0",
    )
    class _Level0HostPanel(BasePanel):
        def draw(self, ctx, layout):
            with layout:
                self.render_surface(_InverseEmptinessLevelOne, ctx)

    registry = PanelRegistry()
    for cls in (_Level0HostPanel, _Level1HostPanel, _LeafPanel):
        registry._register_class(cls, _FAKE_LIBRARY_IDENTITY)

    captured: dict[str, int] = {}

    @ui.page("/")
    def page() -> None:
        with counting_leaves() as leaves:
            _mount_hosting_panel(_Level0HostPanel, registry)
            captured["leaves"] = leaves()

    await user.open("/")

    assert leaf_drew == [True]
    assert captured["leaves"] == 1, "the one real leaf two levels down must count — enough to open a menu"


# ---------------------------------------------------------------------------
# A submenu row whose panels all poll false but implement draw_disabled()
# stays live and shows the greyed rows — through real @panel classes
# ---------------------------------------------------------------------------


class _AllDisabledSurface(Surface):
    id = "render_surface_test_all_disabled_surface"


@pytest.mark.unit
@pytest.mark.anyio
async def test_submenu_row_over_all_disabled_panels_stays_live_and_shows_greyed_rows(
    user: User,
) -> None:
    """Task A's flyout tests prove this with a manual counter increment
    standing in for 'a disabled draw'; this is the same case through a real
    @panel with poll()=False and a real draw_disabled() override, rendered
    via render_surface — the leaf counter a real host reads is the one
    render_panel itself increments (host_rendering.py), not a hand-simulated
    one. Catches a leaf counter wired to poll() instead of to what actually
    drew."""
    from haywire.ui import elements as hui
    from haywire.ui.elements.flyout import SubmenuRow, open_flyout_group

    draw_calls: list[bool] = []
    draw_disabled_calls: list[bool] = []
    captured: dict[str, object] = {}

    @panel(
        surface=_AllDisabledSurface,
        label="DisabledLeaf",
        registry_id="rstest_all_disabled_leaf",
    )
    class _DisabledLeafPanel(BasePanel):
        @classmethod
        def poll(cls, ctx):
            return False

        def draw(self, ctx, layout):
            draw_calls.append(True)

        def draw_disabled(self, ctx, layout):
            draw_disabled_calls.append(True)
            with layout:
                hui.submenu_row("Unavailable Item", enabled=False)

    @panel(
        surface=_PipedSurface,
        hosts=(_AllDisabledSurface,),
        label="RowHost",
        registry_id="rstest_row_host_all_disabled",
    )
    class _RowHostPanel(BasePanel):
        def draw(self, ctx, layout):
            with layout:
                with hui.submenu_row("Parent Row") as row:
                    self.render_surface(_AllDisabledSurface, ctx)
                captured["row"] = row

    registry = PanelRegistry()
    registry._register_class(_RowHostPanel, _FAKE_LIBRARY_IDENTITY)
    registry._register_class(_DisabledLeafPanel, _FAKE_LIBRARY_IDENTITY)

    @ui.page("/")
    def page() -> None:
        with open_flyout_group():
            layout = PanelLayout(ui.column())
            render_panel(_RowHostPanel, _make_ctx(), layout, registry=registry)

    await user.open("/")

    # draw_disabled() ran, draw() never did — same guarantee host_rendering.py
    # enforces at the render_panel level, now proven through the row.
    assert draw_disabled_calls == [True]
    assert draw_calls == []

    # The row stays LIVE: render_panel's own leaf-increment (host_rendering.py)
    # counted the disabled draw as "something drew" at the row's OWN body
    # level (the SubmenuRow's __enter__ pushes a fresh counter scope for
    # exactly that decision), so __exit__ does not grey the row.
    parent_row: SubmenuRow = captured["row"]  # type: ignore[assignment]
    assert "hw-disabled" not in parent_row._row._classes, (
        "a row whose only content is a disabled child must stay live, not grey itself"
    )
    assert parent_row._row._style.get("opacity") is None
    assert parent_row._row._style.get("pointer-events") is None
