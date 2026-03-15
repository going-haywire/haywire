# haywire/ui/themes/theme_registry.py
"""
ThemeRegistry — hot-reload-capable registry for WorkbenchTheme and NodeTheme classes.
Extends BaseRegistry for library folder scan and hot-reload support.
"""

from __future__ import annotations
from typing import Type, TYPE_CHECKING

from haywire.core.registry.base import BaseRegistry
from haywire.core.library.identity import LibraryIdentity

from .workbench import WorkbenchTheme
from .node_theme import NodeTheme

if TYPE_CHECKING:
    pass


# Framework identity used for built-in theme registration
_FRAMEWORK_THEME_IDENTITY = LibraryIdentity(
    label='haywire-core',
    version='0.0.0',
    description='Haywire built-in themes',
    url='',
    help_url='',
    author='Haywire',
    author_url='',
    id='haywire-core',
    module_name='haywire',
    folder_path='',
)


class ThemeRegistry(BaseRegistry):
    """
    Registry for WorkbenchTheme and NodeTheme classes.

    Extends BaseRegistry for hot-reload (library plugins can supply themes)
    and folder scan support.

    Built-in themes are registered via register_workbench() / register_node_theme().
    Library themes are discovered automatically when a library calls
    theme_registry.add_folder(path, identity).
    """

    # =========================================================================
    # BaseRegistry abstract methods
    # =========================================================================

    def _class_filter(self, cls: Type) -> bool:
        """Accept WorkbenchTheme and NodeTheme subclasses with class_identity."""
        return (
            isinstance(cls, type)
            and issubclass(cls, (WorkbenchTheme, NodeTheme))
            and cls not in (WorkbenchTheme, NodeTheme)
            and hasattr(cls, 'class_identity')
        )

    def _register_class(self, cls: Type, library_identity: LibraryIdentity) -> str | None:
        registry_key = cls.class_identity.registry_key
        return super()._register(registry_key, cls, library_identity or _FRAMEWORK_THEME_IDENTITY)

    def _unregister_class(self, registry_key: str) -> type | None:
        return super()._unregister(registry_key)

    # =========================================================================
    # Typed registration helpers
    # =========================================================================

    def register_workbench(self, cls: Type[WorkbenchTheme], library_identity: LibraryIdentity | None = None) -> str | None:
        """Register a WorkbenchTheme class."""
        return self._register_class(cls, library_identity or _FRAMEWORK_THEME_IDENTITY)

    def register_node_theme(self, cls: Type[NodeTheme], library_identity: LibraryIdentity | None = None) -> str | None:
        """Register a NodeTheme class."""
        return self._register_class(cls, library_identity or _FRAMEWORK_THEME_IDENTITY)

    # =========================================================================
    # Typed accessors
    # =========================================================================

    def get_workbench(self, registry_key: str) -> WorkbenchTheme:
        """Instantiate and return a WorkbenchTheme by registry_key."""
        cls = self._classes.get(registry_key)
        if cls is not None and issubclass(cls, WorkbenchTheme):
            return cls()
        raise KeyError(f"Unknown workbench theme: '{registry_key}'")

    def get_node_theme(self, registry_key: str) -> NodeTheme:
        """Instantiate and return a NodeTheme by registry_key."""
        cls = self._classes.get(registry_key)
        if cls is not None and issubclass(cls, NodeTheme):
            return cls()
        raise KeyError(f"Unknown node theme: '{registry_key}'")

    def list_workbench_keys(self) -> list[str]:
        """Return sorted list of registered workbench theme registry_keys."""
        return sorted(
            cls.class_identity.registry_key
            for cls in self._classes.values()
            if issubclass(cls, WorkbenchTheme)
        )

    def list_workbench_themes(self) -> list[tuple[str, str]]:
        """Return sorted list of (registry_key, label) pairs for all workbench themes."""
        return sorted(
            (cls.class_identity.registry_key, cls.class_identity.label)
            for cls in self._classes.values()
            if issubclass(cls, WorkbenchTheme)
        )

    def list_node_theme_keys(self) -> list[str]:
        """Return sorted list of registered node theme registry_keys."""
        return sorted(
            cls.class_identity.registry_key
            for cls in self._classes.values()
            if issubclass(cls, NodeTheme)
        )
