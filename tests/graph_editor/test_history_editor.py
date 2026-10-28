"""HistoryEditor: the active file's undo history, newest first, with origin, interior path and marker."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.core.access import AccessTier
from haywire.core.graph.editor import Editor
from haywire.core.session.handlers import _REDRAW_ON_ATTR
from haywire.core.signals import ActiveGraphMoved, GraphHistoryChanged
from haywire.core.undo.base_action import ActionBase
from haywire.core.undo.config import UndoConfig
from haywire.core.undo.origin import StepOrigin
from haywire.ui.editor.identity import SlotName

from haybale_graph_editor.editors.history_editor import HistoryEditor, graph_path
from haybale_graph_editor.state.edit_state import EditState
from haybale_graph_editor.state.graph_app_state import GraphAppState

pytestmark = pytest.mark.unit

ALICE = StepOrigin("alice", "a1", "canvas")
AGENT = StepOrigin("bot", None, "farmhand")


def _graph(label: str = "", **subgraphs: Any) -> Any:
    graph = SimpleNamespace(label=label, subgraphs=subgraphs, graph_id=label or "root")
    for definition in subgraphs.values():
        definition.root_graph = graph
    graph.root_graph = graph
    return graph


class _Step(ActionBase):
    def __init__(self, name: str, graph: Any):
        super().__init__(name)
        self.graph = graph

    def _execute_impl(self) -> None:
        pass

    def _undo_impl(self) -> None:
        pass


class _Harness:
    """Draws a HistoryEditor over one open file and redraws it the way its wrapper does."""

    def __init__(self, active: Any, root: Any, *, grouping: bool = False) -> None:
        config = UndoConfig(
            enable_auto_grouping=grouping, enable_action_merging=False, grouping_time_window_ms=60_000
        )
        self.document = SimpleNamespace(
            binding_id="doc", display_name="Rig", editor=Editor(root, cast(Any, None), config)
        )
        state = GraphAppState()
        self.published: list[object] = []
        dispatcher = SimpleNamespace(broadcast=self.published.append)
        state._dispatcher = lambda: dispatcher  # type: ignore[assignment,return-value]
        state.register(cast(Any, self.document))
        self.ctx = SimpleNamespace(
            data={EditState: SimpleNamespace(active_graph=active)}, app_data={GraphAppState: state}
        )
        self.wrapper = MagicMock()
        self.wrapper.redraw.side_effect = self.redraw
        self.editor = HistoryEditor(self.wrapper)
        self.container: ui.element | None = None

    @property
    def history(self) -> Any:
        return self.document.editor.history_manager

    def mount(self) -> None:
        self.container = ui.column()
        self.redraw()

    def redraw(self) -> None:
        assert self.container is not None
        self.container.clear()
        self.editor.draw(self.ctx, self.container)  # type: ignore[arg-type]

    def labels(self) -> list[str]:
        assert self.container is not None
        return [el.text for el in self.container.descendants() if isinstance(el, ui.label)]

    def row(self, description: str) -> ui.element:
        """Return the clickable row whose first label reads ``description``."""
        assert self.container is not None
        for el in self.container.descendants():
            if isinstance(el, ui.label) and el.text == description:
                row: ui.element = el
                while "cursor-pointer" not in row._classes:
                    assert row.parent_slot is not None
                    row = row.parent_slot.parent
                return row
        raise AssertionError(f"no row {description!r}")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


async def _open(user: User, harness: _Harness) -> None:
    @ui.page("/")
    def page() -> None:
        harness.mount()

    await user.open("/")


def test_editor_identity_is_an_edit_tier_context_slot_editor() -> None:
    identity = HistoryEditor.class_identity
    assert identity.label == "History"
    assert identity.default_slot is SlotName.CONTEXT
    assert identity.requires is AccessTier.EDIT
    assert getattr(HistoryEditor._on_history, _REDRAW_ON_ATTR, ()) == (ActiveGraphMoved, GraphHistoryChanged)


def test_graph_path_walks_down_from_the_file() -> None:
    inner = _graph("Inner")
    group = _graph("Mixer", inner=inner)
    root = _graph(group=group)

    assert graph_path(root, root) == []
    assert graph_path(root, group) == ["Mixer"]
    assert graph_path(root, inner) == ["Mixer", "Inner"]
    assert graph_path(root, _graph("Gone")) is None


@pytest.mark.anyio
async def test_without_an_active_graph_it_says_so(user: User) -> None:
    harness = _Harness(None, _graph())
    await _open(user, harness)

    assert "Open a graph to see its undo history." in harness.labels()


@pytest.mark.anyio
async def test_steps_list_newest_first_with_who_and_where(user: User) -> None:
    group = _graph("Mixer")
    root = _graph(group=group)
    harness = _Harness(root, root)
    harness.history.add_action(_Step("Add node", root), origin=ALICE)
    harness.history.add_action(_Step("Connect", group), origin=AGENT)
    await _open(user, harness)

    labels = harness.labels()

    assert labels[0] == "History · Rig"
    assert labels.index("Connect") < labels.index("Add node")
    assert any(text.startswith("Farmhand · bot · Mixer · ") for text in labels)
    assert any(text.startswith("alice · a1 · ") for text in labels)


@pytest.mark.anyio
async def test_an_interiors_history_is_its_files(user: User) -> None:
    group = _graph("Mixer")
    root = _graph(group=group)
    harness = _Harness(group, root)
    harness.history.add_action(_Step("Add node", group), origin=ALICE)
    await _open(user, harness)

    assert "History · Rig" in harness.labels()
    assert "Add node" in harness.labels()


@pytest.mark.anyio
async def test_the_marker_sits_below_the_redo_branch_and_names_the_last_move(user: User) -> None:
    root = _graph()
    harness = _Harness(root, root)
    harness.history.add_action(_Step("one", root), origin=ALICE)
    harness.history.add_action(_Step("two", root), origin=ALICE)
    harness.history.undo(origin=AGENT)
    await _open(user, harness)

    labels = harness.labels()
    (marker,) = [text for text in labels if text.startswith("Now")]
    assert marker.startswith("Now · last undo by Farmhand · bot at ")
    assert labels.index("two") < labels.index(marker) < labels.index("one")
    assert "opacity-50" in harness.row("two")._classes
    assert "opacity-50" not in harness.row("one")._classes


@pytest.mark.anyio
async def test_a_click_opens_a_steps_details(user: User) -> None:
    root = _graph()
    harness = _Harness(root, root)
    harness.history.add_action(_Step("one", root), origin=ALICE)
    await _open(user, harness)
    assert "_Step" not in harness.labels()

    harness.editor._toggle("0")  # what a click on the row calls

    assert "_Step" in harness.labels()
    assert "canvas" in harness.labels()


@pytest.mark.anyio
async def test_pending_steps_are_tagged_and_a_group_opens_to_its_steps(user: User) -> None:
    root = _graph()
    harness = _Harness(root, root, grouping=True)
    harness.history.add_fence()
    harness.history.add_action(_Step("one", root), origin=ALICE)
    await _open(user, harness)
    assert any(isinstance(el, ui.badge) and el.text == "pending" for el in harness.container.descendants())  # type: ignore[union-attr]

    harness.history.add_action(_Step("two", root), origin=AGENT)
    harness.history.add_fence()
    harness.redraw()
    assert "Group of 2 actions" in harness.labels()
    assert "fence" in harness.labels()
    assert "one" not in harness.labels()

    group_key = str(len(harness.history.snapshot()) - 2)
    harness.editor._toggle(group_key)

    assert "one" in harness.labels()
    assert "two" in harness.labels()
