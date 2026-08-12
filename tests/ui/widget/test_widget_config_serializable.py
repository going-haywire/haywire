# tests/ui/widget/test_widget_config_serializable.py
"""
Plain (non-promoted) ports reject a non-serializable widget_config at
construction time:

- a callable (bound method / lambda) in widget_config on a PLAIN port raises
  TypeError at DataPort.__post_init__ (i.e. when node.add(...) runs), naming
  the port — not nine frames deep in json.dumps at save time
- the SAME callable on a PROMOTED port does NOT raise (its widget_config is
  never serialized; it round-trips through the descriptor)
- a serializable widget_config (list/dict options) constructs fine
"""

from typing import Any, cast

import pytest

from haywire.barn.builtin.types import CHOICES

pytestmark = pytest.mark.integration


def _dynamic_options():
    return ["a", "b", "c"]


class TestPlainPortRejectsCallable:
    def test_callable_widget_config_raises_on_plain_port(self, library_system):
        from haywire.core.di.context import set_settings_registry, set_type_registry
        from haywire.core.types.port import DataPort

        set_type_registry(library_system.get_type_registry())
        set_settings_registry(library_system.get_settings_registry())

        spec = CHOICES.as_config(
            "mode",
            widget_config={"options": _dynamic_options},  # a live callable
        )
        with pytest.raises(TypeError, match="mode"):
            DataPort.from_spec(
                cast(Any, spec), library_system.get_type_registry(), cast(Any, None), cast(Any, None)
            )

    def test_nested_callable_under_properties_raises(self, library_system):
        from haywire.core.types.port import DataPort

        spec = CHOICES.as_config(
            "mode",
            widget_config={"properties": {"options": _dynamic_options}},
        )
        with pytest.raises(TypeError, match="mode"):
            DataPort.from_spec(
                cast(Any, spec), library_system.get_type_registry(), cast(Any, None), cast(Any, None)
            )


class TestSerializableWidgetConfigOk:
    def test_list_options_construct_fine(self, library_system):
        from haywire.core.types.port import DataPort

        spec = CHOICES.as_config("mode", widget_config={"options": ["a", "b"]})
        port = DataPort.from_spec(
            cast(Any, spec), library_system.get_type_registry(), cast(Any, None), cast(Any, None)
        )
        assert port.widget_config["options"] == ["a", "b"]


class TestPromotedPortAllowsCallable:
    def test_callable_widget_config_ok_on_promoted_port(self, library_system):
        from haywire.core.types.port import DataPort

        spec = CHOICES.as_inlet(
            "mode",
            promoted=True,
            widget_config={"options": _dynamic_options},
        )
        # Must NOT raise: promoted ports never serialize widget_config.
        port = DataPort.from_spec(
            cast(Any, spec), library_system.get_type_registry(), cast(Any, None), cast(Any, None)
        )
        assert port.promoted is True
