# haywire/core/settings/descriptor.py
"""
setting — reactive property descriptor for Settings subclasses.

Instance-level access reads/writes the value stored in the owning Settings's
_local_store.  Change notifications are fired via Settings._on_prop_change().

Two operating modes:

  Simple mode  (no registry injected on the Settings):
      _setting_key is empty or Settings._registry is None.
      Reads and writes go directly to _local_store keyed by attr name.

  Extended mode (registry injected by @node decorator):
      _setting_key is set and Settings._registry is not None.
      Reads go through Settings._resolve() — full resolution chain.
      Writes go to _local_store keyed by _setting_key.
      mirrors= points to a FrameworkSettings/LibrarySettings descriptor whose
      _setting_key is stored as _mirror_key (used by _resolve for shadow/watch).
      read_only=True prevents writes (watch behaviour).

Convenience factories:
    shadow(src, ...)  — writable mirror of src setting
    watch(src, ...)   — read-only mirror of src setting
"""

from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar, overload

from .base import SettingDescriptor

T = TypeVar("T")


class setting(SettingDescriptor, Generic[T]):
    """
    Descriptor for a reactive field on a ``Settings`` subclass.

    **choices** = can be a list of valid values, a dict of {value: label},
        or a callable that returns either of those.
    **widget** =...
    **on_change** = is the name of a method on the OWNING Settings instance,
        called when the field value changes.
        **For callbacks that are outside the OWNING Settings instance,
        use the subscribe method on the OWNING Settings instance.**
    **mirrors** = can be a string field key or a class-level descriptor access (SettingDescriptor)
        to mirror another field's value and metadata.
        **It is recommended to use the shadow() and watch() factories instead of setting mirrors= directly.**
    **read_only** = True makes the field a read-only mirror (watch);
    **validator** = is a callable that accepts a value and returns True if it's valid
        (used for validating the default value).
    """

    def __init__(
        self,
        default: "T | Callable[[], T]" = None,  # type: ignore[assignment]
        *,
        label: str = "",
        description: str = "",
        category: str = "root",
        order: int = 0,
        min: Any = None,
        max: Any = None,
        choices: "list | dict | Callable | None" = None,
        widget: "str | None" = None,
        on_change: "str | None" = None,
        mirrors: "SettingDescriptor | str | None" = None,
        read_only: bool = False,
        type_: "type | None" = None,
        stored: bool = True,
        validator: "Callable | None" = None,
        metadata: "dict | None" = None,
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
        self._metadata: dict = metadata or {}
        self._attr_name: str = ""  # set by __set_name__
        self._setting_key: str = ""  # set by @node decorator (extended mode)
        self._mirror_descriptor: "SettingDescriptor | None" = None  # set when mirrors= is a descriptor

        if self._validator is not None and default is not None and not self.validate(default):
            raise ValueError(f"Default value {default!r} fails validation for field '{label or '?'}'")

        # mirrors= accepts either:
        #   - a class-level descriptor access (SettingDescriptor) — key may not be set yet
        #   - a plain string field key (e.g. "ui.node.default.skin.studio_skin")
        if mirrors is not None:
            if isinstance(mirrors, str):
                self._mirror_key: str = mirrors
            else:
                # Descriptor form: inherit metadata immediately; resolve key lazily via property
                self._mirror_descriptor = mirrors
                self._mirror_key = getattr(mirrors, "_setting_key", "")
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
            return self._mirror_descriptor._setting_key
        return self.__mirror_key

    @_mirror_key.setter
    def _mirror_key(self, value: str) -> None:
        self.__mirror_key = value

    def validate(self, value: Any) -> bool:
        """Return True if *value* passes the validator (or if no validator is set)."""
        if self._validator is None:
            return True
        return bool(self._validator(value))

    @overload
    def __get__(self, obj: None, objtype: type | None = None) -> "setting[T]": ...
    @overload
    def __get__(self, obj: object, objtype: type | None = None) -> T: ...
    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            return self  # class-level access -> descriptor itself

        # Extended mode: resolution chain via registry
        if self._setting_key and getattr(obj, "_registry", None) is not None:
            return obj._resolve(self._setting_key, self._mirror_key, self._default)

        # Simple mode: direct local store lookup by attr name
        value = obj._local_store.get(self._attr_name, self._default)
        return value() if callable(value) else value

    def __set__(self, obj: Any, value: T) -> None:
        if self._read_only:
            raise AttributeError(
                f"'{self._attr_name}' is read-only — it mirrors a global setting "
                f"and cannot be set per-instance."
            )

        if not self.validate(value):
            return

        key = self._setting_key if self._setting_key else self._attr_name
        old = obj._local_store.get(key, self._default)
        obj._local_store[key] = value

        if value != old:
            obj._on_property_change(self._attr_name, value, old, self._on_change)


def shadow(src: "setting[T]", **kwargs: Any) -> "setting[T]":
    """Writable mirror of *src* setting. Inherits src metadata; local writes are allowed."""
    return setting(mirrors=src, read_only=False, **kwargs)


def watch(src: "setting[T]", **kwargs: Any) -> "setting[T]":
    """Read-only mirror of *src* setting. Inherits src metadata; local writes raise AttributeError."""
    return setting(mirrors=src, read_only=True, **kwargs)
