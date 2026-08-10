import inspect
from pathlib import Path
from typing import Any, Callable, Type, TypeVar

from .base import BaseLibrary
from .haybale_toml import read_haybale_toml
from .identity import LibraryIdentity

# ============================================================================
#    Decorator
# ============================================================================

T = TypeVar("T")


def library(*, id: str | None = None, file_watcher: bool = False) -> Callable[[Type[T]], Type[T]]:
    """
    Decorator to register a class as a Haywire library.

    Always invoked with parentheses — ``@library(...)``. The bare ``@library``
    form (no parens) is not supported.

    **Descriptive metadata is not declared here.** It lives in ``haybale.toml``,
    beside ``__init__.py`` inside the package, and is read from disk at
    decoration time. That is what makes a metadata edit a plain file write:
    visible on the next read, with no ``uv sync`` and no registry reload. A
    decorator kwarg would be a *source* edit, and a source edit needs a reload —
    the cost this design exists to remove. Nothing in the studio writes this
    call.

    Takes exactly these two keyword arguments. The signature is explicit
    rather than ``**kwargs``, so a stale call site passing a descriptive field
    that moved to ``haybale.toml`` (``label``, ``description``, ``tags``,
    ``author``, ``author_url``, ``url``, ``on_reload``, ``linked_libraries``,
    ``version``) — or any other unrecognized name — fails immediately with
    Python's own "unexpected keyword argument" ``TypeError``, rather than
    being silently accepted and overwritten by the file.

    ``haybale.toml``::

        name = "haybale-mylib"
        id = "mylib"
        version = "1.0.0"
        label = "My Library"
        description = "What this library does"
        tags = ["mylib"]
        on_reload = "none"
        linked_libraries = ["haybale_core"]

    ``version`` is required but is not hand-authored: ``pyproject.toml`` is
    canon, and ``scripts/bump_version.py`` / the share wizard keep ``haybale.toml``
    in sync with it. A library missing the key has not been through either path
    yet.

    Args:
        id (str, optional): Unique identifier; prefixes every component's
            registry key. Also declared in ``haybale.toml``, which wins — the
            kwarg exists because the registry needs an id before any file read,
            and a mismatch between the two is reported rather than guessed at.
        file_watcher (bool, optional): Watch this library's files and hot-reload
            on change. Development only; has no publishing meaning.

    Raises:
        HaybaleTomlError: ``haybale.toml`` is missing, malformed, or declares no
            ``id`` or no ``version``. Fatal for this library alone —
            ``LibraryRegistry`` wraps each load, so the studio still starts and
            the failure names the file.
        TypeError: an unrecognized kwarg was passed — including any name that
            moved to ``haybale.toml``.
    """

    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not issubclass(inner_cls, BaseLibrary):
            raise TypeError(f"@library can only be applied to BaseLibrary subclasses, got {inner_cls}")

        kwargs: dict[str, Any] = {"id": id, "file_watcher": file_watcher}

        # Auto-detect folder_path — the directory where inner_cls is defined,
        # which is also where haybale.toml lives.
        class_file = inspect.getfile(inner_cls)
        package_dir = Path(class_file).parent
        kwargs["folder_path"] = str(package_dir)
        kwargs["module_name"] = inner_cls.__module__

        # The file is canon for everything it declares, including `id`: a
        # decorator id that disagrees is the author's bug, and letting the file
        # win keeps one answer rather than two.
        declared = read_haybale_toml(package_dir)
        decorator_id = kwargs.get("id")
        if decorator_id and decorator_id != declared["id"]:
            raise TypeError(
                f"@library(id={decorator_id!r}) disagrees with "
                f"{package_dir / 'haybale.toml'} (id={declared['id']!r}). "
                f"The id prefixes every component's registry key, so the two "
                f"must match."
            )
        kwargs.update(declared)

        inner_cls.class_identity = LibraryIdentity(**kwargs)
        return inner_cls

    return decorator
