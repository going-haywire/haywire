# haywire/core/settings/descriptor.py
"""
setting — reactive property descriptor for Settings subclasses.

Cell-authoritative model:

  __get__ is a pure cell read (``obj._cell_for(self).get_value()``) on every
  path — no mode branch, no resolution-chain walk. The cell is kept correct at
  write/seed time: a plain field's cell seeds with the descriptor default; a
  cross-mirror (shadow/watch of another setting) seeds from the resolved
  global and is synced by ``_on_field_change``; a wired persistent field
  borrows THE registry-owned cell (``registry.cell_for``), kept current by the
  registry's tier write-through. ``_set_keys`` carries the set-or-unset
  opinion; change notification is the cell's own ``on_changed`` event.

  ``persistent_setting`` (FrameworkSettings/LibrarySettings) routes writes to
  ``registry.set_global``; plain ``setting`` writes the instance cell and
  marks the opinion. ``read_only=True`` prevents writes (watch behaviour).

Convenience factories:
    shadow(src, ...)  — writable mirror of src setting
    watch(src, ...)   — read-only mirror of src setting
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Generic, TypeVar, overload

from haywire.core.types.interface import IType

from .base import SettingDescriptor

if TYPE_CHECKING:
    from haywire.core.settings.registry import SettingsRegistry

# ``setting`` is generic over its IType (e.g. ``setting[FLOAT]``). The descriptor
# stores raw Python values, so the value side (default / __get__ / __set__) is
# typed ``Any``: mypy cannot project an IType's value type (FLOAT -> float) from
# the subscript (no higher-kinded types). ``_type`` stays strict (``type[T]``).
T = TypeVar("T", bound=IType)


class setting(SettingDescriptor, Generic[T]):
    """Reactive field descriptor for a ``Settings`` subclass.

    Declare fields on a ``Settings`` subclass to get reactive, typed
    properties with optional UI auto-rendering, validation, mirroring,
    and persistence::

        class MySettings(LibrarySettings):
            threshold = setting[FLOAT](0.5, min=0.0, max=1.0, label='Threshold')
            mode = setting[CHOICES]('fast', widget_config={'options': ['fast', 'precise']}, label='Mode')

    On ``FrameworkSettings`` and ``LibrarySettings`` ,writes go through
    the registry's workspace tier and persist to ``.haywire/settings.json``).

    On ``NodeSettings`` and plain ``Settings``, writes go to the
    instance's per-field ``DataField`` cell only and are stored with the Graph.

    Authors declare ``setting[T](...)`` either way — the framework
    picks the right behaviour.

    Parameters
    ----------
    default
        Initial value for the field. Can be a literal of type ``T`` or a
        zero-argument callable returning ``T`` for late binding (e.g. the
        source registry doesn't exist at class-definition time). A callable
        default is evaluated ONCE, when the field's cell seeds — never per
        read (the read path is a pure cell read). When a
        ``validator`` is set, the default is checked at construction time and
        ``ValueError`` is raised if it fails.

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
        enforcement. Folded into ``widget_config["properties"]`` at
        ``__set_name__`` time.

    widget : dict or None
        Explicit widget contract built via ``WidgetCls.config(...)`` (see
        ``IWidget.config``), e.g. ``widget=SimpleLabelWidget.config()`` or
        ``widget=SelectWidget.config(properties={"options": [...]})``. When
        given, it wins outright over the field IType's declared default
        widget. ``None`` (default): the widget comes from the field IType's
        declared default ``widget_key`` — use ``setting[CHOICES]`` for a
        dropdown (see ``widget_config`` below for its options).

    widget_config : dict or None
        Bare config overrides layered on top of the IType's default widget
        config when the default widget is fine but its properties need a
        tweak — e.g. ``setting[CHOICES]("fast", widget_config={"options":
        ["fast", "precise"]})``. Accepts either a ``{"properties": {...}}``
        wrapper or a bare properties dict (``{"options": [...]}``) — both
        spellings are equivalent.

    mirrors : SettingDescriptor or str or None
        Marks this field as a mirror of another setting. Two forms:

        * A ``SettingDescriptor`` reference — e.g.
          ``mirrors=NodeSkinSettings.studio_skin``. Inherits label,
          description, and type from the source at construction time (the
          mirror's own widget_key/widget_config are stamped from its own
          ``_type`` at ``__set_name__``, since mirrors already inherit IType);
          the source's setting key is resolved lazily.
        * A plain string key — e.g.
          ``mirrors="ui.node.default.skin.studio_skin"``. Use only when
          a descriptor reference is unavailable.

        **Prefer the ``shadow()`` and ``watch()`` factories** over
        constructing ``setting(mirrors=..., read_only=...)`` directly.

    read_only : bool
        When ``True``, the field is read-only and raises ``AttributeError`
        if one does anyway

    type_ : type[IType] or None
        Explicit IType (e.g. ``type_=FLOAT``). Usually omitted — the IType
        comes from the ``setting[T]`` generic subscript via ``__set_name__``.
        Python types are rejected (IType cutover); there is no inference from
        ``default``.

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
        default: "Any | Callable[[], Any]" = None,
        *,
        label: str = "",
        description: str = "",
        category: str = "root",
        order: int = 0,
        min: Any = None,
        max: Any = None,
        widget: "dict | None" = None,
        widget_config: "dict | None" = None,
        mirrors: "SettingDescriptor | str | None" = None,
        read_only: bool = False,
        type_: "type[T] | None" = None,
        validator: "Callable | None" = None,
        metadata: "dict | None" = None,
    ) -> None:
        self._default = default
        # IType cutover: an explicit type_= must be an IType (Python-type inference
        # via type(default) is gone). When type_ is absent, leave _type as the
        # sentinel ``object`` so __set_name__ resolves it from the setting[IType]
        # generic arg and enforces IType there.
        if type_ is not None:
            if not (isinstance(type_, type) and issubclass(type_, IType)):
                raise TypeError(
                    f"setting field '{label or '?'}' type_= must be an IType "
                    f"(e.g. type_=FLOAT); got {type_!r}. Python types are no longer accepted."
                )
        self._type = type_ if type_ is not None else object
        self._label = label
        self._description = description
        self._category = category
        self._order = order
        self._min = min
        self._max = max
        self._widget_spec = widget or {}
        self._widget_config_override = widget_config or {}
        self._read_only = read_only
        self._validator = validator
        self._metadata: dict = metadata or {}
        self._attr_name: str = ""  # set by __set_name__
        self._setting_key: str = ""  # namespaced registry key, set at registration
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
                if self._type is object:
                    self._type = getattr(mirrors, "_type", object)
        else:
            self._mirror_key = ""

        # Stamp the widget contract now if the IType is already known:
        # an explicit type_= (registry.define()/_auto_define(), or any setting(...)
        # built outside a class body) or a mirror that inherited a resolved IType
        # above. A class-body ``setting[T](...)`` field with no explicit type_=
        # still has ``_type is object`` here — __set_name__ resolves the IType
        # from the generic subscript and stamps then (this call would be a no-op
        # widget_key="" anyway, since class_identity isn't available yet).
        if isinstance(self._type, type) and issubclass(self._type, IType):
            self._stamp_widget()

    @property
    def _mirror_key(self) -> str:
        """Resolved mirror field key — lazy when mirrors= was given as a descriptor."""
        if self._mirror_descriptor is not None:
            return self._mirror_descriptor._setting_key
        return self.__mirror_key

    @_mirror_key.setter
    def _mirror_key(self, value: str) -> None:
        self.__mirror_key = value

    @property
    def is_cross_mirror(self) -> bool:
        """True for a shadow/watch field that tracks another setting.

        ``_mirror_key`` means only that: a genuine shadow()/watch() points it at
        another setting's key, and the instance cell is kept authoritative for
        it — seeded from the resolved global, synced by ``_on_field_change``."""
        return bool(self._mirror_key)

    def validate(self, value: Any) -> bool:
        """Return True if *value* passes the validator (or if no validator is set)."""
        if self._validator is None:
            return True
        return bool(self._validator(value))

    def _stamp_widget(self) -> None:
        """Compute the final widget contract ONCE: explicit widget= wins, else
        the field IType's declared default. No render-time resolution."""
        identity = getattr(self._type, "class_identity", None)
        spec = self._widget_spec or {}
        self.widget_key: str = spec.get("key") or (getattr(identity, "widget_key", None) or "")
        type_props = (getattr(identity, "widget_config", None) or {}).get("properties", {})
        own_props: dict = {}
        if self._min is not None:
            own_props["min"] = self._min
        if self._max is not None:
            own_props["max"] = self._max
        spec_props = (spec.get("config") or {}).get("properties", {})
        override_props = self._widget_config_override.get("properties", self._widget_config_override)
        self.widget_config: dict = {
            "properties": {**type_props, **own_props, **spec_props, **override_props}
        }

    @property
    def storage_key(self) -> str:
        """Canonical key for this field's cell / ``_set_keys`` entry on a ``Settings``.

        The fully-qualified ``_setting_key`` (``namespace.accessor.field``) once a
        namespacing path (@node / @settings / schema __init_subclass__) has run,
        otherwise the short ``_attr_name`` set by ``__set_name__``. This single
        accessor replaces the ``_setting_key if _setting_key else name`` fallback
        that was previously hand-written at every value-store call site.

        NOTE: this does NOT change the meaning of an empty ``_setting_key`` — that
        still signals "not namespaced, not registry-eligible" to SettingsRegistry.
        Only per-instance value keying is unified here.
        """
        return self._setting_key or self._attr_name

    @overload
    def __get__(self, obj: None, objtype: type | None = None) -> "setting[T]": ...
    @overload
    def __get__(self, obj: object, objtype: type | None = None) -> Any: ...
    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            return self  # class-level access -> descriptor itself

        # THE read path: a pure cell read — no mode branch, no chain walk, no
        # set-or-unset check. The cell is kept correct at write/seed time
        # instead: seeded with the default (plain field) or the resolved global
        # (cross-mirror), written by descriptor sets / edge drives /
        # _on_field_change, and for a wired persistent field _cell_for returns
        # the registry-owned cell the write-through keeps current. A promoted
        # port SHARES this cell (bind_field), so reading the setting and reading
        # the port hit the same object.
        return obj._cell_for(self).get_value()

    def __set__(self, obj: Any, value: Any) -> None:
        if self._read_only:
            raise AttributeError(
                f"'{self._attr_name}' is read-only — it mirrors a global setting "
                f"and cannot be set per-instance."
            )

        if not self.validate(value):
            return

        # No-op if the write matches what the field already RESOLVES to. For a
        # mirror/shadow field with no local override the resolved value is the
        # mirrored global, not _default — so writing that value back must not
        # create a local override (which is_locally_set() would then report as
        # an override, defeating reset). Comparing against the resolved value
        # also terminates the cross-tab echo loop at the model layer, so the
        # settings-panel setter doesn't need its own equality guard.
        old = self.__get__(obj, type(obj))
        if value == old:
            return

        # The value lives in the field's DataField cell; _set_keys carries the
        # set-or-unset opinion (the cell always holds a value, so it can't).
        # Mark the opinion BEFORE the cell write: set_value fires the cell
        # event — the one notification channel — and a subscriber (e.g. the
        # panel's dot-prefix/reset-button updater) must see is_locally_set()
        # already True inside its callback.
        obj._set_keys.add(self.storage_key)
        obj._cell_for(self).set_value(value)


class persistent_setting(setting, Generic[T]):
    """A `setting` whose writes persist through the registry's workspace tier.

    Used by FrameworkSettings and LibrarySettings — every field declared on
    those schemas is auto-promoted to persistent_setting by their
    __init_subclass__. Instantiating this class directly bypasses the
    registration machinery and is unsupported; declare fields as
    ``setting[T](...)`` and let the parent class promote them.

    Behavior change vs `setting`:
        Writes call ``registry.set_global(setting_key, value)`` followed by
        ``registry.save_to_json_debounced()``. The registry's write-through
        then updates its owned cell for this key, whose event notifies every
        borrowing instance's subscribers and bound widgets —
        so this class deliberately writes NO cell itself.

    Falls back to ``super().__set__`` (a per-instance cell write) when the
    instance has no registry wired (e.g. a test fixture) or when the field has
    no namespaced ``_setting_key``, so a schema constructed without a registry
    still stores its value on the instance.
    """

    def __set__(self, obj: Any, value: Any) -> None:
        if self._read_only:
            raise AttributeError(
                f"'{self._attr_name}' is read-only — it mirrors a global setting "
                f"and cannot be set per-instance."
            )

        if not self.validate(value):
            return

        registry: "SettingsRegistry | None" = getattr(obj, "_registry", None)
        if registry is None or not self._setting_key:
            # No registry wired (test fixture), or no namespaced key — fall back
            # to the per-instance cell write (incl. its resolved-value no-op
            # guard).
            super().__set__(obj, value)
            return

        # No-op if the write matches the resolved value — terminates the
        # cross-tab echo loop and avoids a redundant registry write + JSON save.
        if value == self.__get__(obj, type(obj)):
            return

        # registry.set_global fires _notify_subscribers → the registry-owned
        # cell's write-through → the cell event notifies every borrowing
        # instance. We MUST NOT also write the cell here, or subscribers fire
        # twice.
        registry.set_global(self._setting_key, value)
        registry.save_to_json_debounced()


def shadow(src: "setting[T]", **kwargs: Any) -> "setting[T]":
    """Writable mirror of *src* setting. Inherits src metadata; local writes are allowed."""
    return setting(mirrors=src, read_only=False, **kwargs)


def watch(src: "setting[T]", **kwargs: Any) -> "setting[T]":
    """Read-only mirror of *src* setting. Inherits src metadata; local writes raise AttributeError."""
    return setting(mirrors=src, read_only=True, **kwargs)
