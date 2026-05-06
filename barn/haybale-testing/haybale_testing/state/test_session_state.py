"""TestSessionState — minimal SessionState used by registry regression tests.

This class exists to verify that BaseRegistry._on_creation does not
produce duplicate class objects when test code or panels in the same
library pre-import the state module. See
``tests/core/test_libraries/test_registries.py``.
"""

from __future__ import annotations

from copy import copy
from typing import Optional

from haywire.core.state import SessionState, state
from haywire.ui.reactive import Reactive, iter_reactive_fields, reactive_field


@state(label="Test Session State")
class TestSessionState(SessionState):
    """Trivial per-session state with a single reactive field."""

    counter: Reactive[Optional[int]] = reactive_field(None)

    def __init__(self) -> None:
        for name, initial in iter_reactive_fields(type(self)):
            self.__dict__[name] = Reactive(copy(initial))
