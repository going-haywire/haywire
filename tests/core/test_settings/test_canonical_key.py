# Import order guard (see Global Constraints)

from haywire.barn.builtin.types import FLOAT, INT
from haywire.core.di.test_config import create_test_settings_registry
from haywire.core.settings import FrameworkSettings, NodeSettings, setting


def _descriptor_for(bag_cls: type, field: str) -> setting:
    """Pull the class-level descriptor object for a field off a Settings subclass."""
    return bag_cls.__dict__[field]


def test_storage_key_falls_back_to_attr_name_when_not_namespaced():
    class plain(NodeSettings):
        strength = setting[FLOAT](0.5)

    desc = _descriptor_for(plain, "strength")
    # No @node has run → _setting_key is empty → storage_key is the attr name.
    assert desc._setting_key == ""
    assert desc._attr_name == "strength"
    assert desc.storage_key == "strength"


def test_storage_key_uses_setting_key_when_namespaced():
    class plain(NodeSettings):
        strength = setting[FLOAT](0.5)

    desc = _descriptor_for(plain, "strength")
    # Simulate a namespacing path assigning the fully-qualified key.
    desc._setting_key = "pkg.node.plain.strength"
    assert desc.storage_key == "pkg.node.plain.strength"


def test_set_writes_under_storage_key_simple_mode():
    class plain(NodeSettings):
        strength = setting[FLOAT](0.5)

    bag = plain()  # no registry → simple mode → storage_key == attr name
    bag.strength = 0.9
    desc = _descriptor_for(plain, "strength")
    # The write must land under the canonical storage_key: the field's cell holds
    # the value and _set_keys records the override, both keyed by storage_key.
    assert desc.storage_key == "strength"
    assert bag._cells["strength"].get_value() == 0.9
    assert "strength" in bag._set_keys


def test_container_methods_key_consistently_simple_mode():
    class plain(NodeSettings):
        strength = setting[FLOAT](0.5)

    bag = plain()
    bag.strength = 0.9

    # to_dict surfaces the override under the attr name, nested under "values"
    assert bag.to_dict() == {"values": {"strength": 0.9}, "promoted": {}}
    # is_locally_set reads the same key the setter wrote
    assert bag.is_locally_set("strength") is True
    # reset removes it
    bag.reset("strength")
    assert bag.is_locally_set("strength") is False
    assert bag.strength == 0.5
    # from_dict restores it
    bag.from_dict({"values": {"strength": 0.7}, "promoted": {}})
    assert bag.strength == 0.7
    assert bag.is_locally_set("strength") is True


def test_node_bag_key_is_accessor_dot_field():
    """A @node stamps '<accessor>.<field>' — not the node's registry_key.

    Node bags never reach SettingsRegistry, so the key is only ever a per-node
    identifier; the accessor alone disambiguates same-named fields across bags.
    """
    from haywire.core.node import BaseNode, node

    @node(label="KeyProbe")
    class _KeyProbeNode(BaseNode):
        class filter(NodeSettings):
            strength = setting[FLOAT](0.5)

        def init(self):
            pass

        def worker(self, context):
            return None

    desc = _KeyProbeNode._settings_bags["filter"].__dict__["strength"]
    assert desc._setting_key == "filter.strength"
    assert desc.storage_key == "filter.strength"


def test_inherited_props_bag_is_not_stamped_with_first_node_name():
    """Regression: the shared ``props`` descriptors carry the accessor only.

    ``props`` is declared once on BaseNode, so its descriptor objects are shared
    by every node class. The old "stamp once, first writer wins" rule keyed every
    node's fields under whichever node class happened to be decorated first.
    """
    from haybale_testing.nodes.testbed.print_node import TestPrintNode
    from haywire.barn.builtin.nodes.reroute import RerouteNode

    for cls in (TestPrintNode, RerouteNode):
        bag_cls = cls._settings_bags["props"]
        for field in ("skin", "muted"):
            # getattr, not __dict__: both fields are declared on the
            # NodeProperties base, and class-level access on a descriptor
            # returns the descriptor itself.
            assert getattr(bag_cls, field)._setting_key == f"props.{field}"


def test_storage_key_extended_mode_uses_full_key():
    # A FrameworkSettings subclass with namespace= populates _setting_key on its
    # descriptors at class-definition time (schema.py __init_subclass__). This is
    # the EXTENDED-mode keying path where storage_key == the fully-qualified key.
    class _CanonKeyProbe(FrameworkSettings, namespace="test.canonkey"):
        font_size = setting[INT](12, min=8, max=72, label="Font Size")

    registry = create_test_settings_registry()
    # FrameworkSettings self-wires from the class attribute _registry, populated
    # as a side effect of SettingsRegistry.__init__ draining _pending_global —
    # it does NOT take a registry= constructor kwarg (unlike create_test_bag).
    bag = _CanonKeyProbe()

    desc = type(bag).__dict__["font_size"]
    # Extended mode: _setting_key is populated, so storage_key is the full key.
    assert desc._setting_key == "test.canonkey.font_size"
    assert desc.storage_key == desc._setting_key

    # FrameworkSettings auto-promotes namespaced fields to persistent_setting
    # (schema.py __init_subclass__), whose __set__ writes through
    # registry.set_global(self._setting_key, value) rather than the field's cell
    # when a registry is wired (descriptor.py persistent_setting.__set__). So the
    # round-trip proof for THIS descriptor type targets the registry tier, keyed
    # by storage_key, not the cell/is_locally_set (which stay empty/False by
    # design here — that path is for plain `setting` fields, proven by Tasks 1-3's
    # simple-mode tests and by tests/core/node/ in extended mode for NodeSettings).
    bag.font_size = 20
    assert bag.font_size == 20
    resolved_value, source = registry.resolve(desc.storage_key)
    assert resolved_value == 20
    assert source == "workspace"
