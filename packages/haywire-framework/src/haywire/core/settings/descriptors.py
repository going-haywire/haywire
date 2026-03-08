# haywire/core/settings/descriptors.py
"""
Descriptor classes for the Haywire settings system.

Three descriptor types are provided:
    setting()  — local, stored in graph, shown in properties panel
    shadow()   — mirrors a global setting; per-node override; shown with reset affordance
    watch()    — read-only cached reference to a global; invisible in panel; never serialized
"""

from __future__ import annotations
from typing import Any


class _SettingDescriptor:
    """
    Base descriptor for all setting field types.

    Python calls __set_name__ automatically when the class body is evaluated.
    Class-level __get__ returns self (the descriptor) — this enables:
        shadow(MyLibSettings.bg_color)   ← class access returns descriptor with _full_key set
    Instance-level __get__ raises AttributeError — values come through SettingsHolder.
    """

    # Set by __set_name__
    _attr_name: str = ''
    # Set by _SettingsSchema.__init_subclass__ or BaseNode.__init_subclass__
    _full_key: str = ''

    # Set by constructor
    _default: Any = None
    _label: str = ''
    _description: str = ''
    _category: str = ''
    _order: int = 0
    _on_change: str = ''   # method name on the node instance

    # Flags used by serializer and panel introspection
    _panel_visible: bool = True
    _stored: bool = True
    _read_only: bool = False

    # Widget inference hints (used by properties panel)
    _min: Any = None
    _max: Any = None
    _choices: list | None = None
    _widget: str | None = None   # explicit override: 'color', 'slider', 'toggle', etc.

    def __set_name__(self, owner: type, name: str) -> None:
        # Each instance must have its own copy of _attr_name and _full_key
        # (descriptors are shared across the class hierarchy via class body)
        self._attr_name = name
        # _full_key is set later by schema __init_subclass__ once namespace is known

    def __get__(self, obj: object | None, objtype: type | None = None) -> Any:
        if obj is None:
            # Class-level access → return descriptor itself (typed key handle)
            return self
        raise AttributeError(
            f"Access '{self._attr_name}' via self.settings.{self._attr_name}, "
            f"not self.{self._attr_name}"
        )

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"full_key={self._full_key!r}, "
            f"default={self._default!r})"
        )


class setting(_SettingDescriptor):
    """
    Local node setting — stored in graph, shown in properties panel.

    Widget inference (if _widget is not set explicitly):
        bool              → toggle
        int/float + range → slider
        Color             → color picker
        Icon              → icon picker
        str               → text input
        (Literal types are resolved in panel rendering from _choices)
    """

    _panel_visible = True
    _stored = True
    _read_only = False

    def __init__(
        self,
        default: Any,
        *,
        min: Any = None,
        max: Any = None,
        choices: list | None = None,
        widget: str | None = None,
        label: str = '',
        description: str = '',
        category: str = '',
        order: int = 0,
        on_change: str = '',
    ) -> None:
        self._default = default
        self._min = min
        self._max = max
        self._choices = choices
        self._widget = widget
        self._label = label
        self._description = description
        self._category = category
        self._order = order
        self._on_change = on_change
        # _attr_name and _full_key set by __set_name__ / schema machinery


class shadow(_SettingDescriptor):
    """
    Shadow a global setting — inherits global value; per-node override allowed.

    Stored in graph ONLY when locally overridden.
    Shown in panel with "reset to global" affordance.

    Usage:
        bg_color: Color = shadow(MyLibSettings.bg_color)

    The global_descriptor._full_key is stored as a string immediately
    (object reference discarded — robust to hot-reload).
    """

    _panel_visible = True
    _stored = True
    _read_only = False

    def __init__(self, global_descriptor: _SettingDescriptor) -> None:
        # Store the full_key as string — NOT the object reference
        self._global_key = global_descriptor._full_key
        # Inherit metadata from the global descriptor
        self._default = global_descriptor._default
        self._label = global_descriptor._label
        self._description = global_descriptor._description
        self._category = global_descriptor._category
        self._widget = global_descriptor._widget
        self._min = global_descriptor._min
        self._max = global_descriptor._max
        self._choices = global_descriptor._choices
        self._order = global_descriptor._order
        self._on_change = ''   # shadows don't inherit on_change


class watch(_SettingDescriptor):
    """
    Watch a global setting — read-only cached reference; never stored; invisible in panel.

    Usage:
        verbose: bool = watch(DebugSettings.verbose_logging)
    """

    _panel_visible = False
    _stored = False
    _read_only = True

    def __init__(self, global_descriptor: _SettingDescriptor) -> None:
        self._global_key = global_descriptor._full_key
        self._default = global_descriptor._default
        self._label = global_descriptor._label
        self._description = global_descriptor._description
        self._category = global_descriptor._category
        self._widget = global_descriptor._widget
        self._min = global_descriptor._min
        self._max = global_descriptor._max
        self._choices = global_descriptor._choices
        self._order = 0
        self._on_change = ''
