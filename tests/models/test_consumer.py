"""Consumer helpers: preference, resolve with warnings, pooled acquire."""

from __future__ import annotations

import hashlib
from types import SimpleNamespace
from typing import Any, cast

import pytest

from haywire.core.catalog import ModelFile, Resource
from haywire.core.node.node_wrapper import NodeWrapperState
from haywire.core.volumes import VolumeStore, location_of

from haybale_models import consumer
from haybale_models.keys import MODELS_VOLUME
from haybale_models.pool import LoadedModels
from haybale_models.resolver import ModelMissing
from haybale_models.store.index import ModelIndex
from haybale_models.value.model_ref import ModelRef

KEY = "lib:catalog:demo"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def res(data: bytes, precision: str) -> Resource:
    return Resource(
        "pytorch", "pth", None, sha(data), (), (ModelFile("", sha(data), None, ()),), None, precision
    )


def make_node(value: Any, prefer: Any = None, hook: Any = None) -> Any:
    port = SimpleNamespace(
        widget_config={"properties": {"prefer": prefer}} if prefer is not None else {},
        get_value=lambda: value,
    )
    wrapper = SimpleNamespace(state=NodeWrapperState(), redraws=0)

    def replace_warnings(kind: str, warnings: Any) -> bool:
        changed = wrapper.state.replace_warnings(kind, warnings)
        if changed:
            wrapper.redraws += 1
        return changed

    wrapper.replace_warnings = replace_warnings
    node = SimpleNamespace(ports={"m": port}, wrapper=wrapper)
    if hook is not None:
        node.model_preference = hook
    return node


@pytest.fixture
def env(models_env: VolumeStore, monkeypatch: pytest.MonkeyPatch) -> Any:
    root = location_of(MODELS_VOLUME, models_env)
    root.mkdir(parents=True, exist_ok=True)
    index = ModelIndex()
    entry = SimpleNamespace(
        resources=(res(b"half", "fp16"), res(b"full", "fp32")),
        class_identity=SimpleNamespace(registry_key=KEY),
        name="demo",
    )
    catalog = SimpleNamespace(entry=lambda k: entry if k == KEY else None)
    state = SimpleNamespace(pool=LoadedModels(), index=index, catalog=catalog, hf_cache=None)
    monkeypatch.setattr(consumer, "models_state", lambda: state)

    def put(name: str, data: bytes) -> None:
        (root / name).write_bytes(data)
        index.scan()
        index.hash_pending()

    state.put = put
    return state


def test_preference_from_node_hook_beats_port() -> None:
    node = make_node(None, prefer=[{"precision": "fp16"}], hook=lambda port_id: [{"precision": "fp32"}])
    assert consumer.preference_for(cast(Any, node), "m") == [{"precision": "fp32"}]


def test_preference_from_port_then_default() -> None:
    assert consumer.preference_for(make_node(None, prefer=[{"a": "b"}]), "m") == [{"a": "b"}]
    assert consumer.preference_for(make_node(None, prefer=[]), "m") == [{}]
    assert consumer.preference_for(make_node(None), "m") == [{}]


def test_resolve_port_sets_and_clears_model_warnings(env: Any) -> None:
    env.put("full.pth", b"full")
    node = make_node(ModelRef(catalog=KEY), prefer=[{"precision": "fp16"}, {}])
    consumer.resolve_port(node, "m")
    msgs = [w.message for w in node.wrapper.state.warnings if w.kind == "model"]
    assert msgs == ["Preferred variant pytorch-pth-fp16 is not downloaded — Show in Models"]
    env.put("half.pth", b"half")
    consumer.resolve_port(node, "m")
    assert node.wrapper.state.warnings == []


def test_unpinned_file_ref_warns_and_missing_clears(env: Any) -> None:
    env.put("w.pth", b"w")
    path = location_of(MODELS_VOLUME) / "w.pth"
    env.index.add(path, sha(b"w"), "https://x/w.pth")
    node = make_node(ModelRef(urls=("https://x/w.pth",)))
    consumer.resolve_port(node, "m")
    assert [w.message for w in node.wrapper.state.warnings] == ["Not pinned — use the pin on the card"]
    node.ports["m"].get_value = lambda: ModelRef(urls=("https://x/none",))
    with pytest.raises(ModelMissing):
        consumer.resolve_port(node, "m")
    assert [w.message for w in node.wrapper.state.warnings] == ["Model missing — Show in Models"]
    node.ports["m"].get_value = lambda: ModelRef.empty()
    with pytest.raises(ModelMissing):
        consumer.resolve_port(node, "m")
    assert node.wrapper.state.warnings == []


def test_warning_change_redraws_once_unchanged_not(env: Any) -> None:
    env.put("full.pth", b"full")
    node = make_node(ModelRef(catalog=KEY), prefer=[{"precision": "fp16"}, {}])
    consumer.resolve_port(node, "m")
    assert node.wrapper.redraws == 1
    consumer.resolve_port(node, "m")
    assert node.wrapper.redraws == 1


def test_acquire_port_shares_across_nodes_and_release_node(env: Any) -> None:
    env.put("full.pth", b"full")
    n1, n2 = make_node(ModelRef(catalog=KEY)), make_node(ModelRef(catalog=KEY))
    loads: list[Any] = []
    freed: list[Any] = []

    def load(r: Any) -> object:
        loads.append(r)
        return object()

    a = consumer.acquire_port(n1, "m", variant_key="cpu", load=load, release=freed.append)
    b = consumer.acquire_port(n2, "m", variant_key="cpu", load=load, release=freed.append)
    assert a is b
    assert len(loads) == 1
    consumer.release_node(n1)
    assert freed == []
    consumer.release_node(n2)
    assert freed == [a]
