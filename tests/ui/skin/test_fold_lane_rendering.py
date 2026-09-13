"""A fold's own port is always CONFIG-typed; its children can be any direction.

``fold()`` mints its control port via ``BOOL.as_config(...)``, so
``group_port.port_type`` is always CONFIG regardless of what direction the
fold's children are. ``_render_port_hierarchy`` iterates the three lanes
(OUTLET, CONFIG, INLET) and used to match a fold by its OWN port_type — so
an inlet-only or outlet-only fold was only ever visited during the CONFIG
pass, and its non-CONFIG children were filtered out there and never
rendered. A config-only fold worked by coincidence.
"""

from __future__ import annotations

import pytest
from nicegui import ui

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.types import NodeDetail
from haywire.ui.skin.factory import SkinFactory

pytestmark = [pytest.mark.integration]


def _graph():
    return BaseGraph(filestem="fold lane rendering", validation_scheduler=SyncScheduler())


def _pins(container: ui.element) -> list:
    """Every real pin on the card — ghosts carry no `data-pin-data-type`."""
    return [
        el
        for el in container.descendants()
        if "data-pin-id" in el._props and "data-pin-data-type" in el._props
    ]


def _labels(container: ui.element) -> list[str]:
    return [el.text for el in container.descendants() if isinstance(el, ui.label)]


def _fold_headers(container: ui.element) -> dict[str, int]:
    """Each fold header's left padding in px, by fold id."""
    return {
        el._props["data-hw-fold-id"]: int(el._style["padding-left"].removesuffix("px"))
        for el in container.descendants()
        if "data-hw-fold-id" in el._props
    }


@pytest.fixture
def ctx(library_system, nicegui_slot_context):
    skin_factory = library_system.injector.get(SkinFactory)
    graph = _graph()
    skin_key = skin_factory._skin_registry.get_default_skin_registry_key()
    assert skin_key, "no default skin registered"
    return skin_factory, graph, skin_key


def _render(ctx, wrapper) -> ui.element:
    skin_factory, _graph_obj, skin_key = ctx
    # PINS_ALL: these ports are freshly added and unlinked, so the default
    # PINS rank would hide them behind .hw-detail-pins_all regardless of
    # whether the fold-lane bug is present — orthogonal to what this test
    # checks.
    wrapper.node.props.detail = NodeDetail.PINS_ALL.value
    container = ui.element("div")
    with container:
        skin_factory.render(skin_registry_key=skin_key, wrapper=wrapper)
    return container


def test_an_inlet_fold_s_children_render_their_pins(ctx) -> None:
    """InletFoldNode holds inlet 'a', plus 'b' in a fold nested inside it."""
    from haybale_testing.nodes.testbed.inlet_fold import InletFoldNode

    _skin_factory, graph, _skin_key = ctx
    wrapper = graph.create_node_wrapper(InletFoldNode.class_identity.registry_key, position=(0, 0))
    assert wrapper is not None

    container = _render(ctx, wrapper)

    pin_ids = {el._props["data-pin-id"] for el in _pins(container)}
    assert "a" in pin_ids, "inlet 'a' inside the 'Input as' fold has no pin"
    assert "b" in pin_ids, "inlet 'b' inside the nested 'Input bs' fold has no pin"

    labels = _labels(container)
    assert "Input as" in labels, "the fold header itself must still render"
    assert "Input bs" in labels, "the nested fold's header must render too"


def test_a_config_fold_s_children_still_render(ctx) -> None:
    """The config-only fold path (which worked before this fix) must not regress."""
    from haybale_testing.nodes.testbed.fold_probe import FoldProbeNode

    _skin_factory, graph, _skin_key = ctx
    wrapper = graph.create_node_wrapper(FoldProbeNode.class_identity.registry_key, position=(0, 0))
    assert wrapper is not None

    container = _render(ctx, wrapper)

    labels = _labels(container)
    assert "Solver" in labels, "the fold header itself must still render"
    # 'substeps' has no explicit label=, so it falls back to its type's
    # label ("Float") — this is the fold's config child rendering.
    assert "Float" in labels, "the fold's config child ('substeps') must render alongside its header"


def test_a_nested_fold_header_indents_past_its_parent(ctx) -> None:
    """A fold header is pinless, so it indents like a config row. Measured
    against CONTENT_GAP (negative, to overlap the pin gutter) the step
    disappeared and both headers sat flush at the card edge."""
    from haybale_testing.nodes.testbed.nested_fold import NestedFoldNode

    _skin_factory, graph, _skin_key = ctx
    wrapper = graph.create_node_wrapper(NestedFoldNode.class_identity.registry_key, position=(0, 0))
    assert wrapper is not None

    headers = _fold_headers(_render(ctx, wrapper))

    assert headers.keys() == {"solver", "interpolation_range"}
    assert headers["solver"] >= 0, "a header must not sit left of the card padding"
    assert headers["interpolation_range"] > headers["solver"], (
        "a nested fold must read as nested — its header indents past its parent's"
    )
