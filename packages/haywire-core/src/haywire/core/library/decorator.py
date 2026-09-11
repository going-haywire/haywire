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


def library(*, file_watcher: bool = False) -> Callable[[Type[T]], Type[T]]:
    """Register a class as a Haywire library.

    Always invoked with parentheses — ``@library(...)``; the bare ``@library``
    form is not supported. ``file_watcher`` is the only keyword it accepts.

    Descriptive metadata is not declared here: it lives in ``haybale.toml``,
    beside ``__init__.py`` inside the package, and is read from disk at
    decoration time, so a metadata edit is a plain file write — visible on the
    next read, with no ``uv sync`` and no registry reload::

        name = "haybale-mylib"
        version = "1.0.0"
        label = "My Library"
        description = "What this library does"
        tags = ["mylib"]
        on_reload = "none"
        linked_libraries = ["haybale_core"]

    ``version`` is required there and is written by ``scripts/bump_version.py``
    or the share wizard, which sync the generated copy into ``pyproject.toml``.

    Args:
        file_watcher: Watch this library's files and hot-reload on change.
            Development only; has no publishing meaning.

    Raises:
        HaybaleTomlError: ``haybale.toml`` is missing, malformed, or declares no
            ``name`` or no ``version``. Fatal for this library alone —
            ``LibraryRegistry`` wraps each load, so the studio still starts and
            the failure names the file.
        TypeError: the decorated class is not a ``BaseLibrary`` subclass, or an
            unrecognized kwarg was passed — including any descriptive field
            (``name``, ``label``, ``description``, ``tags``, ``author``,
            ``author_url``, ``url``, ``on_reload``, ``linked_libraries``,
            ``version``) that belongs in ``haybale.toml``.
    """

    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not issubclass(inner_cls, BaseLibrary):
            raise TypeError(f"@library can only be applied to BaseLibrary subclasses, got {inner_cls}")

        kwargs: dict[str, Any] = {"file_watcher": file_watcher}

        # The directory holding the class's module is also where haybale.toml lives.
        class_file = inspect.getfile(inner_cls)
        package_dir = Path(class_file).parent
        kwargs["folder_path"] = str(package_dir)
        kwargs["module_name"] = inner_cls.__module__

        # haybale.toml is canon for everything it declares, including `name` —
        # the library's sole identifier and the prefix of every component's
        # registry key.
        declared = read_haybale_toml(package_dir)
        # Filter, don't splat: read_haybale_toml() also returns file-only fields
        # (description, tags, ...) that LibraryIdentity does not accept, and
        # they would raise "unexpected keyword argument" here at import time.
        kwargs.update(
            {
                k: v
                for k, v in declared.items()
                if k in ("name", "label", "version", "on_reload", "linked_libraries")
            }
        )

        inner_cls.class_identity = LibraryIdentity(**kwargs)
        return inner_cls

    return decorator
