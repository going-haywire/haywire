"""A throwaway ``SessionContext`` for the settings-panel render tests.

``render_settings`` / ``render_schema`` / ``render_keys`` take a
``SessionContext`` as their first argument: a row's context menu offers
session-scoped actions (opening a component's source in this session's editor
slot) that neither a bag nor the registry can supply. None of the render
invariants these tests cover — subscription bookkeeping, ordering, chrome,
promotion state — read the context at all, so they share this one minimal
context over a mocked app.

A plain factory rather than only a fixture: most of these files render through a
module-level ``_render(bag)`` helper that pytest cannot inject into, and
threading a fixture down to it would mean adding an unused parameter to every
test in the file. ``conftest.render_ctx`` wraps this for tests that render
inline.
"""

from typing import Any, cast
from unittest.mock import MagicMock

from haywire.core.session.context import SessionContext
from haywire.core.state import LibraryStateContainer, LibraryStateRegistry


def make_render_ctx() -> SessionContext:
    """A minimal SessionContext accepted by the render_* entry points."""
    app = MagicMock()
    app.library_state_container = LibraryStateContainer(LibraryStateRegistry())
    ctx = SessionContext(session_id="render-test", app=cast(Any, app))
    # signal_field writes deref self.session; see tests/conftest.attach_stub_session.
    ctx.session = MagicMock()
    return ctx
