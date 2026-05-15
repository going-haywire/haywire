"""SignalSource — ABC for hosts that emit signal-field signals.

Concrete implementors: SessionContext, SessionState, AppState. Authors
do not subclass this directly — they subclass one of the three concrete
bases.

Enforcement: Python's ABC machinery refuses to instantiate any concrete
class that omits `_signal_emit`. The signal_field descriptor's
`issubclass(owner, SignalSource)` check at class-definition time
catches the "wrong base class" mistake earlier with a clearer error.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .signal import Signal


class SignalSource(ABC):
    """Anything that can emit signal-field signals."""

    @abstractmethod
    def _signal_emit(self, signal: Signal) -> None:
        """Emit `signal` to whatever subscribers this host fans out to.

        SessionContext / SessionState: forward to `Session.publish`.
        AppState: forward to `SessionManager.broadcast`.
        """
        raise NotImplementedError


__all__ = ["SignalSource"]
