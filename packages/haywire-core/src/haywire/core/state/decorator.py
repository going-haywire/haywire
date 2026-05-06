"""Decorator for registering AppState and SessionState classes.

@state(...) — marks an AppState or SessionState subclass for auto-discovery
by LibraryStateRegistry when a library calls add_folder_to_registry().

Consistent with @node, @editor, @panel, @theme, @settings:
  - Derives library identity via derive_library_identity()
  - Attaches class_library so hot-reload works
  - Auto-detects scope from the base class (AppState vs SessionState)
  - Validates the base class with issubclass()

Per session_state.md §1: scope is decided by the base class
(AppState vs SessionState), not by a decorator parameter. The
decorator only attaches identity metadata.

Decoration is optional — undecorated AppState/SessionState subclasses
still work; LibraryStateRegistry auto-creates a class_identity at
registration time as a fallback.
"""

from __future__ import annotations

from typing import Callable, Type, TypeVar

from haywire.core.library.utils import derive_library_identity, reg_key
from haywire.core.state.base import AppState, LibraryState, SessionState
from haywire.core.state.identity import LibraryStateClassIdentity

T = TypeVar("T", bound=LibraryState)


def state(
    *,
    label: str = "",
    description: str = "",
    registry_id: str | None = None,
) -> Callable[[Type[T]], Type[T]]:
    """Decorator that registers an AppState or SessionState subclass.

    Always invoked with parentheses — ``@state(...)`` or ``@state()``.
    The bare ``@state`` form (no parens) is not supported.

    Scope (app-global vs per-session) is auto-detected from the base
    class. ``class X(AppState)`` is app-scoped; ``class X(SessionState)``
    is per-session.

    Args:
        label:        Human-readable display name. Defaults to registry_id.
        description:  Human-readable description. Defaults to ''.
        registry_id:  Unique state identifier. Defaults to the class name.
                      Used as the final segment of the registry_key.

    Usage:
        @state(label='Edit State')
        class EditState(SessionState):
            active_node = reactive_field(None)
            ...

        @state()
        class MidiPool(AppState):
            devices = reactive_field([])
            ...
    """

    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not (issubclass(inner_cls, AppState) or issubclass(inner_cls, SessionState)):
            raise TypeError(
                f"@state can only be applied to AppState or SessionState subclasses, got {inner_cls}"
            )

        _registry_id = registry_id or inner_cls.__name__
        _label = label or _registry_id

        library_identity = derive_library_identity(inner_cls)
        _registry_key = reg_key(library_identity.id, "state", _registry_id)

        inner_cls.class_identity = LibraryStateClassIdentity(
            registry_id=_registry_id,
            registry_key=_registry_key,
            label=_label,
            description=description,
            class_name=inner_cls.__name__,
            module=inner_cls.__module__,
        )
        inner_cls.class_library = library_identity  # type: ignore[attr-defined]
        return inner_cls

    return decorator
