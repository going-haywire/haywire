"""LibraryState base class.

A LibraryState is a Python class that a library declares to hold its own
app-global runtime data. The framework instantiates it once when the library
is enabled, owns its lifecycle, and exposes the instance through a uniform
class-keyed access pattern on both SessionContext (UI) and ExecutionContext
(node execution).

See docs/documentation/architecture/library_state.md for the full design.
"""

from __future__ import annotations

from haywire.core.state.identity import LibraryStateClassIdentity


class LibraryState:
    """Base class for library-owned runtime state.

    Subclasses may define optional lifecycle hooks:
        on_enable(self) -> None   — called once after instantiation
        on_disable(self) -> None  — called once before destruction

    Both hooks are duck-typed: absence is fine, the framework checks via
    hasattr/callable before invoking.

    Subclasses are otherwise unconstrained — fields, methods, internal state
    are entirely the author's choice.
    """

    class_identity: LibraryStateClassIdentity
