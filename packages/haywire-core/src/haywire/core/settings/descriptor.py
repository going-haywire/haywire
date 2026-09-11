# haywire/core/settings/descriptor.py
"""
setting — reactive property descriptor for Settings subclasses.

``__get__`` reads the field's ``DataField`` cell; ``__set__`` writes that cell
and records the local opinion in ``_set_keys``, and the cell's own
``on_changed`` event is the one change-notification channel.
``persistent_setting`` (FrameworkSettings/LibrarySettings) routes writes to
``registry.set_global`` instead. See ADR 0013.

Convenience factories:
    shadow(src, ...)  — writable mirror of src setting
    watch(src, ...)   — mirror of src setting, seeded disabled + outlet-only
                        (the write guard is convention, not enforced)
    graph(src, ...)   — mirror of a field on the owning graph's settings bag
"""

from __future__ import annotations

from enum import Flag, IntEnum, auto
from typing import TYPE_CHECKING, Any, Callable, Generic, TypeVar, overload

from haywire.core.types.base import WrapperType
from haywire.core.types.interface import IType

from .base import SettingDescriptor

if TYPE_CHECKING:
    from haywire.core.settings.registry import SettingsRegistry
    from haywire.core.types.enums import PortType

# The descriptor stores raw Python values, so its value side (default,
# __get__, __set__) is typed ``Any``: mypy cannot project an IType's value type
# (FLOAT -> float) from the subscript. ``_type`` stays strict (``type[T]``).
T = TypeVar("T", bound=IType)


class Promotable(Flag):
    """Which data-port directions a ``setting()`` may be promoted to.

    ``NONE`` bars promotion entirely: use it where a port would be misleading
    rather than ill-typed, such as a restart-required device parameter that a
    live edge could not actually control.

    ``CONFIG`` promotes a field to a pinless ``PortType.CONFIG`` port, which no
    edge can drive. ``INPUT`` groups the two directions whose value arrives
    from outside the panel widget, ``INLET`` and ``CONFIG``, as opposed to
    ``OUTLET``, whose value the setting itself still owns and writes.
    """

    NONE = 0
    INLET = auto()
    OUTLET = auto()
    CONFIG = auto()
    INPUT = INLET | CONFIG
    ALL = INLET | OUTLET | CONFIG


class UiState(IntEnum):
    """Presentation state of a settings field in the properties panel.

    Pure chrome: a DISABLED or HIDDEN field stays fully readable/writable
    from code, keeps its value, and serializes normally.
    Severity-ordered, so ``Settings._effective_ui_state`` composes multiple
    sources by ``max()``: NORMAL < DISABLED < HIDDEN.

    - NORMAL: rendered, interactive.
    - DISABLED: rendered, non-interactive (exists but locked).
    - HIDDEN: row not rendered.
    """

    NORMAL = 0
    DISABLED = 1
    HIDDEN = 2


class setting(SettingDescriptor, Generic[T]):
    """Reactive field descriptor for a ``Settings`` subclass.

    Declare fields on a ``Settings`` subclass to get reactive, typed
    properties with optional UI auto-rendering, validation, mirroring,
    and persistence::

        class MySettings(LibrarySettings):
            threshold = setting[FLOAT](0.5, min=0.0, max=1.0, label='Threshold')
            mode = setting[CHOICES]('fast', widget_config={'options': ['fast', 'precise']}, label='Mode')

    On ``FrameworkSettings`` and ``LibrarySettings``, writes go through the
    registry's workspace tier and persist to ``.haywire/settings.json``. On
    ``NodeSettings`` and plain ``Settings``, writes go to the instance's
    per-field ``DataField`` cell only and are stored with the graph. Authors
    declare ``setting[T](...)`` either way.

    Args:
        default: Initial value — a literal of type ``T``, or a zero-argument
            callable returning ``T`` for late binding (e.g. a source registry
            that doesn't exist at class-definition time). A callable default is
            evaluated once, when the field's cell seeds. With a ``validator``
            set, the default is checked at construction and ``ValueError`` is
            raised if it fails.
        label: Name shown in the UI. Empty falls back to the attribute name.
            Display-only.
        description: Tooltip / inline help text. Display-only.
        category: Grouping key for auto-rendered panels — fields sharing a
            category cluster under one section header. Defaults to ``"root"``
            (no nesting).
        order: Sort key within a category; lower renders first.
        min: Lower bound for numeric widgets, folded into
            ``widget_config["properties"]`` at ``__set_name__`` time. Not
            enforced on writes — use ``validator`` for that.
        max: Upper bound, same rules as ``min``.
        widget: Explicit widget contract built via ``WidgetCls.config(...)``
            (see ``IWidget.config``), e.g.
            ``widget=SelectWidget.config(properties={"options": [...]})``. It
            wins outright over the field IType's declared default widget.
            ``None`` takes the IType's declared ``widget_key``.
        widget_config: Config overrides layered on top of the IType's default
            widget config, e.g.
            ``setting[CHOICES]("fast", widget_config={"options": [...]})``.
            A ``{"properties": {...}}`` wrapper and a bare properties dict are
            equivalent spellings.
        mirrors: Marks this field as a mirror of another setting, either as a
            ``SettingDescriptor`` reference (``mirrors=NodeSkinSettings.studio_skin``),
            which inherits label, description and type from the source at
            construction and resolves the source's setting key lazily, or as a
            plain string key (``mirrors="ui.node.default.skin.studio_skin"``)
            for when no descriptor reference is available. The referenced field
            must be declared on a different class; a same-bag sibling raises
            ``ValueError``. Prefer the ``shadow()``, ``watch()`` and ``graph()``
            factories over passing this directly.
        type_: Explicit IType (e.g. ``type_=FLOAT``). Usually omitted — the
            IType comes from the ``setting[T]`` subscript via ``__set_name__``.
            A Python type raises ``TypeError``, and nothing is inferred from
            ``default``.
        validator: Callable ``(value) -> bool`` returning True if the value is
            valid. ``__set__`` silently drops an invalid write; an invalid
            default raises ``ValueError`` at construction.
        metadata: Free-form dict for application-specific metadata; the
            framework does not consult it. Defaults to ``{}``. The panel reads
            the ``enabled_when`` / ``visible_when`` conventions from it — see
            ``Settings._effective_ui_state``.
        ui_state: The field's initial presentation state. ``DISABLED`` renders
            the widget non-interactive, ``HIDDEN`` removes the row; neither
            affects reads or writes. This seeds only the initial state — the
            live state goes through ``Settings._set_ui_state``, which announces
            on the UI-state channel, never on the value channel.
        promotable: Which port directions this field may be promoted to
            (NodeSettings fields only; default ``Promotable.ALL``). A
            wrapper-typed (``OPTIONAL[T]``) field promotes to a port of its
            element type. ``Promotable.NONE`` leaves no eligible direction, so
            the row menu offers no promotion and ``promote_setting()`` raises.
        promote_default: Seeds this field as promoted in that direction when
            the bag is constructed (NodeSettings fields only), so a
            freshly-dropped node arrives with the face its author intended. A
            graph's saved promotion state always wins, so the user stays free
            to demote. Must be a direction ``promotable=`` allows, checked at
            class-definition time. Prefer it over promoting from
            ``post_init()``, which runs on graph load too — after promotions are
            restored — so a promote there re-applies on every load and the
            user's demotion never sticks.
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
        type_: "type[T] | None" = None,
        validator: "Callable | None" = None,
        metadata: "dict | None" = None,
        ui_state: UiState = UiState.NORMAL,
        promotable: Promotable = Promotable.ALL,
        promote_default: "PortType | None" = None,
    ) -> None:
        self._default = default
        # With type_ absent, _type stays the sentinel ``object`` so __set_name__
        # resolves it from the setting[IType] generic arg and enforces it there.
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
        self._validator = validator
        self._metadata: dict = metadata or {}
        self._ui_state: UiState = ui_state
        self._promotable: Promotable = promotable
        self._promote_default: "PortType | None" = promote_default
        self._validator_lifted: bool = False
        self._attr_name: str = ""  # set by __set_name__
        """the literal attribute name you'd write as ``self.<bag>.<attr_name>``"""
        self._setting_key: str = ""  # namespaced registry key, set at registration
        """the registry key ``<namespace>.<attr_name>``"""
        self._mirror_descriptor: "SettingDescriptor | None" = None  # set when mirrors= is a descriptor
        self._graph_mirror: bool = False  # set True by the graph() factory

        if self._validator is not None and default is not None and not self.validate(default):
            raise ValueError(f"Default value {default!r} fails validation for field '{label or '?'}'")

        if mirrors is not None:
            if isinstance(mirrors, str):
                self._mirror_key: str = mirrors
            else:
                # Descriptor form: the source's key may not be stamped yet, so
                # inherit metadata now and resolve the key lazily (see _mirror_key).
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

        # Stamp only when the IType is already known — an explicit type_= or a
        # mirror that inherited one. A class-body setting[T](...) still has
        # _type is object here and gets stamped by __set_name__ instead.
        if isinstance(self._type, type) and issubclass(self._type, IType):
            self._stamp_widget()
            self._apply_wrapper_rules()

    def _is_wrapper_type(self) -> bool:
        """True when this field's IType wraps another (``OPTIONAL[T]``)."""
        return isinstance(self._type, type) and issubclass(self._type, WrapperType)

    def _apply_wrapper_rules(self, owner: "type | None" = None, name: str = "") -> None:
        """Apply the rules that hold only for a wrapper-typed (``OPTIONAL[T]``) field.

        Lifts the validator so that clearing the field always passes: a
        validator written for the wrapped type then sees present values only.
        No-op for a non-wrapper field, and idempotent. Called once the IType is
        known — from ``__set_name__``, or from the end of ``__init__`` for an
        explicit ``type_=`` — never on the read or write path.
        """
        if not self._is_wrapper_type():
            return

        if self._validator is not None and not self._validator_lifted:
            user_validator = self._validator
            self._validator = lambda value: value is None or bool(user_validator(value))
            self._validator_lifted = True

    def __set_name__(self, owner: type, name: str) -> None:
        if self._mirror_descriptor is not None and self._mirror_descriptor in owner.__dict__.values():
            raise ValueError(
                f"setting field '{name}' on {owner.__name__} mirrors a field declared "
                f"on the same bag ({owner.__name__}) — mirrors= must reference a field "
                f"on a DIFFERENT class (a registered LibrarySettings/FrameworkSettings "
                f"global, or any other class's field). Same-bag mirroring is not "
                f"supported."
            )
        # super() resolves _type from the setting[T] subscript, so the wrapper
        # rules can only run after it.
        super().__set_name__(owner, name)
        self._apply_wrapper_rules(owner, name)

        if self._promote_default is not None:
            # Checked at class definition: a seed promote_setting() would refuse
            # is a declaration bug, not one node failing to build later.
            from haywire.core.node.promotion import eligible_promotion_directions

            eligible = eligible_promotion_directions(self)
            if self._promote_default not in eligible:
                allowed = ", ".join(d.value for d in eligible) or "none"
                raise ValueError(
                    f"setting field '{name}' on {owner.__name__} declares "
                    f"promote_default={self._promote_default.value!r}, which promotable="
                    f"{self._promotable!r} does not allow (allowed: {allowed})."
                )

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
    def is_mirror(self) -> bool:
        """True for a shadow/watch field that tracks another setting's key."""
        return bool(self._mirror_key)

    @property
    def is_graph_mirror(self) -> bool:
        """True for a field declared via the ``graph()`` factory — a mirror
        of a field on the owning graph's settings bag (GraphSettings).

        These are wired cell-to-cell against the graph bag's live cell, not
        through the registry-key channel, so ``is_mirror`` is False for them:
        the source has no ``_setting_key``."""
        return self._graph_mirror

    def validate(self, value: Any) -> bool:
        """Return True if *value* passes the validator (or if no validator is set)."""
        if self._validator is None:
            return True
        return bool(self._validator(value))

    def _stamp_widget(self) -> None:
        """Compute the field's widget contract: an explicit ``widget=`` wins,
        else the field IType's declared default."""
        identity = getattr(self._type, "class_identity", None)
        spec = self._widget_spec or {}
        self.widget_key: str = spec.get("key") or (getattr(identity, "widget_key", None) or "")
        type_props = (getattr(identity, "widget_config", None) or {}).get("properties", {})
        own_props: dict = {}
        if self._min is not None:
            own_props["min"] = self._min
        if self._max is not None:
            own_props["max"] = self._max
        # A wrapper-typed field's non-absent default doubles as the value the
        # panel restores when the user leaves absence. A widget property, so
        # widget_config={"restore": ...} can override it per use.
        if self._default is not None and self._is_wrapper_type():
            own_props["restore"] = self._default
        spec_props = (spec.get("config") or {}).get("properties", {})
        override_props = self._widget_config_override.get("properties", self._widget_config_override)
        self.widget_config: dict = {
            "properties": {**type_props, **own_props, **spec_props, **override_props}
        }

    @property
    def storage_key(self) -> str:
        """Canonical key for this field's cell / ``_set_keys`` entry on a ``Settings``.

        The fully-qualified ``_setting_key`` (``namespace.accessor.field``) once
        a namespacing path (@node / @settings / schema ``__init_subclass__``)
        has run, otherwise the short ``_attr_name`` set by ``__set_name__``. An
        empty ``_setting_key`` still means "not namespaced, not registry-eligible"
        to SettingsRegistry; only per-instance value keying falls back here.
        """
        return self._setting_key or self._attr_name

    @overload
    def __get__(self, obj: None, objtype: type | None = None) -> "setting[T]": ...
    @overload
    def __get__(self, obj: object, objtype: type | None = None) -> Any: ...
    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            return self  # class-level access -> descriptor itself

        # A plain cell read: the cell is kept correct at write and seed time
        # instead. A promoted port shares this cell (bind_field), so reading
        # the setting and reading the port hit the same object.
        return obj._cell_for(self).get_value()

    def __set__(self, obj: Any, value: Any) -> None:
        if not self.validate(value):
            return

        # Compared against the resolved value, not _default: for a mirror with
        # no local override that is the mirrored global, and writing it back
        # must not create an override that then defeats reset. It also ends the
        # cross-tab echo loop here, at the model layer.
        old = self.__get__(obj, type(obj))
        if value == old:
            return

        # Opinion before the cell write: set_value fires the cell event, and a
        # subscriber must already see _is_locally_set() True inside its callback.
        obj._set_keys.add(self.storage_key)
        obj._cell_for(self).set_value(value)


class persistent_setting(setting, Generic[T]):
    """A `setting` whose writes persist through the registry's workspace tier.

    Every field on a ``FrameworkSettings`` or ``LibrarySettings`` schema is
    promoted to this class by the parent's ``__init_subclass__``. Instantiating
    it directly bypasses the registration machinery and is unsupported; declare
    fields as ``setting[T](...)`` instead.

    A write calls ``registry.set_global(setting_key, value)`` and then
    ``registry.save_to_json_debounced()``; the registry's write-through updates
    its owned cell for the key, and that cell's event reaches every borrowing
    instance. This class writes no cell of its own.

    Falls back to ``super().__set__`` (a per-instance cell write) when the
    instance has no registry wired or the field has no namespaced
    ``_setting_key``, so a schema built without a registry still stores its
    value on the instance.
    """

    def __set__(self, obj: Any, value: Any) -> None:
        if not self.validate(value):
            return

        registry: "SettingsRegistry | None" = getattr(obj, "_registry", None)
        if registry is None or not self._setting_key:
            # Per-instance cell write, including its resolved-value no-op guard.
            super().__set__(obj, value)
            return

        # No-op on a write matching the resolved value: ends the cross-tab echo
        # loop and avoids a redundant registry write plus JSON save.
        if value == self.__get__(obj, type(obj)):
            return

        # set_global's write-through updates the registry-owned cell, whose
        # event reaches every borrowing instance; writing the cell here too
        # would fire subscribers twice.
        registry.set_global(self._setting_key, value)
        registry.save_to_json_debounced()


def shadow(src: "setting[T]", **kwargs: Any) -> "setting[T]":
    """Writable mirror of *src* setting. Inherits src metadata; local writes are allowed."""
    return setting(mirrors=src, **kwargs)


def watch(src: "setting[T]", **kwargs: Any) -> "setting[T]":
    """Read-only-by-convention mirror of *src* setting. Inherits src metadata.

    Sugar over ``shadow()``: seeds ``ui_state=UiState.DISABLED`` (a greyed,
    non-interactive widget) and ``promotable=Promotable.OUTLET``. Nothing
    prevents a direct Python write (``obj.field = x``) — read-only is a usage
    convention, not an enforced guarantee.
    """
    return setting(mirrors=src, ui_state=UiState.DISABLED, promotable=Promotable.OUTLET, **kwargs)


def graph(src: "setting[T]", **kwargs: Any) -> "setting[T]":
    """Mirror of a field on the owning graph's settings bag (GraphSettings).

    The graph-tier analogue of ``shadow()``: while unset, the field tracks
    the graph bag's live value; a local set wins; a reset returns it to the
    graph's current value. Tracking needs a graph-attached bag (node → wrapper
    → graph); a detached bag (tests, standalone construction) holds the
    descriptor default and never tracks — there is no registry fallback.

    Raises ``TypeError`` unless *src* is a field declared on a
    ``GraphSettings`` subclass (e.g. ``GraphProperties.default_skin``). For
    framework/library settings use ``shadow()``/``watch()``.
    """
    from haywire.core.settings.settings_graph import GraphSettings

    owner = getattr(src, "_owner_cls", None)
    if not (isinstance(owner, type) and issubclass(owner, GraphSettings)):
        raise TypeError(
            f"graph(src=...) requires a field declared on a GraphSettings subclass; "
            f"got {src!r} (owner: {owner!r}). For framework/library settings use shadow()."
        )
    s = setting(mirrors=src, **kwargs)
    s._graph_mirror = True
    return s
