"""FileBrowserState — per-session state for the FileBrowser editor.

Holds transient context for the right-click context menu. Contracts:

  - ``right_clicked_file`` is set by SessionFileMenuProvider when the
    user right-clicks a file in the tree.
  - Cleared back to None when the menu closes (any dismissal path).
  - Panels with focus=FileFocus may read this in their poll() to
    decide whether they appear in the menu (e.g. extension-based
    filtering).

Mirrors the EditState.active_port / active_edge pattern: pure menu
state, NOT a persistent selection. ``active_file`` (which IS
persistent) lives on SessionContext, not here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from haywire.core.session.signals import signal_field
from haywire.core.state import SessionState, state


@state(label="File Browser State")
class FileBrowserState(SessionState):
    """Per-session state for the FileBrowser editor."""

    right_clicked_file: Optional[Path] = signal_field(None)
