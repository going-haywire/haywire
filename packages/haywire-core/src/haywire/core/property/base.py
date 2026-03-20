# haywire/core/property/base.py
"""
FieldDescriptor — shared base for all property/setting descriptors.

Provides the metadata contract that UI panels (e.g. _render_widget_impl)
rely on: _default, _type, _label, _description, _category, _order,
_min, _max, _choices, _widget, _attr_name, and the choices property.

Subclasses:
    prop (property/descriptor.py)       — reactive instance property
    SettingDescriptor (settings/descriptors.py) — settings with resolution chain
"""

from __future__ import annotations

from typing import Any, Callable


class FieldDescriptor:
    """
    Common ancestor for ``prop`` and ``SettingDescriptor``.

    Carries the metadata attributes that UI widget renderers depend on,
    plus ``__set_name__`` and the class-level branch of ``__get__``
    (returning ``self`` for introspection).
    """

    # Set by __set_name__
    _attr_name: str = ''

    # Set by constructor (subclass __init__)
    _default: Any = None
    _type: type = object
    _label: str = ''
    _description: str = ''
    _category: str = ''
    _order: int = 0

    # Widget inference hints (used by properties panel)
    _min: Any = None
    _max: Any = None
    _choices: list | Callable | None = None
    _widget: str | None = None

    @property
    def choices(self) -> list | dict | None:
        """Resolve choices — calls the provider if it is a callable."""
        if callable(self._choices):
            return self._choices()
        return self._choices

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr_name = name

    def __get__(self, obj: object | None, objtype: type | None = None) -> Any:
        if obj is None:
            # Class-level access -> return descriptor itself (typed key handle)
            return self
        # Subclasses override for instance-level access
        raise NotImplementedError(
            f"{type(self).__name__} must override __get__ for instance access"
        )

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"attr={self._attr_name!r}, "
            f"default={self._default!r})"
        )
