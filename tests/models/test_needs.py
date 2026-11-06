"""The needs-list: graph notice and card warnings for missing models."""

from __future__ import annotations

import hashlib
from pathlib import Path
import importlib
import sys
import types
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, cast

import pytest
from haywire.core.access import AccessTier
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.graph.subgraph import SubgraphDefinition
from haywire.core.undo.no_op_history_manager import NoOpHistoryManager
from haywire.core.volumes import VolumeStore, location_of

from haybale_graph_editor.state.graph_app_state import GraphAppState
from haybale_models.consumer import MISSING_WARNING
from haybale_models.download import DownloadJob
from haybale_models.keys import MODELS_VOLUME, NEEDS_NOTICE
from haybale_models.needs import NeedsWatcher, format_size
from haybale_models.sources import builtin_sources
from haybale_models.store.index import ModelIndex
from haybale_models.store.records import FetchRecord, FetchRecords
from haybale_models.value.model_ref import ModelRef

from tests.conftest import make_edge, make_node
from tests.models.conftest import make_hf_snapshot

pytestmark = pytest.mark.integration

DATA = b"x" * 64
SHA = hashlib.sha256(DATA).hexdigest()
URL = "https://example.invalid/m.bin"
SIZE = 12_000_000


@dataclass
class _Editor:
    graph: Any = None
    history_manager: Any = field(default_factory=NoOpHistoryManager)


@dataclass
class _Container:
    binding_id: str
    editor: _Editor


class _Loop:
    def is_running(self) -> bool:
        return True

    def call_soon_threadsafe(self, fn: Any, *args: Any) -> None:
        fn(*args)


class _Queue:
    def __init__(self) -> None:
        self.listeners: list[Any] = []
        self.job_list: list[DownloadJob] = []

    def add_listener(self, cb: Any) -> None:
        self.listeners.append(cb)

    def remove_listener(self, cb: Any) -> None:
        self.listeners.remove(cb)

    def jobs(self) -> list[DownloadJob]:
        return list(self.job_list)

    def changed(self) -> None:
        for cb in list(self.listeners):
            cb()


class _Catalog:
    def add_batch_event_subscriber(self, cb: Any) -> None:
        pass

    def remove_batch_event_subscriber(self, cb: Any) -> None:
        pass


def ref(sha: str = SHA, url: str = URL, size: int | None = SIZE) -> ModelRef:
    return ModelRef(urls=(url,), sha256=sha, size=size, label="m.bin")


def _node_key() -> str:
    cls = importlib.import_module("haybale_models.nodes.resolve_model").ResolveModelNode
    return cast(str, cls.class_identity.registry_key)


@pytest.fixture
def env(models_env: VolumeStore, tmp_path: Any, monkeypatch: pytest.MonkeyPatch, library_system: Any) -> Any:
    from nicegui import core

    monkeypatch.setattr(core, "loop", _Loop())
    root = location_of(MODELS_VOLUME, models_env)
    root.mkdir(parents=True, exist_ok=True)
    graphs = GraphAppState()
    monkeypatch.setattr(graphs, "_signal_emit", lambda signal: None)
    index = ModelIndex()
    models = SimpleNamespace(
        index=index,
        queue=_Queue(),
        records=FetchRecords(tmp_path / "fetched.json"),
        catalog=_Catalog(),
        sources=builtin_sources(index, hf_cache=lambda: None),
    )
    watcher = NeedsWatcher(graphs, cast(Any, models), debounce_s=0.02, throttle_s=0.0)
    watcher.start()

    def put(data: bytes = DATA, name: str = "m.bin") -> None:
        (root / name).write_bytes(data)
        models.index.scan()
        models.index.hash_pending()

    def open_graph(graph: Any, binding: str = "g1") -> None:
        graphs.register(cast(Any, _Container(binding, _Editor(graph))))

    def settle() -> None:
        assert watcher.wait_idle()

    yield SimpleNamespace(
        graphs=graphs, models=models, watcher=watcher, put=put, open=open_graph, settle=settle
    )
    watcher.stop()


@pytest.fixture
def graph(library_system: Any) -> Any:
    from haywire.core.graph.base import BaseGraph

    return BaseGraph(filestem="needs", validation_scheduler=SyncScheduler())


def _add(graph: Any, value: ModelRef | None) -> Any:
    wrapper = make_node(graph, _node_key(), position=(0, 0))
    if value is not None:
        wrapper.node.ports["model"].set_value(value)
    return wrapper


def _texts(env: Any, binding: str = "g1") -> list[str]:
    return [n.text for n in env.graphs.notices(binding)]


def test_format_size() -> None:
    assert format_size(12_000_000) == "12.0 MB"
    assert format_size(512) == "512 B"
    assert format_size(3_400_000_000) == "3.4 GB"


def test_notice_posted_on_open_and_retracted_when_resolved(env: Any, graph: Any) -> None:
    _add(graph, ref())
    env.open(graph)
    env.settle()
    notice = env.graphs.notices("g1")[0]
    assert notice.key == NEEDS_NOTICE
    assert notice.text == "Needs 1 model (12.0 MB)"
    assert notice.action_label == "Show in Models"
    assert notice.requires == AccessTier.VIEW
    assert notice.icon == "model_training"

    assert list(env.watcher.latest_reports()) == ["g1"]
    assert len(env.watcher.latest_reports()["g1"].missing) == 1

    env.put()
    env.settle()

    assert env.graphs.notices("g1") == []
    assert env.watcher.latest_reports() == {}


def test_unknown_size_is_counted(env: Any, graph: Any) -> None:
    _add(graph, ref(size=None))
    env.open(graph)
    env.settle()
    assert _texts(env) == ["Needs 1 model (0 B, 1 of unknown size)"]


def test_subgraph_interior_counted(env: Any, graph: Any) -> None:
    definition = graph.add_subgraph(
        SubgraphDefinition(key="sg", label="G", validation_scheduler=SyncScheduler())
    )
    _add(definition, ref())
    env.open(graph)
    env.settle()
    assert _texts(env) == ["Needs 1 model (12.0 MB)"]


def test_wired_ref_not_counted(env: Any, graph: Any) -> None:
    from haybale_models.types.model_ref import MODEL_REF

    source = _add(graph, None)
    sink = _add(graph, ref())
    with source.node.rejig():
        source.node.add(MODEL_REF.as_outlet("out"))
    make_edge(graph, source.node_id, "out", sink.node_id, "model")
    env.open(graph)
    env.settle()
    assert env.graphs.notices("g1") == []
    assert sink.state.warnings == []


def test_edit_adding_a_ref_rechecks(env: Any, graph: Any) -> None:
    wrapper = _add(graph, None)
    env.open(graph)
    env.settle()
    assert env.graphs.notices("g1") == []

    wrapper.node.ports["model"].set_value(ref())
    wrapper.mark_value_edited()  # what a user edit reports
    env.settle()

    assert _texts(env) == ["Needs 1 model (12.0 MB)"]


def test_same_model_on_two_nodes_counted_once(env: Any, graph: Any) -> None:
    _add(graph, ref())
    _add(graph, ref())
    env.open(graph)
    env.settle()
    assert _texts(env) == ["Needs 1 model (12.0 MB)"]


def test_two_models_sum(env: Any, graph: Any) -> None:
    _add(graph, ref())
    _add(graph, ref(sha="b" * 64, url="https://example.invalid/b.bin", size=1_000_000))
    env.open(graph)
    env.settle()
    assert _texts(env) == ["Needs 2 models (13.0 MB)"]


def test_progress_text_while_fetching(env: Any, graph: Any) -> None:
    _add(graph, ref())
    env.open(graph)
    env.settle()
    env.models.queue.job_list = [
        DownloadJob("dl-1", "m", SHA, SIZE, (URL,), state="running", done_bytes=3_000_000, total_bytes=SIZE)
    ]
    env.models.queue.changed()
    env.settle()
    assert _texts(env) == ["Fetching 1 of 1 — 25 %"]

    env.models.queue.job_list = []
    env.models.queue.changed()
    env.settle()
    assert _texts(env) == ["Needs 1 model (12.0 MB)"]


def test_progress_text_is_throttled(env: Any, graph: Any) -> None:
    env.watcher._throttle_s = 0.3
    _add(graph, ref())
    env.open(graph)
    env.settle()
    job = DownloadJob("dl-1", "m", SHA, SIZE, (URL,), state="running", done_bytes=0, total_bytes=SIZE)
    env.models.queue.job_list = [job]
    env.models.queue.changed()
    env.settle()
    assert _texts(env) == ["Fetching 1 of 1 — 0 %"]

    job.done_bytes = SIZE // 2
    env.models.queue.changed()
    env.watcher.wait_idle(0.15)
    assert _texts(env) == ["Fetching 1 of 1 — 0 %"]  # held back inside the window
    env.settle()
    assert _texts(env) == ["Fetching 1 of 1 — 50 %"]  # delivered when the window ends


def test_card_warning_set_and_cleared(env: Any, graph: Any) -> None:
    wrapper = _add(graph, ref())
    other = _add(graph, None)
    env.open(graph)
    env.settle()
    assert wrapper.state.warnings == [MISSING_WARNING]
    assert other.state.warnings == []

    env.put()
    env.settle()

    assert wrapper.state.warnings == []


def test_stop_retracts_notice_and_own_warning(env: Any, graph: Any) -> None:
    wrapper = _add(graph, ref())
    env.open(graph)
    env.settle()
    assert _texts(env) != []
    assert wrapper.state.warnings == [MISSING_WARNING]

    env.watcher.stop()

    assert _texts(env) == []
    assert wrapper.state.warnings == []


def test_stop_keeps_the_consumers_own_warnings(env: Any, graph: Any) -> None:
    from haywire.core.node.node_warning import NodeWarning

    wrapper = _add(graph, ref())
    env.open(graph)
    env.settle()
    other = [
        *wrapper.state.warnings,
        NodeWarning(message="consumer's", source_version=None, kind="model"),
    ]
    wrapper.state.warnings = other  # the consumer added its own: not exactly [MISSING_WARNING]

    env.watcher.stop()

    assert wrapper.state.warnings == other


def test_stop_waits_for_a_walk_in_flight(env: Any, graph: Any) -> None:
    import threading

    _add(graph, ref())
    env.open(graph)
    env.settle()
    started, release = threading.Event(), threading.Event()
    original = env.watcher._update_notice

    def slow(w: Any, report: Any) -> None:
        started.set()
        release.wait(5)
        original(w, report)

    env.watcher._update_notice = slow
    env.watcher._schedule("g1")
    assert started.wait(2)
    stopper = threading.Thread(target=env.watcher.stop)
    stopper.start()
    stopper.join(0.2)
    assert stopper.is_alive()  # stop() is waiting on the walk
    release.set()
    stopper.join(3)
    assert not stopper.is_alive()
    assert _texts(env) == []  # the walk's post was retracted, not left behind


def test_close_unsubscribes_validation(env: Any, graph: Any) -> None:
    definition = graph.add_subgraph(
        SubgraphDefinition(key="sg", label="G", validation_scheduler=SyncScheduler())
    )
    before = (len(graph._validation._callbacks), len(definition._validation._callbacks))
    _add(graph, ref())
    env.open(graph)
    env.settle()
    assert len(graph._validation._callbacks) == before[0] + 1
    assert len(definition._validation._callbacks) == before[1] + 1

    env.graphs.unregister("g1")

    assert (len(graph._validation._callbacks), len(definition._validation._callbacks)) == before


def test_removed_subgraph_is_unsubscribed_on_rewalk(env: Any, graph: Any) -> None:
    definition = graph.add_subgraph(
        SubgraphDefinition(key="sg", label="G", validation_scheduler=SyncScheduler())
    )
    env.open(graph)
    env.settle()
    count = len(definition._validation._callbacks)
    graph.subgraphs.pop("sg")
    env.watcher._schedule("g1")
    env.settle()
    assert len(definition._validation._callbacks) == count - 1


def test_action_reveals_the_editor(env: Any, graph: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _add(graph, ref())
    env.open(graph)
    env.settle()
    published: list[Any] = []
    context = SimpleNamespace(session=SimpleNamespace(publish=published.append))
    editor_cls = type("ModelsEditor", (), {})
    module = types.ModuleType("haybale_models.editors.models_editor")
    module.ModelsEditor = editor_cls  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "haybale_models.editors.models_editor", module)
    env.graphs.notices("g1")[0].action(context)

    assert len(published) == 1
    assert published[0].editor is editor_cls


def test_unchanged_notice_reposts_equal(env: Any, graph: Any) -> None:
    _add(graph, ref())
    env.open(graph)
    env.settle()
    first = env.graphs.notices("g1")[0]
    env.watcher._schedule("g1")
    env.settle()
    assert env.graphs.notices("g1")[0] is first


def test_macro_instance_interior_is_counted_and_subscribed(env: Any, graph: Any) -> None:
    definition = graph.add_subgraph(
        SubgraphDefinition(key="mac", label="M", validation_scheduler=SyncScheduler())
    )
    definition.template_key = "some-macro"  # a macro instance is a marked Subgraph definition
    _add(definition, ref())
    before = len(definition._validation._callbacks)

    env.open(graph)
    env.settle()

    assert _texts(env) == ["Needs 1 model (12.0 MB)"]
    assert len(definition._validation._callbacks) == before + 1


def test_graph_closed_during_a_walk_leaves_no_subscription(env: Any, graph: Any) -> None:
    import threading

    _add(graph, ref())
    env.open(graph)
    env.settle()
    callbacks = len(graph._validation._callbacks)
    entered, release = threading.Event(), threading.Event()
    original = env.watcher._reconcile

    def blocked(w: Any) -> None:
        entered.set()
        assert release.wait(5)
        original(w)

    env.watcher._reconcile = blocked
    env.watcher._schedule("g1")
    assert entered.wait(5)
    env.graphs.unregister("g1")
    release.set()
    env.settle()

    assert len(graph._validation._callbacks) == callbacks - 1


def test_concurrent_reconcile_subscribes_once(env: Any, graph: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    import threading
    import time

    from haybale_models.needs import _Watched

    before = len(graph._validation._callbacks)
    original = graph.subscribe_to_validation

    def slow(cb: Any) -> None:
        time.sleep(0.05)
        original(cb)

    monkeypatch.setattr(graph, "subscribe_to_validation", slow)
    w = _Watched("x", graph)
    threads = [threading.Thread(target=env.watcher._reconcile, args=(w,)) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(5)

    assert len(w.subs) == 1
    assert len(graph._validation._callbacks) == before + 1


def test_steady_notifications_do_not_starve_the_walk(env: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    watcher = NeedsWatcher(env.graphs, env.models, debounce_s=0.2, throttle_s=0.0)
    watcher.start()
    runs: list[str] = []
    monkeypatch.setattr(watcher, "_run", runs.append)
    try:
        end = time.monotonic() + 1.5
        first_run_at = None
        while time.monotonic() < end:
            watcher._schedule("x")
            if runs and first_run_at is None:
                first_run_at = time.monotonic()
            time.sleep(0.1)
        assert runs, "no walk ran while notifications kept arriving"
        assert first_run_at is not None
    finally:
        watcher.stop()


def test_a_records_change_rewalks_the_graphs_and_stop_unsubscribes(env: Any, graph: Any) -> None:
    _add(graph, ref())
    env.open(graph)
    env.settle()
    assert _texts(env) == ["Needs 1 model (12.0 MB)"]

    env.models.queue.job_list = [  # no queue notification: only the records change tells the watcher
        DownloadJob("dl-1", "m", SHA, SIZE, (URL,), state="running", done_bytes=3_000_000, total_bytes=SIZE)
    ]
    env.models.records.add(FetchRecord("v", "m.bin", SHA, "lib:catalog:m", URL))
    env.settle()
    assert _texts(env) == ["Fetching 1 of 1 — 25 %"]

    env.watcher.stop()
    assert env.models.records._listeners == []
    env.watcher.start()  # the fixture's teardown stops it again


def test_job_matches_requires_the_same_include():
    from haywire.core.catalog import ModelFile, Resource
    from haybale_models.needs import job_matches
    from haybale_models.resolver import FetchSpec

    address = "hf://org/repo@" + "a" * 40

    def spec_of(include):
        resource = Resource(
            "diffusers",
            "dir",
            None,
            None,
            (address,),
            (ModelFile("", None, None, (address,)),),
            include=include,
        )
        return FetchSpec(entry=SimpleNamespace(), resource=resource)  # type: ignore[arg-type]

    job = DownloadJob("dl-1", "m", None, None, (address,), include=("*.onnx",))
    assert not job_matches(job, spec_of(("*.safetensors",)))
    assert job_matches(job, spec_of(("*.onnx",)))


def test_refresh_notices_a_file_gone_from_a_cache(env: Any, graph: Any, tmp_path: Path) -> None:
    """A file removed from the Hugging Face cache touches neither the index, the queue nor the records."""
    commit = "c" * 40
    hub = tmp_path / "hub"
    hub.mkdir()
    snap = make_hf_snapshot(hub, "o/r", commit, {"w.bin": DATA}, None, linked=True)
    env.models.sources = builtin_sources(env.models.index, hf_cache=lambda: hub)
    _add(graph, ModelRef(urls=(f"hf://o/r/w.bin@{commit}",), sha256=SHA, size=len(DATA)))
    env.open(graph)
    env.settle()
    assert env.watcher.latest_reports() == {}

    env.models.sources.lookup("hf://o").remove(snap / "w.bin")
    env.settle()
    assert env.watcher.latest_reports() == {}  # nothing told it yet

    env.watcher.refresh()
    env.settle()
    assert len(env.watcher.latest_reports()["g1"].missing) == 1
