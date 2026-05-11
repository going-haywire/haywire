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

from typing import TYPE_CHECKING, Any, Callable, Generic, TypeVar, overload

from .base import SettingDescriptor

if TYPE_CHECKING:
    from haywire.core.settings.registry import SettingsRegistry

T = TypeVar("T")


class setting(SettingDescriptor, Generic[T]):
    """Reactive field descriptor for a ``Settings`` subclass.

    Declare fields on a ``Settings`` subclass to get reactive, typed
    properties with optional UI auto-rendering, validation, mirroring,
    and persistence::

        class MySettings(LibrarySettings):
            threshold = setting[float](0.5, min=0.0, max=1.0, label='Threshold')
            mode = setting[str]('fast', choices=['fast', 'precise'], label='Mode')

    On ``FrameworkSettings`` and ``LibrarySettings`` ,writes go through
    the registry's workspace tier and persist to ``.haywire/settings.toml``).

    On ``NodeSettings`` and plain ``Settings``, writes go to the
    instance's ``_local_store`` only and are stored with the Graph.

    Authors declare ``setting[T](...)`` either way — the framework
    picks the right behaviour.

    Parameters
    ----------
    default
        Initial value for the field. Can be a literal of type ``T`` or a
        zero-argument callable returning ``T`` (for late-binding / dynamic
        defaults). When a ``validator`` is set, the default is checked at
        construction time and ``ValueError`` is raised if it fails.

    label : str
        Human-readable name shown in the UI. If empty, auto-renderers fall
        back to the attribute name. Display-only; no functional effect.

    description : str
        Help text surfaced as a tooltip / inline help by the auto-renderer
        (``render_schema``). Display-only.

    category : str
        Grouping key for auto-rendered panels — fields with the same
        category cluster under one section header. Defaults to ``"root"``
        (no nesting).

    order : int
        Sort key within a category. Lower numbers render first. Defaults to 0.

    min, max
        Bounds passed to numeric widgets (``NumberDrag``). UI-only — NOT
        enforced on direct writes. Use ``validator`` if you need runtime
        enforcement.

    choices
        Valid values for the field. Three forms:

        * ``list[T]`` — values shown and stored verbatim.
        * ``dict[T, str]`` — keys are the stored values, values are the
          displayed labels.
        * ``Callable[[], list | dict]`` — evaluated at render time. Use for
          dynamic lists that depend on registry state (e.g. enumerate
          installed themes).

        Presence of ``choices=`` makes the auto-renderer use a ``ui.select``
        widget regardless of type. Not enforced on direct writes — use
        ``validator`` for enforcement.

    widget : str or None
        Optional widget override. Two recognised values:

        * ``"label"`` — read-only ``ui.label``.
        * ``"color"`` — ``ui.color_input``.

        ``None`` (default) means auto-dispatch by ``type_`` and the presence
        of ``choices=``:

        1. ``choices`` set → ``ui.select``
        2. ``type_ is bool`` → ``ui.switch``
        3. ``type_ in (int, float)`` → ``NumberDrag`` (honours ``min``/``max``)
        4. otherwise → text input with expand-to-modal button

    on_change : str or None
        Name of a method on the **owning** ``Settings`` instance, called when
        the value changes. Dispatched as ``method(value, name)``; falls back
        to ``method(value)`` if the two-arg form raises ``TypeError``.

        For callbacks defined outside the owning class, use
        ``Settings.subscribe(callback)`` instead — that callback receives
        ``(name, value, old)``.

    mirrors : SettingDescriptor or str or None
        Marks this field as a mirror of another setting. Two forms:

        * A ``SettingDescriptor`` reference — e.g.
          ``mirrors=NodeSkinSettings.studio_skin``. Inherits label,
          description, choices, widget, and type from the source at
          construction time; the source's setting key is resolved lazily.
        * A plain string key — e.g.
          ``mirrors="ui.node.default.skin.studio_skin"``. Use only when
          a descriptor reference is unavailable.

        **Prefer the ``shadow()`` and ``watch()`` factories** over
        constructing ``setting(mirrors=..., read_only=...)`` directly.

    read_only : bool
        When ``True``, the field is read-only and raises ``AttributeError`
        if one does anyway

    type_ : type or None
        Explicit Python type. Defaults to ``type(default)`` if ``default`` is
        a value, or ``object`` if ``default`` is ``None`` or a callable. The
        auto-renderer uses this to pick a widget. Override when the default
        doesn't disambiguate (e.g. ``type_=Color`` for hex strings, or
        ``type_=float`` when ``default=None``).

    stored : bool
        When ``False``, the field is omitted from serialisation.
        Use for ephemeral fields that shouldn't persist to disk.
        Has no effect in LibryarySetting and FrameworkSetting.
        Defaults to ``True``.

    validator : Callable or None
        Callable ``(value) -> bool`` returning ``True`` if the value is
        valid. Called from ``__set__`` (silently ignores invalid writes) AND
        at construction time on the default (raises ``ValueError`` if the
        default itself fails validation).

    metadata : dict or None
        Free-form dict for application-specific metadata. The framework
        doesn't consult it; downstream code (custom renderers, introspection)
        can store anything here. Defaults to ``{}``.
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


class persistent_setting(setting, Generic[T]):
    """A `setting` whose writes persist through the registry's workspace tier.

    Used by FrameworkSettings and LibrarySettings — every field declared on
    those schemas is auto-promoted to persistent_setting by their
    __init_subclass__. Instantiating this class directly bypasses the
    registration machinery and is unsupported; declare fields as
    ``setting[T](...)`` and let the parent class promote them.

    Behavior change vs `setting`:
        Writes call ``registry.set_global(setting_key, value)`` followed by
        ``registry.save_to_toml_debounced()``. The registry then fires
        change notifications to subscribers (including the owning Settings
        instance), so this class deliberately does NOT call
        ``_on_property_change`` itself — that would double-fire every
        callback.

    Falls back to ``super().__set__`` (parent's local-store write) when the
    instance has no registry wired (e.g. test fixtures in simple mode) or
    when the field has no namespaced ``_setting_key``. This preserves
    backwards compatibility with tests that construct schemas without a
    registry.
    """

    def __set__(self, obj: Any, value: T) -> None:
        if self._read_only:
            raise AttributeError(
                f"'{self._attr_name}' is read-only — it mirrors a global setting "
                f"and cannot be set per-instance."
            )

        if not self.validate(value):
            return

        registry: "SettingsRegistry | None" = getattr(obj, "_registry", None)
        if registry is None or not self._setting_key:
            # No registry wired (test fixture / simple mode), or no
            # namespaced key — fall back to local-store write so existing
            # behaviour is preserved.
            super().__set__(obj, value)
            return

        # registry.set_global fires _notify_subscribers → owning instance's
        # _on_field_change → _on_property_change. We MUST NOT also call
        # _on_property_change ourselves here, or subscribers fire twice.
        registry.set_global(self._setting_key, value)
        registry.save_to_toml_debounced()


def shadow(src: "setting[T]", **kwargs: Any) -> "setting[T]":
    """Writable mirror of *src* setting. Inherits src metadata; local writes are allowed."""
    return setting(mirrors=src, read_only=False, **kwargs)


def watch(src: "setting[T]", **kwargs: Any) -> "setting[T]":
    """Read-only mirror of *src* setting. Inherits src metadata; local writes raise AttributeError."""
    return setting(mirrors=src, read_only=True, **kwargs)
