# haywire/core/settings/descriptors.py
"""
Descriptor classes for the Haywire settings system.

Three descriptor types are provided:
    setting()  — local, stored in graph, shown in properties panel
    shadow()   — mirrors a global setting; per-node override; shown with reset affordance
    watch()    — read-only cached reference to a global; invisible in panel; never serialized
"""

from __future__ import annotations
from typing import Any, Callable


class SettingDescriptor:
    """
    Base descriptor for all setting field types.

    Python calls __set_name__ automatically when the class body is evaluated.
    Class-level __get__ returns self (the descriptor) — this enables:
        shadow(MyLibSettings.bg_color)   ← class access returns descriptor with _field_key set
    Instance-level __get__ raises AttributeError — values come through SettingsHolder.
    """

    # Set by __set_name__
    _attr_name: str = ''

    _field_key: str = ''
    """
    Fully-qualified dotted key for this field within the node's settings namespace
    (e.g. ``haybale_core.node.transform.bg_color``).

    Set by the ``@node`` decorator.

    Used as the storage key for per-node local overrides in the ``ResolutionChain``.
    """

    _mirror_key: str = ''
    """
    Key of the global setting this descriptor mirrors in the ``GlobalSettingsRegistry``
    (e.g. ``ui.node.bg_color``).

    Set by ``shadow``/``watch`` constructors; empty string on plain ``setting()``.

    Used to look up the mirrored values during resolution.
    """


    # Set by constructor
    _default: Any = None
    _type: type = object          # Python type for validation and coercion
    _validator: Callable | None = None  # Optional custom validator
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
    _choices: list | Callable | None = None
    _widget: str | None = None   # explicit override: 'color', 'slider', 'toggle', etc.

    @property
    def choices(self) -> list | None:
        """Resolve choices — calls the provider if it is a callable."""
        if callable(self._choices):
            return self._choices()
        return self._choices

    def __set_name__(self, owner: type, name: str) -> None:
        # Each instance must have its own copy of _attr_name and _field_key
        # (descriptors are shared across the class hierarchy via class body)
        self._attr_name = name
        # _field_key is set later by schema __init_subclass__ once namespace is known

    def __get__(self, obj: object | None, objtype: type | None = None) -> Any:
        if obj is None:
            # Class-level access → return descriptor itself (typed key handle)
            return self
        raise AttributeError(
            f"Access '{self._attr_name}' via self.settings.{self._attr_name}, "
            f"not self.{self._attr_name}"
        )

    def validate(self, value: Any) -> bool:
        """Validate a value against this descriptor's constraints."""
        if value is not None and self._type not in (object, type(None)):
            if self._type is float and isinstance(value, int):
                pass  # int is valid for float
            elif self._type is str and not isinstance(value, str):
                return False
            elif self._type is bool and not isinstance(value, bool):
                return False
            elif self._type is int and not isinstance(value, int):
                return False
        resolved_choices = self.choices
        valid = list(resolved_choices.keys()) if isinstance(resolved_choices, dict) else resolved_choices
        if valid is not None and value not in valid:
            return False
        if self._min is not None and value < self._min:
            return False
        if self._max is not None and value > self._max:
            return False
        if self._validator is not None:
            try:
                if not self._validator(value):
                    return False
            except Exception:
                return False
        return True

    def coerce(self, value: Any) -> Any:
        """Attempt to coerce a value to this descriptor's type."""
        if value is None:
            return self._default
        if self._type in (object, type(None)) or isinstance(value, self._type):
            return value
        try:
            if self._type is bool:
                if isinstance(value, str):
                    return value.lower() in ('true', '1', 'yes', 'on')
                return bool(value)
            return self._type(value)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Cannot coerce {value!r} to {self._type.__name__}: {e}")

    def to_dict(self) -> dict:
        """Serialise descriptor metadata (for TOML-defined settings)."""
        return {
            'default': self._default,
            'type': self._type.__name__ if self._type not in (object, type(None)) else 'str',
            'label': self._label,
            'description': self._description,
            'category': self._category,
            'min_value': self._min,
            'max_value': self._max,
            'choices': self.choices,
            'ui_widget': self._widget,
            'ui_order': self._order,
        }

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"full_key={self._field_key!r}, "
            f"default={self._default!r})"
        )


class setting(SettingDescriptor):
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
        type_: type | None = None,
        validator: Callable | None = None,
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
        self._type = type_ if type_ is not None else (type(default) if default is not None else object)
        self._validator = validator
        self._min = min
        self._max = max
        self._choices = choices
        self._widget = widget
        self._label = label
        self._description = description
        self._category = category
        self._order = order
        self._on_change = on_change
        # _attr_name and _field_key set by __set_name__ / schema machinery


class shadow(SettingDescriptor):
    """
    Shadow a global setting — inherits global value; per-node override allowed.

    Stored in graph ONLY when locally overridden.
    Shown in panel with "reset to global" affordance.

    Usage:
        bg_color: Color = shadow(MyLibSettings.bg_color)

    The global_descriptor._field_key is stored as a string immediately
    (object reference discarded — robust to hot-reload).
    """

    _panel_visible = True
    _stored = True
    _read_only = False

    def __init__(self, global_descriptor: SettingDescriptor) -> None:
        # Store the full_key as string — NOT the object reference
        self._mirror_key = global_descriptor._field_key
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


class watch(SettingDescriptor):
    """
    Watch a global setting — read-only cached reference; never stored; invisible in panel.

    Usage:
        verbose: bool = watch(DebugSettings.verbose_logging)
    """

    _panel_visible = False
    _stored = False
    _read_only = True

    def __init__(self, global_descriptor: SettingDescriptor) -> None:
        self._mirror_key = global_descriptor._field_key
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
