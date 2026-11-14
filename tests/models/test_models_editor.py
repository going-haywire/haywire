"""ModelsEditor: needed / catalog / local / HF sections, Fetch all, admin gating, remove, progress."""

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
from nicegui import app as nicegui_app
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.core.access import AccessTier
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.library.identity import LibraryIdentity
from haywire.core.catalog import CatalogRegistry
from haywire.core.undo.no_op_history_manager import NoOpHistoryManager
from haywire.core.volumes import VolumeStore, location_of

from haybale_graph_editor.states.graph_app_state import GraphAppState
from haybale_models.download import DownloadJob
from haybale_models.editors import assisted_dialog
from haybale_models.editors import models_editor as editor_module
from haybale_models.editors.assisted_dialog import open_assisted_dialog
from haybale_models.editors.models_editor import ModelsEditor
from haybale_models.filters import FILTER_FIELDS
from haybale_models.hf import HfCachedFile
from haybale_models.keys import MODELS_VOLUME
from haybale_models.needs import collect_needs
from haybale_models.resolver import resolve
from haybale_models.sources import builtin_sources
from haybale_models.signals import ModelsChanged
from haybale_models.states.models_state import ModelsState
from haybale_models.store.index import ModelIndex
from haybale_models.store.records import FetchRecord, FetchRecords
from haybale_models.value.model_ref import ModelRef

from tests.conftest import make_node
from tests.models.conftest import make_hf_snapshot

pytestmark = pytest.mark.unit

DATA = b"weights-weights"
SHA = hashlib.sha256(DATA).hexdigest()
OTHER = b"other-bytes"
OTHER_SHA = hashlib.sha256(OTHER).hexdigest()
KEY = "haybale-alpha:catalog:Sharp"
URL = "https://example.invalid/sharp.pth"
ADDR = "https://example.invalid/files/pasted.pth"


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
        self.refuse = False
        self.assist: set[str] = set()

    def assistable(self, job_id: str) -> bool:
        return job_id in self.assist

    def jobs(self) -> list[DownloadJob]:
        return list(self.job_list)

    def cancel(self, job_id: str) -> bool:
        if self.refuse:
            return False
        self.cancelled.append(job_id)
        return True


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
        catalog = CatalogRegistry()
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
        self.files_changed: list[bool] = []
        index = ModelIndex()
        self.models = SimpleNamespace(
            index=index,
            records=FetchRecords(tmp_path / "fetched.json"),
            queue=_Queue(),
            catalog=catalog,
            hf_cache=tmp_path / "hf",
            sources=builtin_sources(index, hf_cache=lambda: tmp_path / "hf"),
            fetch=self._fetch,
            needed_reports=lambda: self.reports,
            files_changed=lambda: self.files_changed.append(True),
        )
        self.reports: dict[str, Any] = {}
        self.graphs = GraphAppState()
        self.graphs._signal_emit = lambda signal: None  # type: ignore[method-assign]
        self.ctx = SimpleNamespace(
            data={},
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


def _report_for(harness: _Harness, binding: str = "g1") -> None:
    graph = harness.graphs.get(binding).editor.graph  # type: ignore[union-attr]
    m = harness.models
    harness.reports[binding] = collect_needs(
        graph,
        lambda ref, pref: resolve(ref, pref, catalog=m.catalog, index=m.index, sources=m.sources),
    )


def _tooltip_of(harness: _Harness, mark: str) -> str:
    """Return the text of the tooltip aimed at the element marked *mark* (``.tooltip()`` adds a sibling)."""
    target = f"#{harness.marked(mark)[0].html_id}"
    assert harness.container is not None
    tips = [el for el in harness.container.descendants() if isinstance(el, ui.tooltip)]
    return next(t.text for t in tips if t.props.get("target") == target)


def test_identity() -> None:
    identity = ModelsEditor.class_identity
    assert identity.label == "Models"
    assert identity.requires is AccessTier.VIEW


@pytest.mark.anyio
@pytest.mark.anyio
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
@pytest.mark.anyio
@pytest.mark.anyio
@pytest.mark.anyio
async def test_hf_rows_sort_case_insensitively(
    user: User, env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import haybale_models.hf as hf_module

    class _File:
        def __init__(self, name: str) -> None:
            self.file_name = name
            self.file_path = Path("/snap") / name
            self.size_on_disk = 1
            self.blob_path = Path("/b")

    def repo(rid: str) -> Any:
        rev = SimpleNamespace(commit_hash="c", snapshot_path=Path("/snap"), files=[_File("f")])
        return SimpleNamespace(repo_type="model", repo_id=rid, revisions=[rev])

    monkeypatch.setattr(
        hf_module.huggingface_hub,
        "scan_cache_dir",
        lambda root: SimpleNamespace(repos=[repo("Kim2091/x"), repo("alpha/y"), repo("Zed/z")]),
    )
    rows = hf_module.list_cache(Path(__file__).parent)
    assert [r.repo_id for r in rows] == ["alpha/y", "Kim2091/x", "Zed/z"]


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
async def test_no_cancel_icon_for_a_running_job_that_cannot_stop(user: User, env: Any) -> None:
    h = env()
    h.models.queue.job_list = [
        DownloadJob(
            "dl-1",
            "Sharp",
            SHA,
            100,
            (URL,),
            state="running",
            done_bytes=45,
            total_bytes=100,
            cancellable=False,
        ),
        DownloadJob(
            "dl-2",
            "pasted",
            None,
            None,
            (ADDR,),
            state="running",
            done_bytes=1,
            total_bytes=9,
            cancellable=False,
        ),
    ]
    await _open(user, h)

    assert "downloading 45 %" in h.texts()
    assert h.marked("models-cancel") == []
    assert h.marked("models-needed-cancel") == []


@pytest.mark.anyio
async def test_cancel_icon_follows_a_running_job_that_becomes_unstoppable(user: User, env: Any) -> None:
    h = env()
    job = DownloadJob("dl-1", "Sharp", SHA, 100, (URL,), state="running", done_bytes=4, total_bytes=100)
    h.models.queue.job_list = [job]
    await _open(user, h)
    assert len(h.marked("models-cancel")) == 1

    job.cancellable = False  # the fetch moved to a source that cannot stop
    h.editor._on_models_changed(cast(Any, h.ctx), ModelsChanged())
    assert h.marked("models-cancel") == []

    job.cancellable = True  # and back to one that can
    h.editor._on_models_changed(cast(Any, h.ctx), ModelsChanged())
    assert len(h.marked("models-cancel")) == 1


@pytest.mark.anyio
async def test_a_refused_cancel_says_so(user: User, env: Any) -> None:
    h = env()
    h.models.queue.job_list = [
        DownloadJob("dl-1", "Sharp", SHA, 100, (URL,), state="running", done_bytes=4, total_bytes=100)
    ]
    await _open(user, h)
    h.models.queue.refuse = True  # the job became unstoppable after the icon was drawn
    user.find(marker="models-cancel").click()
    await user.should_see("This download can no longer be stopped")


@pytest.mark.anyio
async def test_progress_tick_updates_status_without_redraw(user: User, env: Any) -> None:
    h = env()
    job = DownloadJob("dl-1", "Sharp", SHA, 100, (URL,), state="running", done_bytes=45, total_bytes=100)
    h.models.queue.job_list = [job]
    await _open(user, h)
    h.wrapper.redraw.reset_mock()

    job.done_bytes = 80
    h.editor._on_models_changed(cast(Any, h.ctx), ModelsChanged())

    h.wrapper.redraw.assert_not_called()
    assert "downloading 80 %" in h.texts()
    assert "downloading 45 %" not in h.texts()


@pytest.mark.anyio
async def test_job_state_change_redraws(user: User, env: Any) -> None:
    h = env()
    job = DownloadJob("dl-1", "Sharp", SHA, 100, (URL,), state="running", done_bytes=45, total_bytes=100)
    h.models.queue.job_list = [job]
    await _open(user, h)
    h.wrapper.redraw.reset_mock()

    job.state = "failed"
    h.editor._on_models_changed(cast(Any, h.ctx), ModelsChanged())

    h.wrapper.redraw.assert_called_once()


@pytest.mark.anyio
async def test_scroll_position_is_restored_after_a_redraw(
    user: User, env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = env()
    await _open(user, h)
    h.editor._on_scroll(SimpleNamespace(vertical_position=240.0))
    calls: list[float] = []
    monkeypatch.setattr(ui.scroll_area, "scroll_to", lambda self, *, pixels=None, **kw: calls.append(pixels))

    h.redraw()

    assert calls == [240.0]


@pytest.mark.anyio
async def test_unknown_progress_says_downloading_without_percent(user: User, env: Any) -> None:
    h = env()
    h.models.queue.job_list = [
        DownloadJob("dl-1", "Sharp", SHA, 100, (URL,), state="running", done_bytes=0, total_bytes=100)
    ]
    await _open(user, h)

    assert "downloading…" in h.texts()
    assert "downloading 0 %" not in h.texts()


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
@pytest.mark.anyio
async def test_one_locate_per_catalog_row_per_draw(
    user: User, env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = env()
    await _open(user, h)
    calls: list[Any] = []
    real = editor_module.locate_resource

    def counting(resource: Any, *args: Any) -> Any:
        calls.append(resource)
        return real(resource, *args)

    monkeypatch.setattr(editor_module, "locate_resource", counting)
    h.redraw()

    assert len(h.marked("models-row")) == 2
    assert len(calls) == 2


@pytest.mark.anyio
@pytest.mark.anyio
@pytest.mark.anyio
@pytest.mark.anyio
@pytest.mark.anyio
@pytest.mark.anyio
@pytest.mark.anyio
async def test_downloads_section_lists_non_catalog_jobs_only(user: User, env: Any) -> None:
    h = env()
    h.models.queue.job_list = [
        DownloadJob("dl-1", "pasted", None, None, (ADDR,), state="running", done_bytes=10, total_bytes=100),
        DownloadJob("dl-2", "Sharp", SHA, 100, (URL,), state="running", done_bytes=5, total_bytes=100),
        DownloadJob("dl-3", "broken", None, None, ("https://b.invalid/x",), state="failed", error="boom"),
        DownloadJob("dl-4", "done", None, None, ("https://d.invalid/y",), state="done"),
    ]
    await _open(user, h)

    assert len(h.marked("models-download-row")) == 2
    assert "Downloads" in h.texts()
    assert "downloading 10 %" in h.texts()
    assert "failed: boom" in h.texts()
    assert len(h.marked("models-cancel")) == 2  # catalog row + the one active non-catalog job
    h.models.queue.job_list = [j for j in h.models.queue.job_list if j.id != "dl-2"]
    h.redraw()
    assert len(h.marked("models-cancel")) == 1
    user.find(marker="models-cancel").click()
    assert h.models.queue.cancelled == ["dl-1"]

    h.tier = AccessTier.VIEW
    h.redraw()
    assert len(h.marked("models-download-row")) == 2
    assert not h.marked("models-cancel")


@pytest.mark.anyio
async def test_view_lists_graph_with_missing_model_without_walking(
    user: User, env: Any, library_system: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = env()
    _open_graph(h, library_system, ModelRef(catalog=KEY))
    _report_for(h)
    walks: list[Any] = []

    def _spy(*a: Any, **k: Any) -> Any:
        walks.append(a)
        return iter(())

    monkeypatch.setattr(editor_module, "iter_model_refs", _spy)
    await _open(user, h)

    assert len(h.marked("models-needed-row")) == 1
    assert "Needed" in h.texts()
    assert "Rig" in h.texts()
    assert "1 model, 2.4 MB" in h.texts()
    assert walks == []


@pytest.mark.anyio
@pytest.mark.anyio
async def test_needed_fetch_enqueues_and_rechecks_at_click(
    user: User, env: Any, library_system: Any
) -> None:
    h = env()
    _open_graph(h, library_system, ModelRef(catalog=KEY))
    _report_for(h)
    await _open(user, h)

    assert h.marked("models-needed-fetch")
    h.tier = AccessTier.VIEW  # demoted after the draw
    user.find(marker="models-needed-fetch").click()
    assert h.fetched == []
    h.tier = AccessTier.ADMIN
    user.find(marker="models-needed-fetch").click()
    assert [s.entry.name for s in h.fetched] == ["Sharp"]


@pytest.mark.anyio
async def test_needed_section_absent_when_nothing_is_missing(
    user: User, env: Any, library_system: Any
) -> None:
    h = env()
    h.put("alpha/Sharp/sharp.pth", DATA)
    _open_graph(h, library_system, ModelRef(catalog=KEY))
    _report_for(h)
    await _open(user, h)

    assert not h.marked("models-needed-row")
    assert "Needed" not in h.texts()


@pytest.mark.anyio
async def test_needed_lists_graph_name_and_each_missing_model_with_an_action(
    user: User, env: Any, library_system: Any
) -> None:
    h = env()
    _open_graph(h, library_system, ModelRef(catalog=KEY), name="Rig")
    _report_for(h)
    await _open(user, h)

    assert "Rig" in h.texts()
    assert len(h.marked("models-needed-model")) == 1
    assert "Sharp · 4x" in h.texts()
    assert any(t.endswith("2.4 MB") for t in h.texts())
    assert len(h.marked("models-needed-download")) == 1
    user.find(marker="models-needed-download").click()
    assert [s.entry.name for s in h.fetched] == ["Sharp"]


@pytest.mark.anyio
async def test_needed_model_line_has_no_action_below_admin(
    user: User, env: Any, library_system: Any
) -> None:
    h = env(AccessTier.VIEW)
    _open_graph(h, library_system, ModelRef(catalog=KEY))
    _report_for(h)
    await _open(user, h)
    assert h.marked("models-needed-model")
    assert not h.marked("models-needed-download")


@pytest.mark.anyio
async def test_needed_model_progress_tick_updates_in_place(
    user: User, env: Any, library_system: Any
) -> None:
    h = env()
    _open_graph(h, library_system, ModelRef(urls=(ADDR,)))
    _report_for(h)
    job = DownloadJob("dl-9", "pasted", None, None, (ADDR,), state="running", done_bytes=30, total_bytes=100)
    h.models.queue.job_list = [job]
    await _open(user, h)
    assert "pasted.pth" in h.texts()
    assert h.marked("models-needed-cancel")
    h.wrapper.redraw.reset_mock()

    job.done_bytes = 60
    h.editor._on_models_changed(cast(Any, h.ctx), ModelsChanged())

    h.wrapper.redraw.assert_not_called()
    assert "downloading 60 %" in h.texts()
    assert "downloading 30 %" not in h.texts()


@pytest.mark.anyio
async def test_catalog_row_shows_name_and_a_detail_line(user: User, env: Any) -> None:
    h = env()
    await _open(user, h)

    assert "Sharp · 4x" in h.texts()  # name with scale (and precision, when the variant has one)
    # What it is (architecture), then the format, not the full variant name.
    assert "esrgan · pth · 2.4 MB · MIT ·" in h.texts()
    assert "not downloaded" in h.texts()
    assert h.marked("models-download")


HF_CAT_URL = "hf://org/cat/w1.safetensors"
HF_GRAPH_URL = "hf://org/graph/w2.safetensors@main"


def _hf_catalog_entry(h: _Harness, tmp_path: Path) -> None:
    folder = tmp_path / "catalog" / "haybale-alpha"
    doc = _doc("HfModel", "d" * 64, HF_CAT_URL)
    (folder / "HfModel.json").write_text(json.dumps(doc))
    h.models.catalog.register_file(
        folder / "HfModel.json",
        LibraryIdentity(
            label="Alpha", name="haybale-alpha", folder_path=str(folder), module_name="haybale-alpha"
        ),
    )


@pytest.mark.anyio
async def test_hf_section_lists_only_used_files_with_their_users(
    user: User, env: Any, library_system: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = env()
    _hf_catalog_entry(h, tmp_path)
    _open_graph(h, library_system, ModelRef(urls=(HF_GRAPH_URL,)), name="Rig")
    hf = [
        HfCachedFile("org/cat", "abcdef123456", "w1.safetensors", 5000, Path("/x")),
        HfCachedFile("org/graph", "abcdef123456", "w2.safetensors", 7000, Path("/y")),
        HfCachedFile("org/other", "abcdef123456", "unrelated.bin", 9000, Path("/z")),
    ]
    monkeypatch.setattr(editor_module, "list_cache", lambda root: hf)
    await _open(user, h)

    texts = h.texts()
    assert "org/cat/w1.safetensors" in texts
    assert "org/graph/w2.safetensors" in texts
    assert "org/other/unrelated.bin" not in texts
    assert len(h.marked("models-hf-row")) == 2
    used = [el.text for el in h.marked("models-hf-used")]
    assert "catalog: HfModel" in used
    assert "graph: Rig" in used
    assert "Huggingface — 2 files, 12.0 KB" in texts  # the header counts what it lists
    assert _tooltip_of(h, "models-header-huggingface") == (
        "Hugging Face cache: 21.0 KB in all, shared with other tools"
    )
    assert not h.marked("models-remove")
    assert not h.marked("models-hf-reveal")


@pytest.mark.anyio
async def test_hf_section_lists_files_of_a_whole_repo_entry(
    user: User, env: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = env()
    commit = "c" * 40
    folder = tmp_path / "catalog" / "haybale-alpha"
    doc = _doc("RepoModel", "d" * 64, f"hf://o/r@{commit}")
    doc["resources"][0]["include"] = ["*.safetensors"]
    (folder / "RepoModel.json").write_text(json.dumps(doc))
    h.models.catalog.register_file(
        folder / "RepoModel.json",
        LibraryIdentity(
            label="Alpha", name="haybale-alpha", folder_path=str(folder), module_name="haybale-alpha"
        ),
    )
    hf = [
        HfCachedFile("o/r", commit, "a.safetensors", 100, Path("/x")),
        HfCachedFile("o/r", commit, "b.bin", 200, Path("/y")),
        HfCachedFile("o/r", "e" * 40, "a.safetensors", 300, Path("/z")),
    ]
    monkeypatch.setattr(editor_module, "list_cache", lambda root: hf)
    await _open(user, h)

    texts = h.texts()
    assert "o/r/a.safetensors" in texts
    assert "o/r/b.bin" not in texts
    assert len(h.marked("models-hf-row")) == 1
    assert [el.text for el in h.marked("models-hf-used")] == ["catalog: RepoModel"]


@pytest.mark.anyio
async def test_hf_section_hidden_when_no_cached_file_is_used(
    user: User, env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = env()
    hf = [HfCachedFile("org/other", "abcdef123456", "unrelated.bin", 9000, Path("/z"))]
    monkeypatch.setattr(editor_module, "list_cache", lambda root: hf)
    await _open(user, h)

    assert not h.marked("models-hf-section")
    assert not h.marked("models-hf-row")
    assert "HF cache" not in h.texts()


@pytest.mark.anyio
async def test_finished_hf_download_refreshes_hf_rows_once(
    user: User, env: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = env()
    _hf_catalog_entry(h, tmp_path)
    reads: list[int] = []
    cached: list[HfCachedFile] = []

    def fake_list(root: Path) -> list[HfCachedFile]:
        reads.append(1)
        return list(cached)

    monkeypatch.setattr(editor_module, "list_cache", fake_list)
    await _open(user, h)
    assert len(reads) == 1
    assert not h.marked("models-hf-row")

    cached.append(HfCachedFile("org/cat", "abcdef123456", "w1.safetensors", 10, Path("/x")))
    job = DownloadJob("dl-1", "W", None, 10, (HF_CAT_URL,), state="running")
    h.models.queue.job_list = [job]
    h.editor._on_models_changed(cast(Any, h.ctx), ModelsChanged())  # progress tick
    assert len(reads) == 1

    job.state = "done"
    h.editor._on_models_changed(cast(Any, h.ctx), ModelsChanged())
    thread = h.editor._hf_thread
    assert thread is not None
    thread.join(5)
    h.editor._on_models_changed(cast(Any, h.ctx), ModelsChanged())  # same finished set
    assert len(reads) == 2
    h.redraw()
    assert len(h.marked("models-hf-row")) == 1


# =============================================================================
# The filter row: "Show:" toggles and search
# =============================================================================


@pytest.mark.anyio
async def test_show_toggles_hide_and_bring_back_sections(user: User, env: Any) -> None:
    h = env()
    h.put("mine/loose.bin", b"loose")
    await _open(user, h)
    assert "Sharp · 4x" in h.texts()
    assert "mine/loose.bin" in h.texts()

    user.find(marker="models-filters").click()
    user.find(marker="models-filter-catalog").click()
    assert "Sharp · 4x" not in h.texts()
    assert not h.marked("models-header-catalog")
    assert "mine/loose.bin" in h.texts()  # Models still lists only files no catalog entry occupies

    user.find(marker="models-filter-models").click()
    assert "mine/loose.bin" not in h.texts()

    user.find(marker="models-filter-catalog").click()
    user.find(marker="models-filter-models").click()
    assert "Sharp · 4x" in h.texts()
    assert "mine/loose.bin" in h.texts()


@pytest.mark.anyio
async def test_search_narrows_every_section_and_hiding_it_clears(user: User, env: Any) -> None:
    h = env()
    h.put("mine/loose.bin", b"loose")
    await _open(user, h)
    assert not h.marked("models-search")

    user.find(marker="models-filters").click()
    user.find(marker="models-filter-search").click()
    cast(ui.input, h.marked("models-search")[0]).value = "soft"
    texts = h.texts()
    assert "Soft · 4x" in texts
    assert "Sharp · 4x" not in texts
    assert "mine/loose.bin" not in texts

    user.find(marker="models-filter-search").click()
    assert not h.marked("models-search")
    assert "Sharp · 4x" in h.texts()
    assert "mine/loose.bin" in h.texts()


@pytest.mark.anyio
async def test_section_headers_count_what_they_list(user: User, env: Any) -> None:
    h = env()
    h.put("mine/loose.bin", b"loose")
    h.put("lib/sharp.pth", DATA)  # occupied by the Sharp catalog entry
    await _open(user, h)
    texts = h.texts()

    assert "Catalog — 2 files, 4.8 MB" in texts
    assert "Models — 1 file, 5 B" in texts  # only the file no catalog entry occupies
    assert _tooltip_of(h, "models-header-models").startswith("Models volume: ")
    assert "Local" not in texts
    assert not any(t.startswith("models: ") for t in texts)


@pytest.mark.anyio
async def test_rows_carry_their_sections_dot(user: User, env: Any) -> None:
    h = env()
    h.put("mine/loose.bin", b"loose")
    await _open(user, h)

    assert len(h.marked("models-dot-catalog")) == 2  # Sharp and Soft
    assert len(h.marked("models-dot-models")) == 1
    assert "bg-blue-500" in h.marked("models-dot-catalog")[0].classes
    assert "bg-green-500" in h.marked("models-dot-models")[0].classes


@pytest.mark.anyio
async def test_catalog_row_of_an_unserved_address_says_so_and_has_no_download(
    user: User, env: Any, tmp_path: Path
) -> None:
    h = env()
    folder = tmp_path / "catalog" / "haybale-alpha"
    (folder / "Demo.json").write_text(json.dumps(_doc("Demo", "e" * 64, "demo://w")))
    h.models.catalog.register_file(
        folder / "Demo.json",
        LibraryIdentity(
            label="Alpha", name="haybale-alpha", folder_path=str(folder), module_name="haybale-alpha"
        ),
    )
    await _open(user, h)

    assert "source unavailable: demo:// not provided" in h.texts()
    assert len(h.marked("models-download")) == 2  # Sharp and Soft only


def _torchhub_entry(h: _Harness, tmp_path: Path, cache: str) -> None:
    folder = tmp_path / "catalog" / "haybale-alpha"
    doc = _doc("Hubbed", "e" * 64, "https://x.invalid/hubbed.pth")
    doc["resources"][0]["cache"] = cache
    (folder / "Hubbed.json").write_text(json.dumps(doc))
    h.models.catalog.register_file(
        folder / "Hubbed.json",
        LibraryIdentity(
            label="Alpha", name="haybale-alpha", folder_path=str(folder), module_name="haybale-alpha"
        ),
    )


@pytest.mark.anyio
async def test_editor_row_in_a_cache_shows_its_place_and_no_download(
    user: User, env: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TORCH_HOME", str(tmp_path / "torch"))
    checkpoints = tmp_path / "torch" / "hub" / "checkpoints"
    checkpoints.mkdir(parents=True)
    (checkpoints / "hubbed.pth").write_bytes(b"w" * 2_400_000)  # the catalog size
    h = env()
    _torchhub_entry(h, tmp_path, "torchhub://hubbed.pth")
    await _open(user, h)

    statuses = [el.text for el in h.marked("models-status")]
    assert "Torch Hub cache" in statuses
    assert len(h.marked("models-download")) == 2  # Sharp and Soft only, not the cached Hubbed
    assert len(h.marked("models-remove")) == 1  # the catalog entry entitles Remove


@pytest.mark.anyio
async def test_an_unserved_cache_prefix_reads_source_unavailable_and_offers_no_download(
    user: User, env: Any, tmp_path: Path
) -> None:
    h = env()
    _torchhub_entry(h, tmp_path, "demo://hubbed.pth")
    await _open(user, h)

    assert "source unavailable: demo:// not provided" in [el.text for el in h.marked("models-status")]
    assert len(h.marked("models-download")) == 2


@pytest.mark.anyio
async def test_an_unused_cache_volume_is_no_problem(
    user: User, env: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TORCH_HOME", str(tmp_path / "never"))
    h = env()
    _torchhub_entry(h, tmp_path, "torchhub://hubbed.pth")
    await _open(user, h)

    statuses = [el.text for el in h.marked("models-status")]
    assert statuses.count("not downloaded") == 3
    assert not any("unavailable" in t for t in statuses)


def _cached_hubbed(h: _Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, record: bool) -> Path:
    """Put the Hubbed entry's file in the torch hub cache; with *record*, as fetched for that entry."""
    monkeypatch.setenv("TORCH_HOME", str(tmp_path / "torch"))
    checkpoints = tmp_path / "torch" / "hub" / "checkpoints"
    checkpoints.mkdir(parents=True)
    path = checkpoints / "hubbed.pth"
    path.write_bytes(b"w" * 2_400_000)  # the catalog size
    _torchhub_entry(h, tmp_path, "torchhub://hubbed.pth")
    if record:
        source = h.models.sources.lookup("torchhub://hubbed.pth")
        assert source is not None
        root = source.root()
        assert root is not None
        entry = next(e for e in h.models.catalog.entries() if e.name == "Hubbed")
        h.models.records.add(
            FetchRecord(
                source.volume,
                path.relative_to(root).as_posix(),
                "e" * 64,
                entry.class_identity.registry_key,
                "torchhub://hubbed.pth",
            )
        )
    return path


def _hubbed_status(h: _Harness) -> list[str]:
    return [cast(Any, el).text for el in h.marked("models-status")]


@pytest.mark.anyio
async def test_fetched_cache_file_can_be_removed(
    user: User, env: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = env()
    path = _cached_hubbed(h, tmp_path, monkeypatch, record=True)
    # as ModelsState wires it: a records change becomes ModelsChanged
    h.models.records.add_listener(lambda: h.editor._on_models_changed(cast(Any, h.ctx), ModelsChanged()))
    await _open(user, h)
    assert "Torch Hub cache" in _hubbed_status(h)
    assert len(h.marked("models-remove")) == 1

    user.find(marker="models-remove").click()
    await user.should_see("Delete")
    user.find(content="Delete", kind=ui.button).click()

    assert not path.exists()
    assert h.models.records._records == []
    assert "Torch Hub cache" not in _hubbed_status(h)
    assert _hubbed_status(h).count("not downloaded") == 3


@pytest.mark.anyio
async def test_unrecorded_cache_file_can_be_removed(
    user: User, env: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = env()
    path = _cached_hubbed(h, tmp_path, monkeypatch, record=False)
    await _open(user, h)
    assert "Torch Hub cache" in _hubbed_status(h)
    assert len(h.marked("models-remove")) == 1

    user.find(marker="models-remove").click()
    await user.should_see("Delete")
    user.find(content="Delete", kind=ui.button).click()
    assert not path.exists()
    assert _hubbed_status(h).count("not downloaded") == 3


@pytest.mark.anyio
async def test_cache_remove_confirmation_names_entries_and_shared_cache(
    user: User, env: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = env()
    _cached_hubbed(h, tmp_path, monkeypatch, record=True)
    await _open(user, h)
    user.find(marker="models-remove").click()
    await user.should_see("This file is in the shared Torch Hub cache; other tools may use it.")
    await user.should_see("Catalog entries: Hubbed")


@pytest.mark.anyio
async def test_viewer_cannot_remove_from_a_cache(
    user: User, env: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = env(AccessTier.VIEW)
    path = _cached_hubbed(h, tmp_path, monkeypatch, record=True)
    await _open(user, h)
    assert not h.marked("models-remove")

    removal = editor_module._Removal("Hubbed", cache_paths=(path,))
    h.editor._remove(cast(Any, h.ctx), cast(Any, h.models), removal, user._client)
    assert path.exists()
    assert len(h.models.records._records) == 1


@pytest.mark.anyio
async def test_cache_remove_needs_no_fetch_record(
    user: User, env: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = env()
    path = _cached_hubbed(h, tmp_path, monkeypatch, record=False)
    await _open(user, h)
    removal = editor_module._Removal("Hubbed", cache_paths=(path,))
    h.editor._remove(cast(Any, h.ctx), cast(Any, h.models), removal, user._client)
    assert not path.exists()


def _second_hubbed(h: _Harness, tmp_path: Path) -> Any:
    """A second catalog entry whose resource is the same torch hub file as Hubbed."""
    folder = tmp_path / "catalog" / "haybale-alpha"
    doc = _doc("Twin", "e" * 64, "https://x.invalid/hubbed.pth")
    doc["resources"][0]["cache"] = "torchhub://hubbed.pth"
    (folder / "Twin.json").write_text(json.dumps(doc))
    h.models.catalog.register_file(
        folder / "Twin.json",
        LibraryIdentity(
            label="Alpha", name="haybale-alpha", folder_path=str(folder), module_name="haybale-alpha"
        ),
    )
    return next(e for e in h.models.catalog.entries() if e.name == "Twin")


@pytest.mark.anyio
async def test_cache_remove_confirmation_names_every_entry_sharing_the_file(
    user: User, env: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = env()
    _cached_hubbed(h, tmp_path, monkeypatch, record=True)  # record for Hubbed only
    _second_hubbed(h, tmp_path)
    await _open(user, h)
    user.find(marker="models-remove").click()
    await user.should_see("Catalog entries: Hubbed · 4x, Twin · 4x")


@pytest.mark.anyio
async def test_every_row_sharing_a_cache_file_has_remove(
    user: User, env: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = env()
    path = _cached_hubbed(h, tmp_path, monkeypatch, record=True)  # record for Hubbed
    _second_hubbed(h, tmp_path)
    await _open(user, h)
    assert len(h.marked("models-remove")) == 2  # Hubbed's and Twin's rows

    removal = editor_module._Removal("Twin", cache_paths=(path,))
    h.editor._remove(cast(Any, h.ctx), cast(Any, h.models), removal, user._client)
    assert not path.exists()
    assert h.models.records._records == []


def _register(h: _Harness, tmp_path: Path, doc: dict[str, Any]) -> Any:
    folder = tmp_path / "catalog" / "haybale-alpha"
    (folder / f"{doc['name']}.json").write_text(json.dumps(doc))
    h.models.catalog.register_file(
        folder / f"{doc['name']}.json",
        LibraryIdentity(
            label="Alpha", name="haybale-alpha", folder_path=str(folder), module_name="haybale-alpha"
        ),
    )
    return next(e for e in h.models.catalog.entries() if e.name == doc["name"])


@pytest.mark.anyio
async def test_cache_file_changed_since_its_fetch_can_be_removed(
    user: User, env: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TORCH_HOME", str(tmp_path / "torch"))
    checkpoints = tmp_path / "torch" / "hub" / "checkpoints"
    checkpoints.mkdir(parents=True)
    path = checkpoints / "unsized.pth"
    path.write_bytes(b"fetched")
    h = env()
    doc = _doc("Unsized", "e" * 64, "https://x.invalid/unsized.pth")
    del doc["resources"][0]["size"]
    del doc["resources"][0]["sha256"]
    doc["resources"][0]["cache"] = "torchhub://unsized.pth"
    entry = _register(h, tmp_path, doc)
    source = h.models.sources.lookup("torchhub://unsized.pth")
    assert source is not None
    h.models.records.add(
        FetchRecord(
            source.volume,
            "unsized.pth",
            "e" * 64,
            entry.class_identity.registry_key,
            "torchhub://unsized.pth",
            len(b"fetched"),
        )
    )
    path.write_bytes(b"replaced by another tool")
    await _open(user, h)
    assert "Torch Hub cache" in _hubbed_status(h)
    assert len(h.marked("models-remove")) == 1


@pytest.mark.anyio
async def test_bundle_split_over_a_cache_and_the_models_volume_can_be_removed(
    user: User, env: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KERAS_HOME", str(tmp_path / "keras"))
    xml, binary = b"<net/>", b"bin-weights"
    xml_sha, bin_sha = hashlib.sha256(xml).hexdigest(), hashlib.sha256(binary).hexdigest()
    (tmp_path / "keras" / "models").mkdir(parents=True)
    xml_path = tmp_path / "keras" / "models" / "a.xml"
    xml_path.write_bytes(xml)
    h = env()
    bin_path = h.put("a.bin", binary)
    doc = _doc("Mixed", "e" * 64, "https://x.invalid/a.xml")
    doc["resources"] = [
        {
            "platform": "openvino",
            "type": "xml",
            "files": [
                {
                    "path": "a.xml",
                    "sha256": xml_sha,
                    "size": len(xml),
                    "urls": ["https://x.invalid/a.xml"],
                    "cache": "keras://a.xml",
                },
                {
                    "path": "a.bin",
                    "sha256": bin_sha,
                    "size": len(binary),
                    "urls": ["https://x.invalid/a.bin"],
                },
            ],
        }
    ]
    entry = _register(h, tmp_path, doc)
    source = h.models.sources.lookup("keras://a.xml")
    assert source is not None
    assert source.root() is not None
    h.models.records.add(
        FetchRecord(
            source.volume, "a.xml", xml_sha, entry.class_identity.registry_key, "keras://a.xml", len(xml)
        )
    )
    h.models.records.add_listener(lambda: h.editor._on_models_changed(cast(Any, h.ctx), ModelsChanged()))
    h.models.index.add_listener(lambda: h.editor._on_models_changed(cast(Any, h.ctx), ModelsChanged()))
    await _open(user, h)
    assert "Keras cache" in _hubbed_status(h)
    assert len(h.marked("models-remove")) == 1

    user.find(marker="models-remove").click()
    await user.should_see("Delete")
    user.find(content="Delete", kind=ui.button).click()

    assert not xml_path.exists()
    assert not bin_path.exists()
    assert h.models.records.all() == ()
    assert h.models.index.by_sha256(bin_sha) is None
    assert _hubbed_status(h).count("not downloaded") == 3


WHOLE_COMMIT = "a" * 40


def _whole_repo_entry(h: _Harness, tmp_path: Path, include: tuple[str, ...] = ("*.bin",)) -> Any:
    doc = _doc("Whole", "e" * 64, "https://x.invalid/unused")
    doc["resources"] = [
        {
            "platform": "pytorch",
            "type": "bin",
            "urls": [f"hf://o/r@{WHOLE_COMMIT}"],
            "include": list(include),
        }
    ]
    return _register(h, tmp_path, doc)


async def _confirm_remove(user: User) -> None:
    user.find(marker="models-remove").click()
    await user.should_see("Delete")
    user.find(content="Delete", kind=ui.button).click()


@pytest.mark.anyio
async def test_whole_repo_entry_can_be_removed(user: User, env: Any, tmp_path: Path) -> None:
    files = {"a.bin": b"weights", "unet/b.bin": b"more", "c.json": b"{}"}
    snap = make_hf_snapshot(tmp_path / "hf", "o/r", WHOLE_COMMIT, files, list(files), linked=True)
    h = env()
    _whole_repo_entry(h, tmp_path)
    await _open(user, h)
    assert "HF cache" in _hubbed_status(h)
    assert len(h.marked("models-remove")) == 1

    await _confirm_remove(user)
    assert not (snap / "a.bin").exists()
    assert not (snap / "unet" / "b.bin").exists()
    assert (snap / "c.json").read_bytes() == b"{}"  # not in include: not the entry's file
    assert _hubbed_status(h).count("not downloaded") == 3


@pytest.mark.anyio
async def test_single_file_hf_entry_can_be_removed(user: User, env: Any, tmp_path: Path) -> None:
    data = b"hf weights"
    snap = make_hf_snapshot(tmp_path / "hf", "o/r", WHOLE_COMMIT, {"w.bin": data}, None, linked=True)
    blob = (snap / "w.bin").resolve()
    h = env()
    doc = _doc("Single", hashlib.sha256(data).hexdigest(), f"hf://o/r/w.bin@{WHOLE_COMMIT}")
    doc["resources"][0]["size"] = len(data)
    _register(h, tmp_path, doc)
    await _open(user, h)
    assert "HF cache" in _hubbed_status(h)

    await _confirm_remove(user)
    assert not (snap / "w.bin").exists()
    assert not blob.exists()
    assert _hubbed_status(h).count("not downloaded") == 3
    assert h.files_changed  # so a node using the file learns it is gone


@pytest.mark.anyio
async def test_cache_remove_never_unlinks_outside_the_volume(
    user: User, env: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TORCH_HOME", str(tmp_path / "torch"))
    checkpoints = tmp_path / "torch" / "hub" / "checkpoints"
    checkpoints.mkdir(parents=True)
    outside = tmp_path / "elsewhere.pth"
    outside.write_bytes(b"w" * 2_400_000)
    (checkpoints / "hubbed.pth").symlink_to(outside)
    h = env()
    _torchhub_entry(h, tmp_path, "torchhub://hubbed.pth")
    await _open(user, h)
    removal = editor_module._Removal("Hubbed", cache_paths=(checkpoints / "hubbed.pth", outside))
    h.editor._remove(cast(Any, h.ctx), cast(Any, h.models), removal, user._client)
    assert outside.exists()


def _failed_job(
    job_id: str = "dl-1", sha: str | None = SHA, url: str = URL, label: str = "Sharp"
) -> DownloadJob:
    return DownloadJob(job_id, label, sha, 2_400_000, (url,), state="failed", error="HTTP 404")


def _assistable(harness: _Harness, *jobs: DownloadJob) -> None:
    harness.models.queue.job_list.extend(jobs)
    harness.models.queue.assist.update(j.id for j in jobs)


def _layout(user: User) -> ui.element:
    assert user.client is not None
    return user.client.layout


def _page_marked(user: User, mark: str) -> list[ui.element]:
    return [el for el in _layout(user).descendants() if mark in el._markers]  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_failed_job_offers_download_in_browser_on_a_catalog_row(user: User, env: Any) -> None:
    harness = env()
    _assistable(harness, _failed_job())
    await _open(user, harness)
    assert harness.marked("models-assisted")


@pytest.mark.anyio
async def test_failed_job_offers_it_in_the_downloads_section(user: User, env: Any) -> None:
    harness = env()
    _assistable(harness, _failed_job(sha="d" * 64, url=ADDR, label="pasted"))
    await _open(user, harness)
    assert harness.marked("models-download-assisted")


@pytest.mark.anyio
async def test_no_offer_when_the_job_does_not_qualify(user: User, env: Any) -> None:
    harness = env()
    harness.models.queue.job_list.append(_failed_job())
    await _open(user, harness)
    assert not harness.marked("models-assisted")


@pytest.mark.anyio
async def test_no_offer_for_view_tier(user: User, env: Any) -> None:
    harness = env(AccessTier.VIEW)
    _assistable(harness, _failed_job())
    await _open(user, harness)
    assert not harness.marked("models-assisted")


@pytest.mark.anyio
async def test_no_offer_when_the_file_is_found(user: User, env: Any) -> None:
    harness = env()
    harness.put("x/sharp.pth", DATA)
    _assistable(harness, _failed_job())
    await _open(user, harness)
    assert not harness.marked("models-assisted")


@pytest.mark.anyio
async def test_redraw_keeps_the_open_dialog(user: User, env: Any) -> None:
    harness = env()
    _assistable(harness, _failed_job())
    await _open(user, harness)
    user.find(marker="models-assisted").click()
    uploads = _page_marked(user, "assisted-upload")
    assert len(uploads) == 1
    harness.redraw()
    assert not uploads[0].is_deleted
    assert _page_marked(user, "assisted-upload") == uploads


@pytest.mark.anyio
async def test_one_slot_per_failed_file_with_links_and_notice(user: User, env: Any) -> None:
    harness = env()
    hf_job = _failed_job("dl-1", "a" * 64, "hf://org/repo/a.bin@abc", "a.bin")
    web_job = _failed_job("dl-2", None, URL, "b.bin")
    harness.models.queue.job_list.extend([hf_job, web_job])
    await _open(user, harness)
    with _layout(user):
        open_assisted_dialog(cast(Any, harness.models), "alice", [hf_job, web_job])
    assert len(_page_marked(user, "assisted-slot")) == 2
    links = {el._props["href"] for el in _page_marked(user, "assisted-link")}
    assert links == {"https://huggingface.co/org/repo/blob/abc/a.bin", URL}
    assert len(_page_marked(user, "assisted-no-digest")) == 1


@pytest.mark.anyio
async def test_close_while_active_confirms_then_stops(user: User, env: Any, monkeypatch: Any) -> None:
    harness = env()
    job = _failed_job()
    upload_job = DownloadJob("dl-2", "Sharp", SHA, None, (URL,), state="running", via_browser=True)
    harness.models.queue.job_list.extend([job, upload_job])
    confirmed: list[Any] = []
    monkeypatch.setattr(assisted_dialog, "confirm_modal", lambda **kw: confirmed.append(kw))
    began: list[Any] = []
    real_mount = assisted_dialog.mount_upload_route

    def mount(*args: Any, **kw: Any) -> Any:
        began.append(kw["on_begin"])
        return real_mount(*args, **kw)

    monkeypatch.setattr(assisted_dialog, "mount_upload_route", mount)
    await _open(user, harness)
    with _layout(user):
        open_assisted_dialog(cast(Any, harness.models), "alice", [job])
    began[0]("dl-2")
    routes_before = {getattr(r, "path", "") for r in nicegui_app.router.routes}
    user.find(marker="assisted-close").click()
    assert confirmed
    assert harness.models.queue.cancelled == []
    confirmed[0]["on_confirm"]()
    assert harness.models.queue.cancelled == ["dl-2"]
    assert not _page_marked(user, "assisted-upload")
    gone = routes_before - {getattr(r, "path", "") for r in nicegui_app.router.routes}
    assert any(path.startswith("/_haybale_models/upload/") for path in gone)


@pytest.mark.anyio
async def test_a_long_failure_cannot_push_the_row_actions_away(user: User, env: Any) -> None:
    harness = env()
    error = f"digest mismatch: got {'a' * 64}, expected {'b' * 64}"
    job = DownloadJob("dl-1", "Sharp", SHA, None, (URL,), state="failed", error=error)
    _assistable(harness, job)
    await _open(user, harness)
    status = harness.marked("models-status")[0]
    assert "flex-shrink-0" not in status._classes
    assert {"truncate", "min-w-0"} <= set(status._classes)
    assert isinstance(status, ui.label)
    assert error in status.text
    assert harness.container is not None
    tips = [el for el in harness.container.descendants() if isinstance(el, ui.tooltip)]
    assert any(tip.props.get("target") == f"#{status.html_id}" and error in tip.text for tip in tips)


def _filter_doc(name: str, **fields: Any) -> dict[str, Any]:
    return {
        **_doc(name, hashlib.sha256(name.encode()).hexdigest(), f"https://x.invalid/{name}.pth"),
        **fields,
    }


def _add_entries(harness: _Harness, tmp_path: Path, *documents: dict[str, Any]) -> None:
    """Replace the catalog by *documents*, in a library of their own."""
    folder = tmp_path / "filter-catalog"
    folder.mkdir(exist_ok=True)
    for document in documents:
        (folder / f"{document['name']}.json").write_text(json.dumps(document))
    catalog = CatalogRegistry()
    catalog.add_folder(
        str(folder),
        LibraryIdentity(
            label="Beta", name="haybale-beta", folder_path=str(folder), module_name="haybale-beta"
        ),
    )
    harness.models.catalog = catalog


def _add_field(user: User, field: str) -> None:
    user.find(marker=f"models-filter-add-{field}").click()


def _select(harness: _Harness, field: str) -> ui.select:
    return cast(ui.select, harness.marked(f"models-select-{field}")[0])


def _pick(user: User, harness: _Harness, field: str, *values: str) -> None:
    if not harness.marked(f"models-select-{field}"):
        _add_field(user, field)
    _select(harness, field).value = list(values)


def _titles(harness: _Harness) -> list[str]:
    return [t for t in harness.texts() if " · " in t and t.split(" · ")[0] in {"Aaa", "Bbb", "Ccc"}]


@pytest.mark.anyio
async def test_the_filter_section_starts_closed(user: User, env: Any) -> None:
    h = env()
    await _open(user, h)
    assert h.marked("models-filters")
    assert not h.marked("models-filter")
    assert not h.marked("models-filter-catalog")


@pytest.mark.anyio
async def test_the_icon_opens_the_section_with_show_and_search(user: User, env: Any) -> None:
    h = env()
    await _open(user, h)
    user.find(marker="models-filters").click()
    assert h.marked("models-filter-catalog")
    assert h.marked("models-filter-search")


@pytest.mark.anyio
async def test_the_open_section_survives_a_redraw(user: User, env: Any, tmp_path: Path) -> None:
    h = env()
    _add_entries(h, tmp_path, _filter_doc("Aaa", tags=["anime"]), _filter_doc("Bbb", tags=["photo"]))
    await _open(user, h)
    user.find(marker="models-filters").click()
    _pick(user, h, "tags", "anime")
    h.redraw()
    assert _select(h, "tags").value == ["anime"]
    assert len(h.marked("models-row")) == 1


@pytest.mark.anyio
async def test_closing_switches_the_filters_off_and_reopening_restores_them(
    user: User, env: Any, tmp_path: Path
) -> None:
    h = env()
    _add_entries(h, tmp_path, _filter_doc("Aaa", tags=["anime"]), _filter_doc("Bbb", tags=["photo"]))
    h.put("mine/loose.bin", b"loose")
    await _open(user, h)
    user.find(marker="models-filters").click()
    _pick(user, h, "tags", "anime")
    user.find(marker="models-filter-models").click()
    user.find(marker="models-filter-search").click()
    cast(ui.input, h.marked("models-search")[0]).value = "aaa"
    assert "mine/loose.bin" not in h.texts()
    assert len(h.marked("models-row")) == 1

    user.find(marker="models-filters").click()
    assert not h.marked("models-filter")
    assert "mine/loose.bin" in h.texts()
    assert len(h.marked("models-row")) == 3  # Aaa, Bbb and the loose file

    user.find(marker="models-filters").click()
    assert _select(h, "tags").value == ["anime"]
    assert cast(ui.input, h.marked("models-search")[0]).value == "aaa"
    assert "mine/loose.bin" not in h.texts()
    assert len(h.marked("models-row")) == 1


@pytest.mark.anyio
async def test_a_redraw_while_closed_keeps_the_settings_off(user: User, env: Any, tmp_path: Path) -> None:
    h = env()
    _add_entries(h, tmp_path, _filter_doc("Aaa", tags=["anime"]), _filter_doc("Bbb", tags=["photo"]))
    await _open(user, h)
    user.find(marker="models-filters").click()
    _pick(user, h, "tags", "anime")
    user.find(marker="models-filters").click()
    h.redraw()
    assert len(h.marked("models-row")) == 2
    user.find(marker="models-filters").click()
    assert len(h.marked("models-row")) == 1


@pytest.mark.anyio
async def test_no_field_row_until_one_is_added(user: User, env: Any, tmp_path: Path) -> None:
    h = env()
    _add_entries(h, tmp_path, _filter_doc("Aaa", tags=["anime"]))
    await _open(user, h)
    user.find(marker="models-filters").click()
    for key, _label in FILTER_FIELDS:
        assert h.marked(f"models-filter-add-{key}")
        assert not h.marked(f"models-select-{key}")


@pytest.mark.anyio
async def test_an_added_field_leaves_the_menu_and_x_brings_it_back(
    user: User, env: Any, tmp_path: Path
) -> None:
    h = env()
    _add_entries(h, tmp_path, _filter_doc("Aaa", tags=["anime"]), _filter_doc("Bbb", tags=["photo"]))
    await _open(user, h)
    user.find(marker="models-filters").click()
    _pick(user, h, "tags", "anime")
    assert len(h.marked("models-row")) == 1
    assert not h.marked("models-filter-add-tags")
    user.find(marker="models-filter-remove-tags").click()
    assert not h.marked("models-select-tags")
    assert h.marked("models-filter-add-tags")
    assert len(h.marked("models-row")) == 2


@pytest.mark.anyio
async def test_fields_stay_in_the_order_they_were_added(user: User, env: Any, tmp_path: Path) -> None:
    h = env()
    _add_entries(h, tmp_path, _filter_doc("Aaa", tags=["anime"]), _filter_doc("Bbb", tags=["photo"]))
    await _open(user, h)
    user.find(marker="models-filters").click()
    _add_field(user, "status")
    _add_field(user, "tags")
    assert h.container is not None
    selects = [e for e in h.container.descendants() if isinstance(e, ui.select)]
    assert selects == [_select(h, "status"), _select(h, "tags")]


@pytest.mark.anyio
async def test_a_row_with_nothing_selected_narrows_nothing(user: User, env: Any, tmp_path: Path) -> None:
    h = env()
    _add_entries(h, tmp_path, _filter_doc("Aaa", tags=["anime"]), _filter_doc("Bbb", tags=["photo"]))
    await _open(user, h)
    user.find(marker="models-filters").click()
    _add_field(user, "tags")
    assert len(h.marked("models-row")) == 2


@pytest.mark.anyio
async def test_a_selection_narrows_the_catalog_only(user: User, env: Any, tmp_path: Path) -> None:
    h = env()
    _add_entries(h, tmp_path, _filter_doc("Aaa", tags=["anime"]), _filter_doc("Bbb", tags=["photo"]))
    h.put("mine/loose.bin", b"loose")
    await _open(user, h)
    user.find(marker="models-filters").click()
    _pick(user, h, "tags", "anime")
    titles = {t.split(" · ")[0] for t in h.texts()}
    assert "Aaa" in titles
    assert "Bbb" not in titles
    assert "mine/loose.bin" in h.texts()


@pytest.mark.anyio
async def test_or_within_and_between_fields_in_the_list(user: User, env: Any, tmp_path: Path) -> None:
    h = env()
    _add_entries(
        h,
        tmp_path,
        _filter_doc("Aaa", tags=["anime"], scale=2),
        _filter_doc("Bbb", tags=["photo"], scale=4),
        _filter_doc("Ccc", tags=["other"], scale=4),
    )
    await _open(user, h)
    user.find(marker="models-filters").click()
    _pick(user, h, "tags", "anime", "photo")
    assert len(h.marked("models-row")) == 2
    _pick(user, h, "scale", "4x")
    assert len(h.marked("models-row")) == 1


@pytest.mark.anyio
async def test_a_field_with_one_value_or_none_works_like_any_other(
    user: User, env: Any, tmp_path: Path
) -> None:
    h = env()
    _add_entries(h, tmp_path, _filter_doc("Aaa", tags=[], architecture="esrgan"))
    await _open(user, h)
    user.find(marker="models-filters").click()
    _add_field(user, "architecture")
    _add_field(user, "tags")
    assert list(_select(h, "architecture").options) == ["esrgan"]
    assert list(_select(h, "tags").options) == []


@pytest.mark.anyio
async def test_status_is_per_resource(user: User, env: Any, tmp_path: Path) -> None:
    h = env()
    sha = hashlib.sha256(DATA).hexdigest()
    document = _filter_doc("Aaa")
    document["resources"] = [
        {
            "platform": "pytorch",
            "type": "pth",
            "size": len(DATA),
            "sha256": sha,
            "urls": ["https://x.invalid/a.pth"],
        },
        {
            "platform": "onnx",
            "type": "onnx",
            "size": 5,
            "sha256": "e" * 64,
            "urls": ["https://x.invalid/a.onnx"],
        },
    ]
    _add_entries(h, tmp_path, document)
    h.put("x/a.pth", DATA)
    await _open(user, h)
    user.find(marker="models-filters").click()
    _pick(user, h, "status", "on this machine")
    assert len(h.marked("models-row")) == 1


@pytest.mark.anyio
async def test_a_stale_selection_does_not_empty_the_list(user: User, env: Any, tmp_path: Path) -> None:
    h = env()
    _add_entries(h, tmp_path, _filter_doc("Aaa", tags=["anime"]), _filter_doc("Bbb", tags=["photo"]))
    await _open(user, h)
    user.find(marker="models-filters").click()
    _pick(user, h, "tags", "anime")
    _add_entries(h, tmp_path, _filter_doc("Aaa", tags=["photo"]), _filter_doc("Bbb", tags=["other"]))
    h.redraw()
    assert _select(h, "tags").value == []
    assert len(h.marked("models-row")) == 2


@pytest.mark.anyio
async def test_a_selection_keeps_the_same_select(user: User, env: Any, tmp_path: Path) -> None:
    """Rebuilding the select on a pick would close its dropdown after every value."""
    h = env()
    _add_entries(h, tmp_path, _filter_doc("Aaa", tags=["anime"]), _filter_doc("Bbb", tags=["photo"]))
    await _open(user, h)
    user.find(marker="models-filters").click()
    _add_field(user, "tags")
    select = _select(h, "tags")
    select.value = ["anime"]
    assert _select(h, "tags") is select
    assert not select.is_deleted


@pytest.mark.anyio
async def test_row_says_non_commercial_unless_flagged(user: User, env: Any, tmp_path: Path) -> None:
    h = env()
    _add_entries(h, tmp_path, _filter_doc("Aaa"), _filter_doc("Bbb", commercial=True))
    await _open(user, h)
    labels = h.marked("models-non-commercial")
    assert len(labels) == 1
    assert cast(ui.label, labels[0]).text == "non-commercial ·"
    # Its own element, so a long summary beside it cannot cut it off.
    assert "flex-shrink-0" in labels[0]._classes
    assert "truncate" not in labels[0]._classes


@pytest.mark.anyio
async def test_recommended_changes_nothing_in_the_editor(user: User, env: Any, tmp_path: Path) -> None:
    h = env()
    _add_entries(h, tmp_path, _filter_doc("Aaa"), _filter_doc("Bbb", recommended=True))
    await _open(user, h)
    assert [t for t in h.texts() if t.startswith(("Aaa", "Bbb"))] == ["Aaa · 4x", "Bbb · 4x"]
    assert not any("ecommended" in t for t in h.texts())
    user.find(marker="models-filters").click()
    assert "recommended" not in {key for key, _label in FILTER_FIELDS}


@pytest.mark.anyio
async def test_the_fields_scroll_rather_than_squeeze_the_list(user: User, env: Any) -> None:
    h = env()
    await _open(user, h)
    user.find(marker="models-filters").click()
    classes = h.marked("models-filter-fields")[0]._classes
    assert "overflow-y-auto" in classes
    assert any(c.startswith("max-h-") for c in classes)


def test_the_editor_docs_name_the_filters() -> None:
    doc = ModelsEditor.__doc__ or ""
    assert "**Filters**" in doc
    assert "**+**" in doc
    assert "non-commercial" in doc
    assert "Recommended" not in doc
    assert "reopening" in doc


def _search(user: User, harness: _Harness, text: str) -> None:
    if not harness.marked("models-filter-search"):
        user.find(marker="models-filters").click()
    if not harness.marked("models-search"):
        user.find(marker="models-filter-search").click()
    cast(ui.input, harness.marked("models-search")[0]).value = text


@pytest.mark.anyio
async def test_search_takes_several_words_across_fields(user: User, env: Any, tmp_path: Path) -> None:
    h = env()
    _add_entries(
        h,
        tmp_path,
        _filter_doc("Aaa", tags=["anime"], scale=2),
        _filter_doc("Bbb", tags=["anime"], scale=4, commercial=True),
    )
    await _open(user, h)
    _search(user, h, "anime 4x")
    assert len(h.marked("models-row")) == 1
    _search(user, h, "4x anime")
    assert len(h.marked("models-row")) == 1
    _search(user, h, "commercial anime")
    assert len(h.marked("models-row")) == 1
    _search(user, h, "non-commercial")
    assert len(h.marked("models-row")) == 1
    _search(user, h, "anime nosuchword")
    assert not h.marked("models-row")


@pytest.mark.anyio
async def test_search_takes_several_words_in_the_models_section(user: User, env: Any) -> None:
    h = env()
    h.put("mine/loose.bin", b"loose")
    await _open(user, h)
    _search(user, h, "loose mine")
    assert "mine/loose.bin" in h.texts()
    _search(user, h, "loose nosuchword")
    assert "mine/loose.bin" not in h.texts()


@pytest.mark.anyio
async def test_adding_a_field_never_closes_a_deleted_menu(
    user: User, env: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The row's click redraws the fields, which deletes the menu the row then closes."""
    closed_deleted: list[bool] = []
    real_close = ui.menu.close

    def close(self: ui.menu) -> None:
        closed_deleted.append(self.is_deleted)
        real_close(self)

    monkeypatch.setattr(ui.menu, "close", close)
    h = env()
    _add_entries(h, tmp_path, _filter_doc("Aaa", tags=["anime"]))
    await _open(user, h)
    user.find(marker="models-filters").click()
    _add_field(user, "tags")
    assert h.marked("models-select-tags")
    assert True not in closed_deleted
