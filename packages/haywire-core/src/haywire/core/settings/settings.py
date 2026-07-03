# haywire/core/settings/settings.py
"""
Settings — observable setting container for Haywire.

Subclass and declare settings with ``setting()``:

    class FilterSettings(Settings):
        strength = setting[FLOAT](0.5, min=0.0, max=1.0, label='Strength')
        mode     = setting[STRING]('fast', choices=['fast', 'precise'])

Single-cell value model (P4):
    Every declared field owns a per-instance ``DataField`` cell (the same cell a
    port uses), built lazily by ``_cell_for`` from the field's IType. The value
    lives in the cell; ``__get__`` returns ``cell-if-set else default``, where
    "set" is ``_set_keys`` membership (the cell always holds *a* value, so it
    can't itself encode set-or-unset). See ADR 0013.

No registry (plain ``Settings`` / ``NodeSettings``):
    ``__get__`` returns the cell value when locally set, else the descriptor
    default.  Zero registry overhead.

Registry injected (@node / FrameworkSettings / LibrarySettings):
    An unset field's read goes through ``_resolve()`` — the full resolution
    chain. A local override short-circuits the chain via the cell.
    mirrors= on a setting links to a FrameworkSettings/LibrarySettings setting.
    read_only=True on a setting prevents per-instance writes (watch behaviour).

Supports:
- Direct attribute access (``obj.setting = value``)
- on_change callbacks (``setting(on_change='method_name')``)
- Change notification (``obj.subscribe(callback)``)
- Serialization (``to_dict()`` / ``from_dict()``)
- Reset (``reset(name)`` / ``reset_all()``)
- Cleanup of global subscriptions (``cleanup()``)
"""

from __future__ import annotations

import logging
from typing import Any, Callable, ClassVar, TYPE_CHECKING

from typing_extensions import dataclass_transform

from haywire.core.types.interface import IType

from .descriptor import setting, shadow, watch

if TYPE_CHECKING:
    from haywire.core.settings.registry import SettingsRegistry
    from haywire.core.settings.value import SettingValue
    from haywire.core.settings.decorator import SettingsClassIdentity
    from haywire.core.library.identity import LibraryIdentity
    from haywire.core.types.fields import DataField
    from haywire.core.node.data import NodeData

logger = logging.getLogger(__name__)


@dataclass_transform(field_specifiers=(setting, shadow, watch))
class Settings:
    """
    Base Settings class for observable settings.

    Subclasses declare typed settings using ``setting()``.  When a
    ``SettingsRegistry`` is injected (extended mode), ``setting`` fields
    gain full TOML-tier resolution.
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
        self._callbacks: list[Callable] = []
        # Per-field DataField cell — one cell per declared (IType-typed) field,
        # built lazily by _cell_for. The cell holds the field's value (same cell
        # a port uses); this is the store that supersedes the old dict (P4).
        self._cells: dict[str, "DataField"] = {}
        # The set-or-unset opinion. A cell ALWAYS holds a value (its default), so
        # cell membership can't distinguish "inheriting" from "set to the default";
        # _set_keys carries that opinion explicitly (mirrors the registry tiers'
        # set-or-unset design from P2). storage_key ∈ _set_keys ⇔ locally set.
        self._set_keys: set[str] = set()
        self._registry: "SettingsRegistry | None" = registry
        self._cleaned_up: bool = False
        # Back-reference to the owning node (None for standalone Framework/Library
        # settings). Lets promotion resolve node.ports from a bag. Constructor arg —
        # no object.__setattr__ monkeypatch (ADR 0015).
        self._node: "NodeData | None" = node

    def _is_locally_set(self, descriptor: setting) -> bool:
        """Return True if this field has a local instance override (P4)."""
        return descriptor.storage_key in self._set_keys

    def _local_value(self, descriptor: setting) -> Any:
        """Return this field's locally-set value from its cell. Only meaningful
        when the field is in ``_set_keys``."""
        return self._cell_for(descriptor).get_value()

    def _write_local(self, descriptor: setting, value: Any) -> None:
        """Write *value* into this field's cell and mark it locally set. Used by
        the silent-restore path (from_dict); the live path goes through the
        descriptor's __set__."""
        self._cell_for(descriptor).set_value(value)
        self._set_keys.add(descriptor.storage_key)

    def _cell_for(self, descriptor: setting) -> "DataField":
        """Return (creating + caching on first call) this field's DataField cell.

        The cell is built from the field's IType via ``create_field`` and seeded
        with the descriptor default. Cached per ``storage_key``. Settings are
        IType-only (``SettingDescriptor.__set_name__`` enforces it at
        class-definition time), so every field has a cell; a descriptor that
        somehow bypassed enforcement fails loudly here.
        """
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
            # meaningful descriptor default — its value is the resolved global
            # (P5 Task 2.5). Seed the cell with the resolved value so a headless
            # graph is correct before any change fires. A plain field (and a
            # self-namespaced persistent field) seeds with its own default.
            if descriptor.is_cross_mirror and self._registry is not None:
                seed = self._resolve(descriptor.storage_key, descriptor._mirror_key, descriptor._default)
            else:
                default = descriptor._default
                seed = default() if callable(default) else default
            cell = itype.create_field(default_override={"value": seed})
            self._cells[key] = cell
        return cell

    # -------------------------------------------------------------------------
    # Extended mode: resolution chain
    # -------------------------------------------------------------------------

    def _resolve(self, field_key: str, mirror_key: str, default: Any) -> Any:
        """
        Full resolution chain (extended mode):
            local SET > workspace SET > global SET > default
        """
        from haywire.core.settings.value import SettingValue

        registry = self._registry
        assert (
            registry is not None
        )  # _resolve only called from extended mode (descriptor gates on _registry is not None)
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
        """Subscribe a single field's _mirror_key to the registry (extended mode, no-op if no registry)."""
        if self._registry is None or not descriptor._mirror_key:
            return
        self._registry.subscribe(descriptor._mirror_key, self._on_field_change)

    def _on_field_change(self, full_key: str, value: "SettingValue") -> None:
        """
        Dispatched by the registry when a mirrored field's effective value changes.

        "Unset tracks; set ignores" (DECISIONS.md §A): when the instance has a
        local override the resolved value is unchanged, so the callback is
        suppressed. With no local override the field re-resolves and fires.
        """
        if self._cleaned_up:
            return
        for attr_name, descriptor in type(self)._property_settings().items():
            if descriptor._mirror_key != full_key:
                continue
            if self._is_locally_set(descriptor):
                continue
            # Keep a cross-mirror's shared cell authoritative: write the resolved
            # value into it so the cell (which a promoted port may share) always
            # holds the current global. Headless-correct — no UI subscriber
            # required (P5 Task 2.5). A self-namespaced persistent field resolves
            # from the registry tier, so its cell is not written here.
            new_val = self._resolve(descriptor.storage_key, descriptor._mirror_key, descriptor._default)
            if descriptor.is_cross_mirror:
                self._cell_for(descriptor).set_value(new_val)
            self._on_property_change(attr_name, new_val, None, descriptor._on_change or "")

    # -------------------------------------------------------------------------
    # Subscription
    # -------------------------------------------------------------------------

    def subscribe(self, callback: Callable) -> None:
        """Register ``callback(name, value, old)`` called on any setting change."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)
        self._subscribe_settings()

    def unsubscribe(self, callback: Callable) -> None:
        """Remove a previously registered callback."""
        try:
            self._callbacks.remove(callback)
        except ValueError:
            pass

    # -------------------------------------------------------------------------
    # Change hook (called also by field.__set__)
    # -------------------------------------------------------------------------

    def _on_property_change(self, name: str, value: Any, old: Any, on_change: str = "") -> None:
        """Called when a setting value changes. Fires on_change method and all subscribe() callbacks."""
        if on_change:
            method = getattr(self, on_change, None)
            if method is not None:
                try:
                    method(value, name)
                except TypeError:
                    try:
                        method(value)
                    except Exception as e:
                        logger.error(f"on_change error for '{name}': {e}")
        for cb in list(self._callbacks):
            try:
                cb(name, value, old)
            except Exception as e:
                logger.error(f"subscribe callback error for '{name}': {e}")

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def to_dict(self) -> dict:
        """
        Return only fields whose value differs from the descriptor default.

        Extended mode: only locally-set fields (not inherited from global tiers).
        Simple mode: any field whose current value differs from its default.
        read_only (mirrored) fields are never serialized.
        """
        fields = type(self)._property_settings()
        result: dict = {}
        for name, descriptor in fields.items():
            if descriptor._read_only:
                continue
            if not descriptor._stored:
                continue
            if not self._is_locally_set(descriptor):
                continue
            val = self._local_value(descriptor)
            if val != descriptor._default:
                result[name] = val
        return result

    def from_dict(self, data: dict, *, silent: bool = True) -> None:
        """
        Restore values from *data*.

        silent=True (default): writes directly into the field's cell — no
            callbacks fired. Used during deserialization (graph load).
        silent=False: uses normal setattr — callbacks fire.
            Used for live updates.

        Unknown keys are silently ignored (forward compatibility).
        read_only fields are silently skipped.
        """
        fields = type(self)._property_settings()
        for attr_name, value in data.items():
            if attr_name not in fields:
                continue
            descriptor = fields[attr_name]
            if descriptor._read_only:
                continue
            if silent:
                self._write_local(descriptor, value)
            else:
                setattr(self, attr_name, value)

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
            # resume tracking, P5 Task 2.5); for a plain field it is the
            # descriptor default. The cell is never structurally reset — only its
            # *value* returns (DECISIONS §C3).
            cell = self._cell_for(descriptor)
            if descriptor.is_cross_mirror and self._registry is not None:
                new = self._resolve(descriptor.storage_key, descriptor._mirror_key, descriptor._default)
                cell.set_value(new)
            else:
                cell.reset()
                new = descriptor._default
            if old != new:
                self._on_property_change(name, new, old)

    def reset_all(self) -> None:
        """Reset all fields to their defaults (clear all local overrides)."""
        for name in type(self)._property_settings():
            self.reset(name)

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    def cleanup(self) -> None:
        """Release global namespace subscriptions.  Call on node removal."""
        self._cleaned_up = True
        self._callbacks.clear()
        # Symmetric with _subscribe_setting: drop each mirror field's registry
        # subscription so the registry doesn't hold a stale handler (P5 Task 2.5).
        if self._registry is not None:
            for descriptor in type(self)._property_settings().values():
                if descriptor._mirror_key:
                    self._registry.unsubscribe(descriptor._mirror_key, self._on_field_change)

    # -------------------------------------------------------------------------
    # Introspection
    # -------------------------------------------------------------------------

    def is_locally_set(self, name: str) -> bool:
        """Return True if *name* has a local instance override."""
        fields = type(self)._property_settings()
        if name not in fields:
            return False
        return self._is_locally_set(fields[name])

    @classmethod
    def _property_settings(cls) -> dict[str, setting]:
        """Return all setting descriptors defined on this class (walks MRO, base-first)."""
        result: dict[str, setting] = {}
        for klass in reversed(cls.__mro__):
            for name, val in klass.__dict__.items():
                if isinstance(val, setting):
                    result[name] = val
        return result
