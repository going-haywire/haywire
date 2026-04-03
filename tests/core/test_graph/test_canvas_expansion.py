"""
Unit tests for the auto-expanding canvas feature.

Covers:
- BaseGraph initial canvas state
- _check_canvas_size() expansion, shrink, and flag logic
- estimate_canvas_size() (no changed flag side-effect)
- ValidationResult.canvas_size field and has_changes()
- canvas_size propagation through the validation pipeline
"""

import math

import pytest
from unittest.mock import MagicMock

from haywire.core.graph.base import (
    BaseGraph,
    _CANVAS_MIN_SIZE,
    _CANVAS_EXPANSION_STEP,
    _CANVAS_EDGE_MARGIN,
)
from haywire.core.graph.types import ChangeReason, ValidationResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stub_wrapper(pos_x: float, pos_y: float) -> MagicMock:
    """Return a minimal stub NodeWrapper with node.props.posX/posY."""
    wrapper = MagicMock()
    wrapper.node.props.posX = pos_x
    wrapper.node.props.posY = pos_y
    return wrapper


def _inject(graph: BaseGraph, node_id: str, pos_x: float, pos_y: float) -> None:
    """Inject a stub wrapper directly into graph.node_wrappers, bypassing hooks."""
    graph.node_wrappers[node_id] = _stub_wrapper(pos_x, pos_y)


def _expected_size(extent: float) -> int:
    """Return expected canvas dimension for a node whose max position is `extent`."""
    needed = extent + _CANVAS_EDGE_MARGIN
    return max(_CANVAS_MIN_SIZE, math.ceil(needed / _CANVAS_EXPANSION_STEP) * _CANVAS_EXPANSION_STEP)


def _trigger_validation(graph: BaseGraph) -> ValidationResult:
    """Mark a synthetic dirty node and force an immediate validation batch."""
    graph._validation.mark_node_dirty("_synthetic_", ChangeReason.NODE_MOVED)
    return graph._validation.force_immediate_validation()


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
class TestCanvasInitialState:
    """A new graph starts at _CANVAS_MIN_SIZE with the changed flag cleared."""

    def test_new_graph_has_min_canvas_width(self):
        graph = BaseGraph(graph_id="g", name="G")
        assert graph.canvas_width == _CANVAS_MIN_SIZE

    def test_new_graph_has_min_canvas_height(self):
        graph = BaseGraph(graph_id="g", name="G")
        assert graph.canvas_height == _CANVAS_MIN_SIZE

    def test_new_graph_changed_flag_is_false(self):
        graph = BaseGraph(graph_id="g", name="G")
        assert graph._canvas_size_changed is False


# ---------------------------------------------------------------------------
# _check_canvas_size()
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
class TestCheckCanvasSize:
    """_check_canvas_size() expands, shrinks, and manages the changed flag."""

    def test_empty_graph_stays_at_min_size(self):
        graph = BaseGraph(graph_id="g", name="G")
        changed = graph._check_canvas_size()
        assert not changed
        assert graph.canvas_width == _CANVAS_MIN_SIZE
        assert graph.canvas_height == _CANVAS_MIN_SIZE

    def test_node_well_inside_canvas_no_change(self):
        """A node far from the boundary does not trigger a resize."""
        graph = BaseGraph(graph_id="g", name="G")
        _inject(graph, "n1", 100, 100)
        changed = graph._check_canvas_size()
        assert not changed
        assert graph.canvas_width == _CANVAS_MIN_SIZE
        assert graph.canvas_height == _CANVAS_MIN_SIZE

    def test_returns_false_on_consecutive_unchanged_check(self):
        """Calling _check_canvas_size() twice without moving nodes returns False."""
        graph = BaseGraph(graph_id="g", name="G")
        _inject(graph, "n1", 100, 100)
        graph._check_canvas_size()
        changed = graph._check_canvas_size()
        assert not changed

    def test_node_past_boundary_triggers_width_expansion(self):
        """posX that pushes needed_w above current canvas_width expands width."""
        graph = BaseGraph(graph_id="g", name="G")
        # posX = MIN - MARGIN + 1 = 7901: needed_w = 8001 > 8000
        boundary_x = _CANVAS_MIN_SIZE - _CANVAS_EDGE_MARGIN + 1
        _inject(graph, "n1", boundary_x, 100)
        changed = graph._check_canvas_size()
        assert changed
        assert graph.canvas_width > _CANVAS_MIN_SIZE
        assert graph.canvas_height == _CANVAS_MIN_SIZE

    def test_node_past_boundary_triggers_height_expansion(self):
        graph = BaseGraph(graph_id="g", name="G")
        boundary_y = _CANVAS_MIN_SIZE - _CANVAS_EDGE_MARGIN + 1
        _inject(graph, "n1", 100, boundary_y)
        graph._check_canvas_size()
        assert graph.canvas_height > _CANVAS_MIN_SIZE
        assert graph.canvas_width == _CANVAS_MIN_SIZE

    def test_expansion_follows_step_formula(self):
        """Canvas expands to the nearest STEP boundary above the needed extent."""
        graph = BaseGraph(graph_id="g", name="G")
        # posX=9500 → needed=9600 → ceil(9600/2000)*2000 = 5*2000 = 10000
        _inject(graph, "n1", 9500, 100)
        graph._check_canvas_size()
        assert graph.canvas_width == _expected_size(9500)

    def test_large_offset_jumps_multiple_steps(self):
        """A node far outside jumps multiple expansion steps."""
        graph = BaseGraph(graph_id="g", name="G")
        # posX=15000 → needed=15100 → ceil(15100/2000)*2000 = 8*2000 = 16000
        _inject(graph, "n1", 15000, 100)
        graph._check_canvas_size()
        assert graph.canvas_width == 16000

    def test_width_and_height_expand_independently(self):
        """Width and height are computed and expanded independently."""
        graph = BaseGraph(graph_id="g", name="G")
        # posX=9500 → 10000; posY=4500 → needed=5500 → 6000
        _inject(graph, "n1", 9500, 4500)
        graph._check_canvas_size()
        assert graph.canvas_width == _expected_size(9500)
        assert graph.canvas_height == _expected_size(4500)

    def test_multiple_nodes_uses_furthest_position(self):
        """Canvas size is driven by the node with the largest posX / posY."""
        graph = BaseGraph(graph_id="g", name="G")
        _inject(graph, "n1", 100, 100)
        _inject(graph, "n2", 11000, 3000)
        _inject(graph, "n3", 5000, 9500)
        graph._check_canvas_size()
        assert graph.canvas_width == _expected_size(11000)
        assert graph.canvas_height == _expected_size(9500)

    def test_canvas_shrinks_when_node_moves_inward(self):
        """Moving a node away from the expanded edge shrinks the canvas."""
        graph = BaseGraph(graph_id="g", name="G")
        # posX=10000 → needed=10100 → ceil(10100/2000)*2000 = 6*2000 = 12000
        _inject(graph, "n1", 10000, 100)
        graph._check_canvas_size()
        assert graph.canvas_width == 12000

        # Reposition node back inside the original MIN area
        graph.node_wrappers["n1"].node.props.posX = 100
        changed = graph._check_canvas_size()
        assert changed
        assert graph.canvas_width == _CANVAS_MIN_SIZE

    def test_canvas_never_shrinks_below_min(self):
        """Removing all nodes resets to _CANVAS_MIN_SIZE, never below."""
        graph = BaseGraph(graph_id="g", name="G")
        _inject(graph, "n1", 15000, 15000)
        graph._check_canvas_size()

        del graph.node_wrappers["n1"]
        graph._check_canvas_size()

        assert graph.canvas_width == _CANVAS_MIN_SIZE
        assert graph.canvas_height == _CANVAS_MIN_SIZE

    def test_changed_flag_set_when_size_changes(self):
        graph = BaseGraph(graph_id="g", name="G")
        _inject(graph, "n1", 9000, 100)
        graph._check_canvas_size()
        assert graph._canvas_size_changed is True

    def test_changed_flag_not_set_when_size_unchanged(self):
        graph = BaseGraph(graph_id="g", name="G")
        _inject(graph, "n1", 100, 100)
        graph._canvas_size_changed = False
        graph._check_canvas_size()
        assert graph._canvas_size_changed is False


# ---------------------------------------------------------------------------
# estimate_canvas_size()
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
class TestEstimateCanvasSize:
    """estimate_canvas_size() sets the correct size but does NOT set the changed flag."""

    def test_sets_correct_dimensions(self):
        graph = BaseGraph(graph_id="g", name="G")
        # posX=9500 → 10000; posY=4500 → needed=5500 → 6000
        _inject(graph, "n1", 9500, 4500)
        graph.estimate_canvas_size()
        assert graph.canvas_width == _expected_size(9500)
        assert graph.canvas_height == _expected_size(4500)

    def test_does_not_set_changed_flag(self):
        graph = BaseGraph(graph_id="g", name="G")
        _inject(graph, "n1", 9500, 100)
        graph.estimate_canvas_size()
        assert graph._canvas_size_changed is False

    def test_empty_graph_stays_at_min_without_flag(self):
        graph = BaseGraph(graph_id="g", name="G")
        graph.estimate_canvas_size()
        assert graph.canvas_width == _CANVAS_MIN_SIZE
        assert graph.canvas_height == _CANVAS_MIN_SIZE
        assert graph._canvas_size_changed is False


# ---------------------------------------------------------------------------
# ValidationResult.canvas_size
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
class TestValidationResultCanvasSize:
    """ValidationResult.canvas_size field and has_changes()."""

    def test_canvas_size_defaults_to_none(self):
        result = ValidationResult(nodes={}, edges={}, validation_time_ms=0.0)
        assert result.canvas_size is None

    def test_has_changes_false_when_all_empty(self):
        result = ValidationResult(nodes={}, edges={}, validation_time_ms=0.0)
        assert not result.has_changes()

    def test_has_changes_true_when_canvas_size_set(self):
        result = ValidationResult(nodes={}, edges={}, canvas_size=(10000, 8000), validation_time_ms=0.0)
        assert result.has_changes()

    def test_canvas_size_tuple_preserved(self):
        result = ValidationResult(nodes={}, edges={}, canvas_size=(12000, 10000), validation_time_ms=0.0)
        assert result.canvas_size == (12000, 10000)


# ---------------------------------------------------------------------------
# Validation pipeline propagation
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
class TestCanvasSizePipelinePropagation:
    """canvas_size propagates through _validate_batch() and the flag is cleared."""

    def test_canvas_size_in_result_when_flag_set(self):
        """When _canvas_size_changed is True, ValidationResult carries canvas_size."""
        graph = BaseGraph(graph_id="g", name="G")
        graph.canvas_width = 10000
        graph.canvas_height = 12000
        graph._canvas_size_changed = True

        result = _trigger_validation(graph)

        assert result is not None
        assert result.canvas_size == (10000, 12000)

    def test_canvas_size_none_in_result_when_flag_not_set(self):
        """ValidationResult.canvas_size is None when _canvas_size_changed is False."""
        graph = BaseGraph(graph_id="g", name="G")
        graph._canvas_size_changed = False

        result = _trigger_validation(graph)

        assert result is not None
        assert result.canvas_size is None

    def test_flag_cleared_after_validation(self):
        """_canvas_size_changed is reset to False after the validation batch runs."""
        graph = BaseGraph(graph_id="g", name="G")
        graph._canvas_size_changed = True

        _trigger_validation(graph)

        assert graph._canvas_size_changed is False
