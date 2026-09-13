"""fold() mints one container port: no pin, no widget, state persists."""

from __future__ import annotations

import pytest

# Integration: building a node with real ports needs the library system.
pytestmark = pytest.mark.integration


def _make_probe(graph, position=(100.0, 100.0)):
    from haybale_testing.nodes.testbed.fold_probe import FoldProbeNode

    wrapper = graph.create_node_wrapper(FoldProbeNode.class_identity.registry_key, position=position)
    assert wrapper is not None, "node creation failed"
    return wrapper.node


def test_fold_id_is_derived_from_the_label() -> None:
    from haywire.core.node.data import NodeData

    assert NodeData._fold_id("Solver") == "solver"
    assert NodeData._fold_id("Interpolation Range") == "interpolation_range"
    assert NodeData._fold_id("Custom Name") == "custom_name"


def test_fold_mints_a_port_with_no_pin(graph_with_library_system) -> None:
    probe = _make_probe(graph_with_library_system)
    fold = probe.ports["solver"]
    assert fold.has_pin() is False
    assert fold.is_config() is True


def test_a_fold_takes_the_direction_of_its_children(graph_with_library_system) -> None:
    """The fold renders in its children's lane, so it carries their port_type —
    not the CONFIG its as_config() spec starts out with."""
    from haywire.core.types.enums import PortType

    from haybale_testing.nodes.testbed.inlet_fold import InletFoldNode

    wrapper = graph_with_library_system.create_node_wrapper(
        InletFoldNode.class_identity.registry_key, position=(100.0, 100.0)
    )
    assert wrapper is not None, "node creation failed"
    fold = wrapper.node.ports["input_as"]
    assert fold.port_type is PortType.INLET


def test_an_inherited_direction_refreshes_the_is_inlet_cache(graph_with_library_system) -> None:
    """set_value branches on the cached _is_inlet, not on is_inlet(). A fold
    that took INLET with a stale cache would run the OUTLET write path —
    node-set plus propagate, skipping on_change — silently."""
    from haybale_testing.nodes.testbed.inlet_fold import InletFoldNode

    wrapper = graph_with_library_system.create_node_wrapper(
        InletFoldNode.class_identity.registry_key, position=(100.0, 100.0)
    )
    assert wrapper is not None, "node creation failed"
    fold = wrapper.node.ports["input_as"]
    assert fold._is_inlet == fold.is_inlet()


def test_an_inlet_fold_still_draws_no_pin(graph_with_library_system) -> None:
    """is_group, not is_config, is what keeps a fold pinless — otherwise a fold
    that inherits INLET would sprout a connectable pin of its own."""
    from haybale_testing.nodes.testbed.inlet_fold import InletFoldNode

    wrapper = graph_with_library_system.create_node_wrapper(
        InletFoldNode.class_identity.registry_key, position=(100.0, 100.0)
    )
    assert wrapper is not None, "node creation failed"
    fold = wrapper.node.ports["input_as"]
    assert fold.is_config() is False, "fixture assumption: this fold inherited INLET"
    assert fold.has_pin() is False


def test_fold_carries_no_widget(graph_with_library_system) -> None:
    """BOOL declares SWITCH_WIDGET; a fold must not inherit it."""
    probe = _make_probe(graph_with_library_system)
    assert probe.ports["solver"].widget_key is None


def test_fold_persists_its_open_state(graph_with_library_system) -> None:
    """A widget-less port only stores when the strategy says ALWAYS."""
    from haywire.core.types.enums import StoreStrategy

    probe = _make_probe(graph_with_library_system)
    fold = probe.ports["solver"]
    assert fold.store_strategy.should_store(is_linked=False, has_widget=False, node_set=False), (
        "a fold that does not store forgets whether it was open"
    )
    assert fold.store_strategy & StoreStrategy.ALWAYS


def test_fold_parents_its_children(graph_with_library_system) -> None:
    probe = _make_probe(graph_with_library_system)
    assert probe.ports["substeps"].parent_group == "solver"
    assert probe.ports["out"].parent_group is None


def test_fold_is_marked_as_a_group(graph_with_library_system) -> None:
    probe = _make_probe(graph_with_library_system)
    assert probe.ports["solver"].is_group is True


def test_fold_defaults_to_open(graph_with_library_system) -> None:
    probe = _make_probe(graph_with_library_system)
    assert probe.value("solver") is True


def test_mixing_directions_in_one_fold_raises(graph_with_library_system) -> None:
    """init() raises inside NodeWrapper.build(), which records rather than
    propagates it (see NodeWrapper.build) — so the raise is checked on
    wrapper.state.error_initialize.original_exception, not via pytest.raises.
    """
    from haybale_testing.nodes.testbed.mixed_fold import MixedFoldNode

    wrapper = graph_with_library_system.create_node_wrapper(
        MixedFoldNode.class_identity.registry_key, position=(100.0, 100.0)
    )
    assert wrapper is not None, "node creation failed"
    error = wrapper.state.error_initialize
    assert error is not None, "expected init() to fail"
    assert isinstance(error.original_exception, ValueError)
    assert "one direction" in str(error.original_exception)


def test_a_nested_fold_of_the_wrong_direction_raises(graph_with_library_system) -> None:
    """Deferring a nested fold's vote must not drop it: once the inner block
    closes and it knows it is CONFIG, an INLET parent still has to reject it."""
    from haybale_testing.nodes.testbed.mixed_nested_fold import MixedNestedFoldNode

    wrapper = graph_with_library_system.create_node_wrapper(
        MixedNestedFoldNode.class_identity.registry_key, position=(100.0, 100.0)
    )
    assert wrapper is not None, "node creation failed"
    error = wrapper.state.error_initialize
    assert error is not None, "expected init() to fail"
    assert isinstance(error.original_exception, ValueError)
    assert "one direction" in str(error.original_exception)


def test_an_empty_fold_raises(graph_with_library_system) -> None:
    """A fold with nothing inside has no direction to take. Recorded on the
    wrapper rather than raised — see test_mixing_directions_in_one_fold_raises."""
    from haybale_testing.nodes.testbed.empty_fold import EmptyFoldNode

    wrapper = graph_with_library_system.create_node_wrapper(
        EmptyFoldNode.class_identity.registry_key, position=(100.0, 100.0)
    )
    assert wrapper is not None, "node creation failed"
    error = wrapper.state.error_initialize
    assert error is not None, "expected init() to fail"
    assert isinstance(error.original_exception, ValueError)
    assert "holds no ports" in str(error.original_exception)


def test_a_fold_of_inlets_is_fine(graph_with_library_system) -> None:
    from haybale_testing.nodes.testbed.inlet_fold import InletFoldNode

    wrapper = graph_with_library_system.create_node_wrapper(
        InletFoldNode.class_identity.registry_key, position=(100.0, 100.0)
    )
    assert wrapper is not None, "node creation failed"
    probe = wrapper.node
    assert probe.ports["a"].parent_group == "input_as"
    assert probe.ports["b"].parent_group == "input_bs"


def test_a_fold_nests_inside_an_inlet_fold(graph_with_library_system) -> None:
    """A fold is spec'd as_config and only takes a direction when its block
    closes, so it must not vote CONFIG into its parent's lane on the way in —
    that rejects every nested fold from an inlet or outlet parent."""
    from haywire.core.types.enums import PortType

    from haybale_testing.nodes.testbed.inlet_fold import InletFoldNode

    wrapper = graph_with_library_system.create_node_wrapper(
        InletFoldNode.class_identity.registry_key, position=(100.0, 100.0)
    )
    assert wrapper is not None, "node creation failed"
    assert wrapper.state.error_initialize is None, "a nested inlet fold must build"

    inner = wrapper.node.ports["input_bs"]
    assert inner.parent_group == "input_as"
    assert inner.port_type is PortType.INLET
    assert inner.is_group is True


def test_folds_nest(graph_with_library_system) -> None:
    from haybale_testing.nodes.testbed.nested_fold import NestedFoldNode

    wrapper = graph_with_library_system.create_node_wrapper(
        NestedFoldNode.class_identity.registry_key, position=(100.0, 100.0)
    )
    assert wrapper is not None, "node creation failed"
    probe = wrapper.node
    assert probe.ports["substeps"].parent_group == "solver"
    assert probe.ports["interpolation_range"].parent_group == "solver"
    assert probe.ports["begin"].parent_group == "interpolation_range"
    assert probe.ports["end"].parent_group == "interpolation_range"


def test_a_closed_outer_fold_hides_a_nested_fold_child(graph_with_library_system) -> None:
    """_is_any_ancestor_collapsed walks the whole chain, not just one level."""
    from haybale_testing.nodes.testbed.nested_closed_fold import NestedClosedFoldNode

    wrapper = graph_with_library_system.create_node_wrapper(
        NestedClosedFoldNode.class_identity.registry_key, position=(100.0, 100.0)
    )
    assert wrapper is not None, "node creation failed"
    probe = wrapper.node
    visible = {p.id for p in probe.get_visible_ports()}
    assert "begin" not in visible
    assert "interpolation_range" not in visible
    assert "solver" in visible


def test_section_api_is_gone() -> None:
    from haywire.core.node.data import NodeData
    from haywire.core.types import DataPort

    assert not hasattr(NodeData, "section")
    assert not hasattr(NodeData, "group")
    assert not hasattr(NodeData, "iter_section_ports")
    assert not hasattr(NodeData, "get_section_ports")
    assert "section" not in {f.name for f in DataPort.__dataclass_fields__.values()}
    assert "is_section" not in {f.name for f in DataPort.__dataclass_fields__.values()}


def test_visible_ports_takes_no_section_argument() -> None:
    import inspect

    from haywire.core.node.data import NodeData

    assert "include_sections" not in inspect.signature(NodeData.get_visible_ports).parameters
    assert "include_sections" not in inspect.signature(NodeData.iter_visible_ports).parameters
