"""The uninstall flow's state machine. UI rendering is smoke-tested only.

The properties under test: the venv is not touched until the final step, and
the impact step informs without ever blocking.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend() -> str:
    """anyio's backend parametrization. The repo runs asyncio only."""
    return "asyncio"


class _FakeSource:
    """Stands in for LibraryManager: records the uninstall instead of running it."""

    def __init__(self, *, dist_name: str = "haybale-vision", install_type: str = "REGULAR") -> None:
        self._dist_name = dist_name
        self._install_type = install_type
        self.uninstalled: list[str] = []
        self.result: tuple[bool, str, object] = (True, "Uninstalled: haybale-vision", None)
        self.raises: Exception | None = None

    def get_library_distribution_name(self, library_id: str) -> str | None:
        return self._dist_name

    def get_library_install_type(self, library_id: str) -> str:
        return self._install_type

    async def uninstall_streaming(self, library_id: str, on_output):
        if self.raises is not None:
            raise self.raises
        on_output(f"Removing {library_id}…")
        self.uninstalled.append(library_id)
        return self.result


def _graph(path: Path, *registry_keys: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    nodes = {f"N{i}": {"node_id": f"N{i}", "registry_key": key} for i, key in enumerate(registry_keys)}
    path.write_text(json.dumps({"graph_id": path.stem, "nodes": nodes, "edges": {}}))


def _flow(root: Path | None = None, source: _FakeSource | None = None):
    from haybale_marketplace.editors._uninstall_flow import UninstallFlow

    return UninstallFlow(
        source=source or _FakeSource(),
        library_id="visiongraph",
        label="VisionGraph",
        workspace_root=root,
    )


@pytest.mark.anyio
async def test_impact_scan_does_not_uninstall(tmp_path: Path) -> None:
    source = _FakeSource()
    flow = _flow(tmp_path, source)

    await flow.advance_from_selected()

    assert flow.step == "impact"
    assert flow.error is None
    assert source.uninstalled == []


@pytest.mark.anyio
async def test_impact_reports_graph_usage(tmp_path: Path) -> None:
    _graph(tmp_path / "cam.haywire", "visiongraph:node:Cam", "visiongraph:type:Frame")
    _graph(tmp_path / "other.haywire", "core:node:BeginPlay")
    flow = _flow(tmp_path)

    await flow.advance_from_selected()

    assert flow.impact is not None
    assert [g.name for g in flow.impact.graphs] == ["cam.haywire"]
    assert flow.impact.total_references == 2


@pytest.mark.anyio
async def test_impact_never_blocks_even_with_usage(tmp_path: Path) -> None:
    """Graphs using the library are information, not a gate (Q4: inform+confirm)."""
    _graph(tmp_path / "cam.haywire", "visiongraph:node:Cam")
    flow = _flow(tmp_path)
    await flow.advance_from_selected()

    await flow.advance_from_impact()

    assert flow.step == "confirm"
    assert flow.error is None


@pytest.mark.anyio
async def test_confirm_is_the_only_step_that_uninstalls(tmp_path: Path) -> None:
    source = _FakeSource()
    flow = _flow(tmp_path, source)
    await flow.advance_from_selected()
    await flow.advance_from_impact()
    assert source.uninstalled == []

    await flow.advance_from_confirm()

    assert flow.step == "removed"
    assert source.uninstalled == ["visiongraph"]
    assert flow.succeeded is True


@pytest.mark.anyio
async def test_abandoning_before_confirm_removes_nothing(tmp_path: Path) -> None:
    source = _FakeSource()
    flow = _flow(tmp_path, source)

    await flow.advance_from_selected()
    await flow.advance_from_impact()

    assert source.uninstalled == []
    assert flow.step == "confirm"


@pytest.mark.anyio
async def test_failed_uninstall_stays_on_confirm(tmp_path: Path) -> None:
    """A failure must be retryable in place, not land on a 'done' step."""
    source = _FakeSource()
    source.result = (False, "Uninstall failed: locked", None)
    flow = _flow(tmp_path, source)
    await flow.advance_from_selected()
    await flow.advance_from_impact()

    await flow.advance_from_confirm()

    assert flow.step == "confirm"
    assert flow.error == "Uninstall failed: locked"
    assert flow.succeeded is False


@pytest.mark.anyio
async def test_raising_uninstall_is_reported_not_swallowed(tmp_path: Path) -> None:
    source = _FakeSource()
    source.raises = RuntimeError("uv exploded")
    flow = _flow(tmp_path, source)
    await flow.advance_from_selected()
    await flow.advance_from_impact()

    await flow.advance_from_confirm()

    assert flow.step == "confirm"
    assert flow.error is not None
    assert "uv exploded" in flow.error


@pytest.mark.anyio
async def test_editable_install_warns_source_remains(tmp_path: Path) -> None:
    source = _FakeSource(install_type="EDITABLE")
    flow = _flow(tmp_path, source)
    await flow.advance_from_selected()
    assert flow.impact is not None
    assert flow.impact.is_editable
    await flow.advance_from_impact()

    await flow.advance_from_confirm()

    assert flow.step == "removed"
    assert any("still on disk" in w for w in flow.warnings)


@pytest.mark.anyio
async def test_regular_install_does_not_warn(tmp_path: Path) -> None:
    flow = _flow(tmp_path, _FakeSource(install_type="REGULAR"))
    await flow.advance_from_selected()
    await flow.advance_from_impact()

    await flow.advance_from_confirm()

    assert flow.warnings == []


@pytest.mark.anyio
async def test_no_workspace_flags_graphs_unscanned(tmp_path: Path) -> None:
    """Without a project the flow must not imply that zero graphs use it."""
    flow = _flow(None)

    await flow.advance_from_selected()

    assert flow.step == "impact"
    assert flow.impact is not None
    assert flow.impact.graphs_scanned is False
    assert flow.impact.graphs == []


@pytest.mark.anyio
async def test_uninstall_output_is_captured(tmp_path: Path) -> None:
    flow = _flow(tmp_path)
    await flow.advance_from_selected()
    await flow.advance_from_impact()

    await flow.advance_from_confirm()

    assert any("Removing visiongraph" in line for line in flow.log_lines)


def test_steps_and_titles_stay_in_lockstep() -> None:
    from haybale_marketplace.editors._uninstall_flow import STEPS
    from haybale_marketplace.editors._uninstall_flow.copy import STEP_TITLES

    assert set(STEPS) == set(STEP_TITLES)
    assert STEPS.index("selected") < STEPS.index("impact") < STEPS.index("confirm")
