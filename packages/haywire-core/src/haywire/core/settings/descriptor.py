# haywire/core/settings/descriptor.py
"""
setting — reactive property descriptor.

Instance-level access reads/writes the value stored in the owning Settings's
_local_store.  Change notifications are fired via Settings._on_prop_change().

Two operating modes:

  Simple mode  (no registry injected on the Settings):
      _field_key is empty or Settings._registry is None.
      Reads and writes go directly to _local_store keyed by attr name.

  Extended mode (registry injected by @node decorator):
      _field_key is set and Settings._registry is not None.
      Reads go through Settings._resolve() — full resolution chain.
      Writes go to _local_store keyed by _field_key.
      mirrors= points to a FrameworkSettings/LibrarySettings descriptor whose
      _field_key is stored as _mirror_key (used by _resolve for shadow/watch).
      read_only=True prevents writes (watch behaviour).
"""

from __future__ import annotations

from typing import Any, Callable

from .base import FieldDescriptor


class setting(FieldDescriptor):
    """
    Descriptor for a reactive setting on a ``Settings`` subclass.

    Class-level access returns the descriptor itself (for introspection and
    use as the ``mirrors=`` argument on another setting).
    Instance-level access reads/writes via the owning Settings's _local_store.
    """

    def __init__(
        self,
        default: Any = None,
        *,
        label: str = "",
        description: str = "",
        category: str = "general",
        order: int = 0,
        min: Any = None,
        max: Any = None,
        choices: "list | dict | Callable | None" = None,
        widget: "str | None" = None,
        on_change: "str | None" = None,
        mirrors: "FieldDescriptor | None" = None,
        read_only: bool = False,
        type_: "type | None" = None,
        stored: bool = True,
        validator: "Callable | None" = None,
    ) -> None:
        self._default = default
        self._type = type_ if type_ is not None else (type(default) if default is not None else object)
        self._label = label
        self._description = description
        self._category = category
        self._order = order
        self._min = min
        self._max = max
        self._choices = choices
        self._widget = widget
        self._on_change = on_change
        self._read_only = read_only
        self._stored = stored
        self._validator = validator
        self._attr_name: str = ""  # set by __set_name__
        self._field_key: str = ""  # set by @node decorator (extended mode)

        if self._validator is not None and default is not None and not self.validate(default):
            raise ValueError(f"Default value {default!r} fails validation for setting '{label or '?'}'")

        # mirrors= accepts a class-level descriptor access which returns the
        # descriptor itself (FieldDescriptor.__get__ with obj=None).
        if mirrors is not None:
            mirror_key = getattr(mirrors, "_field_key", "")
            if not mirror_key:
                raise ValueError(
                    "setting(mirrors=...) target has no _field_key set. "
                    "Ensure the target FrameworkSettings/LibrarySettings class has been "
                    "registered and its descriptors have _field_key assigned."
                )
            self._mirror_key: str = mirror_key
            if self._type is object:
                self._type = getattr(mirrors, "_type", object)
        else:
            self._mirror_key = ""

    def validate(self, value: Any) -> bool:
        """Return True if *value* passes the validator (or if no validator is set)."""
        if self._validator is None:
            return True
        return bool(self._validator(value))

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            return self  # class-level access -> descriptor itself

        # Extended mode: resolution chain via registry
        if self._field_key and getattr(obj, "_registry", None) is not None:
            return obj._resolve(self._field_key, self._mirror_key, self._default)

        # Simple mode: direct local store lookup by attr name
        return obj._local_store.get(self._attr_name, self._default)

    def __set__(self, obj: Any, value: Any) -> None:
        if self._read_only:
            raise AttributeError(
                f"'{self._attr_name}' is read-only — it mirrors a global setting "
                f"and cannot be set per-instance."
            )

        if not self.validate(value):
            return

        key = self._field_key if self._field_key else self._attr_name
        old = obj._local_store.get(key, self._default)
        obj._local_store[key] = value

        if value != old:
            obj._on_prop_change(self._attr_name, value, old)
            if self._on_change:
                method = getattr(obj, self._on_change, None)
                if method is not None:
                    try:
                        method(value, self._attr_name)
                    except TypeError:
                        method(value)
