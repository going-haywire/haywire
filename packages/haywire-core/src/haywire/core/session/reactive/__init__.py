"""Reactive primitives for Haywire UI.

Phase 1 ships:
- Reactive[T]: a value-holder primitive.
- ReactivePath: a typed reference to a reactive field (class identity).
- reactive_field(): descriptor declaring a reactive field on a class.
- iter_reactive_fields(): helper for hosting classes to initialize
  per-instance Reactive[T] containers.

Phase 2 will add Subscription, auto-tracking, and @reads verification.
"""

from haywire.core.session.reactive.descriptor import iter_reactive_fields, reactive_field
from haywire.core.session.reactive.path import ReactivePath
from haywire.core.session.reactive.reactive import Reactive

__all__ = ["Reactive", "ReactivePath", "reactive_field", "iter_reactive_fields"]
