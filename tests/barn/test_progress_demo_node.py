"""ProgressDemoNode: an overall bar over the jobs, a per-job bar over the steps, a sweeping last stage."""

import importlib
from typing import Any
from unittest.mock import MagicMock

import pytest

from haywire.barn.builtin.types import PROGRESS
from haywire.core.types.enums import PortType
from tests.conftest import make_node

pytestmark = pytest.mark.integration


def _demo_node(graph: Any) -> Any:
    # Imported at call time: a barn module reload would leave a top-level import stale.
    cls = importlib.import_module("haybale_example.nodes.progress_demo").ProgressDemoNode
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def test_both_bars_are_card_rows(graph_with_library_system):
    node = _demo_node(graph_with_library_system)

    assert node.ports["progress.main"].port_type is PortType.CONFIG
    assert node.ports["progress.job"].port_type is PortType.CONFIG


def test_a_run_reports_jobs_and_steps_then_returns_to_idle(graph_with_library_system, monkeypatch):
    node = _demo_node(graph_with_library_system)
    node.ports["jobs"].set_value(2)
    node.ports["steps"].set_value(3)
    node.ports["step_ms"].set_value(0.0)

    seen: list[tuple[str, str]] = []
    module = importlib.import_module("haybale_example.nodes.progress_demo")
    monkeypatch.setattr(
        module.time, "sleep", lambda _s: seen.append((node.progress.main.label, node.progress.job.label))
    )

    assert node.worker(MagicMock()) == "done"

    assert seen[0] == ("processing", "job 1 of 2")
    assert ("processing", "job 2 of 2") in seen
    assert seen[-1] == ("finishing", "")
    assert node.ports["processed"].get_value() == 6
    assert node.progress.main == PROGRESS()
    assert node.progress.job == PROGRESS()
