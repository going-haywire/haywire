# haywire/core/settings/base.py
"""
FieldDescriptor — shared base for all property descriptors.

Provides the metadata contract that UI panels rely on: _default, _type,
_label, _description, _category, _order, _min, _max, _choices, _widget,
_attr_name, and the choices property.

Subclass:
    setting (settings/descriptor.py) — reactive instance setting on Settings subclasses
"""

from __future__ import annotations

import typing
from typing import Any, Callable


class FieldDescriptor:
    """
    Common ancestor for all property descriptors.

    Carries the metadata attributes that UI widget renderers depend on,
    plus ``__set_name__`` and the class-level branch of ``__get__``
    (returning ``self`` for introspection).
    """

    # Set by __set_name__
    _attr_name: str = ""
    """Short attribute name on the owning class, assigned by ``__set_name__``."""

    # Set by constructor (subclass __init__)
    _default: Any = None
    """Default value returned when no local or global override is set."""

    _type: type = object
    """Python type of the field — drives widget inference (bool→switch, int/float→number, etc.)."""

    _label: str = ""
    """Human-readable label shown next to the widget in the properties panel."""

    _description: str = ""
    """Tooltip text displayed on hover over the label in the properties panel."""

    _category: str = "root"
    """Panel grouping key — fields with the same category are rendered under a shared section header."""

    _order: int = 0
    """Sort order within a category — lower values appear first."""

    # Widget inference hints (used by properties panel)
    _min: Any = None
    """Minimum allowed value — used as the lower bound for numeric widgets."""

    _max: Any = None
    """Maximum allowed value — used as the upper bound for numeric widgets."""

    _choices: list | Callable | None = None
    """Dropdown options: a static list, a ``{value: label}`` dict, or a callable returning either."""

    _widget: str | None = None
    """Explicit widget hint (e.g. ``'color'``) that overrides type-based inference."""

    @property
    def choices(self) -> list | dict | None:
        """Resolve choices — calls the provider if it is a callable."""
        if callable(self._choices):
            return self._choices()
        return self._choices

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr_name = name
        # The annotation may be more specific than what was inferred from the default
        # (e.g. Vec3f vs plain list, or an explicit type_ that matches the annotation).
        # Always let the annotation win if it resolves to a concrete type.
        try:
            hints = typing.get_type_hints(owner)
            hint = hints.get(name)
            if hint is not None and isinstance(hint, type) and hint is not self._type:
                self._type = hint
        except Exception:
            pass

    def __get__(self, obj: object | None, objtype: type | None = None) -> Any:
        if obj is None:
            # Class-level access -> return descriptor itself (typed key handle)
            return self
        # Subclasses override for instance-level access
        raise NotImplementedError(f"{type(self).__name__} must override __get__ for instance access")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(attr={self._attr_name!r}, default={self._default!r})"
