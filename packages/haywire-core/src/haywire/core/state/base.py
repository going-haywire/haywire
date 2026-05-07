"""LibraryState taxonomy — abstract marker + concrete scope bases.

A library author **never directly subclasses `LibraryState`**. They pick
one of the concrete scope bases:

  - `AppState`     — one instance, shared across all sessions and execution.
  - `SessionState` — one instance per UI session.

The mental rule is one line: *scope = base class*. Inheritance picks
multiplicity. See internals/documentation/architecture/session_state.md.
"""

from __future__ import annotations

from haywire.core.state.identity import LibraryStateClassIdentity


class LibraryState:
    """Abstract marker base. Never directly subclassed by users.

    Exists as a type-system hierarchy root and as the registry-filter
    target for `issubclass(cls, LibraryState)`. Concrete bases are
    `AppState` (app-global) and `SessionState` (per-session).
    """

    class_identity: LibraryStateClassIdentity


class AppState(LibraryState):
    """Concrete base for app-global library state.

    One instance is created when the owning library is enabled and
    shared across every browser session and the execution VM. The
    framework calls optional `on_enable()` after instantiation and
    optional `on_disable()` before teardown.

    See internals/documentation/architecture/library_state.md.
    """


class SessionState(LibraryState):
    """Concrete base for per-UI-session library state.

    One instance is created per active session × per registered SessionState
    class. The container stamps ``self.session_id`` between ``cls()`` and
    ``on_enable()`` — read it in ``on_enable`` or any later method, never
    in ``__init__``.

    A SessionState **must not** compose ``LibrarySettings`` as a field —
    settings are app-global, sessions are per-session. The
    ``__init_subclass__`` check below catches this at class-definition time.

    See internals/documentation/architecture/session_state.md.
    """

    session_id: str  # set by the container before on_enable runs

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        _reject_library_settings_fields(cls)


def _reject_library_settings_fields(cls: type) -> None:
    """Walk class type annotations and raise TypeError for any LibrarySettings field.

    Catches `field: MyLibSettings`, `field: MyLibSettings | None`,
    `field: Optional[MyLibSettings]`, and Union variants.
    """
    from typing import get_type_hints

    from haywire.core.settings.schema import LibrarySettings

    try:
        hints = get_type_hints(cls, include_extras=False)
    except Exception:
        # Forward references that don't resolve at class-creation time are
        # skipped — best-effort check, not a guaranteed catch-all.
        return

    for name, ann in hints.items():
        if name == "session_id":
            continue
        for resolved in _flatten_annotation(ann):
            if isinstance(resolved, type) and issubclass(resolved, LibrarySettings):
                raise TypeError(
                    f"SessionState '{cls.__name__}' has field "
                    f"'{name}: {resolved.__name__}' — LibrarySettings cannot be "
                    f"composed inside SessionState (settings are app-global; "
                    f"sessions are per-session). Read settings values inside "
                    f"methods/hooks instead, never hold a LibrarySettings instance."
                )


def _flatten_annotation(ann: object) -> list[object]:
    """Return all concrete types referenced by an annotation.

    Handles ``X``, ``Optional[X]`` (= ``X | None``), and ``Union[A, B, ...]``.
    """
    import types
    import typing

    origin = typing.get_origin(ann)
    if origin is None:
        return [ann]
    if origin is typing.Union or origin is types.UnionType:
        out: list[object] = []
        for arg in typing.get_args(ann):
            out.extend(_flatten_annotation(arg))
        return out
    return [ann]
