# haywire/core/settings/base.py
"""
SettingDescriptor — shared base for all property descriptors.

Carries the metadata attributes (``_default``, ``_type``, ``_label``,
``_description``, ``_category``, ``_order``, ``_min``, ``_max``,
``_attr_name``) and the widget contract (``widget_key``, ``widget_config``),
which ``_stamp_widget()`` computes at ``__set_name__`` time and never on the
render path.

The one subclass is ``setting`` in :mod:`haywire.core.settings.descriptor`.
"""

from __future__ import annotations

import typing
from typing import Any


class SettingDescriptor:
    """
    Common ancestor for all property descriptors.

    Class-level access (``MySettings.field``) returns the descriptor itself;
    subclasses implement instance-level access.
    """

    # Set by __set_name__
    _attr_name: str = ""
    """Short attribute name on the owning class, assigned by ``__set_name__``."""

    _owner_cls: "type | None" = None
    """Class this descriptor was declared on, recorded by ``__set_name__``."""

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
    """Widget registry key, stamped at ``__set_name__`` by ``_stamp_widget()``."""

    widget_config: dict = {}
    """Widget config (``{"properties": {...}}``), stamped at ``__set_name__``."""

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr_name = name
        self._owner_cls = owner
        # _type comes from the owner's annotation when there is one, else from
        # the descriptor's generic argument (`field[T](...)`, __orig_class__).
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
        """Compute the field's widget contract. No-op on the base; ``setting`` overrides it."""
        pass

    def _enforce_itype(self, owner: type, name: str) -> None:
        """Raise ``TypeError`` unless this field's resolved type is an IType (e.g. ``setting[FLOAT]``).

        A Python type (``float``, ``str``, ...), an unresolved ``object``, and a
        union all fail. ``shadow()``/``watch()`` mirrors inherit the source's
        IType and pass.
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
