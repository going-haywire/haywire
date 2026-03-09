# tests/core/test_settings/test_sub_holders.py
"""
Tests for the namespaced SettingsHolder / SubHolder architecture.

Covers:
- Inner class form (class node(NodeSettings): ...)
- Direct assignment form (image = ImageLibSettings)
- '_node' reserved accessor always present
- '_node' reserved name raises ValueError in decorator
- Multiple sub-holders on one node
- Namespaced to_dict() / from_dict() round-trip
- cleanup() releases all sub-holders
- registered_schemas() / definitions_for_schema() on the registry
"""

import pytest
from haywire.core.settings.schema import NodeSettings, GlobalSettings
from haywire.core.settings.descriptors import setting
from haywire.core.settings.holder import SettingsHolder, SubHolder
from haywire.core.settings.builtins.node_instance import NodeInstanceSettings
from haywire.core.di.test_config import create_test_settings_registry


# ---------------------------------------------------------------------------
# Shared schemas
# ---------------------------------------------------------------------------

class _ThresholdSchema(NodeSettings, namespace='test.thresh'):
    threshold: float = setting(0.5, label='Threshold')
    verbose:   bool  = setting(False, label='Verbose')


class _ColorSchema(GlobalSettings, namespace='test.color'):
    bg_color: str = setting('#ffffff', label='Background Color')
    fg_color: str = setting('#000000', label='Foreground Color')


def _make_holder(schemas: dict, registry=None) -> SettingsHolder:
    if registry is None:
        registry = create_test_settings_registry(register_builtins=False)
    return SettingsHolder(schemas=schemas, registry=registry, node_instance=None)


# ---------------------------------------------------------------------------
# Sub-holder access — inner class form
# ---------------------------------------------------------------------------

class TestInnerClassForm:

    def test_sub_holder_accessible_by_name(self):
        holder = _make_holder({'node': _ThresholdSchema, '_node': NodeInstanceSettings})
        sub = holder.node
        assert isinstance(sub, SubHolder)

    def test_field_read(self):
        holder = _make_holder({'node': _ThresholdSchema, '_node': NodeInstanceSettings})
        assert holder.node.threshold == 0.5

    def test_field_write_and_read(self):
        holder = _make_holder({'node': _ThresholdSchema, '_node': NodeInstanceSettings})
        holder.node.threshold = 0.9
        assert holder.node.threshold == 0.9

    def test_bool_field(self):
        holder = _make_holder({'node': _ThresholdSchema, '_node': NodeInstanceSettings})
        holder.node.verbose = True
        assert holder.node.verbose is True

    def test_missing_accessor_raises(self):
        holder = _make_holder({'node': _ThresholdSchema, '_node': NodeInstanceSettings})
        with pytest.raises(AttributeError):
            _ = holder.nonexistent

    def test_missing_field_raises(self):
        holder = _make_holder({'node': _ThresholdSchema, '_node': NodeInstanceSettings})
        with pytest.raises(AttributeError):
            _ = holder.node.nonexistent_field


# ---------------------------------------------------------------------------
# Sub-holder access — direct assignment form
# ---------------------------------------------------------------------------

class TestDirectAssignmentForm:
    """
    Simulates: image = ImageLibSettings (direct assignment in node body).
    The accessor name ('image') is arbitrary; the schema's _full_key is set
    by the schema class definition, independent of the accessor name.
    """

    def test_direct_assignment_accessible(self):
        holder = _make_holder({'image': _ThresholdSchema, '_node': NodeInstanceSettings})
        assert holder.image.threshold == 0.5

    def test_two_different_accessor_names_same_schema(self):
        """Same schema class can be used under any accessor name."""
        h1 = _make_holder({'alpha': _ThresholdSchema, '_node': NodeInstanceSettings})
        h2 = _make_holder({'beta': _ThresholdSchema, '_node': NodeInstanceSettings})
        h1.alpha.threshold = 0.1
        h2.beta.threshold = 0.2
        assert h1.alpha.threshold == 0.1
        assert h2.beta.threshold == 0.2


# ---------------------------------------------------------------------------
# Reserved '_node' accessor
# ---------------------------------------------------------------------------

class TestNodeReservedAccessor:

    def test_node_accessor_always_present(self):
        holder = _make_holder({'custom': _ThresholdSchema, '_node': NodeInstanceSettings})
        assert '_node' in holder

    def test_node_is_subholder(self):
        holder = _make_holder({'custom': _ThresholdSchema, '_node': NodeInstanceSettings})
        assert isinstance(holder._node, SubHolder)

    def test_node_schema_is_nodeinstancesettings(self):
        holder = _make_holder({'custom': _ThresholdSchema, '_node': NodeInstanceSettings})
        schema = object.__getattribute__(holder._node, '_schema')
        assert schema is NodeInstanceSettings

    def test_node_reserved_name_raises_in_decorator(self):
        """@node decorator raises ValueError if developer names an inner class '_node'."""
        from haywire.core.node.decorator import _wire_settings_namespace
        from haywire.core.node.base import BaseNode

        class _FakeNode:
            _node = _ThresholdSchema   # reserved name

        with pytest.raises(ValueError, match="reserved"):
            _wire_settings_namespace(_FakeNode, 'test:node:fake')


# ---------------------------------------------------------------------------
# Multiple sub-holders on one holder
# ---------------------------------------------------------------------------

class TestMultipleSubHolders:

    def test_two_sub_holders_independent(self):
        holder = _make_holder({
            'thresh': _ThresholdSchema,
            '_node': NodeInstanceSettings,
        })
        holder.thresh.threshold = 0.7
        # _node subholder is there too
        assert holder.thresh.threshold == 0.7
        assert '_node' in holder

    def test_iteration_returns_all_accessors(self):
        holder = _make_holder({
            'thresh': _ThresholdSchema,
            '_node': NodeInstanceSettings,
        })
        names = list(holder)
        assert 'thresh' in names
        assert '_node' in names

    def test_contains(self):
        holder = _make_holder({
            'thresh': _ThresholdSchema,
            '_node': NodeInstanceSettings,
        })
        assert 'thresh' in holder
        assert '_node' in holder
        assert 'nonexistent' not in holder

    def test_sub_holders_property(self):
        holder = _make_holder({
            'thresh': _ThresholdSchema,
            '_node': NodeInstanceSettings,
        })
        subs = holder.sub_holders
        assert isinstance(subs, dict)
        assert 'thresh' in subs
        assert '_node' in subs


# ---------------------------------------------------------------------------
# Namespaced to_dict() / from_dict()
# ---------------------------------------------------------------------------

class TestNamespacedSerialization:

    def test_to_dict_has_accessor_keys(self):
        holder = _make_holder({
            'thresh': _ThresholdSchema,
            '_node': NodeInstanceSettings,
        })
        data = holder.to_dict()
        assert 'thresh' in data
        assert '_node' in data

    def test_to_dict_sub_has_schema_values(self):
        holder = _make_holder({
            'thresh': _ThresholdSchema,
            '_node': NodeInstanceSettings,
        })
        holder.thresh.threshold = 0.8
        data = holder.to_dict()
        assert data['thresh']['schema_values']['threshold'] == 0.8

    def test_to_dict_empty_when_nothing_set(self):
        holder = _make_holder({
            'thresh': _ThresholdSchema,
            '_node': NodeInstanceSettings,
        })
        data = holder.to_dict()
        assert data['thresh']['schema_values'] == {}

    def test_from_dict_restores_value(self):
        holder = _make_holder({
            'thresh': _ThresholdSchema,
            '_node': NodeInstanceSettings,
        })
        holder.from_dict({'thresh': {'schema_values': {'threshold': 0.3}}})
        assert holder.thresh.threshold == 0.3

    def test_round_trip(self):
        h1 = _make_holder({'thresh': _ThresholdSchema, '_node': NodeInstanceSettings})
        h1.thresh.threshold = 0.77
        data = h1.to_dict()

        h2 = _make_holder({'thresh': _ThresholdSchema, '_node': NodeInstanceSettings})
        h2.from_dict(data)
        assert h2.thresh.threshold == 0.77

    def test_from_dict_ignores_unknown_accessor(self):
        """Extra keys in serialized data don't cause errors."""
        holder = _make_holder({
            'thresh': _ThresholdSchema,
            '_node': NodeInstanceSettings,
        })
        holder.from_dict({'thresh': {'schema_values': {}}, 'obsolete': {'schema_values': {}}})
        # No exception — just silently ignored


# ---------------------------------------------------------------------------
# cleanup()
# ---------------------------------------------------------------------------

class TestCleanup:

    def test_cleanup_clears_all_sub_holders(self):
        holder = _make_holder({'thresh': _ThresholdSchema, '_node': NodeInstanceSettings})
        holder.thresh.threshold = 0.9   # prime cache

        holder.cleanup()

        # After cleanup, each sub-holder's cache is cleared
        thresh_sub = object.__getattribute__(holder, '_sub_holders')['thresh']
        assert object.__getattribute__(thresh_sub, '_cleaned_up') is True


# ---------------------------------------------------------------------------
# Registry query methods: registered_schemas / definitions_for_schema
# ---------------------------------------------------------------------------

class TestRegistryQueryMethods:

    def test_registered_schemas_returns_list(self):
        registry = create_test_settings_registry(register_builtins=False)
        registry.register_schema(_ColorSchema)
        schemas = registry.registered_schemas()
        assert _ColorSchema in schemas

    def test_registered_schemas_empty_when_none(self):
        registry = create_test_settings_registry(register_builtins=False)
        assert registry.registered_schemas() == []

    def test_definitions_for_schema_returns_matching_definitions(self):
        registry = create_test_settings_registry(register_builtins=False)
        registry.register_schema(_ColorSchema)

        defns = registry.definitions_for_schema(_ColorSchema)
        assert 'test.color.bg_color' in defns
        assert 'test.color.fg_color' in defns

    def test_definitions_for_schema_empty_for_unregistered(self):
        registry = create_test_settings_registry(register_builtins=False)
        defns = registry.definitions_for_schema(_ColorSchema)
        assert defns == {}

    def test_definitions_for_schema_does_not_include_other_schemas(self):
        from haywire.core.settings.schema import GlobalSettings

        registry = create_test_settings_registry(register_builtins=False)

        class _OtherSchema(GlobalSettings, namespace='test.other'):
            x: int = setting(1)

        registry.register_schema(_ColorSchema)
        registry.register_schema(_OtherSchema)

        color_defns = registry.definitions_for_schema(_ColorSchema)
        assert 'test.other.x' not in color_defns
