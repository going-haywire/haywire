# barn/haybale-studio/haybale_studio/editors/properties_editor_actions.py
"""PropertiesEditorActions — the action contract panels mounted in
PropertiesEditor are typed against.

Panels declared with ``@panel(action=PropertiesEditorActions, ...)`` receive
an instance satisfying this Protocol as the ``actions`` argument to ``draw``.
The editor itself satisfies the Protocol (structural typing) — no inheritance
required.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PropertiesEditorActions(Protocol):
    """Actions exposed by PropertiesEditor to the panels it mounts.

    Phase 1 surface is intentionally tiny. Add methods only when a panel
    needs to perform an action that touches editor-owned state.
    """

    def clear_selection(self) -> None:
        """Clear the current node/edge/port selection."""
        ...
