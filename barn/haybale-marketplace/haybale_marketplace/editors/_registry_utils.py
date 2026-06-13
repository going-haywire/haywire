"""Shared registry-lookup utilities for marketplace editors.

Both ComponentSourceEditor and LibraryComponentEditor need to resolve a
component class from a registry_key string. This module owns that lookup.
"""

from __future__ import annotations

from typing import Optional

from haywire.core.library.utils import (
    ADAPTER,
    EDITOR,
    NODE,
    PANEL,
    SETTING,
    SKIN,
    STATE,
    THEME,
    TYPE,
    WIDGET,
    split_reg_key,
)

# Maps the singular comp_type segment of a registry_key to the
# library_service getter method name.
_REGISTRY_GETTER: dict[str, str] = {
    NODE: "get_node_registry",
    WIDGET: "get_widget_registry",
    TYPE: "get_type_registry",
    ADAPTER: "get_adapter_registry",
    SKIN: "get_skin_registry",
    THEME: "get_theme_registry",
    SETTING: "get_settings_registry",
    STATE: "get_state_registry",
    PANEL: "get_panel_registry",
    EDITOR: "get_editor_registry",
}


def lookup_component_class(app, registry_key: str) -> Optional[type]:
    """Return the component class registered under registry_key, or None.

    Resolves the appropriate registry from app.library_service based on
    the singular comp_type segment of the key (e.g. 'node' in
    'mylib:node:MyNode').

    Args:
        app: The project app state (provides library_service).
        registry_key: Three-part key ``lib_id:comp_type:class_name``.

    Returns:
        The registered class, or None when the key is malformed, the
        registry is unavailable, or the class is not found.
    """
    if not app or not registry_key:
        return None
    _lib_id, comp_singular, _class_name = split_reg_key(registry_key)
    getter_name = _REGISTRY_GETTER.get(comp_singular)
    if getter_name is None:
        return None
    try:
        svc = app.library_service
        registry = getattr(svc, getter_name, lambda: None)()
        if registry is None:
            return None
        return registry.get(registry_key)
    except Exception:
        return None
