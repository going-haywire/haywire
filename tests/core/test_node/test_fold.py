"""fold() mints one container port: no pin, no widget, state persists.

``FoldProbeNode`` carries three sibling folds — ``solver`` (config),
``inputs`` (inlet) and ``advanced`` (config, starts closed) — so one built
node covers the lane, pin and open-state cases. The three raising cases each
need their own node: ``init()`` aborts at the first raise, so a node that
fails cannot also serve as the happy path.
"""

from __future__ import annotations

import pytest

# Integration: building a node with real ports needs the library system.
pytestmark = pytest.mark.integration


def _make_probe(graph, position=(100.0, 100.0)):
    from haybale_testing.nodes.testbed.fold_probe import FoldProbeNode

    wrapper = graph.create_node_wrapper(FoldProbeNode.class_identity.registry_key, position=position)
    assert wrapper is not None, "node creation failed"
    return wrapper.node


def _build(graph, node_cls, position=(100.0, 100.0)):
    """Build a probe whose init() raises, returning its recorded error.

    NodeWrapper.build() records an init() failure on the wrapper rather than
    propagating it, so a raise is asserted here and not with pytest.raises.
    """
    wrapper = graph.create_node_wrapper(node_cls.class_identity.registry_key, position=position)
    assert wrapper is not None, "node creation failed"
    error = wrapper.state.error_initialize
    assert error is not None, "expected init() to fail"
    assert isinstance(error.original_exception, ValueError)
    return error.original_exception


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

    probe = _make_probe(graph_with_library_system)
    assert probe.ports["inputs"].port_type is PortType.INLET
    assert probe.ports["solver"].port_type is PortType.CONFIG


def test_an_inherited_direction_refreshes_the_is_inlet_cache(graph_with_library_system) -> None:
    """set_value branches on the cached _is_inlet, not on is_inlet(). A fold
    that took INLET with a stale cache would run the OUTLET write path —
    node-set plus propagate, skipping on_change — silently."""
    probe = _make_probe(graph_with_library_system)
    fold = probe.ports["inputs"]
    assert fold._is_inlet == fold.is_inlet()


def test_an_inlet_fold_still_draws_no_pin(graph_with_library_system) -> None:
    """is_group, not is_config, is what keeps a fold pinless — otherwise a fold
    that inherits INLET would sprout a connectable pin of its own."""
    probe = _make_probe(graph_with_library_system)
    fold = probe.ports["inputs"]
    assert fold.is_config() is False, "fixture assumption: this fold inherited INLET"
    assert fold.has_pin() is False


def test_fold_carries_no_widget(graph_with_library_system) -> None:
    """The disclosure triangle is the whole control, so FOLD overrides the
    SWITCH_WIDGET it would otherwise inherit from BOOL."""
    probe = _make_probe(graph_with_library_system)
    assert probe.ports["solver"].widget_key is None


def test_a_fold_describes_itself_without_the_author(graph_with_library_system) -> None:
    """An undescribed fold must not fall through to BOOL's "True or False",
    which describes the mechanism rather than what the fold holds."""
    probe = _make_probe(graph_with_library_system)
    assert probe.ports["advanced"].description == "Hides or shows the ports inside it"
    assert probe.ports["solver"].description == "How the solver steps through time.", (
        "an explicit description= must still win"
    )


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
    assert probe.ports["a"].parent_group == "inputs"
    assert probe.ports["out"].parent_group is None


def test_fold_is_marked_as_a_group(graph_with_library_system) -> None:
    probe = _make_probe(graph_with_library_system)
    assert probe.ports["solver"].is_group is True


def test_fold_defaults_to_open(graph_with_library_system) -> None:
    probe = _make_probe(graph_with_library_system)
    assert probe.value("solver") is True
    assert probe.value("advanced") is False, "default=False starts a fold closed"


def test_a_closed_fold_hides_its_children(graph_with_library_system) -> None:
    """get_visible_ports() drops a closed fold's children, keeping the fold."""
    probe = _make_probe(graph_with_library_system)
    visible = {p.id for p in probe.get_visible_ports()}
    assert "epsilon" not in visible
    assert "advanced" in visible
    assert "substeps" in visible, "an open fold's child stays visible"


def test_mixing_directions_in_one_fold_raises(graph_with_library_system) -> None:
    from haybale_testing.nodes.testbed.mixed_fold import MixedFoldNode

    error = _build(graph_with_library_system, MixedFoldNode)
    assert "one direction" in str(error)


def test_a_fold_inside_a_fold_raises(graph_with_library_system) -> None:
    """A fold holds ports, not other folds."""
    from haybale_testing.nodes.testbed.nested_fold import NestedFoldNode

    error = _build(graph_with_library_system, NestedFoldNode)
    assert "not other folds" in str(error)


def test_an_empty_fold_raises(graph_with_library_system) -> None:
    """A fold with nothing inside has no direction to take."""
    from haybale_testing.nodes.testbed.empty_fold import EmptyFoldNode

    error = _build(graph_with_library_system, EmptyFoldNode)
    assert "holds no ports" in str(error)


def test_section_api_is_gone() -> None:
    from haywire.core.node.data import NodeData
    from haywire.core.types import DataPort

    assert not hasattr(NodeData, "section")
    assert not hasattr(NodeData, "group")
    assert not hasattr(NodeData, "iter_section_ports")
    assert not hasattr(NodeData, "get_section_ports")
    assert "section" not in {f.name for f in DataPort.__dataclass_fields__.values()}
    assert "is_section" not in {f.name for f in DataPort.__dataclass_fields__.values()}


def test_the_tree_shaped_port_api_is_gone() -> None:
    """Folds are one level, so an ancestor path has nothing to walk."""
    from haywire.core.node.data import NodeData

    assert not hasattr(NodeData, "get_port_hierarchy")
    assert not hasattr(NodeData, "iter_group_children")
    assert not hasattr(NodeData, "is_group_expanded")


def test_visible_ports_takes_no_section_argument() -> None:
    import inspect

    from haywire.core.node.data import NodeData

    assert "include_sections" not in inspect.signature(NodeData.get_visible_ports).parameters
    assert "include_sections" not in inspect.signature(NodeData.iter_visible_ports).parameters
