import importlib.metadata
import inspect
import logging
from pathlib import Path
from typing import Any, Callable, Type, TypeVar

from .base import BaseLibrary
from .distmeta import distribution_fields
from .identity import LibraryIdentity

# ============================================================================
#    Decorator
# ============================================================================

T = TypeVar("T")

logger = logging.getLogger(__name__)

#: Kwargs an author used to pass that now come from pyproject.toml, plus the
#: pre-migration spelling of ``linked_libraries``. Rejected rather than ignored:
#: silently dropping one hides a real authoring mistake.
_SUPERSEDED_KWARGS = frozenset(
    {"version", "description", "author", "author_url", "url", "tags", "dependencies"}
)


def _dist_for_module(module: str) -> str | None:
    """The distribution owning *module*, or None when it is not installed.

    ``packages_distributions()`` is keyed on top-level package names, so the
    dotted module a library class is defined in (``haybale_core.library``) is
    reduced to its root before the lookup.
    """
    from .dep_detect import _resolve_module_to_dist

    top_level = module.split(".", 1)[0]
    return _resolve_module_to_dist(top_level, importlib.metadata.packages_distributions())


def library(**kwargs: Any) -> Callable[[Type[T]], Type[T]]:
    """
    Decorator to register a class as a Haywire library.

    Always invoked with parentheses — `@library(...)`. `label` and `id` are
    required.

    Args:
        label (str, required): Human-readable library name.
        id (str, required): Unique identifier; prefixes every component's
            registry key.
        linked_libraries (list[str], optional): Sibling haybale **module** names
            (e.g. ``"haybale_core"``) whose classes this library subscribes to.
            Required for hot-reload: without it a subscriber holds a stale class
            reference after a reload. Not the same as ``[project] dependencies``.
        on_reload (str, optional): ``"none"`` (default), ``"refresh"`` or
            ``"restart"`` — what the user must do after this library is
            installed, updated or uninstalled.
        os (list[str], optional): Platforms this library supports
            (``"macos"``, ``"windows"``, ``"linux"``). Empty means all. Gates
            installation from a marketplace.
        examples_path (str, optional): Path to this library's examples, relative
            to the library directory. Trailing slash means a directory.
        tests_path (str, optional): Likewise for tests.
        file_watcher (bool, optional): Watch this library's files and hot-reload
            on change. Development only. Defaults to False.

    **Not decorator arguments.** ``version``, ``description``, ``author``,
    ``author_url``, ``url`` and ``tags`` are read from the installed
    distribution's metadata, which the build backend copies from
    ``pyproject.toml``. Authoring them here as well is what let the two drift,
    so passing any of them — or ``dependencies``, the old spelling of
    ``linked_libraries`` — raises ``TypeError``. Declare them in ``[project]``
    and ``[project.urls]``::

        [project]
        version = "0.0.40"
        description = "…"
        keywords = ["haywire", "core"]
        authors = [{ name = "…" }]

        [project.urls]
        Homepage = "…"
        Documentation = "…"
        Author = "…"
        Issues = "…"

    Usage::

        @library(
            id="core",
            label="Core",
            linked_libraries=["haybale_studio"],
            on_reload="restart",
            os=["macos", "linux"],
            examples_path="examples/OVERVIEW.md",
            file_watcher=True,
        )
        class Library(BaseLibrary): ...
    """

    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not issubclass(inner_cls, BaseLibrary):
            raise TypeError(f"@library can only be applied to BaseLibrary subclasses, got {inner_cls}")

        if "label" not in kwargs:
            raise ValueError("@library decorator requires 'label' argument")
        if "id" not in kwargs:
            raise ValueError("@library decorator requires 'id' argument")

        # Rejected explicitly rather than left to LibraryIdentity's own
        # TypeError: four of the six ARE identity fields (the distribution read
        # below fills them), so passing one would be accepted and then silently
        # overwritten — exactly the drift this consolidation removed. `author`
        # and `url` are not fields at all, and `dependencies` is the old
        # spelling of `linked_libraries` that also collides with [project]
        # dependencies, which means something entirely different.
        superseded = _SUPERSEDED_KWARGS & kwargs.keys()
        if superseded:
            raise TypeError(
                f"@library({kwargs['id']!r}): {', '.join(sorted(superseded))} "
                f"{'is' if len(superseded) == 1 else 'are'} not decorator "
                "argument(s). version, description, author, author_url, url and tags are "
                "read from the installed distribution's metadata — declare them in "
                "[project] and [project.urls]. dependencies= is now linked_libraries=."
            )

        # Auto-detect folder_path - use the directory where inner_cls is defined
        class_file = inspect.getfile(inner_cls)
        kwargs["folder_path"] = str(Path(class_file).parent)
        kwargs["module_name"] = inner_cls.__module__

        # pyproject.toml is the single source for the PEP 621 half. Read from
        # the installed distribution, which is where the build backend copied
        # them — a path import with no distribution simply leaves them empty.
        dist = _dist_for_module(inner_cls.__module__)
        if dist:
            kwargs.update(distribution_fields(dist))

        inner_cls.class_identity = LibraryIdentity(**kwargs)
        return inner_cls

    return decorator
