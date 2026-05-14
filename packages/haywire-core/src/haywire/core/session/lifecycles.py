# packages/haywire-core/src/haywire/core/session/lifecycles.py
"""
Lifecycle commands — imperative half of the session dispatch story.

``LifecycleCommand`` subclasses describe imperative mutations of the workspace
tree (which editor instances exist, in which slot, which is in front).
``Reveal`` brings an editor to the front; ``Close`` removes tabs bound to a
binding_id in the issuing session; ``BroadcastClose`` does the same across
every session. Sent via ``Session.lifecycle(...)``. Local-by-default;
subclasses opt into cross-session fan-out by setting
``cross_session: ClassVar[bool] = True`` (mirroring ``ContextSignal``).

Lifecycle commands are imperative requests to mutate the workspace tree
(which editor instances exist, in which slot, which is in front). They are
not observations — they don't fan out to "anyone who cares"; they are routed
by AppShell to the slot(s) that can carry them out.

Lifecycle commands are local-by-default: session-scoped UI actions (e.g.
``Reveal`` a panel because the user clicked) belong to the issuing session.
Subclasses can opt into cross-session fan-out by setting
``cross_session: ClassVar[bool] = True`` — used for fact-driven imperatives
where the underlying entity is gone and every session's tabs bound to it must
close (e.g. ``BroadcastClose``).

The sibling :mod:`haywire.core.session.signals` module hosts the
observation half (``ContextSignal`` and its subclasses).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.ui.editor.base import BaseEditor


@dataclass(frozen=True, kw_only=True)
class LifecycleCommand:
    """Base class for editor-lifecycle commands sent via ``Session.lifecycle(...)``.

    Subclasses describe a specific mutation of the workspace tree.
    Routing is per-subclass: ``Reveal`` is point-to-point (one slot),
    ``Close`` is fan-out across slots.

    Cross-session routing is a class-level property mirroring
    ``ContextSignal``: set ``cross_session: ClassVar[bool] = True`` on a
    subclass to have ``Session.lifecycle(...)`` dispatch the command to
    every session via ``SessionManager.broadcast_lifecycle``. The default
    is local-only.
    """

    cross_session: ClassVar[bool] = False


@dataclass(frozen=True, kw_only=True)
class Reveal(LifecycleCommand):
    """Bring an editor to the front in its default slot.

    Routed point-to-point: the orchestrator resolves
    ``editor.class_identity.default_slot`` and dispatches to that slot.
    If the slot is not hostable in the active workspace, the reveal is
    dropped with a warning.

    Attributes:
        editor: The editor class to reveal.
        binding_id: Optional disambiguator for multi-instance editors
            (e.g. a graph entry id). The orchestrator switches to the
            specific ``(editor_key, binding_id)`` tab rather than the first
            binding matching ``editor_key``.
        label: Optional display label for the revealed tab. Used only
            when the reveal creates a new tab; falls back to
            ``editor.class_identity.label`` if omitted.
    """

    editor: "type[BaseEditor]"
    binding_id: Optional[str] = None
    label: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class Close(LifecycleCommand):
    """Close every tab bound to ``binding_id`` across all slots.

    Routed as fan-out: the orchestrator asks every slot to close any
    tab whose binding matches ``binding_id``. Used for session-local
    close decisions (e.g. dismissing a tab from a confirmation dialog
    in *this* session). For close decisions that follow from a global
    fact — the underlying entity is gone for everyone — use
    :class:`BroadcastClose` instead, which fans out to every session.

    Attributes:
        binding_id: The binding binding_id (e.g. a graph entry id). Slots
            close every wrapper whose binding_id matches this value.
    """

    binding_id: str


@dataclass(frozen=True, kw_only=True)
class BroadcastClose(Close):
    """Cross-session ``Close``: fan tab-close out to every session.

    Used for fact-driven imperatives where the underlying entity has
    gone away (e.g. an entry was removed from a haystack, or the
    haystack itself was torn down by a library hot-reload). Each
    receiving session asks its own AppShell to close every wrapper whose
    binding_id matches; sessions with no matching tab are unaffected.

    Prefer ``Close`` for session-local UI actions (e.g. a confirmation
    dialog the user dismissed in this tab). ``BroadcastClose`` is the
    right choice only when the close decision follows from a global
    fact rather than a session-local interaction.
    """

    cross_session: ClassVar[bool] = True
