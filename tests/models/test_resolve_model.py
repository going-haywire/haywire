"""Resolve Model: a MODEL_REF becomes a volume path, its sha256 and its size."""

from __future__ import annotations

import hashlib
import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from haywire.core.volumes import VolumePath, VolumeStore, location_of

from tests.conftest import make_node

pytestmark = pytest.mark.integration


def _node(graph: Any) -> Any:
    cls = importlib.import_module("haybale_models.nodes.resolve_model").ResolveModelNode
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


@pytest.fixture
def state(models_env: VolumeStore, monkeypatch: pytest.MonkeyPatch, library_system) -> Any:
    """A ModelsState stand-in over the temp volumes, with a fresh index."""
    consumer = importlib.import_module("haybale_models.consumer")
    index_mod = importlib.import_module("haybale_models.store.index")
    keys = importlib.import_module("haybale_models.keys")
    location_of(keys.MODELS_VOLUME).mkdir(parents=True, exist_ok=True)
    hf_root = location_of(keys.HF_VOLUME)
    hf_root.mkdir(parents=True, exist_ok=True)
    real = consumer.models_state()
    index = index_mod.ModelIndex()
    sources = importlib.import_module("haybale_models.sources").builtin_sources(
        index, hf_cache=lambda: hf_root
    )
    fake = SimpleNamespace(
        index=index, catalog=real.catalog, hf_cache=hf_root, sources=sources, pool=real.pool
    )
    monkeypatch.setattr(consumer, "models_state", lambda: fake)
    return fake


def _put(state: Any, relative: str, data: bytes) -> str:
    keys = importlib.import_module("haybale_models.keys")
    path = location_of(keys.MODELS_VOLUME) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    state.index.scan()
    state.index.hash_pending()
    return hashlib.sha256(data).hexdigest()


def _outputs(node: Any) -> dict[str, Any]:
    return {name: node.ports[name].get_value() for name in ("path", "sha256", "size")}


def test_resolve_model_outputs_volume_path(graph_with_library_system, state) -> None:
    keys = importlib.import_module("haybale_models.keys")
    ModelRef = importlib.import_module("haybale_models.value.model_ref").ModelRef
    sha = _put(state, "mine/x.pth", b"weights")
    node = _node(graph_with_library_system)
    ref = ModelRef(sha256=sha, size=7, label="x.pth")
    node.ports["model"].set_value(ref)

    node.worker(None, model=ref)

    out = _outputs(node)
    assert out["path"] == VolumePath(keys.MODELS_VOLUME, "mine/x.pth")
    assert out["sha256"] == sha
    assert out["size"] == 7


def test_an_undigested_hf_file_outputs_an_empty_sha256(
    graph_with_library_system, state, monkeypatch: pytest.MonkeyPatch
) -> None:
    keys = importlib.import_module("haybale_models.keys")
    ModelRef = importlib.import_module("haybale_models.value.model_ref").ModelRef
    snapshot = state.hf_cache / "models--org--repo" / "snapshots" / "abc" / "cfg.json"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_bytes(b"{}")
    huggingface_hub = importlib.import_module("huggingface_hub")
    monkeypatch.setattr(huggingface_hub, "try_to_load_from_cache", lambda *a, **k: str(snapshot))
    node = _node(graph_with_library_system)
    ref = ModelRef(urls=("hf://org/repo/cfg.json",))
    node.ports["model"].set_value(ref)

    node.worker(None, model=ref)

    out = _outputs(node)
    assert out["path"] == VolumePath(keys.HF_VOLUME, "models--org--repo/snapshots/abc/cfg.json")
    assert out["sha256"] == ""
    assert out["size"] == 2


def test_resolve_model_missing_raises_named_message(graph_with_library_system, state) -> None:
    ModelRef = importlib.import_module("haybale_models.value.model_ref").ModelRef
    ModelMissing = importlib.import_module("haybale_models.resolver").ModelMissing
    node = _node(graph_with_library_system)
    ref = ModelRef(catalog="haybale-nowhere:catalog:gone")
    node.ports["model"].set_value(ref)

    with pytest.raises(ModelMissing, match="catalog entry haybale-nowhere:catalog:gone is not installed"):
        node.worker(None, model=ref)


def test_a_file_outside_both_volumes_is_refused(tmp_path: Path, state) -> None:
    resolve_model = importlib.import_module("haybale_models.nodes.resolve_model")
    with pytest.raises(ValueError, match="in no model volume"):
        resolve_model._volume_path(tmp_path / "elsewhere.pth")


def test_resolve_model_outputs_a_cache_volume_path(
    graph_with_library_system, state, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ModelRef = importlib.import_module("haybale_models.value.model_ref").ModelRef
    monkeypatch.setenv("TORCH_HOME", str(tmp_path / "torch"))
    checkpoints = tmp_path / "torch" / "hub" / "checkpoints"
    checkpoints.mkdir(parents=True)
    (checkpoints / "w.pth").write_bytes(b"weights")
    node = _node(graph_with_library_system)
    ref = ModelRef(urls=("torchhub://w.pth",))
    node.ports["model"].set_value(ref)

    node.worker(None, model=ref)

    assert _outputs(node)["path"] == VolumePath("haybale-models:volume:torchhub", "w.pth")
