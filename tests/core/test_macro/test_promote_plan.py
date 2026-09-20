"""Promoting a Group into a macro: the read-only plan, then the one write.

A stepper may only be built over an operation that stops between reading and
writing (``.insights/project_stepper_flows.md``), so promotion is split:
``plan_promotion`` answers what would happen and why it might be refused,
``write_macro_file`` is the single mutating step.
"""

import json
from typing import cast

import pytest

pytestmark = pytest.mark.integration

_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"
_ADD = "haybale-testing:node:TestAddFloatNode"


def _group(graph, key="g1", label="Group"):
    """A Group with both boundary nodes and one interior node."""
    from haywire.core.graph.scheduler import SyncScheduler
    from haywire.core.graph.subgraph import SubgraphDefinition

    definition = graph.add_subgraph(
        SubgraphDefinition(key=key, label=label, validation_scheduler=SyncScheduler())
    )
    definition.create_node_wrapper(_INPUT, position=(0, 0))
    definition.create_node_wrapper(_OUTPUT, position=(200, 0))
    definition.create_node_wrapper(_ADD, position=(100, 0))
    definition.force_validation()
    return definition


# ---------------------------------------------------------------------------
# The name rule
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["Blur", "Blur2", "My_Macro", "My-Macro", "A"])
def test_a_conforming_name_is_accepted(name):
    from haywire.core.macro.promote import name_refusal

    assert name_refusal(name) is None


@pytest.mark.parametrize("name", ["", "9lives", "_private", "my macro", "my.macro", "café"])
def test_a_nonconforming_name_is_refused_with_a_reason(name):
    """Decision 17: the filestem becomes the registry key, so it is constrained."""
    from haywire.core.macro.promote import name_refusal

    refusal = name_refusal(name)

    assert refusal is not None
    assert refusal.strip()


def test_a_suggested_name_is_derived_from_the_group_label():
    from haywire.core.macro.promote import suggest_name

    assert suggest_name("My Group") == "My_Group"
    assert suggest_name("blur filter") == "Blur_filter"


def test_a_suggestion_is_always_usable():
    """Whatever the label, the sanitized form must pass the rule."""
    from haywire.core.macro.promote import name_refusal, suggest_name

    for label in ["9 lives", "", "   ", "café au lait", "!!!", "a"]:
        assert name_refusal(suggest_name(label)) is None, label


# ---------------------------------------------------------------------------
# The plan
# ---------------------------------------------------------------------------


def test_the_plan_names_the_file_it_would_write(tmp_path, graph_with_library_system):
    from haywire.core.macro.promote import plan_promotion

    definition = _group(graph_with_library_system)

    plan = plan_promotion(definition, name="Blur", macros_folder=tmp_path)

    assert plan.path == tmp_path / "Blur.hwm"
    assert plan.registry_key_stem == "Blur"
    assert plan.refusal is None


def test_the_plan_writes_nothing(tmp_path, graph_with_library_system):
    """The whole point of the split: planning is read-only."""
    from haywire.core.macro.promote import plan_promotion

    definition = _group(graph_with_library_system)

    plan_promotion(definition, name="Blur", macros_folder=tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_the_plan_carries_the_document_that_would_be_written(tmp_path, graph_with_library_system):
    from haywire.core.macro.promote import plan_promotion

    definition = _group(graph_with_library_system)

    plan = plan_promotion(definition, name="Blur", macros_folder=tmp_path)

    assert len(plan.document["nodes"]) == 3
    assert "key" not in plan.document


def test_a_bad_name_is_refused_before_anything_is_read(tmp_path, graph_with_library_system):
    from haywire.core.macro.promote import plan_promotion

    definition = _group(graph_with_library_system)

    plan = plan_promotion(definition, name="9lives", macros_folder=tmp_path)

    assert plan.refusal is not None


def test_an_existing_file_is_refused(tmp_path, graph_with_library_system):
    """Overwriting someone else's macro is never what promote means."""
    from haywire.core.macro.promote import plan_promotion

    (tmp_path / "Blur.hwm").write_text("{}")
    definition = _group(graph_with_library_system)

    plan = plan_promotion(definition, name="Blur", macros_folder=tmp_path)

    assert plan.refusal is not None
    assert "exists" in plan.refusal.lower()


def test_a_group_missing_a_boundary_node_is_refused(tmp_path, graph_with_library_system):
    """Containment is what the registry would reject on load; catch it here."""
    from haywire.core.graph.scheduler import SyncScheduler
    from haywire.core.graph.subgraph import SubgraphDefinition
    from haywire.core.macro.promote import plan_promotion

    graph = graph_with_library_system
    definition = graph.add_subgraph(
        SubgraphDefinition(key="g2", label="G", validation_scheduler=SyncScheduler())
    )
    definition.create_node_wrapper(_INPUT, position=(0, 0))
    definition.force_validation()

    plan = plan_promotion(definition, name="Halfy", macros_folder=tmp_path)

    assert plan.refusal is not None
    assert "exactly one" in plan.refusal


# ---------------------------------------------------------------------------
# The write
# ---------------------------------------------------------------------------


def test_the_write_creates_a_loadable_macro(tmp_path, graph_with_library_system, library_system):
    """The file must register as a macro immediately — decision 15."""
    from haywire.core.library.identity import LibraryIdentity
    from haywire.core.macro.promote import plan_promotion, write_macro_file

    definition = _group(graph_with_library_system)
    plan = plan_promotion(definition, name="Blur", macros_folder=tmp_path)

    write_macro_file(plan)

    registry = library_system.get_macro_registry()
    identity = LibraryIdentity(
        label="testlib", name="testlib", folder_path=str(tmp_path), module_name="testlib"
    )
    registry.add_folder(str(tmp_path), identity)
    try:
        assert registry.has("testlib:macro:Blur")
    finally:
        registry.remove_folder(str(tmp_path), identity)


def test_the_written_document_round_trips(tmp_path, graph_with_library_system):
    from haywire.core.macro.promote import plan_promotion, write_macro_file

    definition = _group(graph_with_library_system)
    plan = plan_promotion(definition, name="Blur", macros_folder=tmp_path)

    write_macro_file(plan)

    document = json.loads(plan.path.read_text())
    assert document["nodes"] == plan.document["nodes"]


def test_writing_a_refused_plan_raises(tmp_path, graph_with_library_system):
    """A refusal is a stop, not a warning."""
    from haywire.core.macro.promote import plan_promotion, write_macro_file

    definition = _group(graph_with_library_system)
    plan = plan_promotion(definition, name="9lives", macros_folder=tmp_path)

    with pytest.raises(ValueError, match="cannot be promoted"):
        write_macro_file(plan)

    assert not plan.path.exists()


def test_a_promoted_group_can_be_placed_and_runs_its_interior(
    tmp_path, graph_with_library_system, library_system
):
    """The point of promoting: the result is a macro you can place like any node."""
    from haywire.barn.builtin.nodes.macro_node import MacroNode
    from haywire.core.library.identity import LibraryIdentity
    from haywire.core.macro.promote import plan_promotion, write_macro_file
    from tests.conftest import make_node

    graph = graph_with_library_system
    definition = _group(graph, key="g_promote", label="Blur Filter")
    interior_size = len(definition.node_wrappers)

    plan = plan_promotion(definition, name=_suggested(definition.label), macros_folder=tmp_path)
    write_macro_file(plan)

    registry = library_system.get_macro_registry()
    identity = LibraryIdentity(
        label="testlib", name="testlib", folder_path=str(tmp_path), module_name="testlib"
    )
    registry.add_folder(str(tmp_path), identity)
    try:
        card = make_node(graph, f"testlib:macro:{plan.registry_key_stem}")
        placement = cast(MacroNode, card.node)
        interior = placement.resolve_definition()

        assert placement.display_label == plan.registry_key_stem
        assert interior is not None
        assert len(interior.node_wrappers) == interior_size
    finally:
        registry.remove_folder(str(tmp_path), identity)


def _suggested(label: str) -> str:
    from haywire.core.macro.promote import suggest_name

    return suggest_name(label)


def test_the_write_creates_the_folder_if_absent(tmp_path, graph_with_library_system):
    """A library scaffolded before macros existed has no macros/ folder yet."""
    from haywire.core.macro.promote import plan_promotion, write_macro_file

    folder = tmp_path / "macros"
    definition = _group(graph_with_library_system)
    plan = plan_promotion(definition, name="Blur", macros_folder=folder)

    write_macro_file(plan)

    assert plan.path.exists()
