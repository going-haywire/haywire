# haywire/ui/themes/theme_registry.py
"""
ThemeRegistry — hot-reload-capable registry for BaseTheme classes.
Extends BaseRegistry for library folder scan and hot-reload support.
"""

from __future__ import annotations
from typing import Optional, Type

from haywire.core.registry.base import BaseRegistry
from haywire.core.library.identity import LibraryIdentity

from .workbench import BaseTheme


# Framework identity used for built-in theme registration
_FRAMEWORK_THEME_IDENTITY = LibraryIdentity(
    label="haywire-core",
    version="0.0.0",
    name="haywire-core",
    module_name="haywire",
    folder_path="",
)


class ThemeRegistry(BaseRegistry[BaseTheme]):
    """
    Registry for BaseTheme classes — both workbench and node flavours.

    Extends BaseRegistry for hot-reload (library plugins can supply themes)
    and folder scan support. "Workbench" vs "node" is a property of a
    class's ``class_identity.theme_type``, set by the required
    ``theme_type=`` kwarg on ``@theme`` — see decorator.py. Every method
    below branches on that field.

    Built-in themes are registered via register_workbench() / register_node_theme().
    Library themes are discovered automatically when a library calls
    theme_registry.add_folder(path, identity).
    """

    # =========================================================================
    # BaseRegistry abstract methods
    # =========================================================================

    def _class_filter(self, cls: Type) -> bool:
        """Accept BaseTheme subclasses with class_identity.

        Note: the base class declares `class_identity: ThemeClassIdentity = None`
        for mypy. Undecorated subclasses inherit that `None`, so `hasattr` is
        not enough — we must check the value is non-None (set by @theme).
        """
        return (
            isinstance(cls, type)
            and issubclass(cls, BaseTheme)
            and cls is not BaseTheme
            and getattr(cls, "class_identity", None) is not None
        )

    def _register_class(
        self, cls: type[BaseTheme], library_identity: Optional[LibraryIdentity] = None
    ) -> str | None:
        registry_key = cls.class_identity.registry_key
        return super()._register(registry_key, cls, library_identity or _FRAMEWORK_THEME_IDENTITY)

    def _unregister_class(self, registry_key: str) -> type[BaseTheme] | None:
        return super()._unregister(registry_key)

    # =========================================================================
    # Typed registration helpers
    # =========================================================================

    def register_workbench(
        self, cls: Type[BaseTheme], library_identity: LibraryIdentity | None = None
    ) -> str | None:
        """Register a BaseTheme class authored with @theme(theme_type='workbench')."""
        return self._register_class(cls, library_identity or _FRAMEWORK_THEME_IDENTITY)

    def register_node_theme(
        self, cls: Type[BaseTheme], library_identity: LibraryIdentity | None = None
    ) -> str | None:
        """Register a BaseTheme class authored with @theme(theme_type='node')."""
        return self._register_class(cls, library_identity or _FRAMEWORK_THEME_IDENTITY)

    # =========================================================================
    # Typed accessors
    # =========================================================================

    def get_workbench(self, registry_key: str) -> BaseTheme:
        """Instantiate and return a workbench-flavoured BaseTheme by registry_key."""
        cls = self._classes.get(registry_key)
        if cls is not None and cls.class_identity.theme_type == "workbench":
            return cls()
        raise KeyError(f"Unknown workbench theme: '{registry_key}'")

    def get_node_theme(self, registry_key: str) -> BaseTheme:
        """Instantiate and return a node-flavoured BaseTheme by registry_key."""
        cls = self._classes.get(registry_key)
        if cls is not None and cls.class_identity.theme_type == "node":
            return cls()
        raise KeyError(f"Unknown node theme: '{registry_key}'")

    def list_workbench_keys(self) -> list[str]:
        """Return sorted list of registered workbench theme registry_keys."""
        return sorted(
            cls.class_identity.registry_key
            for cls in self._classes.values()
            if cls.class_identity.theme_type == "workbench"
        )

    def list_workbench_themes(self) -> list[tuple[str, str]]:
        """Return sorted list of(registry_key, label) pairs for ALL workbench themes."""
        return sorted(
            (cls.class_identity.registry_key, cls.class_identity.label)
            for cls in self._classes.values()
            if cls.class_identity.theme_type == "workbench"
        )

    def list_visible_workbench_themes(self) -> list[tuple[str, str]]:
        """Return sorted (registry_key, label) pairs for non-hidden workbench themes —
        those offered as a choice in the theme picker.
        """
        return sorted(
            (cls.class_identity.registry_key, cls.class_identity.label)
            for cls in self._classes.values()
            if cls.class_identity.theme_type == "workbench" and not cls.class_identity.hidden
        )

    def list_node_theme_keys(self) -> list[str]:
        """Return sorted list of registered node theme registry_keys."""
        return sorted(
            cls.class_identity.registry_key
            for cls in self._classes.values()
            if cls.class_identity.theme_type == "node"
        )

    def list_node_themes(self) -> list[tuple[str, str]]:
        """Return sorted (registry_key, label) pairs for ALL node themes."""
        return sorted(
            (cls.class_identity.registry_key, cls.class_identity.label)
            for cls in self._classes.values()
            if cls.class_identity.theme_type == "node"
        )

    def list_visible_node_themes(self) -> list[tuple[str, str]]:
        """Return sorted (registry_key, label) pairs for non-hidden node themes —
        those offered as a choice in a theme picker.
        """
        return sorted(
            (cls.class_identity.registry_key, cls.class_identity.label)
            for cls in self._classes.values()
            if cls.class_identity.theme_type == "node" and not cls.class_identity.hidden
        )
