"""TestSessionState — minimal SessionState used by registry regression tests.

This class exists to verify that BaseRegistry._on_creation does not
produce duplicate class objects when test code or panels in the same
library pre-import the state module. See
``tests/core/test_libraries/test_registries.py``.
"""

from __future__ import annotations

from typing import Optional

from haywire.core.session.signals import signal_field
from haywire.core.state import SessionState, state


@state(label="Test Session State")
class TestSessionState(SessionState):
    """Trivial per-session state with a single reactive field."""

    counter: Optional[int] = signal_field(None)
