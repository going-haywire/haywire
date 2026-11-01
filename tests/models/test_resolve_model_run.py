"""Resolve Model through a real graph run: BeginPlay -> Print, Size wired into the Print message."""

from __future__ import annotations

import hashlib
import importlib
import json
import threading
from pathlib import Path
from typing import Any

import pytest

from haywire.core.assembly.flow_assembly_manager import FlowAssemblyManager
from haywire.core.execution.event_source import Trigger
from haywire.core.execution.vm import HaywireVM
from haywire.core.library.identity import LibraryIdentity
from haywire.core.volumes import VolumeStore, location_of

from tests.conftest import make_node

pytestmark = pytest.mark.integration


def _add(graph: Any, module: str, name: str) -> Any:
    cls = getattr(importlib.import_module(module), name)
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def _node_of(graph: Any, node_id: str) -> Any:
    wrapper = graph.get_node_wrapper(node_id)
    assert wrapper is not None
    return wrapper.node


def _record(seen: list[Any], printer: Any) -> Any:
    def worker(context: Any) -> str:
        seen.append(printer.value("message"))
        return "done"

    return worker


@pytest.mark.parametrize("reload", [False, True], ids=["fresh", "reloaded"])
@pytest.mark.parametrize("via", ["file", "catalog", "dict"])
def test_resolve_model_size_reaches_a_downstream_print(
    graph_with_library_system: Any,
    models_env: VolumeStore,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    via: str,
    reload: bool,
) -> None:
    graph = graph_with_library_system
    keys = importlib.import_module("haybale_models.keys")
    consumer = importlib.import_module("haybale_models.consumer")
    ModelRef = importlib.import_module("haybale_models.value.model_ref").ModelRef
    state = consumer.models_state()
    data = b"weights-bytes"
    path = location_of(keys.MODELS_VOLUME) / "mine" / "x.pth"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    state.index.scan()
    state.index.hash_pending()

    begin = _add(graph, "haybale_core.nodes.events.begin_play", "BeginPlayNode")
    resolve = _add(graph, "haybale_models.nodes.resolve_model", "ResolveModelNode")
    printer = _add(graph, "haybale_core.nodes.print", "PrintNode")
    graph.create_edge_wrapper(begin.node_id, "exec", printer.node_id, "exec")
    graph.create_edge_wrapper(resolve.node_id, "size", printer.node_id, "message")
    sha = hashlib.sha256(data).hexdigest()
    if via in ("file", "dict"):
        ref = ModelRef(sha256=sha, size=len(data))
    else:
        folder = tmp_path / "cat"
        folder.mkdir()
        (folder / f"demo_{reload}.json").write_text(
            json.dumps(
                {
                    "name": "Demo",
                    "resources": [
                        {"platform": "onnx", "type": "onnx", "precision": "fp32", "size": 1, "sha256": sha}
                    ],
                }
            )
        )
        identity = LibraryIdentity(
            label="T", name="haybale-t", folder_path=str(tmp_path), module_name="haybale_t"
        )
        state.catalog.add_folder(str(folder), identity)
        ref = ModelRef(catalog=f"haybale-t:catalog:demo_{reload}")
    resolve.ports["model"].set_value(ref.to_dict() if via == "dict" else ref)

    if reload:
        from haywire.core.graph.base import BaseGraph
        from haywire.core.graph.scheduler import SyncScheduler

        saved = json.loads(json.dumps(graph.to_dict(include_data=True)))
        graph = BaseGraph(filestem="Reloaded", validation_scheduler=SyncScheduler())
        assert graph.load_from_dict(saved)
        begin = _node_of(graph, begin.node_id)
        resolve = _node_of(graph, resolve.node_id)
        printer = _node_of(graph, printer.node_id)

    seen: list[Any] = []
    monkeypatch.setattr(printer, "worker", _record(seen, printer))
    graph.force_validation()
    flows = FlowAssemblyManager().assemble_graph(graph)
    flow = next(f for f in flows if f.get_entry_node_id() == begin.node_id)
    trigger = Trigger(source_key=flow.get_subscription_key(), payload={}, timestamp=0.0)
    runner = threading.Thread(target=lambda: HaywireVM().execute_control_flow(flow, trigger))
    runner.start()
    runner.join()

    assert seen == [f"{float(len(data))}"], (seen, resolve.ports["size"].get_value())
    assert resolve.ports["size"].get_value() == len(data)
