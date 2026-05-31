import inspect
from pathlib import Path
from typing import Any, Callable, Type, TypeVar

from .base import BaseLibrary
from .identity import LibraryIdentity

# ============================================================================
#    Decorator
# ============================================================================

T = TypeVar("T")


def library(**kwargs: Any) -> Callable[[Type[T]], Type[T]]:
    """
    Decorator to register a class as a Haywire library.

    Always invoked with parentheses — `@library(...)`. The bare `@library`
    form (no parens) is not supported; `label=` is required.

    Accepts any LibraryIdentity field as a keyword argument. Common arguments include:

    Args:
        label (str, required): Human-readable library name.
        version (str, optional): Semantic version string. Defaults to '1.0.0'.
            Ideally use _pkg_version("haybale-packagename")
            from importlib.metadata import version as _pkg_version
        description (str, optional): Human-readable description of the library.
            Defaults to empty string.
        url (str, optional): Library's main URL. Defaults to empty string.
        help_url (str, optional): URL to documentation. Defaults to empty string.
        author (str, optional): Author name. Defaults to empty string.
        author_url (str, optional): Author's URL. Defaults to empty string.
        id (str, optional): Unique identifier for the library.
            Defaults to label if not provided.
        dependencies (list[str], optional): List of required haywire libraries.
            Defaults to empty list.
        file_watcher (bool, optional): Whether to enable file watching for this library.
            Defaults to False.
        needs_refresh (bool, optional): Declares that installing this library registers
            new Vue components or JS resources that an already-open browser tab cannot
            pick up; install completion prompts the user to reload the page. Defaults
            to False. See docs/reference/glossary.md → "Post-install requirements".
        needs_restart (bool, optional): Declares that installing or uninstalling this
            library leaves the Python process in a state requiring a Studio restart
            (typically C-extension modules, haywire-core upgrades, or import-time
            global mutation). Symmetric — applied on uninstall too. Defaults to False.

    Any other keyword arguments will be passed through to the LibraryIdentity constructor.
    See the LibraryIdentity dataclass for the complete list of available fields.

    Usage:
        Minimal usage - only label is required::

            @library(label="my.library")
            class Library(BaseLibrary): 

        Common customization::

            @library(
                label="my.library", 
                version=_pkg_version("haybale-my.library"), 
                description="My custom library")
            class Library(BaseLibrary): 
                ...
        
        Full customization::

            @library(
                label="advanced.library",
                version=_pkg_version("haybale-advanced.library"),
                description="Advanced library with many features",
                url="https://github.com/user/advanced-library",
                help_url="https://advanced-library.readthedocs.io",
                author="John Doe",
                author_url="https://johndoe.com",
                id="advanced_lib",
                dependencies=["haywire.core", "numpy"],
                file_watcher=True
            )
            class Library(BaseLibrary): ...

        With file watching::
                    
            @library(
                label="dev.library", 
                version=_pkg_version("haybale-dev.library"))
                file_watcher=True, 
            class Library(BaseLibrary): ...
    """

    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not issubclass(inner_cls, BaseLibrary):
            raise TypeError(f"@library can only be applied to BaseLibrary subclasses, got {inner_cls}")

        # Require label field
        if "label" not in kwargs:
            raise ValueError("@library decorator requires 'label' argument")

        # Set defaults if not provided
        kwargs.setdefault("version", "1.0.0")
        kwargs.setdefault("id", kwargs["label"])

        # Auto-detect folder_path - use the directory where inner_cls is defined
        class_file = inspect.getfile(inner_cls)
        kwargs["folder_path"] = str(Path(class_file).parent)
        kwargs["module_name"] = inner_cls.__module__

        inner_cls.class_identity = LibraryIdentity(**kwargs)
        return inner_cls

    return decorator
