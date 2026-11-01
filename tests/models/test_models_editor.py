"""ModelsEditor: catalog / local / HF sections, filter + Fetch all, admin gating, remove, progress."""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.core.access import AccessTier
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.library.identity import LibraryIdentity
from haywire.core.models import ModelCatalogRegistry
from haywire.core.undo.no_op_history_manager import NoOpHistoryManager
from haywire.core.volumes import VolumeStore, location_of

from haybale_graph_editor.state.graph_app_state import GraphAppState
from haybale_models.download import DownloadJob
from haybale_models.editors import models_editor as editor_module
from haybale_models.editors.models_editor import ModelsEditor
from haybale_models.hf import HfCachedFile
from haybale_models.keys import MODELS_VOLUME
from haybale_models.state.models_state import ModelsState
from haybale_models.state.models_view_state import ModelsViewState
from haybale_models.store.index import ModelIndex
from haybale_models.value.model_ref import ModelRef

from tests.conftest import make_node

pytestmark = pytest.mark.unit

DATA = b"weights-weights"
SHA = hashlib.sha256(DATA).hexdigest()
OTHER = b"other-bytes"
OTHER_SHA = hashlib.sha256(OTHER).hexdigest()
KEY = "haybale-alpha:model:Sharp"
URL = "https://example.invalid/sharp.pth"


def _doc(name: str, sha: str, url: str) -> dict[str, Any]:
    return {
        "name": name,
        "author": "a",
        "license": "MIT",
        "architecture": "esrgan",
        "scale": 4,
        "tags": [],
        "description": "",
        "resources": [
            {"platform": "pytorch", "type": "pth", "size": 2_400_000, "sha256": sha, "urls": [url]}
        ],
    }


class _Queue:
    def __init__(self) -> None:
        self.job_list: list[DownloadJob] = []
        self.cancelled: list[str] = []

    def jobs(self) -> list[DownloadJob]:
        return list(self.job_list)

    def cancel(self, job_id: str) -> None:
        self.cancelled.append(job_id)


@dataclass
class _Container:
    binding_id: str
    display_name: str
    editor: Any


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


class _Harness:
    def __init__(self, tmp_path: Path, tier: AccessTier) -> None:
        self.tier = tier
        catalog = ModelCatalogRegistry()
        folder = tmp_path / "catalog" / "haybale-alpha"
        folder.mkdir(parents=True)
        (folder / "Sharp.json").write_text(json.dumps(_doc("Sharp", SHA, URL)))
        (folder / "Soft.json").write_text(json.dumps(_doc("Soft", "c" * 64, "https://x.invalid/s.pth")))
        catalog.add_folder(
            str(folder),
            LibraryIdentity(
                label="Alpha", name="haybale-alpha", folder_path=str(folder), module_name="haybale-alpha"
            ),
        )
        self.fetched: list[Any] = []
        self.models = SimpleNamespace(
            index=ModelIndex(),
            queue=_Queue(),
            catalog=catalog,
            hf_cache=tmp_path / "hf",
            fetch=self._fetch,
        )
        self.graphs = GraphAppState()
        self.graphs._signal_emit = lambda signal: None  # type: ignore[method-assign]
        self.view = SimpleNamespace(graph_filter=None)
        self.ctx = SimpleNamespace(
            data={ModelsViewState: self.view},
            app_data={ModelsState: self.models, GraphAppState: self.graphs},
            principal="alice",
            can_access=lambda required: self.tier.satisfies(required),
        )
        self.wrapper = MagicMock()
        self.wrapper.redraw.side_effect = self.redraw
        self.editor = ModelsEditor(self.wrapper)
        self.container: ui.element | None = None

    def _fetch(self, specs: list[Any], principal: str | None) -> list[str]:
        self.fetched.extend(specs)
        return []

    def put(self, relative: str, data: bytes) -> Path:
        path = location_of(MODELS_VOLUME) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.models.index.scan()
        self.models.index.hash_pending()
        return path

    def mount(self) -> None:
        self.container = ui.column()
        self.redraw()
        thread = self.editor._scan_thread
        assert thread is not None
        thread.join(5)
        self.redraw()

    def redraw(self) -> None:
        assert self.container is not None
        self.container.clear()
        self.editor.draw(cast(Any, self.ctx), self.container)

    def texts(self) -> list[str]:
        assert self.container is not None
        return [el.text for el in self.container.descendants() if isinstance(el, ui.label)]

    def marked(self, mark: str) -> list[ui.element]:
        assert self.container is not None
        return [el for el in self.container.descendants() if mark in el._markers]  # type: ignore[attr-defined]


@pytest.fixture
def env(models_env: VolumeStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    location_of(MODELS_VOLUME).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(editor_module, "list_cache", lambda root: [])

    def make(tier: AccessTier = AccessTier.ADMIN) -> _Harness:
        return _Harness(tmp_path, tier)

    return make


async def _open(user: User, harness: _Harness) -> None:
    @ui.page("/")
    def page() -> None:
        harness.mount()

    await user.open("/")


def _open_graph(harness: _Harness, library_system: Any, value: ModelRef, name: str = "Rig") -> None:
    from haybale_models.nodes.resolve_model import ResolveModelNode

    graph = BaseGraph(filestem=name, validation_scheduler=SyncScheduler())
    wrapper = make_node(graph, ResolveModelNode.class_identity.registry_key, position=(0, 0))
    wrapper.node.ports["model"].set_value(value)
    harness.graphs.register(
        cast(Any, _Container("g1", name, SimpleNamespace(graph=graph, history_manager=NoOpHistoryManager())))
    )


def test_identity() -> None:
    identity = ModelsEditor.class_identity
    assert identity.label == "Models"
    assert identity.requires is AccessTier.VIEW


@pytest.mark.anyio
async def test_sections_list_catalog_local_and_hf(
    user: User, env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = env()
    h.put("alpha/Sharp/sharp.pth", DATA)
    h.put("loose/other.bin", OTHER)
    hf = [HfCachedFile("org/repo", "abcdef123456", "w.safetensors", 5000, Path("/x"))]
    monkeypatch.setattr(editor_module, "list_cache", lambda root: hf)
    await _open(user, h)

    texts = h.texts()
    assert {"Catalog", "Local", "Hugging Face cache"} <= set(texts)
    assert "local" in texts  # Sharp resolves through its digest
    assert "not downloaded" in texts  # Soft
    assert "loose/other.bin" in texts  # no catalog resource claims it
    assert "alpha/Sharp/sharp.pth" not in texts
    assert OTHER_SHA[:12] in texts
    assert "org/repo/w.safetensors" in texts
    assert any(t.startswith("models: ") for t in texts)
    assert "HF cache: 5.0 KB" in texts


@pytest.mark.anyio
async def test_filter_shows_only_graph_needs_and_fetch_all_enqueues(
    user: User, env: Any, library_system: Any
) -> None:
    h = env()
    _open_graph(h, library_system, ModelRef(catalog=KEY))
    h.view.graph_filter = "g1"
    await _open(user, h)

    assert len(h.marked("models-row")) == 1
    assert "Needed by Rig" in [el.text for el in h.marked("models-filter-chip")]
    user.find(marker="models-fetch-all").click()
    assert [s.entry.name for s in h.fetched] == ["Sharp"]

    user.find(marker="models-filter-clear").click()
    assert h.view.graph_filter is None


@pytest.mark.anyio
async def test_download_button_hidden_below_admin(user: User, env: Any) -> None:
    h = env(AccessTier.VIEW)
    await _open(user, h)
    assert h.marked("models-row")
    assert not h.marked("models-download")


@pytest.mark.anyio
async def test_download_enqueues_for_admin_and_rechecks_at_click(user: User, env: Any) -> None:
    h = env()
    await _open(user, h)
    assert len(h.marked("models-download")) == 2
    h.tier = AccessTier.VIEW  # demoted after the draw
    user.find(marker="models-download").click()
    assert h.fetched == []
    h.tier = AccessTier.ADMIN
    user.find(marker="models-download").click()
    assert len(h.fetched) == 1


@pytest.mark.anyio
async def test_remove_confirm_lists_using_graphs_and_deletes(
    user: User, env: Any, library_system: Any
) -> None:
    h = env()
    path = h.put("loose/other.bin", OTHER)
    _open_graph(h, library_system, ModelRef(urls=("https://x.invalid/o.bin",), sha256=OTHER_SHA))
    await _open(user, h)

    user.find(marker="models-remove").click()
    await user.should_see(f"Delete loose/other.bin ({len(OTHER)} B)? Used by: Rig")
    user.find(content="Delete", kind=ui.button).click()

    assert not path.exists()
    assert h.models.index.records() == []


@pytest.mark.anyio
async def test_remove_confirm_says_when_unused(user: User, env: Any) -> None:
    h = env()
    path = h.put("loose/other.bin", OTHER)
    await _open(user, h)
    user.find(marker="models-remove").click()
    await user.should_see("Used by: not used by an open graph")
    assert path.exists()


@pytest.mark.anyio
async def test_hf_rows_have_no_remove(user: User, env: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    h = env()
    hf = [HfCachedFile("org/repo", "abcdef123456", "w.bin", 10, Path("/x"))]
    monkeypatch.setattr(editor_module, "list_cache", lambda root: hf)
    await _open(user, h)

    assert len(h.marked("models-hf-row")) == 1
    assert not h.marked("models-remove")  # nothing local, and HF rows never carry one
    user.find(marker="models-hf-reveal").click()
    assert h.marked("models-hf-location")


@pytest.mark.anyio
async def test_progress_shown_from_queue(user: User, env: Any) -> None:
    h = env()
    h.models.queue.job_list = [
        DownloadJob("dl-1", "Sharp", SHA, 100, (URL,), state="running", done_bytes=45, total_bytes=100)
    ]
    await _open(user, h)

    assert "downloading 45 %" in h.texts()
    assert len(h.marked("models-cancel")) == 1
    user.find(marker="models-cancel").click()
    assert h.models.queue.cancelled == ["dl-1"]


@pytest.mark.anyio
async def test_remove_never_unlinks_a_symlink_escaping_the_volume(
    user: User, env: Any, tmp_path: Path
) -> None:
    h = env()
    outside = tmp_path / "outside.bin"
    outside.write_bytes(OTHER)
    link = location_of(MODELS_VOLUME) / "loose" / "link.bin"
    link.parent.mkdir(parents=True)
    link.symlink_to(outside)
    h.models.index.scan()
    h.models.index.hash_pending()
    assert [r.relative for r in h.models.index.records()] == ["loose/link.bin"]
    await _open(user, h)

    user.find(marker="models-remove").click()
    await user.should_see("Nothing to delete")
    assert outside.read_bytes() == OTHER
    assert link.is_symlink()
    assert len(h.models.index.records()) == 1


@pytest.mark.anyio
async def test_filter_says_everything_present_when_nothing_is_missing(
    user: User, env: Any, library_system: Any
) -> None:
    h = env()
    h.put("alpha/Sharp/sharp.pth", DATA)
    _open_graph(h, library_system, ModelRef(catalog=KEY))
    h.view.graph_filter = "g1"
    await _open(user, h)

    assert "Everything this graph needs is present" in h.texts()
    assert not h.marked("models-row")


@pytest.mark.anyio
async def test_one_locate_per_catalog_row_per_draw(
    user: User, env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = env()
    await _open(user, h)
    calls: list[Any] = []
    real = editor_module.locate_resource

    def counting(resource: Any, index: Any, hf_cache: Any) -> Any:
        calls.append(resource)
        return real(resource, index, hf_cache)

    monkeypatch.setattr(editor_module, "locate_resource", counting)
    h.redraw()

    assert len(h.marked("models-row")) == 2
    assert len(calls) == 2


class _FakeTimer:
    def __init__(self, delay: float, callback: Any, once: bool = False) -> None:
        self.delay, self.callback = delay, callback
        self.is_deleted = False
        self._is_canceled = False

    def cancel(self) -> None:
        self._is_canceled = True


@pytest.mark.anyio
async def test_reused_needs_report_gets_one_trailing_redraw_that_recomputes(
    user: User, env: Any, library_system: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = [100.0]
    monkeypatch.setattr(editor_module.time, "monotonic", lambda: clock[0])
    timers: list[_FakeTimer] = []

    def fake_timer(delay: float, callback: Any, once: bool = False) -> _FakeTimer:
        timers.append(_FakeTimer(delay, callback, once))
        return timers[-1]

    monkeypatch.setattr(editor_module.ui, "timer", fake_timer)
    h = env()
    _open_graph(h, library_system, ModelRef(catalog=KEY))
    h.view.graph_filter = "g1"
    await _open(user, h)
    assert len(h.marked("models-row")) == 1  # computed: Sharp is missing
    for t in timers:  # mount's own trailing redraw has fired
        t.is_deleted = True
    timers.clear()

    h.put("alpha/Sharp/sharp.pth", DATA)  # the model arrives
    clock[0] += 0.3
    for _ in range(5):  # burst of signal redraws inside the TTL reuses the stale report
        h.redraw()
    assert len(h.marked("models-row")) == 1
    assert len(timers) == 1  # one coalesced trailing redraw
    assert timers[0].delay == pytest.approx(0.7 + 0.05)

    clock[0] += 0.8
    timers[0].callback()  # the trailing redraw recomputes
    assert "Everything this graph needs is present" in h.texts()
    assert not h.marked("models-row")


@pytest.mark.anyio
async def test_cleanup_cancels_the_trailing_redraw(
    user: User, env: Any, library_system: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    timers: list[_FakeTimer] = []

    def fake_timer(delay: float, callback: Any, once: bool = False) -> _FakeTimer:
        timers.append(_FakeTimer(delay, callback, once))
        return timers[-1]

    monkeypatch.setattr(editor_module.ui, "timer", fake_timer)
    h = env()
    _open_graph(h, library_system, ModelRef(catalog=KEY))
    h.view.graph_filter = "g1"
    await _open(user, h)
    assert timers  # mount's second draw reused the report
    h.editor.cleanup()
    assert all(t._is_canceled for t in timers)
