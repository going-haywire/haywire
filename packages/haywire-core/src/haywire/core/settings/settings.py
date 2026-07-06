# haywire/core/settings/settings.py
"""
Settings — observable setting container for Haywire.

Subclass and declare settings with ``setting()``:

    class FilterSettings(Settings):
        strength = setting[FLOAT](0.5, min=0.0, max=1.0, label='Strength')
        mode     = setting[CHOICES]('fast', widget_config={'options': ['fast', 'precise']})

Cell-authoritative value model:
    Every field's value lives in a ``DataField`` cell (the same cell a port
    uses) and ``__get__`` is a pure cell read on every path. The chain runs at
    write/seed time: a plain field's cell seeds with the descriptor default; a
    cross-mirror (``shadow``/``watch`` of another setting) seeds from the
    resolved global and is synced by ``_on_field_change``; a wired persistent
    field (Framework/Library) borrows THE registry-owned cell, kept current by
    the registry's tier write-through. ``_set_keys`` carries the set-or-unset
    opinion (the cell always holds *a* value, so it can't encode set-ness);
    ``read_only=True`` prevents per-instance writes (watch behaviour).

Supports:
- Direct attribute access (``obj.setting = value``)
- Change notification (``obj.subscribe(callback)`` for the whole bag,
  ``obj.subscribe_field(field, callback)`` for one field — both ride the cell
  event, so every writer notifies: descriptor sets, registry write-through,
  edge drives)
- Serialization (``to_dict()`` / ``from_dict()``)
- Reset (``reset(name)`` / ``reset_all()``)
- Cleanup of subscriptions (``cleanup()``)
"""

from __future__ import annotations

import logging
from typing import Any, Callable, ClassVar, TYPE_CHECKING

from typing_extensions import dataclass_transform

from haywire.core.types.enums import PortType
from haywire.core.types.interface import IType

from .descriptor import persistent_setting, setting, shadow, watch

if TYPE_CHECKING:
    from haywire.core.settings.registry import SettingsRegistry
    from haywire.core.settings.value import SettingValue
    from haywire.core.settings.decorator import SettingsClassIdentity
    from haywire.core.library.identity import LibraryIdentity
    from haywire.core.types.fields import DataField
    from haywire.core.node.data import NodeData

logger = logging.getLogger(__name__)


class PromotedFormatError(Exception):
    """A settings dict is in the pre-promotion-refactor flat ``{field: value}``
    shape and cannot be restored by the current ``{"values", "promoted"}``
    loader. Raised by ``Settings.from_dict``; the node loader catches it,
    resets the bag to defaults, and attaches a WARNING to the node (see
    ``BaseNode._initialize_from_dict``). Hard breaking change — no migration
    (ADR 0019)."""


@dataclass_transform(field_specifiers=(setting, shadow, watch))
class Settings:
    """
    Base Settings class for observable settings.

    Subclasses declare typed settings using ``setting()``.  When a
    ``SettingsRegistry`` is injected, ``setting`` fields gain full
    workspace/global tier resolution.
    """

    # Class-level fallback for subclasses (FrameworkSettings, LibrarySettings)
    # whose registration machinery writes cls._registry. __init__ shadows this
    # with an instance attribute when constructed.
    _registry: "SettingsRegistry | None" = None
    _namespace: ClassVar[str] = ""
    # Set by the settings decorator on registerable subclasses (Library/
    # FrameworkSettings). Declared here so SettingsRegistry can bind
    # BaseRegistry[Settings] against the RegisteredClass structural bound
    # (every managed class has both a class_identity and a class_library).
    class_identity: ClassVar["SettingsClassIdentity"]
    class_library: ClassVar["LibraryIdentity"]

    def __init__(self, registry: "SettingsRegistry | None" = None, node: "NodeData | None" = None) -> None:
        # subscribe() bookkeeping: callback -> [(cell, adapter), ...] so
        # unsubscribe/cleanup can detach the per-field cell adapters.
        self._subscriptions: dict[Callable, list[tuple["DataField", Callable]]] = {}
        # Per-field DataField cell — one cell per declared (IType-typed) field,
        # built lazily by _cell_for. The cell holds the field's value (same cell
        # a port uses).
        self._cells: dict[str, "DataField"] = {}
        # The set-or-unset opinion. A cell ALWAYS holds a value (its default), so
        # cell membership can't distinguish "inheriting" from "set to the default";
        # _set_keys carries that opinion explicitly. storage_key ∈ _set_keys ⇔
        # locally set.
        self._set_keys: set[str] = set()
        # UI-only disabled-state opinion (never persisted, never affects
        # reads/writes, NEVER touches a field's cell — the cell event keeps
        # meaning "the value changed"). Seeded from any field declared
        # setting(..., ui_disabled=True); grown/shrunk later via
        # set_ui_disabled(), which announces transitions on the dedicated
        # UI-state channel below. Declarative same-bag gating (enabled_when)
        # composes with this via OR in the panel — see render_utils.py.
        self._ui_disabled_keys: set[str] = set()
        for _name, _descriptor in type(self)._property_settings().items():
            if _descriptor._ui_disabled:
                self._ui_disabled_keys.add(_descriptor.storage_key)
        # Dedicated UI-state channel: callback(name, disabled) on each flag
        # transition. Separate from the cell/value channel by design (one
        # channel per concern — the NiceGUI BindableProperty model): a
        # chrome change must be structurally incapable of reaching value
        # subscribers (widgets, live-control node handlers, promoted ports).
        self._ui_state_listeners: list[Callable[[str, bool], None]] = []
        self._registry: "SettingsRegistry | None" = registry
        self._cleaned_up: bool = False
        # Back-reference to the owning node (None for standalone Framework/Library
        # settings). Lets promotion resolve node.ports from a bag.
        self._node: "NodeData | None" = node
        # Promotion state — the SINGLE source of truth for which fields are
        # currently promoted to a DATA port and in which direction. Mirrors the
        # per-instance, storage_key-keyed shape of _set_keys/_ui_disabled_keys,
        # but (unlike those) DOES serialize — into this bag's "promoted" block —
        # because a promoted port is regenerated from here on load rather than
        # persisted in the ports block. A field has at most one promoted port
        # (its id IS the storage_key), so this is a single direction per key,
        # never a set. See ADR 0019 and haywire.core.node.promotion.
        self._promoted_keys: dict[str, PortType] = {}

    def _is_locally_set(self, descriptor: setting) -> bool:
        """Return True if this field has a local instance override."""
        return descriptor.storage_key in self._set_keys

    def _local_value(self, descriptor: setting) -> Any:
        """Return this field's locally-set value from its cell. Only meaningful
        when the field is in ``_set_keys``."""
        return self._cell_for(descriptor).get_value()

    def _write_local(self, descriptor: setting, value: Any) -> None:
        """Write *value* into this field's cell and mark it locally set. Used by
        the trusted-restore path (from_dict); the live path goes through the
        descriptor's __set__. Opinion first, then the cell write — the cell
        event must observe is_locally_set() already True."""
        self._set_keys.add(descriptor.storage_key)
        self._cell_for(descriptor).set_value(value)

    def set_promoted(self, name: str, direction: PortType) -> None:
        """Record that field *name* is promoted to a port in *direction*.

        The single source of truth for promotion. Called by
        ``promote_setting`` (interactive AND load-time regen). Unknown *name*:
        logs a warning and ignores (catches typos / stale field names).
        Purely a promotion record — does not touch the field's value cell.
        """
        fields = type(self)._property_settings()
        if name not in fields:
            logger.warning("set_promoted: unknown field %r on %s — ignored", name, type(self).__name__)
            return
        self._promoted_keys[fields[name].storage_key] = direction

    def clear_promoted(self, name: str) -> None:
        """Clear field *name*'s promotion record (no-op if absent/unknown).

        Called by ``demote_setting``. Mirror of :meth:`set_promoted`."""
        fields = type(self)._property_settings()
        if name not in fields:
            return
        self._promoted_keys.pop(fields[name].storage_key, None)

    def is_promoted(self, name: str) -> bool:
        """True if field *name* is currently promoted. False for unknown names."""
        fields = type(self)._property_settings()
        if name not in fields:
            return False
        return fields[name].storage_key in self._promoted_keys

    def get_promoted_direction(self, name: str) -> PortType | None:
        """The direction field *name* is promoted to, or None if not promoted."""
        fields = type(self)._property_settings()
        if name not in fields:
            return None
        return self._promoted_keys.get(fields[name].storage_key)

    def _cell_for(self, descriptor: setting) -> "DataField":
        """Return this field's DataField cell — THE read surface.

        A wired persistent field (FrameworkSettings/LibrarySettings) borrows
        the registry-owned cell for its key ("one cell, N views" — the registry
        keeps it current on every tier change). Every other field owns a
        per-instance cell, created + cached on first call. Settings are
        IType-only (``SettingDescriptor.__set_name__`` enforces it at
        class-definition time), so every field has a cell; a descriptor that
        somehow bypassed enforcement fails loudly here.
        """
        if (
            isinstance(descriptor, persistent_setting)
            and self._registry is not None
            and descriptor._setting_key
        ):
            return self._registry.cell_for(descriptor._setting_key)

        raw_type = descriptor._type
        if not (isinstance(raw_type, type) and issubclass(raw_type, IType)):
            raise TypeError(
                f"setting field {descriptor.storage_key!r} has no IType "
                f"(got {raw_type!r}) — settings are IType-only, there is no "
                f"cell-less fallback store."
            )
        itype = raw_type
        key = descriptor.storage_key
        cell = self._cells.get(key)
        if cell is None:
            # A cross-mirror field (shadow/watch of another setting) has no
            # meaningful descriptor default — its value is the resolved global.
            # Seed the cell with the resolved value so a headless graph is
            # correct before any change fires. A plain field seeds with its own
            # default.
            if descriptor.is_cross_mirror and self._registry is not None:
                seed = self._resolve(descriptor.storage_key, descriptor._mirror_key, descriptor._default)
            else:
                # A callable default is late-binding — evaluated ONCE here at
                # seed time, never on the read path.
                default = descriptor._default
                seed = default() if callable(default) else default
            cell = itype.create_field(default_override={"value": seed})
            cell.field_id = key
            self._cells[key] = cell
        return cell

    # -------------------------------------------------------------------------
    # Resolution chain (registry-wired path)
    # -------------------------------------------------------------------------

    def _resolve(self, field_key: str, mirror_key: str, default: Any) -> Any:
        """
        Full resolution chain:
            local SET > workspace SET > global SET > default
        """
        from haywire.core.settings.value import SettingValue

        registry = self._registry
        assert (
            registry is not None
        )  # only called when a registry is wired (callers gate on _registry is not None)
        key = mirror_key if mirror_key else field_key
        # Local override: the value lives in the field's cell, gated on _set_keys
        # (the cell always holds *a* value, so membership can't stand in for
        # set-ness — see _set_keys).
        local_sv = None
        if field_key in self._set_keys:
            cell = self._cells.get(field_key)
            if cell is not None:
                local_sv = SettingValue.of(cell.get_value())

        def _resolve_default(d: Any) -> Any:
            # Callable defaults are late-binding — evaluated at resolve/seed
            # time only (the read path is a pure cell read).
            return d() if callable(d) else d

        try:
            value, source = registry.resolve(key, local=local_sv)
            if source == "default" and not mirror_key:
                return _resolve_default(default)  # no mirror — use local descriptor's default
            return value
        except KeyError:
            if local_sv is not None:
                return local_sv.value
            return _resolve_default(default)

    def _subscribe_settings(self) -> None:
        """Subscribe all fields that have a _mirror_key. Delegates to _subscribe_setting."""
        for descriptor in type(self)._property_settings().values():
            self._subscribe_setting(descriptor)

    def _subscribe_setting(self, descriptor: setting) -> None:
        """Subscribe a single field's _mirror_key to the registry (no-op if no registry)."""
        if self._registry is None or not descriptor._mirror_key:
            return
        self._registry.subscribe(descriptor._mirror_key, self._on_field_change)

    def _on_field_change(self, full_key: str, value: "SettingValue") -> None:
        """
        Dispatched by the registry when a mirrored field's effective value changes.

        Its ONE job: keep a cross-mirror's shared cell authoritative — write the
        resolved value into it so the cell (which a promoted port may share)
        always holds the current global. Headless-correct, and the cell's own
        event notifies any subscribers. Unset tracks; set ignores — a local
        override suppresses the sync.
        """
        if self._cleaned_up:
            return
        for _attr_name, descriptor in type(self)._property_settings().items():
            if descriptor._mirror_key != full_key or not descriptor.is_cross_mirror:
                continue
            if self._is_locally_set(descriptor):
                continue
            new_val = self._resolve(descriptor.storage_key, descriptor._mirror_key, descriptor._default)
            self._cell_for(descriptor).set_value(new_val)

    # -------------------------------------------------------------------------
    # Subscription — rides the cell event
    # -------------------------------------------------------------------------

    def subscribe(self, callback: Callable) -> None:
        """Register ``callback(name, value, old)`` called on any setting change.

        One adapter per field cell, so EVERY writer notifies uniformly:
        descriptor sets, resets, registry write-through (wired persistent
        fields borrow the registry-owned cell), and edge drives into a
        promoted shared cell."""
        if callback in self._subscriptions:
            return
        adapters: list[tuple["DataField", Callable]] = []
        for attr_name, descriptor in type(self)._property_settings().items():
            cell = self._cell_for(descriptor)

            def adapter(change: Any, _name: str = attr_name, _cb: Callable = callback) -> None:
                try:
                    _cb(_name, change.value, change.old)
                except Exception as e:
                    logger.error(f"subscribe callback error for '{_name}': {e}")

            cell.on_changed.append(adapter)
            adapters.append((cell, adapter))
        self._subscriptions[callback] = adapters
        self._subscribe_settings()

    def subscribe_field(self, field: str, callback: Callable) -> None:
        """Register ``callback(value, old)`` for changes to ONE field.

        A single adapter on the field's cell, so it hears every writer —
        descriptor sets, resets, registry write-through, edge drives. Same
        bookkeeping as :meth:`subscribe`:
        ``unsubscribe(callback)`` and ``cleanup()`` detach it. Idempotent per
        (field, callback); the same callback may watch several fields. Raises
        ``KeyError`` for an unknown field name."""
        fields = type(self)._property_settings()
        if field not in fields:
            raise KeyError(f"No setting '{field}' on {type(self).__name__}")
        descriptor = fields[field]
        cell = self._cell_for(descriptor)
        existing = self._subscriptions.setdefault(callback, [])
        if any(c is cell for c, _ in existing):
            return  # already watching this field with this callback

        def adapter(change: Any, _cb: Callable = callback, _field: str = field) -> None:
            try:
                _cb(change.value, change.old)
            except Exception as e:
                logger.error(f"subscribe_field callback error for '{_field}': {e}")

        cell.on_changed.append(adapter)
        existing.append((cell, adapter))
        self._subscribe_setting(descriptor)

    def unsubscribe(self, callback: Callable) -> None:
        """Remove a previously registered callback (detaches its cell adapters)."""
        for cell, adapter in self._subscriptions.pop(callback, []):
            try:
                cell.on_changed.remove(adapter)
            except ValueError:
                pass

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize to ``{"values": {...}, "promoted": {...}}``.

        ``values``: only fields whose value differs from the descriptor default
        and are locally set (read_only/mirrored fields are never serialized) —
        same value-selection rule as before, now nested under a key.
        ``promoted``: this bag's promotion records, ``storage_key → direction``
        (``"inlet"``/``"outlet"``). A promoted port is regenerated from this on
        load — it is NOT persisted in the node's ports block (ADR 0019).
        """
        fields = type(self)._property_settings()
        values: dict = {}
        for name, descriptor in fields.items():
            if descriptor._read_only:
                continue
            if not self._is_locally_set(descriptor):
                continue
            val = self._local_value(descriptor)
            if val != descriptor._default:
                values[name] = val
        promoted = {key: direction.value for key, direction in self._promoted_keys.items()}
        return {"values": values, "promoted": promoted}

    def from_dict(self, data: dict) -> None:
        """Restore from the ``{"values", "promoted"}`` shape (trusted graph load).

        Values restore exactly as before (direct cell write via ``_write_local``,
        no validator, marked locally set). Promotion records restore into
        ``_promoted_keys``; the node loader then regenerates the actual ports
        (``regenerate_promoted_ports``). Unknown value keys and read_only fields
        are skipped without error (forward compatibility within the new shape).

        Raises ``PromotedFormatError`` if *data* is non-empty but lacks the
        ``"values"`` key — the pre-refactor flat shape. An empty ``{}`` (a bag
        that serialized nothing) is valid and restores nothing.
        """
        if data and "values" not in data:
            raise PromotedFormatError(
                f"{type(self).__name__}: settings dict is in the pre-promotion-refactor "
                f"flat format (no 'values' key); expected {{'values', 'promoted'}}. "
                f"This graph predates ADR 0019 and its settings for this bag cannot be "
                f"restored; the node will load with default settings."
            )
        fields = type(self)._property_settings()
        for attr_name, value in data.get("values", {}).items():
            if attr_name not in fields:
                continue
            descriptor = fields[attr_name]
            if descriptor._read_only:
                continue
            self._write_local(descriptor, value)
        for key, direction_str in data.get("promoted", {}).items():
            self._promoted_keys[key] = PortType(direction_str)

    # -------------------------------------------------------------------------
    # Reset
    # -------------------------------------------------------------------------

    def reset(self, name: str) -> None:
        """Reset a single field to its descriptor default (removes local override)."""
        fields = type(self)._property_settings()
        if name not in fields:
            raise KeyError(f"No setting '{name}' on {type(self).__name__}")
        descriptor = fields[name]
        key = descriptor.storage_key
        if key in self._set_keys:
            old = self._local_value(descriptor)
            self._set_keys.discard(key)
            # Return the cell to the value the field would resolve to with no
            # override. For a mirror field that is the current global (re-seed +
            # resume tracking); for a plain field it is the descriptor default.
            # The cell is never structurally reset — only its *value* returns.
            # set_value (not cell.reset) so the cell event notifies
            # subscribers/widgets of the returned value.
            if descriptor.is_cross_mirror and self._registry is not None:
                new = self._resolve(descriptor.storage_key, descriptor._mirror_key, descriptor._default)
            else:
                default = descriptor._default
                new = default() if callable(default) else default
            if old != new:
                self._cell_for(descriptor).set_value(new)

    def reset_all(self) -> None:
        """Reset all fields to their defaults (clear all local overrides)."""
        for name in type(self)._property_settings():
            self.reset(name)

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    def cleanup(self) -> None:
        """Release subscriptions.  Call on node removal.

        Detaching the cell adapters is MANDATORY for wired persistent fields:
        their cells are registry-owned and outlive this bag."""
        self._cleaned_up = True
        for callback in list(self._subscriptions):
            self.unsubscribe(callback)
        # Symmetric with _subscribe_setting: drop each mirror field's registry
        # subscription so the registry doesn't hold a stale handler.
        if self._registry is not None:
            for descriptor in type(self)._property_settings().values():
                if descriptor._mirror_key:
                    self._registry.unsubscribe(descriptor._mirror_key, self._on_field_change)
        self._ui_state_listeners.clear()

    # -------------------------------------------------------------------------
    # Introspection
    # -------------------------------------------------------------------------

    def is_locally_set(self, name: str) -> bool:
        """Return True if *name* has a local instance override."""
        fields = type(self)._property_settings()
        if name not in fields:
            return False
        return self._is_locally_set(fields[name])

    def set_ui_disabled(self, name: str, disabled: bool) -> None:
        """Set or clear the UI-disabled flag for *name*.

        Purely a display/interaction concern for the properties panel — the
        field's value and writability are completely unaffected; node code
        keeps reading/writing it normally regardless of this flag. Fires the
        UI-state listeners (``subscribe_ui_state``) on an actual transition
        only; idempotent calls are silent. Never touches the field's cell.
        Unknown *name*: logs a warning and ignores (catches typos in
        hand-maintained field-name lists).
        """
        fields = type(self)._property_settings()
        if name not in fields:
            logger.warning("set_ui_disabled: unknown field %r on %s — ignored", name, type(self).__name__)
            return
        key = fields[name].storage_key
        if (key in self._ui_disabled_keys) == disabled:
            return  # no transition — stay silent
        if disabled:
            self._ui_disabled_keys.add(key)
        else:
            self._ui_disabled_keys.discard(key)
        for listener in list(self._ui_state_listeners):
            try:
                listener(name, disabled)
            except Exception as e:
                logger.error(f"ui-state listener error for '{name}': {e}")

    def set_ui_disabled_all(self, disabled: bool) -> None:
        """Set or clear the UI-disabled flag for EVERY field on this bag.

        The bulk form of :meth:`set_ui_disabled`, for whole-bag gating (e.g.
        a node disabling an entire per-stream settings category at once).
        Iterates the bag's own declared fields, so callers need no
        hand-maintained field-name lists. Same contract per field:
        display-only, transition-only listener firing (fields already in the
        target state stay silent), never touches cells.
        """
        for name in type(self)._property_settings():
            self.set_ui_disabled(name, disabled)

    def is_ui_disabled(self, name: str) -> bool:
        """Return True if *name* is currently UI-disabled (manually or by seed).

        This is only HALF the disabled-state check the panel performs — the
        other half, ``enabled_when`` metadata (same-bag declarative gating),
        lives in ``haywire.ui.panel.render_utils`` since it needs the render
        pipeline's own subscription wiring. The panel combines both via OR.
        """
        fields = type(self)._property_settings()
        if name not in fields:
            return False
        return fields[name].storage_key in self._ui_disabled_keys

    def subscribe_ui_state(self, callback: Callable[[str, bool], None]) -> None:
        """Register ``callback(name, disabled)`` for UI-disabled flag transitions.

        The UI-state analogue of :meth:`subscribe` — but a separate channel:
        it fires ONLY for ``set_ui_disabled`` transitions, never for value
        changes, and value subscribers never hear UI-state changes.
        Idempotent per callback."""
        if callback not in self._ui_state_listeners:
            self._ui_state_listeners.append(callback)

    def unsubscribe_ui_state(self, callback: Callable[[str, bool], None]) -> None:
        """Remove a previously registered UI-state callback (no-op if absent)."""
        try:
            self._ui_state_listeners.remove(callback)
        except ValueError:
            pass

    @classmethod
    def _property_settings(cls) -> dict[str, setting]:
        """Return all setting descriptors defined on this class (walks MRO, base-first)."""
        result: dict[str, setting] = {}
        for klass in reversed(cls.__mro__):
            for name, val in klass.__dict__.items():
                if isinstance(val, setting):
                    result[name] = val
        return result
