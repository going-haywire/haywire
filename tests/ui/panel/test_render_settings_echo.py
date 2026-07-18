"""
Echo-discipline regression for render_settings external sync.

The cross-tab update path (subscription -> apply -> widget.value -> widget
on_change -> setattr(model)) is only safe because writing a value the model
already holds does NOT re-fire _on_property_change. This pins that guarantee at
the model layer, independent of the browser.
"""

import pytest

# Per CLAUDE.md test trap: import editor before other haywire modules.

from haywire.core.settings import SettingsRegistry
from haybale_testing.nodes.testbed.settings_node import SettingsNode

pytestmark = pytest.mark.unit


@pytest.fixture
def settings_registry():
    """A bare SettingsRegistry for constructing a SettingsNode.example bag.

    example_string / persistent_value are plain ``setting`` fields (not registry-
    backed), so they exercise the base ``setting.__set__`` value-equality
    short-circuit regardless of the registry.
    """
    return SettingsRegistry()


def test_setting_write_of_equal_value_does_not_refire(settings_registry):
    """Writing the current value back fires NO change callback (loop terminator)."""
    bag = SettingsNode.example(registry=settings_registry)
    calls = []
    bag.subscribe(lambda name, value, old: calls.append((name, value)))

    bag.example_string = "alpha"
    assert calls == [("example_string", "alpha")]

    bag.example_string = "alpha"
    assert calls == [("example_string", "alpha")], f"echo re-fired: {calls}"


def test_distinct_then_equal_write_fires_exactly_once(settings_registry):
    """A change then a redundant write yields exactly one callback per real change."""
    bag = SettingsNode.example(registry=settings_registry)
    calls = []
    bag.subscribe(lambda name, value, old: calls.append(value))

    bag.persistent_value = 5.0
    bag.persistent_value = 5.0
    bag.persistent_value = 6.0

    assert calls == [5.0, 6.0], f"expected one callback per real change, got {calls}"
