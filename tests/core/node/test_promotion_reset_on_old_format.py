# tests/core/node/test_promotion_reset_on_old_format.py
"""
Old-format (pre-ADR-0019) settings dict on load = reset-and-continue:

- the bag is left at descriptor defaults (not restored from the incompatible dict)
- the node still loads and is fully functional
- a WARNING-severity HaywireException is attached to the node so the user sees it

Uses the same "testing:node:SettingsNode" test node + graph fixtures as
test_promotion_serialization.py.
"""

# Per CLAUDE.md test trap: import editor before other haywire modules.

import pytest

from haywire.core.errors.haywire_exception import ErrorSeverity

pytestmark = pytest.mark.integration


class TestResetOnOldFormat:
    def test_old_flat_settings_dict_resets_bag_and_warns(self, graph_with_library_system, library_system):
        graph = graph_with_library_system
        node = graph.create_node_wrapper("testing:node:SettingsNode", position=(0, 0)).node
        node.example.example_float = 0.75  # a non-default value we expect to be RESET
        data = node._to_dict()
        # Corrupt the settings block into the OLD flat shape for the "example" bag.
        data["settings"]["example"] = {"example_float": 0.99}  # pre-refactor flat form

        reloaded = graph.create_node_wrapper("testing:node:SettingsNode", position=(50, 0)).node
        reloaded._initialize_from_dict(data)

        # Bag reset to default (not 0.99, not the old 0.75).
        default = type(reloaded.example).__dict__["example_float"]._default
        assert reloaded.example.example_float == default

        # A WARNING is attached and rendering-visible.
        errs = reloaded.wrapper.state.get_errors()
        assert errs is not None
        assert any(
            e.severity == ErrorSeverity.WARNING and "settings" in str(e.message).lower() for e in errs
        )

    def test_node_still_functional_after_reset(self, graph_with_library_system, library_system):
        graph = graph_with_library_system
        node = graph.create_node_wrapper("testing:node:SettingsNode", position=(0, 0)).node
        data = node._to_dict()
        data["settings"]["example"] = {"example_float": 0.99}  # old flat shape

        reloaded = graph.create_node_wrapper("testing:node:SettingsNode", position=(50, 0)).node
        reloaded._initialize_from_dict(data)
        # Writable, usable — a reset is a recovery, not a broken node.
        reloaded.example.example_float = 0.42
        assert reloaded.example.example_float == 0.42
