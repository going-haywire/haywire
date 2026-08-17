"""
EditorIdentity dataclass for the Haywire editor type system.
"""

from dataclasses import dataclass, field
from enum import Enum, StrEnum

from haywire.core.access import AccessTier
from haywire.core.registry.identity import BaseIdentity


class SlotName(StrEnum):
    """The four named positions in the AppShell where an editor is mounted.

    Each member's *value* is the canonical wire string used in persistence
    (``workspace_state.json``), the ``@editor(default_slot=...)`` decorator,
    and the ``hw-slot-<value>`` DOM ids. Because this is a ``StrEnum`` a
    member *is* a ``str``: ``SlotName.EDIT == "edit"`` and it serializes /
    hashes as ``"edit"`` with no conversion layer.

    Use :attr:`label` for human-facing text (tooltips, settings UI).

    - ACTION:  left edge, icon slot — primary navigation / launchers.
    - CONTEXT: right edge, icon slot — context for the current selection.
    - EDIT:    centre, tab slot — the primary editing surface.
    - INFO:    bottom, tab slot — supplementary / status output.
    """

    ACTION = "action"
    CONTEXT = "context"
    EDIT = "edit"
    INFO = "info"

    @property
    def label(self) -> str:
        """Human-readable display name for this slot (e.g. ``"Edit"``)."""
        return self.value.capitalize()


class OpenBehavior(Enum):
    """How an editor's tabs come into being and how many can exist.

    - REQUIRED: shell guarantees exactly one tab, auto-populated at startup.
      Uncloseable. Content typically reads from session context.
    - ON_CONTEXT: singleton tab, on-demand. Content mirrors a slice of
      session context (e.g. active_library). No binding_id. Closeable.
    - ON_PAYLOAD: per-binding_id tab, on-demand. Payload is both the tab's
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
            A :class:`SlotName` — one of ACTION, CONTEXT, EDIT, INFO.
        opens: Instance-creation behavior. See OpenBehavior.
        order: Sort priority within a slot (lower = earlier in the bar).
            Editors without an explicit order default to 100; ties fall back
            to registration order.
        access: Minimum AccessTier needed to see this editor — an
            :class:`AccessTier` or its string value ('view', 'edit', 'admin').
            Defaults to 'view'. An unknown value raises ``ValueError`` at
            class-definition time.
    """

    icon: str = "extension"
    default_slot: SlotName = SlotName.EDIT
    opens: OpenBehavior = field(default=OpenBehavior.REQUIRED)
    order: int = 100
    access: AccessTier = AccessTier.VIEW
