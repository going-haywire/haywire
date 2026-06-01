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

    Scope (app-global vs per-session) is auto-detected from the base
    class. ``class X(AppState)`` is app-scoped; ``class X(SessionState)``
    is per-session.

    Args:
        label:        Human-readable display name. Defaults to registry_id.
        description:  Human-readable description. Defaults to ''.
        registry_id:  Unique state identifier. Defaults to the class name.
                      Used as the final segment of the registry_key.

    Usage::

        @state(label='Edit State')
        class EditState(SessionState):
            active_node = signal_field(None)
            ...

        @state()
        class MidiPool(AppState):
            devices = signal_field([])
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
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator
