"""persistent_setting — descriptor that persists writes through the registry.

Verifies that writes via FrameworkSettings/LibrarySettings instances reach the
registry's workspace tier (so they survive restart and are visible to peer
instances), while preserving local-store fallback for instances with no
registry.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from haywire.core.settings.descriptor import setting, persistent_setting
from haywire.core.settings.registry import SettingsRegistry
from haywire.core.settings.schema import FrameworkSettings, LibrarySettings


# ---------------------------------------------------------------------------
# Test schemas
# ---------------------------------------------------------------------------


class _FrameworkSchema(FrameworkSettings, namespace="test.persistent.framework"):
    name = setting[str]("default", label="Name")


class _LibrarySchema(LibrarySettings, namespace="test.persistent.library"):
    name = setting[str]("default", label="Name")


# ---------------------------------------------------------------------------
# Class-swap verification
# ---------------------------------------------------------------------------


def test_framework_settings_field_is_promoted_to_persistent_setting():
    """FrameworkSettings.__init_subclass__ swaps each field to persistent_setting."""
    descriptor = _FrameworkSchema.__dict__["name"]
    assert isinstance(descriptor, persistent_setting)


def test_library_settings_field_is_promoted_to_persistent_setting():
    """LibrarySettings.__init_subclass__ swaps each field to persistent_setting."""
    descriptor = _LibrarySchema.__dict__["name"]
    assert isinstance(descriptor, persistent_setting)


# ---------------------------------------------------------------------------
# Persistence behaviour
# ---------------------------------------------------------------------------


@pytest.fixture
def wired_library_schema():
    """Build a registry-wired _LibrarySchema; yield (instance_factory, registry)."""
    registry = SettingsRegistry()
    registry.register_schema(_LibrarySchema)
    _LibrarySchema._registry = registry

    def make_instance():
        return _LibrarySchema()

    yield make_instance, registry
    _LibrarySchema._registry = None


def test_write_persists_through_registry(wired_library_schema):
    """A write on instance A is visible on a freshly-constructed instance B —
    regression test for the original bug (descriptor write only touched
    _local_store, never the registry)."""
    make_instance, registry = wired_library_schema

    a = make_instance()
    a.name = "first"

    b = make_instance()
    assert b.name == "first"


def test_write_calls_set_global(wired_library_schema):
    """Verify that a write routes through registry.set_global with the correct key/value."""
    make_instance, registry = wired_library_schema
    set_global_mock = MagicMock(wraps=registry.set_global)
    registry.set_global = set_global_mock

    inst = make_instance()
    inst.name = "second"

    set_global_mock.assert_called_once_with("test.persistent.library.name", "second")


def test_write_does_not_double_fire_on_property_change(wired_library_schema):
    """persistent_setting.__set__ must NOT call _on_property_change directly —
    registry.set_global → _notify_subscribers → _on_field_change → _on_property_change
    is the single source of truth. Calling _on_property_change directly would
    double-fire every subscriber callback (UI redraws, IPC, etc).

    Regression test for the original review of d8ff3a31."""
    make_instance, _registry = wired_library_schema

    inst = make_instance()
    fired: list[tuple] = []
    inst.subscribe(lambda name, value, old: fired.append((name, value, old)))

    inst.name = "new"

    # Exactly ONE call, not two.
    assert len(fired) == 1, f"Expected single fire, got {len(fired)}: {fired}"


def test_save_to_toml_debounced_is_noop_without_workspace_path():
    """save_to_toml_debounced must be a no-op when no path is configured —
    otherwise the background timer would fire save_to_toml which raises
    ValueError on a thread with no error handling."""
    registry = SettingsRegistry()
    # No workspace_path set, no path argument.
    registry.save_to_toml_debounced()

    # No timer was scheduled.
    assert getattr(registry, "_save_timer", None) is None


# ---------------------------------------------------------------------------
# Fallback: registry not wired
# ---------------------------------------------------------------------------


def test_write_falls_back_to_local_store_when_registry_missing():
    """If a Library/FrameworkSettings is constructed without a registry
    (test/dev environments), persistent_setting falls through to the parent's
    local-store write so existing tests aren't broken.

    Note: setting.__get__ in simple-mode reads by _attr_name while __set__ writes
    by _setting_key (the full namespaced key). That asymmetry exists in the base
    setting descriptor and is out of scope here. What matters is:
      - no exception is raised
      - the value lands in _local_store (not lost), keyed by _setting_key
      - set_global / save_to_toml_debounced are NOT called (no registry)
    """

    # Build a fresh schema and DON'T wire a registry.
    class _UnwiredSchema(LibrarySettings, namespace="test.persistent.unwired"):
        name = setting[str]("default", label="Name")

    # No registry registration — _registry stays None.
    inst = _UnwiredSchema()
    inst.name = "fallback"  # must not raise
    # Value is stored in _local_store under the namespaced key (parent __set__ behaviour)
    assert inst._local_store.get("test.persistent.unwired.name") == "fallback"


# ---------------------------------------------------------------------------
# Read-only mirror still raises
# ---------------------------------------------------------------------------


def test_persistent_setting_respects_read_only():
    """A read_only field must still raise AttributeError on write —
    persistent_setting overrides __set__ but inherits the read_only guard."""
    descriptor = _FrameworkSchema.__dict__["name"]
    descriptor._read_only = True
    try:
        inst = _FrameworkSchema()
        with pytest.raises(AttributeError, match="read-only"):
            inst.name = "x"
    finally:
        descriptor._read_only = False


# ---------------------------------------------------------------------------
# @settings decorator path — separate from class-signature namespace path
# ---------------------------------------------------------------------------


def test_settings_decorator_promotes_descriptor_to_persistent_setting():
    """The @settings decorator path must also promote each field's descriptor
    to persistent_setting. The class-signature namespace path (tested above)
    does this in LibrarySettings.__init_subclass__; the @settings decorator
    must mirror that symmetry — otherwise libraries using the decorator
    pattern (the canonical real-world pattern) silently lose persistence.

    Regression test for a smoke-test discovery: HaystackSettings uses
    @settings(namespace=...) and was NOT promoted before this fix."""
    from haywire.core.settings.decorator import settings

    @settings(namespace="test.decorator.promoted")
    class _DecoratedSchema(LibrarySettings):
        name = setting[str]("default", label="Name")

    descriptor = _DecoratedSchema.__dict__["name"]
    assert isinstance(descriptor, persistent_setting), (
        f"Expected persistent_setting, got {type(descriptor).__name__} — "
        f"the @settings decorator failed to promote the field"
    )


def test_haystack_settings_writes_persist_through_registry():
    """End-to-end smoke equivalent: HaystackSettings uses @settings(namespace=...);
    a write to one instance must be visible to a freshly-constructed instance.

    This is the test that would have caught the production bug surfaced by the
    manual smoke test."""
    from haybale_haystack.settings.haystack_settings import HaystackSettings

    registry = SettingsRegistry()
    registry.register_schema(HaystackSettings)
    HaystackSettings._registry = registry
    try:
        a = HaystackSettings()
        a.last_haystack_name = "from-a"

        b = HaystackSettings()
        assert b.last_haystack_name == "from-a"
    finally:
        HaystackSettings._registry = None
