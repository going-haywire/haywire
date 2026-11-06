"""ModelsState: the two volumes and the Hugging Face cache default."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from haywire.core.volumes import get_volume_store

from haybale_models.keys import HF_VOLUME, MODELS_VOLUME
from haybale_models.state.models_state import ModelsState, hf_default_cache


@pytest.fixture(autouse=True)
def _clean_hf_env(monkeypatch):
    monkeypatch.delenv("HF_HUB_CACHE", raising=False)
    monkeypatch.delenv("HF_HOME", raising=False)


@pytest.fixture
def fresh(monkeypatch, tmp_path):
    """A fresh install: empty temp storage dir and volume store; every state is disabled again."""
    from haywire.core.volumes import VolumeStore, set_volume_store

    storage = tmp_path / "db" / "haybale_models"
    storage.mkdir(parents=True)  # what ``library_storage_dir`` creates
    monkeypatch.setattr("haybale_models.state.models_state.library_storage_dir", lambda _name: storage)
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hf"))
    previous = get_volume_store()
    set_volume_store(VolumeStore(tmp_path / "volumes.toml"))
    states: list[ModelsState] = []

    def make() -> ModelsState:
        state = ModelsState()
        states.append(state)
        return state

    yield SimpleNamespace(make=make, storage=storage, tmp=tmp_path)
    for state in states:
        state.on_disable()
    set_volume_store(previous)


def test_on_enable_adds_both_volumes(fresh):
    store = get_volume_store()
    fresh.make().on_enable()
    hf, models = store.entry(HF_VOLUME), store.entry(MODELS_VOLUME)
    assert hf is not None
    assert models is not None
    assert models.location is not None
    assert hf.location == fresh.tmp / "hf"
    assert models.location == fresh.storage / "models"


def test_fresh_on_enable_creates_only_the_default_models_folder(fresh):
    fresh.make().on_enable()
    assert (fresh.storage / "models").is_dir()
    assert not (fresh.tmp / "hf").exists()  # the Hugging Face cache is HF's to create


def test_download_to_fresh_models_volume_succeeds(fresh, http_server):
    import hashlib
    import time

    from haybale_models.resolver import FetchSpec
    from haybale_models.value.model_ref import ModelRef

    data = b"weights" * 100
    state = fresh.make()
    state.on_enable()
    url = http_server.file("/w.bin", data)
    ref = ModelRef(urls=(url,), sha256=hashlib.sha256(data).hexdigest(), label="w")
    (job_id,) = state.fetch([FetchSpec(ref=ref)], "tester")
    deadline = time.monotonic() + 5
    job = next(j for j in state.queue.jobs() if j.id == job_id)
    while job.state in ("queued", "running") and time.monotonic() < deadline:
        time.sleep(0.01)
        job = next(j for j in state.queue.jobs() if j.id == job_id)
    assert job.state == "done", job.error
    assert job.target is not None
    assert job.target.read_bytes() == data
    assert fresh.storage / "models" in job.target.parents


def test_on_disable_stops_watcher_queue_and_releases_pool(fresh, monkeypatch):
    state = fresh.make()
    calls: list[str] = []
    needs = SimpleNamespace(stop=lambda: calls.append("needs"))
    state._needs = needs  # type: ignore[assignment]
    monkeypatch.setattr(state.queue, "stop", lambda: calls.append("queue"))
    monkeypatch.setattr(state.pool, "release_all", lambda: calls.append("pool"))
    state.on_disable()
    assert calls == ["needs", "queue", "pool"]
    assert state._needs is None


def test_hf_default_order(monkeypatch, tmp_path):
    assert hf_default_cache() == Path("~/.cache/huggingface/hub").expanduser()
    monkeypatch.setenv("HF_HOME", str(tmp_path / "home"))
    assert hf_default_cache() == tmp_path / "home" / "hub"
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    assert hf_default_cache() == tmp_path / "hub"


def test_hf_default_expands_user(monkeypatch):
    monkeypatch.setenv("HF_HUB_CACHE", "~/somewhere")
    assert hf_default_cache() == Path("~/somewhere").expanduser()


def test_user_edited_location_survives_enable(models_env, monkeypatch, tmp_path, request):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "elsewhere"))
    state = ModelsState()
    request.addfinalizer(state.on_disable)
    state.on_enable()
    hf, models = models_env.entry(HF_VOLUME), models_env.entry(MODELS_VOLUME)
    assert hf is not None
    assert models is not None
    assert models.location is not None
    assert hf.location == tmp_path / "hf"
    assert models.location == tmp_path / "models"


def test_state_bridges_queue_and_index_to_models_changed(models_env):
    import asyncio
    import threading

    from nicegui import core

    from haybale_models.signals import ModelsChanged

    state = ModelsState()
    emitted: list[object] = []
    state._signal_emit = emitted.append  # type: ignore[method-assign,assignment]
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    previous = core.loop
    core.loop = loop
    try:
        state.queue._notify()
        state.index._notify()
        done = threading.Event()
        loop.call_soon_threadsafe(done.set)
        assert done.wait(2)
    finally:
        core.loop = previous
        loop.call_soon_threadsafe(loop.stop)
        thread.join(2)
    assert len(emitted) == 2
    assert all(isinstance(s, ModelsChanged) for s in emitted)
    assert ModelsChanged.cross_session is True


def test_fetch_with_nothing_to_download_returns_no_ids(models_env):
    from haybale_models.resolver import FetchSpec

    assert ModelsState().fetch([FetchSpec()], None) == []


def test_on_disable_stops_queue(models_env, monkeypatch):
    state = ModelsState()
    stopped: list[bool] = []
    monkeypatch.setattr(state.queue, "stop", lambda: stopped.append(True))
    state.on_disable()
    assert stopped == [True]


def test_on_enable_scans_in_background(models_env, monkeypatch, request):
    import threading

    state = ModelsState()
    request.addfinalizer(state.on_disable)
    ran = threading.Event()
    monkeypatch.setattr(state.index, "scan", lambda: ran.set() or [])  # type: ignore[func-returns-value]
    monkeypatch.setattr(state.index, "hash_pending", lambda: None)
    state.on_enable()
    assert ran.wait(2)


def test_files_changed_tells_the_needs_watcher_and_publishes(models_env, monkeypatch):
    state = ModelsState()
    published: list[bool] = []
    monkeypatch.setattr(state, "_on_models_changed", lambda: published.append(True))
    refreshed: list[bool] = []
    state._needs = SimpleNamespace(refresh=lambda: refreshed.append(True))  # type: ignore[assignment]
    state.files_changed()
    assert published == [True]
    assert refreshed == [True]
    state._needs = None
    state.files_changed()
    assert published == [True, True]
