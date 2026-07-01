# tests/core/test_settings/conftest.py
"""Shared fixtures for the settings test suite.

The one piece of cross-test state that bites here is the *class attribute*
``FrameworkSettings._registry`` (plus the module-level ``_pending_global``
queue). ``SettingsRegistry.__init__`` → ``_drain_pending_global`` assigns
``FrameworkSettings._registry = self`` on every registry it builds, so the
attribute always points at whatever registry was constructed last in the
process. A ``FrameworkSettings`` subclass defined *inside a test function*
runs ``__init_subclass__`` at definition time and, finding the attribute set
to some earlier (now-dead) registry, self-registers into THAT registry rather
than the one the test then builds — its keys are missing from the test's own
registry and ``resolve`` raises ``KeyError``.

In the real app there is a single registry for the process lifetime, so this
never bites; it is purely a test-isolation artifact. This autouse fixture
snapshots and restores the shared state around each settings test so every
test starts from the clean (unwired) slate and leaves it as it found it.
"""

import pytest


@pytest.fixture(autouse=True)
def _reset_framework_settings_registry():
    from haywire.core.settings.schema import FrameworkSettings, _pending_global

    saved_registry = FrameworkSettings._registry
    saved_pending = list(_pending_global)

    FrameworkSettings._registry = None
    _pending_global.clear()
    try:
        yield
    finally:
        FrameworkSettings._registry = saved_registry
        _pending_global.clear()
        _pending_global.extend(saved_pending)
