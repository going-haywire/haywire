# haywire/core/settings/base.py
"""
SettingDescriptor — shared base for all property descriptors.

Provides the metadata contract that UI panels rely on: _default, _type,
_label, _description, _category, _order, _min, _max, _attr_name, plus the
stamped widget contract (``widget_key``, ``widget_config``) computed ONCE by
``_stamp_widget()`` from ``__set_name__`` — no render-time resolution.

Subclass:
    setting (settings/descriptor.py) — reactive instance setting on Settings subclasses
"""

from __future__ import annotations

import typing
from typing import Any


class SettingDescriptor:
    """
    Common ancestor for all property descriptors.

    Carries the metadata attributes that UI widget renderers depend on,
    plus ``__set_name__`` and the class-level branch of ``__get__``
    (returning ``self`` for introspection).
    """

    # Set by __set_name__
    _attr_name: str = ""
    """Short attribute name on the owning class, assigned by ``__set_name__``."""

    _owner_cls: "type | None" = None
    """Class this descriptor was declared on, recorded by ``__set_name__``.
    Graph mirrors use it to locate 'the instance of that bag on my graph'
    (``BaseGraph.settings_bag_for``)."""

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

    _setting_key: str = ""
    """Fully-qualified registry key — set by persistent_setting subclasses at registration."""

    widget_key: str = ""
    """Widget registry key stamped ONCE at ``__set_name__`` by ``_stamp_widget()``."""

    widget_config: dict = {}
    """Widget config (``{"properties": {...}}``) stamped ONCE at ``__set_name__``."""

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr_name = name
        self._owner_cls = owner
        # Refine _type from a more specific source than the inferred default
        # (e.g. Vec3f vs plain list). Two refinement sources, in priority order:
        #   1. Owner class annotation `name: T = field(...)`
        #   2. Generic parameter on the descriptor `field[T](...)` via __orig_class__
        try:
            hints = typing.get_type_hints(owner)
            hint = hints.get(name)
            if hint is not None and isinstance(hint, type) and hint is not self._type:
                self._type = hint
                self._enforce_itype(owner, name)
                self._stamp_widget()
                return
        except Exception:
            pass
        orig_class = getattr(self, "__orig_class__", None)
        if orig_class is not None:
            args = typing.get_args(orig_class)
            if args and isinstance(args[0], type) and args[0] is not self._type:
                self._type = args[0]
        self._enforce_itype(owner, name)
        self._stamp_widget()

    def _stamp_widget(self) -> None:
        """Compute the final widget contract ONCE. Overridden by ``setting``
        (settings/descriptor.py); the base no-op keeps other SettingDescriptor
        subclasses (if any) from needing to implement it."""
        pass

    def _enforce_itype(self, owner: type, name: str) -> None:
        """A setting field must be typed with an IType (e.g. ``setting[FLOAT]``).

        Python types (``float``/``str``/...), ``object`` (no type resolved), and
        unions are rejected. ``shadow()``/``watch()`` mirrors inherit their
        IType from the source and so pass here once the source is an IType.
        """
        from haywire.core.types.interface import IType

        resolved = self._type
        if isinstance(resolved, type) and issubclass(resolved, IType):
            return
        raise TypeError(
            f"setting field '{owner.__name__}.{name}' must be typed with an IType "
            f"(e.g. setting[FLOAT]); got {resolved!r}. Python types are no longer "
            f"accepted — import the IType from haywire.barn.builtin.types."
        )

    def __get__(self, obj: object | None, objtype: type | None = None) -> Any:
        if obj is None:
            # Class-level access -> return descriptor itself (typed key handle)
            return self
        # Subclasses override for instance-level access
        raise NotImplementedError(f"{type(self).__name__} must override __get__ for instance access")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(attr={self._attr_name!r}, default={self._default!r})"
