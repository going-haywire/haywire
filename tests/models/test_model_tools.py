"""models_list / models_needs / models_fetch, driven directly (no MCP transport)."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from haywire.core.access import AccessTier
from haywire.core.farmhand import FarmhandError
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.library.identity import LibraryIdentity
from haywire.core.models import ModelCatalogRegistry
from haywire.core.undo.no_op_history_manager import NoOpHistoryManager
from haywire.core.volumes import VolumeStore, location_of

from haybale_graph_editor.state.graph_app_state import GraphAppState
from haybale_models.download import DownloadJob
from haybale_models.farmhands.model_tools import ModelsFetchTool, ModelsListTool, ModelsNeedsTool
from haybale_models.keys import MODELS_VOLUME
from haybale_models.state.models_state import ModelsState
from haybale_models.store.index import ModelIndex
from haybale_models.value.model_ref import ModelRef

from tests.conftest import make_node

pytestmark = pytest.mark.integration

DATA = b"weights-weights"
SHA = hashlib.sha256(DATA).hexdigest()
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
        "description": "sharpens",
        "resources": [
            {"platform": "pytorch", "type": "pth", "size": 2_400_000, "sha256": sha, "urls": [url]}
        ],
    }


@dataclass
class _Container:
    binding_id: str
    editor: Any


class _Queue:
    def __init__(self) -> None:
        self.job_list: list[DownloadJob] = []

    def jobs(self) -> list[DownloadJob]:
        return list(self.job_list)


class _Ctx:
    def __init__(self, models: Any, graphs: GraphAppState, principal: str | None = "alice") -> None:
        self._states: dict[Any, Any] = {ModelsState: models, GraphAppState: graphs}
        self.principal = principal

    def state(self, cls: type) -> Any:
        return self._states[cls]


class _Env:
    def __init__(self, tmp_path: Path) -> None:
        catalog = ModelCatalogRegistry()
        folder = tmp_path / "catalog" / "haybale-alpha"
        folder.mkdir(parents=True)
        (folder / "Sharp.json").write_text(json.dumps(_doc("Sharp", SHA, URL)))
        catalog.add_folder(
            str(folder),
            LibraryIdentity(
                label="Alpha", name="haybale-alpha", folder_path=str(folder), module_name="haybale-alpha"
            ),
        )
        self.fetched: list[tuple[list[Any], str | None]] = []

        def fetch(specs: list[Any], principal: str | None) -> list[str]:
            self.fetched.append((specs, principal))
            return ["job-1"]

        self.models = SimpleNamespace(
            index=ModelIndex(),
            queue=_Queue(),
            catalog=catalog,
            hf_cache=tmp_path / "hf",
            fetch=fetch,
        )
        self.graphs = GraphAppState()
        self.graphs._signal_emit = lambda signal: None  # type: ignore[method-assign]
        self.ctx = _Ctx(self.models, self.graphs)

    def run(self, tool: Any, **kwargs: Any) -> dict:
        return asyncio.run(tool().run(self.ctx, **kwargs))

    def open_graph(self, library_system: Any, *refs: ModelRef) -> None:
        from haybale_models.nodes.resolve_model import ResolveModelNode

        graph = BaseGraph(filestem="Rig", validation_scheduler=SyncScheduler())
        for value in refs:
            wrapper = make_node(graph, ResolveModelNode.class_identity.registry_key, position=(0, 0))
            wrapper.node.ports["model"].set_value(value)
        self.graphs.register(
            cast(Any, _Container("g1", SimpleNamespace(graph=graph, history_manager=NoOpHistoryManager())))
        )


@pytest.fixture
def env(models_env: VolumeStore, tmp_path: Path) -> _Env:
    location_of(MODELS_VOLUME).mkdir(parents=True, exist_ok=True)
    return _Env(tmp_path)


def test_list_shape_and_detail_flag(env: _Env) -> None:
    (location_of(MODELS_VOLUME) / "loose.bin").write_bytes(b"abc")
    env.models.index.scan()
    env.models.index.hash_pending()
    env.models.queue.job_list.append(
        DownloadJob("j1", "Sharp", SHA, None, (URL,), state="running", done_bytes=1, total_bytes=4)
    )

    brief = env.run(ModelsListTool)
    [entry] = brief["catalog"]
    assert entry["key"] == KEY
    assert entry["name"] == "Sharp"
    assert "license" not in entry
    assert "description" not in entry
    assert entry["variants"] == [{"variant": "pytorch-pth", "size": 2_400_000, "status": "downloading 25 %"}]
    assert [r["relative"] for r in brief["local"]] == ["loose.bin"]
    assert set(brief["local"][0]) == {"relative", "size", "sha256"}
    assert brief["jobs"] == [
        {"id": "j1", "label": "Sharp", "state": "running", "done_bytes": 1, "total_bytes": 4, "error": None}
    ]

    full = env.run(ModelsListTool, detail=True)
    assert full["catalog"][0]["license"] == "MIT"
    assert full["catalog"][0]["description"] == "sharpens"


def test_list_reports_local_status(env: _Env) -> None:
    (location_of(MODELS_VOLUME) / "sharp.pth").write_bytes(DATA)
    env.models.index.scan()
    env.models.index.hash_pending()
    assert env.run(ModelsListTool)["catalog"][0]["variants"][0]["status"] == "local"


def test_needs_for_open_graph(env: _Env, library_system: Any) -> None:
    ref = ModelRef(catalog=KEY)
    env.open_graph(library_system, ref, ref)
    result = env.run(ModelsNeedsTool, binding_id="g1")
    [row] = result["missing"]
    assert row["label"] == "Sharp"
    assert row["size"] == 2_400_000
    assert len(row["node_ids"]) == 2
    assert len(set(row["node_ids"])) == 2


def test_needs_unknown_binding_errors(env: _Env) -> None:
    with pytest.raises(FarmhandError) as caught:
        env.run(ModelsNeedsTool, binding_id="nope")
    assert caught.value.code == "graph_not_open"
    assert caught.value.help is not None
    assert "haystack_list_graphs" in caught.value.help


def test_fetch_requires_admin() -> None:
    assert ModelsFetchTool.class_identity.requires is AccessTier.ADMIN
    assert ModelsListTool.class_identity.requires is AccessTier.VIEW
    assert ModelsNeedsTool.class_identity.requires is AccessTier.VIEW


def test_fetch_enqueues_and_returns_ids(env: _Env, library_system: Any) -> None:
    result = env.run(ModelsFetchTool, keys=[KEY])
    assert result["job_ids"] == ["job-1"]
    [(specs, principal)] = env.fetched
    assert principal == "alice"
    assert specs[0].entry is not None
    assert specs[0].entry.class_identity.registry_key == KEY

    env.open_graph(library_system, ModelRef(catalog=KEY))
    result = env.run(ModelsFetchTool, binding_id="g1")
    assert result["job_ids"] == ["job-1"]
    assert len(env.fetched[1][0]) == 1


def test_fetch_errors(env: _Env) -> None:
    with pytest.raises(FarmhandError) as unknown:
        env.run(ModelsFetchTool, keys=["haybale-alpha:model:Nope"])
    assert unknown.value.code == "unknown_model"
    assert unknown.value.help is not None
    with pytest.raises(FarmhandError):
        env.run(ModelsFetchTool)
    assert env.fetched == []
