"""The New Node flow's state machine, and the gates on its two entry panels.

UI rendering is not exercised here. The property under test: nothing is
written until Create, and Create reports what the registry answered. A helper
thread plays the file watcher, as in the authoring pipeline's own tests.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from haywire.core.errors.ledger import ErrorLedger
from haywire.core.node.info import NodeInfo
from haywire.core.node.registry import NodeRegistry
from haywire.core.registry.base import FileChangeEvent, FileEventType

from tests.core.test_authoring import conftest as authoring

# The authoring fixtures, shared with tests/core/test_authoring.
packages = authoring.packages
dst_identity = authoring.dst_identity
dst_library = authoring.dst_library
src_modules = authoring.src_modules
target = authoring.target
BROKEN = authoring.BROKEN
FakeLibraries = authoring.FakeLibraries

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend() -> str:
    """anyio's backend parametrization. The repo runs asyncio only."""
    return "asyncio"


class _Host:
    def __init__(self) -> None:
        self.placed: list[str] = []
        self.revealed: list[str] = []
        self.opened: list[Path] = []

    def place(self, registry_key: str) -> None:
        self.placed.append(registry_key)

    def reveal_component(self, registry_key: str) -> None:
        self.revealed.append(registry_key)

    def open_file(self, path: Path) -> None:
        self.opened.append(path)


class _Libraries(FakeLibraries):
    def __init__(self, library) -> None:
        super().__init__(library.identity)
        self._library = library

    def get_library(self, library_id):
        return self._library


def _info(cls) -> NodeInfo:
    return NodeInfo(identity=cls.class_identity, library=getattr(cls, "class_library", None))


@pytest.fixture
def env(src_modules, target, dst_library):
    single, multi = src_modules
    registry = NodeRegistry()
    classes = {cls.class_identity.registry_key: cls for cls in (single.SingleNode, multi.ChildNode)}
    return {
        "host": _Host(),
        "registry": registry,
        "target": target,
        "library": dst_library,
        "single": single.SingleNode,
        "child": multi.ChildNode,
        "templated": multi.TemplatedNode,
        "classes": classes,
    }


def _flow(env, **kwargs):
    from haybale_graph_editor._new_node_flow import NewNodeFlow

    return NewNodeFlow(
        host=env["host"],
        targets=kwargs.pop("targets", [env["target"]]),
        libraries=_Libraries(env["library"]),
        registry=env["registry"],
        ledger=kwargs.pop("ledger", ErrorLedger()),
        templates={"Source": [_info(env["templated"])]},
        clone_sources=[_info(env["single"]), _info(env["child"])],
        resolve=lambda key: env["classes"].get(key)
        or (env["templated"] if key == env["templated"].class_identity.registry_key else None),
        menu_paths=["a/b"],
        timeout_s=kwargs.pop("timeout_s", 5.0),
        **kwargs,
    )


def _watch_for(registry, identity, path: Path) -> threading.Thread:
    """Hand the registry a CREATED event once ``path`` exists, from another thread."""

    def _run():
        deadline = time.monotonic() + 5
        while not path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        registry.event_dispatcher(FileChangeEvent(str(path), FileEventType.CREATED, identity, time.time()))

    thread = threading.Thread(target=_run)
    thread.start()
    return thread


# ── entries ──────────────────────────────────────────────────────────────────


def test_the_graph_entry_starts_at_source(env):
    flow = _flow(env)
    assert flow.step == "source"
    assert flow.source_cls is None


def test_the_node_entry_starts_at_details_with_the_node_as_source(env):
    flow = _flow(env, source_cls=env["single"])
    assert flow.step == "details"
    assert flow.fields.label == "Single Copy"
    assert flow.fields.class_name == "SingleCopy"


# ── source ───────────────────────────────────────────────────────────────────


def test_templates_group_by_library_and_clones_by_menu_path(env):
    flow = _flow(env)
    assert [(group, info.identity.label) for group, info in flow.source_rows()] == [
        ("Source", "Template-ish")
    ]

    flow.mode = "clone"
    assert [(group, info.identity.label) for group, info in flow.source_rows()] == [
        ("src/family", "Child"),
        ("src/single", "Single"),
    ]


def test_the_search_filters_the_list(env):
    flow = _flow(env)
    flow.mode = "clone"
    flow.query = "sing"
    assert [info.identity.label for _group, info in flow.source_rows()] == ["Single"]


@pytest.mark.anyio
async def test_picking_a_row_advances_to_details(env, anyio_backend):
    flow = _flow(env)
    flow.mode = "clone"
    assert flow.pick(_info(env["child"]))
    await flow.advance_from_source()

    assert flow.step == "details"
    assert flow.fields.menu == "src/family", "prefilled from the resolved identity"


@pytest.mark.anyio
async def test_nothing_picked_cannot_advance(env, anyio_backend):
    flow = _flow(env)
    await flow.advance_from_source()
    assert flow.step == "source"
    assert flow.error


# ── details ──────────────────────────────────────────────────────────────────


def test_the_class_name_follows_the_label_until_edited(env):
    flow = _flow(env, source_cls=env["single"])
    flow.set_label("Blur filter")
    assert flow.fields.class_name == "BlurFilter"
    assert flow.file_name == "nodes/blur_filter.py"

    flow.set_class_name("Smear")
    flow.set_label("Something else")
    assert flow.fields.class_name == "Smear"


@pytest.mark.parametrize("class_name", ["", "1Bad", "DevNode"])
def test_an_unusable_class_name_is_refused_live(env, class_name):
    flow = _flow(env, source_cls=env["single"])
    flow.set_class_name(class_name)
    assert flow.details_refusal is not None


def test_an_existing_file_is_refused_live(env):
    flow = _flow(env, source_cls=env["single"])
    (env["target"].folder / "single_copy.py").write_text("")
    assert "already exists" in (flow.details_refusal or "")


def test_no_target_is_refused(env):
    flow = _flow(env, source_cls=env["single"], targets=[])
    assert flow.details_refusal is not None


# ── plan and create ─────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_planning_writes_nothing(env, anyio_backend):
    flow = _flow(env, source_cls=env["single"])
    await flow.advance_from_details()

    assert flow.step == "planned"
    assert flow.plan is not None
    assert flow.plan.refusal is None
    assert not flow.plan.path.exists()
    assert env["host"].placed == env["host"].revealed == []


@pytest.mark.anyio
async def test_create_writes_and_reports_the_registered_key(env, anyio_backend):
    flow = _flow(env, source_cls=env["single"])
    await flow.advance_from_details()
    thread = _watch_for(env["registry"], env["library"].identity, flow.plan.path)

    await flow.advance_from_planned()
    thread.join()

    assert flow.error is None
    assert flow.step == "result"
    assert flow.succeeded
    assert flow.outcome.registry_key == "dst:node:SingleCopy"
    assert flow.plan.path.exists()


@pytest.mark.anyio
async def test_place_and_edit_call_the_host(env, anyio_backend):
    flow = _flow(env, source_cls=env["single"])
    await flow.advance_from_details()
    thread = _watch_for(env["registry"], env["library"].identity, flow.plan.path)
    await flow.advance_from_planned()
    thread.join()

    flow.place()
    flow.edit()

    assert env["host"].placed == ["dst:node:SingleCopy"]
    assert env["host"].revealed == ["dst:node:SingleCopy"]


@pytest.mark.anyio
async def test_a_failed_import_reports_the_error_and_opens_the_file(env, anyio_backend, monkeypatch):
    from haywire.core.di import context as di_context

    ledger = ErrorLedger()
    monkeypatch.setattr(di_context, "_error_ledger", ledger)
    flow = _flow(env, source_cls=env["single"], ledger=ledger)
    await flow.advance_from_details()
    flow.plan.source = BROKEN
    thread = _watch_for(env["registry"], env["library"].identity, flow.plan.path)

    await flow.advance_from_planned()
    thread.join()

    assert flow.step == "result"
    assert not flow.succeeded
    assert flow.outcome.status == "failed"
    assert flow.outcome.errors
    assert flow.plan.path.exists(), "the file stays"

    flow.place()
    flow.open_file()
    assert env["host"].placed == []
    assert env["host"].opened == [flow.plan.path]


@pytest.mark.anyio
async def test_a_refused_plan_is_never_written(env, anyio_backend):
    flow = _flow(env, source_cls=env["single"])
    await flow.advance_from_details()
    flow.plan.refusal = "no"

    await flow.advance_from_planned()

    assert flow.step == "planned"
    assert flow.error == "no"
    assert not flow.plan.path.exists()


# ── entry panels ─────────────────────────────────────────────────────────────


def test_both_entry_panels_require_admin():
    from haybale_graph_editor.panels.graph.menu.graph.context import NewNodeToolbarPanel
    from haybale_graph_editor.panels.graph.menu.selection.selection import CloneToLibraryMenuPanel
    from haywire.core.access import AccessTier

    assert NewNodeToolbarPanel.class_identity.access is AccessTier.ADMIN
    assert CloneToLibraryMenuPanel.class_identity.access is AccessTier.ADMIN


def _ctx(*, node_cls=None, selected: set[str] | None = None):
    from haybale_graph_editor.state.edit_state import EditState

    edit = MagicMock()
    edit.active_node = None
    if node_cls is not None:
        wrapper = MagicMock()
        wrapper.node = node_cls.__new__(node_cls)
        edit.active_node = wrapper
    edit.selected_nodes = selected if selected is not None else ({"n1"} if node_cls else set())
    ctx = MagicMock()
    ctx.data = {EditState: edit}
    return ctx


def test_the_clone_row_shows_for_one_ordinary_node(env):
    from haybale_graph_editor.panels._gating import is_cloneable_selection

    assert is_cloneable_selection(_ctx(node_cls=env["single"])) is True


def test_the_clone_row_is_absent_for_zero_or_several_nodes(env):
    from haybale_graph_editor.panels._gating import is_cloneable_selection

    assert is_cloneable_selection(_ctx()) is False
    assert is_cloneable_selection(_ctx(node_cls=env["single"], selected={"a", "b"})) is False


@pytest.mark.parametrize(
    ("module", "name"),
    [
        ("haywire.barn.builtin.nodes.reroute", "RerouteNode"),
        ("haywire.barn.builtin.nodes.graph_node", "GraphNode"),
        ("haywire.barn.builtin.nodes.macro_node", "MacroNode"),
    ],
)
def test_the_clone_row_is_absent_for_framework_role_nodes(module, name):
    import importlib

    from haybale_graph_editor.panels._gating import is_cloneable_selection

    cls = getattr(importlib.import_module(module), name)
    assert is_cloneable_selection(_ctx(node_cls=cls)) is False
