"""
EditorIdentity dataclass for the Haywire editor type system.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from haywire.core.registry.identity import BaseIdentity


class OpenBehavior(Enum):
    """How an editor's tabs come into being and how many can exist.

    - REQUIRED: shell guarantees exactly one tab, auto-populated at startup.
      Uncloseable. Content typically reads from session context.
    - ON_CONTEXT: singleton tab, on-demand. Content mirrors a slice of
      session context (e.g. active_library). No payload. Closeable.
    - ON_PAYLOAD: per-payload tab, on-demand. Payload is both the tab's
      identity and its content source. N tabs allowed. Closeable.
    """

    REQUIRED = "required"
    ON_CONTEXT = "on_context"
    ON_PAYLOAD = "on_payload"


@dataclass
class EditorIdentity(BaseIdentity):
    """
    Metadata attached to an editor class by the @editor decorator.

    Set once at class-definition time; survives hot-reload.

    Inherits from BaseIdentity:
        registry_id: Short unique ID, e.g. 'graph_editor'.
        registry_key: Fully-qualified registry key; set by decorator via reg_key().
        label: Human-readable display name, e.g. 'Graph Editor'.
        description: Human-readable description.
        class_name: Python class name — set by decorator.
        module: Python module name — set by decorator.

    Additional attributes:
        icon: Material Design icon name, e.g. 'account_tree'.
        default_slot: Which workspace slot this editor belongs in by default.
            One of: 'left', 'right', 'main', 'bottom'.
        opens: Instance-creation behavior. See OpenBehavior.
        context_field: Optional name of a :class:`SessionContext` attribute
            that should mirror the active main binding's payload. The shell's
            ``_follow_main_tab_context`` hook writes ``Path(payload)`` (or
            ``None``) into ``context.<context_field>`` when this editor's
            tab becomes active. Use ``"active_file"`` for a file-viewer,
            ``"active_graph_path"`` for a graph editor (preserves haystack
            lookup and ``ACTIVE_GRAPH_CHANGED`` emission), or ``None`` for
            editors that manage their own context.
    """

    icon: str = "extension"
    default_slot: str = "main"
    opens: OpenBehavior = field(default=OpenBehavior.REQUIRED)
    context_field: Optional[str] = None
