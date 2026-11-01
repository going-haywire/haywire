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
from haybale_models.needs import collect_needs
from haybale_models.resolver import resolve
from haybale_models.signals import ModelsChanged
from haybale_models.state.models_state import ModelsState
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
            needed_reports=lambda: self.reports,
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
        lambda ref, pref: resolve(ref, pref, catalog=m.catalog, index=m.index, hf_cache=m.hf_cache),
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

    def counting(resource: Any, index: Any, hf_cache: Any) -> Any:
        calls.append(resource)
        return real(resource, index, hf_cache)

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
    assert "pth · 2.4 MB · MIT ·" in h.texts()  # the format, not the full variant name
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
