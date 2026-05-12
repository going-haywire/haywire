"""Cross-session signals emitted by HaystackState lifecycle hooks.

These signals announce facts about the haystack registry's identity
swapping — they don't carry UI commands. HaystackEditor translates them
into local lifecycle actions (closing tabs, redrawing the list).

Carried entry_ids on HaystackTeardown are necessary: by the time
receivers process the signal, the old HaystackState has already been
torn down by ``LibraryStateContainer._reload``, so receivers can't
re-derive the vanishing ids from current state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from haywire.core.session.signals_and_lifecycle import ContextSignal


@dataclass(frozen=True)
class HaystackTeardown(ContextSignal):
    """Emitted from ``HaystackState.on_disable`` before entries are cleared.

    HaystackEditor reacts by issuing a local ``Close(binding_id=eid)`` for
    every id in ``entry_ids`` — closing every GraphEditor tab bound to
    a vanishing entry. Cross-session: every session's HaystackEditor
    receives the signal and runs its local closes, so peer sessions
    drop stale tabs without needing a cross-session lifecycle command.
    """

    cross_session: ClassVar[bool] = True
    entry_ids: tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class HaystackReloaded(ContextSignal):
    """Emitted from ``HaystackState.on_enable`` after rehydration.

    HaystackEditor reacts by re-rendering its list against the new
    ``HaystackState`` (typically populated from rehydrated settings).
    Cross-session so peer sessions also refresh.
    """

    cross_session: ClassVar[bool] = True
