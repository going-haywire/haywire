"""The Metadata node's pins follow its field lists, under undo, redo, save and load."""

import json

import pytest
from haybale_image.types.depth import DEPTH
from haybale_image.types.image import IMAGE_GRAY, IMAGE_RGB
from haybale_testing.types.test_types import TEST_FLOAT, TEST_INT

from haywire.barn.builtin.nodes.metadata import MetadataNode
from haywire.barn.builtin.types import BUNDLE, FIELD_LIST, INT
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.editor import Editor
from haywire.core.graph.setting_owner import SettingOwner
from haywire.core.node.layout import position_of
from haywire.core.types.enums import PortOrigin
from tests.core.test_types.test_add_type import _make_link_node

pytestmark = pytest.mark.integration


def _validate(graph):
    graph._validation.force_immediate_validation()


def _metadata(graph, position=(300, 0)):
    wrapper = graph.create_node_wrapper(MetadataNode.class_identity.registry_key, position=position)
    assert isinstance(wrapper.node, MetadataNode)
    return wrapper


@pytest.fixture
def setup(graph_with_library_system, library_system):
    graph = graph_with_library_system
    meta = _metadata(graph)
    source = _make_link_node(graph, (0, 0))
    editor = Editor(graph, source._node_factory)
    owner = SettingOwner(kind="node", accessor="metadata_fields", owner_id=meta.node_id)
    return graph, editor, owner, meta, source


def _with_field_pins(setup):
    """Declare stamp ``a`` and read ``b``, wired to the source and to a sink."""
    graph, editor, owner, meta, source = setup
    assert editor.set_setting(owner, "stamp", FIELD_LIST().with_added("a", TEST_INT))
    assert editor.set_setting(owner, "read", FIELD_LIST().with_added("b", TEST_INT))
    sink = _make_link_node(graph, (600, 0))
    into = graph.create_edge_wrapper(source.node_id, "int_outlet", meta.node_id, "a_in")
    out = graph.create_edge_wrapper(meta.node_id, "b_out", sink.node_id, "int_inlet")
    _validate(graph)
    assert into.is_functional()
    assert out.is_functional()
    editor.history_manager.add_fence()
    return sink, into, out


def test_a_new_node_has_only_the_carrier_pins(setup):
    _, _, _, meta, _ = setup
    field_pins = [p for p in meta.node.ports if p.endswith(("_in", "_out"))]
    assert field_pins == []
    assert meta.node.ports["carrier_inlet"].is_inlet()
    assert meta.node.ports["carrier_outlet"].is_outlet()
    assert meta.node.ports["carrier_inlet"].hidden is False


def test_adding_fields_makes_the_pins(setup):
    graph, editor, owner, meta, _ = setup
    editor.set_setting(owner, "stamp", FIELD_LIST().with_added("a", TEST_FLOAT))
    editor.set_setting(owner, "read", FIELD_LIST().with_added("b", TEST_INT))
    _validate(graph)
    a, b = meta.node.ports["a_in"], meta.node.ports["b_out"]
    assert a.is_inlet()
    assert a.type_cls is TEST_FLOAT
    assert a.origin is PortOrigin.DECLARED
    assert b.is_outlet()
    assert b.type_cls is TEST_INT
    assert not b.should_show_widget()


def test_one_key_can_be_stamped_and_read(setup):
    graph, editor, owner, meta, _ = setup
    editor.set_setting(owner, "stamp", FIELD_LIST().with_added("t", TEST_INT))
    editor.set_setting(owner, "read", FIELD_LIST().with_added("t", TEST_INT))
    _validate(graph)
    assert {"t_in", "t_out"} <= set(meta.node.ports)


def test_removing_a_field_then_undo_restores_pin_and_working_wires(setup):
    graph, editor, owner, meta, source = setup
    sink, into, out = _with_field_pins(setup)

    editor.set_setting(owner, "stamp", FIELD_LIST())
    editor.set_setting(owner, "read", FIELD_LIST())
    _validate(graph)
    assert "a_in" not in meta.node.ports
    assert "b_out" not in meta.node.ports
    assert graph.get_edge_wrapper(into.edge_id) is into
    assert not into.is_functional()
    assert not out.is_functional()

    assert editor.undo()
    _validate(graph)
    assert into.is_functional()
    assert out.is_functional()
    source.node.out("int_outlet", 11)
    meta.node.out("b_out", 77)
    assert meta.node.value("a_in") == 11
    assert sink.node.value("int_inlet") == 77

    assert editor.redo()
    _validate(graph)
    assert not into.is_functional()
    assert editor.undo()
    _validate(graph)
    assert into.is_functional()


def test_a_constant_on_a_stamp_pin_survives_adding_another_field(setup):
    graph, editor, owner, meta, _ = setup
    one = FIELD_LIST().with_added("a", TEST_INT)
    editor.set_setting(owner, "stamp", one)
    _validate(graph)
    meta.node.ports["a_in"].set_value(7)
    editor.set_setting(owner, "stamp", one.with_added("c", TEST_INT))
    _validate(graph)
    assert meta.node.value("a_in") == 7


def test_a_field_named_carrier_does_not_clash(setup):
    graph, editor, owner, meta, _ = setup
    editor.set_setting(owner, "stamp", FIELD_LIST().with_added("carrier", TEST_INT))
    _validate(graph)
    assert {"carrier_in", "carrier_inlet", "carrier_outlet"} <= set(meta.node.ports)


def test_the_pin_menu_cannot_remove_a_field_pin(setup):
    graph, editor, owner, meta, _ = setup
    editor.set_setting(owner, "stamp", FIELD_LIST().with_added("a", TEST_INT))
    _validate(graph)
    assert editor.remove_port(meta.node_id, "a_in") is False
    assert "a_in" in meta.node.ports


def _sources(source):
    source.node.add(IMAGE_RGB.as_outlet("rgb_out"))
    source.node.add(IMAGE_GRAY.as_outlet("gray_out"))
    source.node.add(BUNDLE.as_outlet("bundle_out"))


def test_carrier_outlet_follows_the_source(setup):
    graph, _, _, meta, source = setup
    _sources(source)
    sink = _make_link_node(graph, (600, 0))
    sink.node.add(IMAGE_RGB.as_inlet("rgb_in"))

    first = graph.create_edge_wrapper(source.node_id, "rgb_out", meta.node_id, "carrier_inlet")
    _validate(graph)
    assert meta.node.ports["carrier_outlet"].type_cls is IMAGE_RGB
    assert meta.node.ports["carrier_inlet"].type_cls.__name__ == "CARRIER"

    downstream = graph.create_edge_wrapper(meta.node_id, "carrier_outlet", sink.node_id, "rgb_in")
    _validate(graph)
    assert downstream.is_functional()

    graph.remove_edge_wrapper(first.edge_id)
    _validate(graph)
    assert meta.node.ports["carrier_outlet"].type_cls is IMAGE_RGB

    graph.create_edge_wrapper(source.node_id, "gray_out", meta.node_id, "carrier_inlet")
    _validate(graph)
    assert meta.node.ports["carrier_outlet"].type_cls is IMAGE_GRAY
    assert downstream.is_functional()


@pytest.mark.parametrize(
    ("outlet", "connects"), [("bundle_out", True), ("rgb_out", True), ("int_outlet", False)]
)
def test_what_the_carrier_inlet_accepts(setup, outlet, connects):
    graph, _, _, meta, source = setup
    _sources(source)
    edge = graph.create_edge_wrapper(source.node_id, outlet, meta.node_id, "carrier_inlet")
    _validate(graph)
    assert edge.is_functional() is connects
    if not connects:
        assert meta.node.ports["carrier_outlet"].type_cls.__name__ == "CARRIER"


def _reload(graph):
    loaded = BaseGraph(filestem="reloaded")
    assert loaded.load_from_dict(graph.to_dict()) is True
    _validate(loaded)
    return loaded


def test_a_saved_graph_restores_pins_wires_and_keeps_rebuilding(setup):
    graph, editor, owner, meta, _ = setup
    _, into, out = _with_field_pins(setup)
    loaded = _reload(graph)
    try:
        node = loaded.get_node_wrapper(meta.node_id).node
        assert isinstance(node, MetadataNode)
        assert {"a_in", "b_out", "carrier_inlet", "carrier_outlet"} <= set(node.ports)
        assert [e.is_functional() for e in loaded.edge_wrappers.values()] == [True, True]
        node.metadata_fields.stamp = FIELD_LIST()
        assert "a_in" not in node.ports
    finally:
        loaded.cleanup()


def test_a_stamp_constant_survives_save_and_load(setup):
    graph, editor, owner, meta, _ = setup
    editor.set_setting(owner, "stamp", FIELD_LIST().with_added("a", INT))
    _validate(graph)
    meta.node.ports["a_in"].set_value(7)
    loaded = _reload(graph)
    try:
        assert loaded.get_node_wrapper(meta.node_id).node.value("a_in") == 7
    finally:
        loaded.cleanup()


def test_save_with_a_removed_field_loads_and_re_adding_relinks(setup):
    graph, editor, owner, meta, _ = setup
    _with_field_pins(setup)
    editor.set_setting(owner, "stamp", FIELD_LIST())
    _validate(graph)
    loaded = _reload(graph)
    try:
        node = loaded.get_node_wrapper(meta.node_id).node
        edges = list(loaded.edge_wrappers.values())
        assert any(not e.is_functional() for e in edges)
        node.metadata_fields.stamp = FIELD_LIST().with_added("a", TEST_INT)
        _validate(loaded)
        assert all(e.is_functional() for e in edges)
    finally:
        loaded.cleanup()


GONE = {"entries": [{"key": "x", "recipe": {"registry_key": "nolib:type:GONE"}}]}


def test_an_entry_whose_type_is_missing_keeps_the_node_and_the_entry(setup, caplog):
    graph, editor, owner, meta, _ = setup
    editor.set_setting(owner, "stamp", FIELD_LIST.from_dict(GONE))
    _validate(graph)
    assert isinstance(meta.node, MetadataNode)
    assert "x_in" not in meta.node.ports
    assert [e.key for e in meta.node.metadata_fields.stamp.entries] == ["x"]
    assert "nolib:type:GONE" in caplog.text
    loaded = _reload(graph)
    try:
        node = loaded.get_node_wrapper(meta.node_id).node
        assert isinstance(node, MetadataNode)
        assert [e.key for e in node.metadata_fields.stamp.entries] == ["x"]
    finally:
        loaded.cleanup()


def test_a_saved_pin_whose_type_is_missing_still_loads(setup):
    """The library was there when saved: the file holds the pin, and the type is now gone."""
    graph, editor, owner, meta, _ = setup
    editor.set_setting(owner, "stamp", FIELD_LIST().with_added("a", TEST_INT))
    _validate(graph)
    data = graph.to_dict()
    for node in data["nodes"].values():
        ports = node.get("node_data", {}).get("ports", {})
        if "a_in" in ports:
            ports["a_in"]["recipe"] = {"registry_key": "nolib:type:GONE"}
    loaded = BaseGraph(filestem="reloaded")
    try:
        assert loaded.load_from_dict(data) is True
        wrapper = loaded.get_node_wrapper(meta.node_id)
        # The node reports the failure on its card and still holds its list, so
        # the pin returns on the next load once the library is back.
        assert wrapper is not None
        assert isinstance(wrapper.node, MetadataNode)
        assert wrapper.state.error_initialize is not None
        assert [e.key for e in wrapper.node.metadata_fields.stamp.entries] == ["a"]
    finally:
        loaded.cleanup()


def test_field_lists_survive_a_real_file(setup, tmp_path):
    graph, editor, owner, meta, _ = setup
    _with_field_pins(setup)
    path = tmp_path / "saved.haywire"
    assert graph.save_to_file(str(path)) is True
    loaded = BaseGraph(filestem="saved")
    try:
        assert loaded.load_from_file(str(path)) is True
        _validate(loaded)
        wrapper = loaded.get_node_wrapper(meta.node_id)
        assert wrapper is not None
        assert isinstance(wrapper.node, MetadataNode)
        assert wrapper.state.error_initialize is None
        assert [e.key for e in wrapper.node.metadata_fields.stamp.entries] == ["a"]
        assert [e.is_functional() for e in loaded.edge_wrappers.values()] == [True, True]
    finally:
        loaded.cleanup()


def test_an_emptied_list_still_saves(setup, tmp_path):
    graph, editor, owner, meta, _ = setup
    editor.set_setting(owner, "stamp", FIELD_LIST().with_added("a", TEST_INT))
    editor.set_setting(owner, "stamp", FIELD_LIST())
    assert graph.save_to_file(str(tmp_path / "saved.haywire")) is True


def test_a_field_list_can_be_copied_as_json(setup):
    graph, editor, owner, meta, _ = setup
    editor.set_setting(owner, "stamp", FIELD_LIST().with_added("a", TEST_INT))
    assert "stamp" in json.dumps(meta.serialize(include_data=True))


def test_a_retype_travels_down_a_chain_of_metadata_nodes(setup):
    graph, _, _, first, source = setup
    _sources(source)
    second = _metadata(graph, (600, 0))
    graph.create_edge_wrapper(first.node_id, "carrier_outlet", second.node_id, "carrier_inlet")
    _validate(graph)
    graph.create_edge_wrapper(source.node_id, "rgb_out", first.node_id, "carrier_inlet")
    _validate(graph)
    assert second.node.ports["carrier_outlet"].type_cls is IMAGE_RGB


def test_swapping_the_source_refuses_what_a_chain_can_no_longer_deliver(setup):
    graph, _, _, first, source = setup
    _sources(source)
    source.node.add(DEPTH.as_outlet("depth_out"))
    second = _metadata(graph, (600, 0))
    sink = _make_link_node(graph, (900, 0))
    sink.node.add(IMAGE_RGB.as_inlet("rgb_in"))
    edge = graph.create_edge_wrapper(source.node_id, "rgb_out", first.node_id, "carrier_inlet")
    graph.create_edge_wrapper(first.node_id, "carrier_outlet", second.node_id, "carrier_inlet")
    end = graph.create_edge_wrapper(second.node_id, "carrier_outlet", sink.node_id, "rgb_in")
    _validate(graph)
    assert end.is_functional()
    graph.remove_edge_wrapper(edge.edge_id)
    graph.create_edge_wrapper(source.node_id, "depth_out", first.node_id, "carrier_inlet")
    _validate(graph)
    assert second.node.ports["carrier_outlet"].type_cls is DEPTH
    assert not end.is_functional()


@pytest.mark.parametrize(
    "recipe", [{"registry_key": ["x"]}, {"registry_key": "haywire-core:type:INT", "element_type": "x"}]
)
def test_a_malformed_recipe_costs_only_its_own_pin(setup, recipe):
    graph, editor, owner, meta, _ = setup
    bad = {
        "entries": [
            {"key": "x", "recipe": recipe},
            {"key": "ok", "recipe": {"registry_key": "haywire-core:type:INT"}},
        ]
    }
    editor.set_setting(owner, "stamp", FIELD_LIST.from_dict(bad))
    _validate(graph)
    assert "ok_in" in meta.node.ports
    assert "x_in" not in meta.node.ports
    loaded = _reload(graph)
    try:
        wrapper = loaded.get_node_wrapper(meta.node_id)
        assert wrapper is not None
        assert wrapper.state.error_initialize is None
    finally:
        loaded.cleanup()


def test_saving_a_node_that_failed_to_load_keeps_what_it_loaded_from(setup):
    """The library is gone for one pin; saving must not lose the pins after it."""
    graph, editor, owner, meta, _ = setup
    editor.set_setting(owner, "stamp", FIELD_LIST().with_added("a", INT))
    _validate(graph)
    meta.node.ports["a_in"].set_value(7)
    data = graph.to_dict()
    ports = data["nodes"][meta.node_id]["node_data"]["ports"]
    first = next(iter(ports))
    ports[first]["recipe"] = {"registry_key": "nolib:type:GONE"}
    before = json.dumps(ports, sort_keys=True)

    broken = BaseGraph(filestem="broken")
    try:
        assert broken.load_from_dict(data) is True
        wrapper = broken.get_node_wrapper(meta.node_id)
        assert wrapper is not None
        assert wrapper.state.error_initialize is not None
        saved = wrapper.serialize(include_data=True)["node_data"]["ports"]
        assert json.dumps(saved, sort_keys=True) == before
    finally:
        broken.cleanup()


def _load_with_a_gone_pin_type(graph, node_id):
    """Load ``graph``'s data with the first pin's library gone, so the node fails to load."""
    data = graph.to_dict()
    ports = data["nodes"][node_id]["node_data"]["ports"]
    ports[next(iter(ports))]["recipe"] = {"registry_key": "nolib:type:GONE"}
    broken = BaseGraph(filestem="broken")
    assert broken.load_from_dict(data) is True
    wrapper = broken.get_node_wrapper(node_id)
    assert wrapper is not None
    assert wrapper.state.error_initialize is not None
    return broken, wrapper, data["nodes"][node_id]["node_data"]


def test_a_node_that_failed_to_load_stays_where_it_was_saved(setup):
    graph, _, _, meta, _ = setup
    meta.move(640.0, 320.0)
    broken, wrapper, _ = _load_with_a_gone_pin_type(graph, meta.node_id)
    try:
        assert wrapper.node.props.get_position() == (640.0, 320.0)
        assert position_of(wrapper.serialize(include_data=True)) == (640.0, 320.0)
    finally:
        broken.cleanup()


def test_a_moved_node_that_failed_to_load_saves_its_new_position(setup):
    graph, _, _, meta, _ = setup
    broken, wrapper, original = _load_with_a_gone_pin_type(graph, meta.node_id)
    try:
        broken.move_node(meta.node_id, 111.0, 222.0)
        saved = wrapper.serialize(include_data=True)
        assert position_of(saved) == (111.0, 222.0)
        assert saved["node_data"]["ports"] == original["ports"]
    finally:
        broken.cleanup()


def test_a_rebuild_of_a_node_that_failed_to_load_starts_from_the_saved_data(setup):
    graph, _, _, meta, _ = setup
    broken, wrapper, original = _load_with_a_gone_pin_type(graph, meta.node_id)
    try:
        wrapper.build()
        assert wrapper.state.error_initialize is not None
        assert wrapper.serialize(include_data=True)["node_data"]["ports"] == original["ports"]
    finally:
        broken.cleanup()


def test_a_failed_load_saved_without_data_leaves_out_port_values(setup):
    graph, editor, owner, meta, _ = setup
    editor.set_setting(owner, "stamp", FIELD_LIST().with_added("a", INT))
    _validate(graph)
    meta.node.ports["a_in"].set_value(7)
    broken, wrapper, _ = _load_with_a_gone_pin_type(graph, meta.node_id)
    try:
        ports = wrapper.serialize(include_data=False)["node_data"]["ports"]
        assert all("field_data" not in port for port in ports.values())
    finally:
        broken.cleanup()


def test_a_node_that_failed_to_load_recovers_on_the_rebuild_after_the_fix(setup, monkeypatch):
    graph, editor, owner, meta, _ = setup
    editor.set_setting(owner, "stamp", FIELD_LIST().with_added("a", INT))
    _validate(graph)
    meta.node.ports["a_in"].set_value(7)
    meta.move(640.0, 320.0)
    data = graph.to_dict()

    def fails(self):
        raise RuntimeError("broken for now")

    with monkeypatch.context() as broken_class:
        broken_class.setattr(MetadataNode, "post_init", fails)
        broken = BaseGraph(filestem="broken")
        assert broken.load_from_dict(data) is True
    try:
        wrapper = broken.get_node_wrapper(meta.node_id)
        assert wrapper is not None
        assert wrapper.state.error_initialize is not None

        wrapper.build()

        assert wrapper.state.error_initialize is None
        assert wrapper._kept_data is None
        assert wrapper.node.ports["a_in"].get_value() == 7
        assert wrapper.node.props.get_position() == (640.0, 320.0)
    finally:
        broken.cleanup()
