import haywire.core.graph.editor  # noqa: F401

import pytest

from haywire.core.types.enums import PortType


@pytest.mark.integration
def test_promotable_fields_offers_both_directions_for_writable(make_node_with_setting):
    """A plain/shadow field is eligible for inlet AND outlet; a watch field is
    outlet-only (read-only ⇒ no write path in). Already-promoted fields drop out."""
    from haybale_graph_editor.panels.graph.menu.node.promote import promotable_fields

    node = make_node_with_setting(accessor="filter", field="threshold", with_watch=True)
    fields = {(acc, fld): dirs for acc, fld, dirs in promotable_fields(node)}

    # plain field: both directions
    assert fields[("filter", "threshold")] == (PortType.INLET, PortType.OUTLET)
    # watch mirror field: outlet only
    assert fields[("filter", "threshold_watched")] == (PortType.OUTLET,)


@pytest.mark.integration
def test_promotable_fields_excludes_already_promoted(make_node_with_setting):
    from haybale_graph_editor.panels.graph.menu.node.promote import promotable_fields
    from haywire.core.node.promotion import promote_setting

    node = make_node_with_setting(accessor="filter", field="threshold")
    assert any(acc == "filter" and fld == "threshold" for acc, fld, _ in promotable_fields(node))

    promote_setting(node, "filter", "threshold")
    assert not any(acc == "filter" and fld == "threshold" for acc, fld, _ in promotable_fields(node))


@pytest.mark.integration
def test_detach_panel_identifies_promoted_port(make_node_with_setting):
    """The 'Detach from setting' panel targets a promoted port — identified by the
    port being present with promoted=True at the setting's storage_key (ADR 0015)."""
    from haywire.core.node.promotion import is_field_promoted, promote_setting

    node = make_node_with_setting(accessor="filter", field="threshold")
    promote_setting(node, "filter", "threshold")
    assert is_field_promoted(node.filter, "threshold")
    pid = type(node.filter).__dict__["threshold"].storage_key
    assert node.ports[pid].promoted is True


@pytest.mark.integration
def test_menu_enumerates_one_button_per_direction(make_node_with_setting):
    """The submenu offers a distinct verb per eligible direction: a writable field
    yields two rows (inlet + outlet), a watch field yields one (outlet)."""
    from haybale_graph_editor.panels.graph.menu.node.promote import promotable_fields

    node = make_node_with_setting(accessor="filter", field="threshold", with_watch=True)
    rows = [(acc, fld, d) for acc, fld, dirs in promotable_fields(node) for d in dirs]

    assert ("filter", "threshold", PortType.INLET) in rows
    assert ("filter", "threshold", PortType.OUTLET) in rows
    assert ("filter", "threshold_watched", PortType.OUTLET) in rows
    assert ("filter", "threshold_watched", PortType.INLET) not in rows


@pytest.mark.integration
def test_promote_action_forwards_direction(make_node_with_setting):
    """The provider's promote_setting verb forwards its direction to core promotion."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    captured: list = []

    # A tiny stand-in exercising the same body as the provider verb.
    def promote_verb(accessor, field, direction):
        from haywire.core.node.promotion import promote_setting

        captured.append(direction)
        promote_setting(node, accessor, field, direction)

    promote_verb("filter", "threshold", PortType.OUTLET)
    pid = type(node.filter).__dict__["threshold"].storage_key
    assert captured == [PortType.OUTLET]
    assert node.ports[pid].is_outlet()
