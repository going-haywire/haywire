"""ModelsViewState — per-session view state of the Models editor."""

from __future__ import annotations

from haywire.core.signals import signal_field
from haywire.core.state import SessionState, state


@state(label="Models View", description="Per-session view state of the Models editor.")
class ModelsViewState(SessionState):
    """What this session's Models editor shows."""

    graph_filter: str | None = signal_field(None)
    """Binding id of the graph whose needs the editor is filtered to; ``None`` shows everything."""
