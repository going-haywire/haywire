# tests/core/test_debug/test_logging_configurator.py
"""Tests for LoggingConfigurator — applies DebugSettings log levels to Python logging."""

import logging
import pytest

from haywire.core.settings import setting
from haywire.core.settings.registry import SettingsRegistry
from haywire.core.settings.schema import FrameworkSettings
from haywire.core.debug.debug_settings import DebugSettings
from haywire.core.debug.configurator import LoggingConfigurator, _GROUP_MAP, _ROOT_NAMESPACE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_registry() -> SettingsRegistry:
    """Create a fresh SettingsRegistry with DebugSettings registered."""
    registry = SettingsRegistry()
    registry.register_schema(DebugSettings)
    DebugSettings._registry = registry
    return registry


def _make_configurator(registry: SettingsRegistry) -> tuple[LoggingConfigurator, DebugSettings]:
    settings = DebugSettings()
    configurator = LoggingConfigurator(settings)
    return configurator, settings


# ---------------------------------------------------------------------------
# Construction: initial levels applied
# ---------------------------------------------------------------------------


class TestInitialApplication:
    def test_root_logger_set_to_log_level_default(self):
        registry = _make_registry()
        _make_configurator(registry)
        assert logging.getLogger(_ROOT_NAMESPACE).level == logging.INFO

    def test_root_logger_set_to_custom_log_level(self):
        registry = _make_registry()
        registry.set_global("debug.log_level", "DEBUG")
        _make_configurator(registry)
        assert logging.getLogger(_ROOT_NAMESPACE).level == logging.DEBUG

    def test_group_loggers_notset_when_empty(self):
        registry = _make_registry()
        _make_configurator(registry)
        for namespace in _GROUP_MAP.values():
            assert logging.getLogger(namespace).level == logging.NOTSET

    def test_group_logger_set_when_configured(self):
        registry = _make_registry()
        registry.set_global("debug.log_execution", "DEBUG")
        _make_configurator(registry)
        assert logging.getLogger("haywire.core.execution").level == logging.DEBUG

    def test_all_groups_can_be_set_independently(self):
        registry = _make_registry()
        registry.set_global("debug.log_execution", "DEBUG")
        registry.set_global("debug.log_assembly", "WARNING")
        registry.set_global("debug.log_ui", "ERROR")
        _make_configurator(registry)
        assert logging.getLogger("haywire.core.execution").level == logging.DEBUG
        assert logging.getLogger("haywire.core.assembly").level == logging.WARNING
        assert logging.getLogger("haywire.ui").level == logging.ERROR
        # unset groups remain NOTSET
        assert logging.getLogger("haywire.core.graph").level == logging.NOTSET


# ---------------------------------------------------------------------------
# Reactive: settings changes applied after construction
# ---------------------------------------------------------------------------


class TestReactiveUpdates:
    def test_log_level_change_updates_root_logger(self):
        registry = _make_registry()
        _, debug = _make_configurator(registry)
        debug.log_level = "WARNING"
        assert logging.getLogger(_ROOT_NAMESPACE).level == logging.WARNING

    def test_group_change_sets_level(self):
        registry = _make_registry()
        _, debug = _make_configurator(registry)
        debug.log_execution = "DEBUG"
        assert logging.getLogger("haywire.core.execution").level == logging.DEBUG

    def test_group_change_to_empty_resets_to_notset(self):
        registry = _make_registry()
        _, debug = _make_configurator(registry)
        debug.log_graph = "DEBUG"
        assert logging.getLogger("haywire.core.graph").level == logging.DEBUG
        debug.log_graph = ""
        assert logging.getLogger("haywire.core.graph").level == logging.NOTSET

    def test_unrelated_setting_change_does_not_affect_loggers(self):
        registry = _make_registry()
        _, debug = _make_configurator(registry)
        before = logging.getLogger(_ROOT_NAMESPACE).level
        debug.log_to_file = True
        assert logging.getLogger(_ROOT_NAMESPACE).level == before


# ---------------------------------------------------------------------------
# Teardown: restore logger levels so tests don't bleed into each other
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def restore_logger_levels():
    """Reset haywire logger levels before and after each test."""
    loggers = [_ROOT_NAMESPACE] + list(_GROUP_MAP.values())
    saved = {name: logging.getLogger(name).level for name in loggers}
    yield
    for name, level in saved.items():
        logging.getLogger(name).level = level
    # Also clear DebugSettings class-level registry so tests are isolated
    DebugSettings._registry = None
