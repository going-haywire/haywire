# tests/core/test_settings/test_namespace_sub.py
"""Tests for GlobalSettingsRegistry.subscribe_namespace() and holder cache invalidation."""

import weakref
import pytest
from haywire.core.settings.enums import SettingMode
from haywire.core.settings.descriptors import setting, shadow, watch
from haywire.core.settings.schema import NodeSettings, GlobalSettings
from haywire.core.settings.holder import SettingsHolder
from haywire.core.di.test_config import create_test_settings_registry


# ---------------------------------------------------------------------------
# Global schema used by shadow/watch tests
# ---------------------------------------------------------------------------

class _SubGlobal(GlobalSettings, namespace='sub.global'):
    color: str = setting('#ffffff', label='Color')
    count: int = setting(0,         label='Count')


# ---------------------------------------------------------------------------
# subscribe_namespace / _notify_namespace_subscribers
# ---------------------------------------------------------------------------

class TestSubscribeNamespace:

    def test_subscriber_called_on_set(self):
        registry = create_test_settings_registry(register_builtins=False)
        registry.define(name='ns.test.value', default=0)

        received = []

        def cb(key):
            received.append(key)

        registry.subscribe_namespace('ns.test', weakref.ref(cb))
        registry.set_global('ns.test.value', 99, SettingMode.SET)

        assert 'ns.test.value' in received

    def test_subscriber_called_for_parent_namespace(self):
        """Subscriber on 'ns' is called when 'ns.test.value' changes."""
        registry = create_test_settings_registry(register_builtins=False)
        registry.define(name='ns.deep.key', default=0)

        received = []

        def cb(key):
            received.append(key)

        registry.subscribe_namespace('ns', weakref.ref(cb))
        registry.set_global('ns.deep.key', 1, SettingMode.SET)

        assert 'ns.deep.key' in received

    def test_multiple_subscribers_on_same_namespace(self):
        registry = create_test_settings_registry(register_builtins=False)
        registry.define(name='multi.ns.x', default=0)

        a_calls, b_calls = [], []

        def a(key): a_calls.append(key)
        def b(key): b_calls.append(key)

        registry.subscribe_namespace('multi.ns', weakref.ref(a))
        registry.subscribe_namespace('multi.ns', weakref.ref(b))
        registry.set_global('multi.ns.x', 5, SettingMode.SET)

        assert a_calls
        assert b_calls

    def test_dead_ref_pruned(self):
        """A dead weak reference is pruned and does not cause errors."""
        registry = create_test_settings_registry(register_builtins=False)
        registry.define(name='dead.ns.key', default=0)

        def make_cb():
            def cb(key): pass
            return cb

        cb = make_cb()
        ref = weakref.ref(cb)
        registry.subscribe_namespace('dead.ns', ref)
        del cb   # allow GC to collect

        # Should not raise even with dead ref
        registry.set_global('dead.ns.key', 1, SettingMode.SET)

    def test_no_call_when_value_unchanged(self):
        registry = create_test_settings_registry(register_builtins=False)
        registry.define(name='stable.ns.x', default=0)
        registry.set_global('stable.ns.x', 42, SettingMode.SET)

        received = []
        def cb(key): received.append(key)

        registry.subscribe_namespace('stable.ns', weakref.ref(cb))
        # Set to same value again — should not trigger
        registry.set_global('stable.ns.x', 42, SettingMode.SET)

        assert received == []


# ---------------------------------------------------------------------------
# Holder cache invalidation via namespace subscription
#
# Cache invalidation only fires for shadow() and watch() fields —
# those are the fields that subscribe to the global namespace.
# Plain setting() fields resolve against the chain on each cache miss only.
# ---------------------------------------------------------------------------

def _make_shadow_holder(registry):
    """Create a SettingsHolder whose fields are shadow() references to _SubGlobal."""

    class _ShadowSchema(NodeSettings, namespace='test.shadow.ns'):
        color: str = shadow(_SubGlobal.color)
        count: int = shadow(_SubGlobal.count)

    # Register _SubGlobal so set_global() works
    registry.register_schema(_SubGlobal)

    holder = SettingsHolder(_ShadowSchema, registry, node_instance=None)
    return holder


class TestHolderCacheInvalidationViaSubscription:

    def test_shadow_field_reflects_global_change(self):
        registry = create_test_settings_registry(register_builtins=False)
        holder = _make_shadow_holder(registry)

        assert holder.color == '#ffffff'   # prime cache

        registry.set_global('sub.global.color', '#123456', SettingMode.SET)

        assert holder.color == '#123456'   # cache must have been invalidated

    def test_shadow_field_reflects_override(self):
        registry = create_test_settings_registry(register_builtins=False)
        holder = _make_shadow_holder(registry)

        _ = holder.color   # prime cache

        registry.set_global('sub.global.color', '#abcdef', SettingMode.OVERRIDE)
        assert holder.color == '#abcdef'

    def test_shadow_field_local_override_unaffected(self):
        """A local override on a shadow field is not wiped by a global change."""
        registry = create_test_settings_registry(register_builtins=False)
        holder = _make_shadow_holder(registry)

        holder.set('color', '#ff0000')   # local override
        registry.set_global('sub.global.color', '#aaaaaa', SettingMode.SET)

        # Local override wins over global SET
        assert holder.color == '#ff0000'

    def test_watch_field_invalidated_on_global_change(self):
        """watch() fields also subscribe and auto-invalidate."""
        registry = create_test_settings_registry(register_builtins=False)
        registry.register_schema(_SubGlobal)

        class _WatchSchema(NodeSettings, namespace='test.watch.ns'):
            count: int = watch(_SubGlobal.count)

        holder = SettingsHolder(_WatchSchema, registry, node_instance=None)

        assert holder.count == 0   # prime cache

        registry.set_global('sub.global.count', 42, SettingMode.SET)

        assert holder.count == 42
