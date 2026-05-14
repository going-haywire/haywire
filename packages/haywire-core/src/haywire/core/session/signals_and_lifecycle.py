# packages/haywire-core/src/haywire/core/session/signals_and_lifecycle.py
"""
Transitional re-export shim.

The signal/event vocabulary moved to :mod:`haywire.core.session.signals`
and the lifecycle-command vocabulary moved to
:mod:`haywire.core.session.lifecycles` as part of the event-bus redesign
(see ``internals/speculative/event_bus_redesign.md``, PR #1).

This module continues to re-export everything from those two files so
existing call sites (e.g. ``from haywire.core.session.signals_and_lifecycle
import ContextSignal``) keep working unchanged during the migration. The
shim is scheduled for removal in PR #4 (deprecation closeout) once all
call sites have been moved to the new module paths.
"""

from __future__ import annotations

from .signals import (
    Subject,
    ContextSignal,
    ActiveGraphMoved,
    ActiveFileMoved,
    ActiveLibraryMoved,
    ActiveComponentMoved,
    SelectionMoved,
    GraphDataMutated,
    LibraryCatalogChanged,
    ThemeMoved,
)
from .lifecycles import (
    LifecycleCommand,
    Reveal,
    Close,
    BroadcastClose,
)

__all__ = [
    # Signals
    "Subject",
    "ContextSignal",
    "ActiveGraphMoved",
    "ActiveFileMoved",
    "ActiveLibraryMoved",
    "ActiveComponentMoved",
    "SelectionMoved",
    "GraphDataMutated",
    "LibraryCatalogChanged",
    "ThemeMoved",
    # Lifecycles
    "LifecycleCommand",
    "Reveal",
    "Close",
    "BroadcastClose",
]
