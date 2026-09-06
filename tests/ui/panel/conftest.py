"""Shared fixtures for the settings-panel render tests."""

import pytest

from haywire.core.session.context import SessionContext

from tests.ui.panel.render_ctx import make_render_ctx


@pytest.fixture
def render_ctx() -> SessionContext:
    """``make_render_ctx()`` as a fixture, for tests that render inline.

    See ``render_ctx.py`` for why the factory exists separately.
    """
    return make_render_ctx()
