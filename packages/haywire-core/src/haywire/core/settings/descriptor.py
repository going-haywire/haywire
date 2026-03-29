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
        self._mirror_descriptor: "FieldDescriptor | None" = None  # set when mirrors= is a descriptor

        if self._validator is not None and default is not None and not self.validate(default):
            raise ValueError(f"Default value {default!r} fails validation for setting '{label or '?'}'")

        # mirrors= accepts either:
        #   - a class-level descriptor access (FieldDescriptor) — key may not be set yet
        #   - a plain string field key (e.g. "ui.node.default.skin.studio_skin")
        if mirrors is not None:
            if isinstance(mirrors, str):
                self._mirror_key: str = mirrors
            else:
                # Descriptor form: inherit metadata immediately; resolve key lazily via property
                self._mirror_descriptor = mirrors
                self._mirror_key = getattr(mirrors, "_field_key", "")
                if not label:
                    self._label = getattr(mirrors, "_label", "")
                if not description:
                    self._description = getattr(mirrors, "_description", "")
                if choices is None:
                    self._choices = getattr(mirrors, "_choices", None)
                if widget is None:
                    self._widget = getattr(mirrors, "_widget", None)
                if self._type is object:
                    self._type = getattr(mirrors, "_type", object)
        else:
            self._mirror_key = ""

    @property
    def _mirror_key(self) -> str:
        """Resolved mirror field key — lazy when mirrors= was given as a descriptor."""
        if self._mirror_descriptor is not None:
            return self._mirror_descriptor._field_key
        return self.__mirror_key

    @_mirror_key.setter
    def _mirror_key(self, value: str) -> None:
        self.__mirror_key = value

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
        value = obj._local_store.get(self._attr_name, self._default)
        return value() if callable(value) else value

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
