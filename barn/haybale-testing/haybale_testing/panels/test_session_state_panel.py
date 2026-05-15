"""Test fixture: TestSessionStatePanel.

Eagerly imports ``TestSessionState`` at module load time. The panel
exists to verify that ``BaseRegistry._on_creation`` preserves class
identity even when state/ is registered after panels/ — the placement
that previously produced two distinct class objects (one captured by
this panel's import, one re-imported by the state/ folder scan).

See tests/core/test_libraries/test_registries.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_testing.state import TestSessionState
from haybale_testing.test_actions import TestCanvasContextActions
from haybale_testing.test_focuses import TestCanvasFocus
from haywire.ui.panel import BasePanel
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.layout import PanelLayout

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


# --8<-- [start:test_session_state_panel]
@panel(
    action=TestCanvasContextActions,
    focus=TestCanvasFocus,
    label="Test SessionState Panel",
    order=99,
)
class TestSessionStatePanel(BasePanel):
    """Reads TestSessionState.counter — exists to anchor the eager import."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[TestSessionState].counter is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: TestCanvasContextActions,
    ) -> None:
        counter = ctx.data[TestSessionState].counter
        layout.label(f"counter: {counter}")


# --8<-- [end:test_session_state_panel]
