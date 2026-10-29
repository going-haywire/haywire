"""
Unit tests for the auto-expanding canvas feature.

Covers:
- BaseGraph initial canvas state
- _check_canvas_size() expansion, shrink, and flag logic
- estimate_canvas_size() (no changed flag side-effect)
- trimmed_positions()
- ValidationResult.canvas_sizes field and has_changes()
- canvas_sizes propagation through the validation pipeline
"""

import math

import pytest
from unittest.mock import MagicMock

from haywire.core.graph.base import BaseGraph, _CANVAS_MIN_SIZE
from haywire.core.graph.types import ChangeReason, ValidationResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


W, H = 200, 100
"""Card size of every stub node unless a test says otherwise."""


def _stub_wrapper(pos_x: float, pos_y: float, width: float, height: float) -> MagicMock:
    """Return a minimal stub NodeWrapper with node.props position and size."""
    wrapper = MagicMock()
    wrapper.node.props.posX = pos_x
    wrapper.node.props.posY = pos_y
    wrapper.node.props.width = width
    wrapper.node.props.height = height
    wrapper.node.props.on_stage = False
    return wrapper


def _inject(
    graph: BaseGraph, node_id: str, pos_x: float, pos_y: float, width: float = W, height: float = H
) -> None:
    """Inject a stub wrapper directly into graph.node_wrappers, bypassing hooks."""
    graph.node_wrappers[node_id] = _stub_wrapper(pos_x, pos_y, width, height)


def _expected_size(pos: float, size: float, indent: float = min(W, H)) -> int:
    """Return the canvas extent on one axis for a lone card at ``pos`` of ``size``."""
    return max(_CANVAS_MIN_SIZE, math.ceil(pos + size + max(pos, indent)))


def _trigger_validation(graph: BaseGraph) -> ValidationResult:
    """Mark a synthetic dirty node and force an immediate validation batch."""
    graph._validation.mark_node_dirty("_synthetic_", ChangeReason.NODE_MOVED)
    result = graph._validation.force_immediate_validation()
    assert result is not None, "forced validation produced no result"
    return result


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
class TestCanvasInitialState:
    """A new graph starts at _CANVAS_MIN_SIZE with the changed flag cleared."""

    def test_new_graph_has_min_canvas_width(self):
        graph = BaseGraph(filestem="G")
        assert graph.canvas_width == _CANVAS_MIN_SIZE

    def test_new_graph_has_min_canvas_height(self):
        graph = BaseGraph(filestem="G")
        assert graph.canvas_height == _CANVAS_MIN_SIZE

    def test_new_graph_changed_flag_is_false(self):
        graph = BaseGraph(filestem="G")
        assert graph._canvas_size_changed == set()


# ---------------------------------------------------------------------------
# _check_canvas_size()
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
class TestCheckCanvasSize:
    """_check_canvas_size() expands, shrinks, and manages the changed flag."""

    def test_empty_graph_stays_at_min_size(self):
        graph = BaseGraph(filestem="G")
        changed = graph._check_canvas_size()
        assert not changed
        assert graph.canvas_width == _CANVAS_MIN_SIZE
        assert graph.canvas_height == _CANVAS_MIN_SIZE

    def test_node_well_inside_canvas_no_change(self):
        """A node far from the boundary does not trigger a resize."""
        graph = BaseGraph(filestem="G")
        _inject(graph, "n1", 100, 100)
        changed = graph._check_canvas_size()
        assert not changed
        assert graph.canvas_width == _CANVAS_MIN_SIZE
        assert graph.canvas_height == _CANVAS_MIN_SIZE

    def test_returns_false_on_consecutive_unchanged_check(self):
        """Calling _check_canvas_size() twice without moving nodes returns False."""
        graph = BaseGraph(filestem="G")
        _inject(graph, "n1", 100, 100)
        graph._check_canvas_size()
        changed = graph._check_canvas_size()
        assert not changed

    def test_card_reaching_past_the_minimum_expands_width(self):
        """A card whose edge plus margin passes the minimum widens the canvas."""
        graph = BaseGraph(filestem="G")
        _inject(graph, "n1", 2000, 100)
        changed = graph._check_canvas_size()
        assert changed
        assert graph.canvas_width == 2000 + W + 2000
        assert graph.canvas_height == _CANVAS_MIN_SIZE

    def test_card_reaching_past_the_minimum_expands_height(self):
        graph = BaseGraph(filestem="G")
        _inject(graph, "n1", 100, 2000)
        graph._check_canvas_size()
        assert graph.canvas_height == 2000 + H + 2000
        assert graph.canvas_width == _CANVAS_MIN_SIZE

    def test_margin_mirrors_the_space_before_the_nearest_card(self):
        """The far margin equals the space before the nearest card when that is the larger."""
        graph = BaseGraph(filestem="G")
        _inject(graph, "n1", 9500, 4500)
        graph._check_canvas_size()
        assert graph.canvas_width == _expected_size(9500, W)
        assert graph.canvas_height == _expected_size(4500, H)

    def test_margin_is_the_shorter_side_of_the_cards_box_when_larger(self):
        """With cards near the origin, the far margin is the shorter side of their box."""
        graph = BaseGraph(filestem="G")
        _inject(graph, "n1", 0, 0, width=500, height=300)
        _inject(graph, "n2", 6000, 2500, width=500, height=300)
        graph._check_canvas_size()
        indent = min(6500, 2800)
        assert graph.canvas_width == 6500 + indent
        assert graph.canvas_height == 2800 + indent

    def test_multiple_nodes_uses_furthest_card_edge(self):
        """Canvas size is driven by the furthest card edge on each axis."""
        graph = BaseGraph(filestem="G")
        _inject(graph, "n1", 100, 100)
        _inject(graph, "n2", 11000, 3000)
        _inject(graph, "n3", 5000, 9500)
        graph._check_canvas_size()
        indent = min(11000 + W - 100, 9500 + H - 100)
        assert graph.canvas_width == 11000 + W + indent
        assert graph.canvas_height == 9500 + H + indent

    def test_canvas_shrinks_when_node_moves_inward(self):
        """Moving a node away from the expanded edge shrinks the canvas."""
        graph = BaseGraph(filestem="G")
        _inject(graph, "n1", 10000, 100)
        graph._check_canvas_size()
        assert graph.canvas_width == _expected_size(10000, W)

        graph.node_wrappers["n1"].node.props.posX = 100
        changed = graph._check_canvas_size()
        assert changed
        assert graph.canvas_width == _CANVAS_MIN_SIZE

    def test_canvas_never_shrinks_below_min(self):
        """Removing all nodes resets to _CANVAS_MIN_SIZE, never below."""
        graph = BaseGraph(filestem="G")
        _inject(graph, "n1", 15000, 15000)
        graph._check_canvas_size()

        del graph.node_wrappers["n1"]
        graph._check_canvas_size()

        assert graph.canvas_width == _CANVAS_MIN_SIZE
        assert graph.canvas_height == _CANVAS_MIN_SIZE

    def test_changed_flag_set_when_size_changes(self):
        graph = BaseGraph(filestem="G")
        _inject(graph, "n1", 9000, 100)
        graph._check_canvas_size()
        assert graph._canvas_size_changed == {"patch"}

    def test_changed_flag_not_set_when_size_unchanged(self):
        graph = BaseGraph(filestem="G")
        _inject(graph, "n1", 100, 100)
        graph._canvas_size_changed = set()
        graph._check_canvas_size()
        assert graph._canvas_size_changed == set()


# ---------------------------------------------------------------------------
# estimate_canvas_size()
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
class TestEstimateCanvasSize:
    """estimate_canvas_size() sets the correct size but does NOT set the changed flag."""

    def test_sets_correct_dimensions(self):
        graph = BaseGraph(filestem="G")
        _inject(graph, "n1", 9500, 4500)
        graph.estimate_canvas_size()
        assert graph.canvas_width == _expected_size(9500, W)
        assert graph.canvas_height == _expected_size(4500, H)

    def test_does_not_set_changed_flag(self):
        graph = BaseGraph(filestem="G")
        _inject(graph, "n1", 9500, 100)
        graph.estimate_canvas_size()
        assert graph._canvas_size_changed == set()

    def test_empty_graph_stays_at_min_without_flag(self):
        graph = BaseGraph(filestem="G")
        graph.estimate_canvas_size()
        assert graph.canvas_width == _CANVAS_MIN_SIZE
        assert graph.canvas_height == _CANVAS_MIN_SIZE
        assert graph._canvas_size_changed == set()


# ---------------------------------------------------------------------------
# ValidationResult.canvas_sizes
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
class TestValidationResultCanvasSize:
    """ValidationResult.canvas_sizes field and has_changes()."""

    def test_canvas_sizes_defaults_to_empty(self):
        result = ValidationResult(nodes={}, edges={}, validation_time_ms=0.0)
        assert result.canvas_sizes == {}

    def test_has_changes_false_when_all_empty(self):
        result = ValidationResult(nodes={}, edges={}, validation_time_ms=0.0)
        assert not result.has_changes()

    def test_has_changes_true_when_canvas_size_set(self):
        result = ValidationResult(
            nodes={}, edges={}, canvas_sizes={"patch": (10000, 8000)}, validation_time_ms=0.0
        )
        assert result.has_changes()

    def test_canvas_sizes_preserved(self):
        sizes = {"patch": (12000, 10000), "stage": (6000, 4000)}
        result = ValidationResult(nodes={}, edges={}, canvas_sizes=sizes, validation_time_ms=0.0)
        assert result.canvas_sizes == sizes


# ---------------------------------------------------------------------------
# Validation pipeline propagation
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
class TestCanvasSizePipelinePropagation:
    """canvas_sizes propagates through _validate_batch() and the flag is cleared."""

    def test_canvas_sizes_in_result_when_flag_set(self):
        """When _canvas_size_changed is True, ValidationResult carries canvas_sizes."""
        graph = BaseGraph(filestem="G")
        graph.canvas_width = 10000
        graph.canvas_height = 12000
        graph._canvas_size_changed = {"patch"}

        result = _trigger_validation(graph)

        assert result is not None
        assert result.canvas_sizes == {"patch": (10000, 12000)}

    def test_canvas_sizes_empty_in_result_when_flag_not_set(self):
        """ValidationResult.canvas_sizes is empty when _canvas_size_changed is False."""
        graph = BaseGraph(filestem="G")
        graph._canvas_size_changed = set()

        result = _trigger_validation(graph)

        assert result is not None
        assert result.canvas_sizes == {}

    def test_flag_cleared_after_validation(self):
        """_canvas_size_changed is reset to False after the validation batch runs."""
        graph = BaseGraph(filestem="G")
        graph._canvas_size_changed = {"patch"}

        _trigger_validation(graph)

        assert graph._canvas_size_changed == set()


# ---------------------------------------------------------------------------
# trimmed_positions()
# ---------------------------------------------------------------------------


def _apply(graph: BaseGraph, positions: dict) -> None:
    for node_id, pos in positions.items():
        props = graph.node_wrappers[node_id].node.props
        props.posX, props.posY = pos["x"], pos["y"]


@pytest.mark.unit
@pytest.mark.core
class TestTrimmedPositions:
    """trimmed_positions() centres the cards with an equal margin and keeps the extent stable."""

    def test_empty_graph_has_nothing_to_trim(self):
        assert BaseGraph(filestem="G").trimmed_positions() == {}

    def test_large_layout_gets_the_shorter_side_as_margin_on_every_side(self):
        graph = BaseGraph(filestem="G")
        _inject(graph, "a", 3000, 7000, width=500, height=300)
        _inject(graph, "b", 9500, 12000, width=500, height=300)
        positions = graph.trimmed_positions()
        _apply(graph, positions)
        graph._check_canvas_size()

        box_w, box_h = 9500 + 500 - 3000, 12000 + 300 - 7000
        indent = min(box_w, box_h)
        assert positions["a"] == {"x": indent, "y": indent}
        assert (graph.canvas_width, graph.canvas_height) == (box_w + 2 * indent, box_h + 2 * indent)

    def test_small_layout_is_centred_on_the_minimum_canvas(self):
        graph = BaseGraph(filestem="G")
        _inject(graph, "a", 9000, 9000)
        positions = graph.trimmed_positions()
        _apply(graph, positions)
        graph._check_canvas_size()

        assert positions["a"] == {"x": (_CANVAS_MIN_SIZE - W) / 2, "y": (_CANVAS_MIN_SIZE - H) / 2}
        assert (graph.canvas_width, graph.canvas_height) == (_CANVAS_MIN_SIZE, _CANVAS_MIN_SIZE)

    def test_cards_keep_their_relative_layout(self):
        graph = BaseGraph(filestem="G")
        _inject(graph, "a", 5000, 6000)
        _inject(graph, "b", 5300, 6450)
        positions = graph.trimmed_positions()
        assert positions["b"]["x"] - positions["a"]["x"] == 300
        assert positions["b"]["y"] - positions["a"]["y"] == 450

    def test_a_trimmed_layout_returns_nothing_to_move(self):
        graph = BaseGraph(filestem="G")
        _inject(graph, "a", 3000, 7000, width=500, height=300)
        _inject(graph, "b", 9500, 12000, width=500, height=300)
        _apply(graph, graph.trimmed_positions())
        assert graph.trimmed_positions() == {}
