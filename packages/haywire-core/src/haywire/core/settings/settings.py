# haywire/core/settings/settings.py
"""
Settings — observable setting container for Haywire.

Subclass and declare settings with ``setting()``:

    class FilterSettings(Settings):
        strength = setting[FLOAT](0.5, min=0.0, max=1.0, label='Strength')
        mode     = setting[CHOICES]('fast', widget_config={'options': ['fast', 'precise']})

Every field's value lives in a ``DataField`` cell — the same cell a promoted
port uses — while ``_set_keys`` records which fields are locally set. See
ADR 0013.

Supports:
- Direct attribute access (``obj.setting = value``)
- Change notification (``obj._subscribe(callback)`` for the whole bag,
  ``obj._subscribe_field(field, callback)`` for one field — both ride the cell
  event, so every writer notifies: descriptor sets, registry write-through,
  edge drives)
- Serialization (``_to_dict()`` / ``_from_dict()``)
- Reset (``_reset(name)`` / ``_reset_all()``)
- Cleanup of subscriptions (``_cleanup()``)
"""

from __future__ import annotations

import logging
from typing import Any, Callable, ClassVar, NamedTuple, TypeVar, TYPE_CHECKING

from typing_extensions import dataclass_transform

from haywire.core.types.enums import PortType, ShowWidgetStrategy, default_show_widget
from haywire.core.types.interface import IType

from .descriptor import UiState, persistent_setting, setting

if TYPE_CHECKING:
    from haywire.core.settings.registry import SettingsRegistry
    from haywire.core.settings.value import SettingValue
    from haywire.core.settings.decorator import SettingsClassIdentity
    from haywire.core.library.identity import LibraryIdentity
    from haywire.core.types.fields import DataField
    from haywire.core.node.data import NodeData
    from haywire.core.graph.base import BaseGraph

logger = logging.getLogger(__name__)


class PromotedFormatError(Exception):
    """A settings dict is in the flat ``{field: value}`` shape, which
    ``Settings._from_dict`` cannot restore: it expects
    ``{"values", "promoted"}``. There is no migration."""


class Promotion(NamedTuple):
    """One field's promotion record: the port direction, and the user's
    widget-visibility choice for the generated port.

    ``show_widget`` is ``None`` whenever the port uses its direction's default
    (``default_show_widget``), which is what every promotion starts as; only a
    user who changed it through the pin menu stores anything here.
    """

    direction: PortType
    show_widget: ShowWidgetStrategy | None = None


@dataclass_transform(field_specifiers=(setting,))
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
    # BaseRegistry[Settings] against the RegisteredClass structural bound.
    class_identity: ClassVar["SettingsClassIdentity"]
    class_library: ClassVar["LibraryIdentity"]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Reject field names that would collide with the framework's own members.

        A field name may not start with ``_`` (every framework member on a bag
        is ``_``-prefixed, while field names are public identifiers that become
        graph-JSON keys and panel labels) and may not match a public member of
        ``Settings``. Either raises ``TypeError``.

        Only fields declared on *this* class are checked, so redeclaring an
        inherited field to narrow a shared bag stays legal.
        """
        super().__init_subclass__(**kwargs)

        reserved = {name for name in dir(Settings) if not name.startswith("_")}
        for name, value in vars(cls).items():
            if not isinstance(value, setting):
                continue
            if name.startswith("_"):
                raise TypeError(
                    f"{cls.__name__}.{name}: a setting field name may not start with '_'. "
                    f"Field names are public identifiers — they become graph/TOML keys and "
                    f"panel labels — while every framework member on a settings bag is "
                    f"'_'-prefixed. Rename the field (e.g. '{name.lstrip('_')}'); to hide a "
                    f"field from the panel use ui_state=UiState.HIDDEN instead."
                )
            if name in reserved:
                raise TypeError(
                    f"{cls.__name__}.{name}: '{name}' is a public member of Settings, so a "
                    f"field of that name would shadow it. Choose a different field name."
                )

    def __init__(self, registry: "SettingsRegistry | None" = None, node: "NodeData | None" = None) -> None:
        # subscribe() bookkeeping: callback -> [(cell, adapter), ...] so
        # unsubscribe/cleanup can detach the per-field cell adapters.
        self._subscriptions: dict[Callable, list[tuple["DataField", Callable]]] = {}
        # One cell per declared field, built lazily by _cell_for. It holds the
        # field's value — the same cell a promoted port uses.
        self._cells: dict[str, "DataField"] = {}
        # The set-or-unset opinion: storage_key in _set_keys iff locally set.
        # A cell always holds a value, so membership there cannot say it.
        self._set_keys: set[str] = set()
        # Presentation state only: never persisted, never affects reads/writes,
        # never touches a field's cell. Sparse — only non-NORMAL entries, keyed
        # by storage_key — and seeded from setting(..., ui_state=...).
        self._ui_states: dict[str, UiState] = {}
        for _name, _descriptor in type(self)._settings_descriptors().items():
            if _descriptor._ui_state is not UiState.NORMAL:
                self._ui_states[_descriptor.storage_key] = _descriptor._ui_state
        # Dedicated UI-state channel: callback(name, state) on each transition.
        # Value subscribers never hear a chrome change, and vice versa.
        self._ui_state_listeners: list[Callable[[str, UiState], None]] = []
        self._registry: "SettingsRegistry | None" = registry
        self._cleaned_up: bool = False
        # Back-reference to the owning node (None for standalone Framework/Library
        # settings). Lets promotion resolve node.ports from a bag.
        self._node: "NodeData | None" = node
        # The source of truth for which fields are promoted to a data port and
        # in which direction, keyed by storage_key. Unlike _set_keys/_ui_states
        # it serializes, into this bag's "promoted" block, and a promoted port
        # is regenerated from it on load. A field has at most one promoted port,
        # so this is one direction per key. See haywire.core.node.promotion.
        self._promoted_keys: dict[str, Promotion] = {}
        # setting(promote_default=...) seeds a promotion record at construction.
        # _from_dict() clears the block before restoring, so a saved graph wins
        # and a user's demotion sticks; a bag no saved graph mentions keeps its
        # seeds.
        for _descriptor in type(self)._settings_descriptors().values():
            _seed = getattr(_descriptor, "_promote_default", None)
            if _seed is not None:
                self._promoted_keys[_descriptor.storage_key] = Promotion(_seed)
        # Graph-mirror wiring: storage_key -> (src cell, adapter) for fields
        # synced cell-to-cell against the owning graph's bag.
        self._graph_mirror_adapters: dict[str, tuple["DataField", Callable]] = {}

    def _is_set(self, descriptor: setting) -> bool:
        """Return True if this field has a local instance override."""
        return descriptor.storage_key in self._set_keys

    def _local_value(self, descriptor: setting) -> Any:
        """Return this field's locally-set value from its cell. Only meaningful
        when the field is in ``_set_keys``."""
        return self._cell_for(descriptor).get_value()

    def _write_local(self, descriptor: setting, value: Any) -> None:
        """Write *value* into this field's cell and mark it locally set.

        Skips the validator. The opinion is recorded before the cell write, so
        a subscriber sees ``_is_locally_set()`` already True."""
        self._set_keys.add(descriptor.storage_key)
        self._cell_for(descriptor).set_value(value)

    def _set_promoted(
        self,
        name: str,
        direction: PortType,
        show_widget: ShowWidgetStrategy | None = None,
    ) -> None:
        """Record that field *name* is promoted to a port in *direction*.

        Purely a promotion record — does not touch the field's value cell.
        Unknown *name*: logs a warning and ignores. *show_widget* records the
        user's widget-visibility choice for the generated port; ``None`` means
        "use the direction's default".
        """
        fields = type(self)._settings_descriptors()
        if name not in fields:
            logger.warning("set_promoted: unknown field %r on %s — ignored", name, type(self).__name__)
            return
        self._promoted_keys[fields[name].storage_key] = Promotion(direction, show_widget)

    def _set_promoted_show_widget(self, name: str, strategy: ShowWidgetStrategy | None) -> None:
        """Record *name*'s widget-visibility choice, keeping its direction.

        No-op for an unknown or unpromoted field — the record only exists
        while the field is promoted, so there is nothing to attach a choice
        to otherwise. Pass ``None`` to fall back to the direction default.
        """
        fields = type(self)._settings_descriptors()
        if name not in fields:
            return
        storage_key = fields[name].storage_key
        existing = self._promoted_keys.get(storage_key)
        if existing is None:
            return
        self._promoted_keys[storage_key] = existing._replace(show_widget=strategy)

    def _get_promoted_show_widget(self, name: str) -> ShowWidgetStrategy | None:
        """*name*'s recorded widget-visibility choice, or None when it uses the
        direction default (or is not promoted at all)."""
        fields = type(self)._settings_descriptors()
        if name not in fields:
            return None
        record = self._promoted_keys.get(fields[name].storage_key)
        return record.show_widget if record is not None else None

    def _clear_promoted(self, name: str) -> None:
        """Clear field *name*'s promotion record (no-op if absent/unknown)."""
        fields = type(self)._settings_descriptors()
        if name not in fields:
            return
        self._promoted_keys.pop(fields[name].storage_key, None)

    def _is_promoted(self, name: str) -> bool:
        """True if field *name* is currently promoted. False for unknown names."""
        fields = type(self)._settings_descriptors()
        if name not in fields:
            return False
        return fields[name].storage_key in self._promoted_keys

    def _get_promoted_direction(self, name: str) -> PortType | None:
        """The direction field *name* is promoted to, or None if not promoted."""
        fields = type(self)._settings_descriptors()
        if name not in fields:
            return None
        record = self._promoted_keys.get(fields[name].storage_key)
        return record.direction if record is not None else None

    def _promote(self, field: str, direction: PortType = PortType.INLET) -> None:
        """Promote *field* to a data port in *direction*.

        Sugar over ``haywire.core.node.promotion.promote_setting``, e.g.
        ``self.my_bag._promote("choice_field", PortType.CONFIG)``. No-op if
        *field* is already promoted. Raises ``ValueError`` when the bag is not
        node-bound, and for an ineligible direction (see
        ``eligible_promotion_directions``).
        """
        from haywire.core.node.promotion import bag_accessor, promote_setting

        if self._node is None:
            raise ValueError(
                f"{type(self).__name__}.promote({field!r}): bag has no bound node "
                f"(self._node is None) — promotion requires a node-bound bag."
            )
        accessor = bag_accessor(self._node, self)
        if accessor is None:
            raise ValueError(
                f"{type(self).__name__}.promote({field!r}): bag is not registered "
                f"as a settings bag on its bound node."
            )
        promote_setting(self._node, accessor, field, direction)

    def _demote(self, field: str) -> None:
        """Remove *field*'s promoted port, if any. Sugar over
        ``haywire.core.node.promotion.demote_setting``. No-op if *field* is not
        currently promoted or the bag is not node-bound."""
        fields = type(self)._settings_descriptors()
        if field not in fields or self._node is None:
            return
        storage_key = fields[field].storage_key
        if storage_key not in self._promoted_keys:
            return
        from haywire.core.node.promotion import demote_setting

        demote_setting(self._node, storage_key)

    def _owning_graph(self) -> "BaseGraph | None":
        """The graph this bag can reach: its own (GraphSettings) or its
        node's (node → wrapper → graph). None for standalone bags."""
        graph_obj = getattr(self, "_graph", None)
        if graph_obj is not None:
            return graph_obj
        if self._node is None:
            return None
        wrapper = getattr(self._node, "wrapper", None)
        if wrapper is None:
            return None
        return getattr(wrapper, "graph", None)

    def _graph_src_cell(self, descriptor: setting) -> "DataField | None":
        """The live cell of a graph mirror's src field on the owning graph's
        bag — or None when detached (standalone bag, node not in a graph,
        graph lacks the src bag). Detached fields hold the descriptor
        default and are not live."""
        if not descriptor.is_graph_mirror:
            return None
        src = descriptor._mirror_descriptor
        owner = getattr(src, "_owner_cls", None)
        if src is None or owner is None:
            return None
        graph_obj = self._owning_graph()
        if graph_obj is None:
            return None
        bag = graph_obj.settings_bag_for(owner)
        if bag is None or bag is self:
            return None
        if not isinstance(src, setting):
            return None
        return bag._cell_for(src)

    def _cell_for(self, descriptor: setting) -> "DataField":
        """Return this field's DataField cell — the read surface for its value.

        A wired persistent field (FrameworkSettings/LibrarySettings) borrows
        the registry-owned cell for its key, which the registry keeps current
        on every tier change. Every other field owns a per-instance cell,
        created and cached on first call. Raises ``TypeError`` for a field
        whose type is not an IType.
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
            # A cross-mirror field's value is the resolved global, not its own
            # descriptor default, so seed it from there — a headless graph is
            # then correct before any change fires.
            src_cell = self._graph_src_cell(descriptor) if descriptor.is_graph_mirror else None
            if src_cell is not None:
                # Graph mirror on an attached bag: seed from the src field's
                # live cell (the graph bag restores before nodes on load).
                seed = src_cell.get_value()
            elif descriptor.is_mirror and self._registry is not None:
                seed = self._resolve(descriptor.storage_key, descriptor._mirror_key, descriptor._default)
            else:
                # Plain field, detached graph mirror, or no registry: the
                # descriptor default, a callable one evaluated once, here.
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
        # A local override lives in the field's cell, gated on _set_keys: the
        # cell always holds a value, so it cannot say whether one was set.
        local_sv = None
        if field_key in self._set_keys:
            cell = self._cells.get(field_key)
            if cell is not None:
                local_sv = SettingValue.of(cell.get_value())

        def _resolve_default(d: Any) -> Any:
            # A callable default is late-binding, evaluated at resolve time.
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
        """Wire every mirror field on this bag to what it mirrors."""
        for descriptor in type(self)._settings_descriptors().values():
            self._subscribe_setting(descriptor)

    def _subscribe_setting(self, descriptor: setting) -> None:
        """Keep a single mirror field's cell synced to what it mirrors.

        Registry-key mirror → registry notification channel. Graph mirror →
        cell adapter on the src bag's cell (detached bags stay at the
        descriptor default, not live). No-op for plain fields."""
        if descriptor.is_graph_mirror:
            self._subscribe_graph_mirror(descriptor)
            return
        if descriptor._mirror_descriptor is not None and not descriptor._mirror_key:
            # A plain shadow() pointed at a per-instance bag field: it has no
            # registry key to ride and was not declared via graph(), so it
            # would silently never track. Fail loudly at wiring time.
            raise TypeError(
                f"setting field '{descriptor.storage_key}' on {type(self).__name__} shadows a "
                f"field on a per-instance bag ({descriptor._mirror_descriptor!r}) — declare it "
                f"with graph(src=...) instead of shadow()."
            )
        if self._registry is None or not descriptor._mirror_key:
            return
        self._registry.subscribe(descriptor._mirror_key, self._on_field_change)

    def _subscribe_graph_mirror(self, descriptor: setting) -> None:
        """Wire one graph mirror: unset tracks, set ignores.

        Attaches one adapter to the src field's cell on the owning graph's bag;
        the adapter writes changes into this field's own cell unless a local
        opinion suppresses it. No-op on a detached bag, which keeps the
        descriptor default. Idempotent per field."""
        key = descriptor.storage_key
        if key in self._graph_mirror_adapters:
            return
        src_cell = self._graph_src_cell(descriptor)
        if src_cell is None:
            return  # detached — seeded with the descriptor default
        self._cell_for(descriptor)  # ensure own cell exists + is seeded first

        def _adapter(change: Any, _descriptor: setting = descriptor) -> None:
            if self._cleaned_up or self._is_set(_descriptor):
                return
            self._cell_for(_descriptor).set_value(change.value)

        src_cell.on_changed.append(_adapter)
        self._graph_mirror_adapters[key] = (src_cell, _adapter)

    def _on_field_change(self, full_key: str, value: "SettingValue") -> None:
        """
        Dispatched by the registry when a mirrored field's effective value changes.

        Writes the newly resolved value into the cell of every cross-mirror
        field pointing at *full_key*, so the cell — which a promoted port may
        share — always holds the current global, and its own event notifies
        subscribers. Unset tracks, set ignores: a local override suppresses
        the sync.
        """
        if self._cleaned_up:
            return
        for _attr_name, descriptor in type(self)._settings_descriptors().items():
            if descriptor._mirror_key != full_key or not descriptor.is_mirror:
                continue
            if self._is_set(descriptor):
                continue
            new_val = self._resolve(descriptor.storage_key, descriptor._mirror_key, descriptor._default)
            self._cell_for(descriptor).set_value(new_val)

    # -------------------------------------------------------------------------
    # Subscription — rides the cell event
    # -------------------------------------------------------------------------

    def _subscribe(self, callback: Callable) -> None:
        """Register ``callback(name, value, old)`` called on any setting change.

        One adapter per field cell, so every writer notifies uniformly:
        descriptor sets, resets, registry write-through, and edge drives into
        a promoted shared cell. Idempotent per callback; a callback that raises
        is logged and does not stop the others."""
        if callback in self._subscriptions:
            return
        adapters: list[tuple["DataField", Callable]] = []
        for attr_name, descriptor in type(self)._settings_descriptors().items():
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

    def _subscribe_field(self, field: str, callback: Callable) -> None:
        """Register ``callback(value, old)`` for changes to one field.

        A single adapter on the field's cell, so it hears every writer —
        descriptor sets, resets, registry write-through, edge drives.
        :meth:`_unsubscribe` and :meth:`_cleanup` detach it. Idempotent per
        (field, callback); the same callback may watch several fields. Raises
        ``KeyError`` for an unknown field name."""
        fields = type(self)._settings_descriptors()
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

    def _unsubscribe(self, callback: Callable) -> None:
        """Remove a previously registered callback (detaches its cell adapters)."""
        for cell, adapter in self._subscriptions.pop(callback, []):
            try:
                cell.on_changed.remove(adapter)
            except ValueError:
                pass

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def _to_dict(self) -> dict:
        """Serialize to the format-v3 ``{"values": {...}, "promoted": {...}}`` shape.

        ``values`` holds only fields that are locally set and whose value
        differs from the descriptor default, keyed by attribute name.

        ``promoted`` holds this bag's promotion records, ``storage_key → {...}``.
        Each record carries ``"direction"`` (``"inlet"``/``"outlet"``/
        ``"config"``), and ``"show_widget"`` only when the user chose a strategy
        other than the direction's default. A promoted port is regenerated from
        this on load rather than persisted in the node's ports block.
        """
        fields = type(self)._settings_descriptors()
        values: dict = {}
        for name, descriptor in fields.items():
            if not self._is_set(descriptor):
                continue
            val = self._local_value(descriptor)
            if val != descriptor._default:
                values[name] = val
        promoted: dict[str, dict] = {}
        for key, record in self._promoted_keys.items():
            entry: dict[str, str] = {"direction": record.direction.value}
            # A strategy that restates the direction default is omitted; the
            # reader re-derives it. Mirrors how `values` skips defaults.
            if record.show_widget is not None and record.show_widget is not default_show_widget(
                record.direction
            ):
                entry["show_widget"] = record.show_widget.value
            promoted[key] = entry
        return {"values": values, "promoted": promoted}

    def _from_dict(self, data: dict) -> None:
        """Restore from the ``{"values", "promoted"}`` shape (trusted graph load).

        Values are written straight into their cells and marked locally set,
        bypassing the validator; an unknown value key is skipped silently.
        Promotion records restore into ``_promoted_keys``, replacing any
        ``promote_default`` seeds, and the actual ports are regenerated
        separately. An empty ``{}`` is valid and restores nothing.

        Raises ``PromotedFormatError`` when *data* is non-empty but has no
        ``"values"`` key, and when a promotion record is not a dict — a bare
        direction string is the pre-v3 shape, which the prehydrator rewrites
        before any bag sees it.
        """
        if data and "values" not in data:
            raise PromotedFormatError(
                f"{type(self).__name__}: settings dict is in the pre-promotion-refactor "
                f"flat format (no 'values' key); expected {{'values', 'promoted'}}. "
                f"This graph's settings for this bag cannot be restored; the node will "
                f"load with default settings."
            )
        fields = type(self)._settings_descriptors()
        for attr_name, value in data.get("values", {}).items():
            if attr_name not in fields:
                continue
            descriptor = fields[attr_name]
            self._write_local(descriptor, value)
        # The saved block is authoritative, so drop promote_default seeds first:
        # a demotion is an absence there, and an absence only beats a seed once
        # the seed is gone.
        self._promoted_keys.clear()
        for key, record in data.get("promoted", {}).items():
            if not isinstance(record, dict):
                raise PromotedFormatError(
                    f"{type(self).__name__}: promotion record for {key!r} is "
                    f"{record!r}, not a dict — this is the pre-v3 shape and should "
                    f"have been migrated by the prehydrator before reaching here."
                )
            direction = PortType(record["direction"])
            raw_strategy = record.get("show_widget")
            self._promoted_keys[key] = Promotion(
                direction,
                ShowWidgetStrategy(raw_strategy) if raw_strategy is not None else None,
            )

    # -------------------------------------------------------------------------
    # Reset
    # -------------------------------------------------------------------------

    def _reset(self, name: str) -> None:
        """Reset a single field to its descriptor default (removes local override)."""
        fields = type(self)._settings_descriptors()
        if name not in fields:
            raise KeyError(f"No setting '{name}' on {type(self).__name__}")
        descriptor = fields[name]
        key = descriptor.storage_key
        if key in self._set_keys:
            old = self._local_value(descriptor)
            self._set_keys.discard(key)
            # Return the cell to the value the field resolves to with no
            # override: the current global for a mirror, the descriptor default
            # for a plain field. set_value, not cell.reset, so the cell event
            # notifies subscribers and widgets of the returned value.
            src_cell = self._graph_src_cell(descriptor) if descriptor.is_graph_mirror else None
            if src_cell is not None:
                new = src_cell.get_value()
            elif descriptor.is_mirror and self._registry is not None:
                new = self._resolve(descriptor.storage_key, descriptor._mirror_key, descriptor._default)
            else:
                default = descriptor._default
                new = default() if callable(default) else default
            if old != new:
                self._cell_for(descriptor).set_value(new)

    def _reset_all(self) -> None:
        """Reset all fields to their defaults (clear all local overrides)."""
        for name in type(self)._settings_descriptors():
            self._reset(name)

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    def _cleanup(self) -> None:
        """Release every subscription and adapter this bag holds. Call on node removal.

        Required for wired persistent fields and graph mirrors: their cells are
        owned by the registry or the graph and outlive this bag."""
        self._cleaned_up = True
        for callback in list(self._subscriptions):
            self._unsubscribe(callback)
        # Symmetric with _subscribe_setting: drop each mirror field's registry
        # subscription so the registry doesn't hold a stale handler.
        if self._registry is not None:
            for descriptor in type(self)._settings_descriptors().values():
                if descriptor._mirror_key:
                    self._registry.unsubscribe(descriptor._mirror_key, self._on_field_change)
        # Detach graph-mirror adapters: the src cells are graph-owned and
        # outlive this bag, same rule as registry-owned cells.
        for cell, adapter in self._graph_mirror_adapters.values():
            try:
                cell.on_changed.remove(adapter)
            except ValueError:
                pass
        self._graph_mirror_adapters.clear()
        self._ui_state_listeners.clear()

    # -------------------------------------------------------------------------
    # Introspection
    # -------------------------------------------------------------------------

    def _is_locally_set(self, name: str) -> bool:
        """Return True if field *name* has a local instance override.

        Takes a field name; :meth:`_is_set` is the descriptor-taking sibling.
        A non-string raises ``TypeError`` rather than silently answering False;
        an unknown name returns False.
        """
        if not isinstance(name, str):
            raise TypeError(
                f"_is_locally_set() takes a field name, got {type(name).__name__}. "
                f"For a descriptor use _is_set()."
            )
        fields = type(self)._settings_descriptors()
        if name not in fields:
            return False
        return self._is_set(fields[name])

    def _set_ui_state(self, name: str, state: UiState) -> None:
        """Set the presentation state for *name* (``UiState.NORMAL`` clears it).

        Display only: the field's value and writability are unaffected, and the
        field's cell is never touched. Fires the UI-state listeners
        (:meth:`_subscribe_ui_state`) on an actual transition only, so a
        repeated call is silent. Unknown *name*: logs a warning and ignores.
        """
        fields = type(self)._settings_descriptors()
        if name not in fields:
            logger.warning("set_ui_state: unknown field %r on %s — ignored", name, type(self).__name__)
            return
        key = fields[name].storage_key
        if self._ui_states.get(key, UiState.NORMAL) is state:
            return  # no transition — stay silent
        if state is UiState.NORMAL:
            self._ui_states.pop(key, None)
        else:
            self._ui_states[key] = state
        for listener in list(self._ui_state_listeners):
            try:
                listener(name, state)
            except Exception as e:
                logger.error(f"ui-state listener error for '{name}': {e}")

    def _set_ui_state_all(self, state: UiState, category: str | None = None) -> None:
        """Set the presentation state for every field on this bag, or for
        every field in *category* when given.

        The bulk form of :meth:`_set_ui_state`, with the same per-field
        contract. *category* is purely a selector over the fields' declared
        ``category=``; a category carries no state of its own. Unknown
        *category*: logs a warning and changes nothing.
        """
        fields = type(self)._settings_descriptors()
        if category is not None and not any(d._category == category for d in fields.values()):
            logger.warning(
                "set_ui_state_all: unknown category %r on %s — ignored", category, type(self).__name__
            )
            return
        for name, descriptor in fields.items():
            if category is None or descriptor._category == category:
                self._set_ui_state(name, state)

    def _ui_state(self, name: str) -> UiState:
        """Return *name*'s imperative presentation state — the ``ui_state=``
        seed plus any :meth:`_set_ui_state` call.

        Ignores the declarative ``enabled_when`` / ``visible_when`` metadata;
        :meth:`_effective_ui_state` is the composed answer. Unknown *name*
        returns ``UiState.NORMAL``.
        """
        fields = type(self)._settings_descriptors()
        if name not in fields:
            return UiState.NORMAL
        return self._ui_states.get(fields[name].storage_key, UiState.NORMAL)

    def _effective_ui_state(self, name: str) -> UiState:
        """Return *name*'s composed presentation state.

        Severity max (``NORMAL < DISABLED < HIDDEN``, the ``UiState`` int
        order) over every source:

        - the imperative state (``ui_state=`` seed + :meth:`_set_ui_state`),
        - ``enabled_when`` metadata — contributes at most ``DISABLED``,
        - ``visible_when`` metadata — contributes ``HIDDEN``.

        Both metadata gates are ``(field_name, expected_value)`` tuples,
        same-bag and exact-match; a gate whose controller field is not on this
        bag is skipped silently. Reads controller values with plain ``getattr``
        — never writes, never touches cells. Unknown *name* returns
        ``UiState.NORMAL``.
        """
        fields = type(self)._settings_descriptors()
        if name not in fields:
            return UiState.NORMAL
        descriptor = fields[name]
        state = self._ui_states.get(descriptor.storage_key, UiState.NORMAL)
        metadata = descriptor._metadata or {}
        gate = metadata.get("enabled_when")
        if gate is not None:
            controller, expected = gate
            if controller in fields and getattr(self, controller) != expected:
                state = max(state, UiState.DISABLED)
        gate = metadata.get("visible_when")
        if gate is not None:
            controller, expected = gate
            if controller in fields and getattr(self, controller) != expected:
                state = max(state, UiState.HIDDEN)
        return state

    def _subscribe_ui_state(self, callback: Callable[[str, UiState], None]) -> None:
        """Register ``callback(name, state)`` for UI-state transitions.

        A channel separate from :meth:`_subscribe`: it fires only for
        :meth:`_set_ui_state` transitions, never for value changes, and value
        subscribers never hear UI-state changes. Idempotent per callback."""
        if callback not in self._ui_state_listeners:
            self._ui_state_listeners.append(callback)

    def _unsubscribe_ui_state(self, callback: Callable[[str, UiState], None]) -> None:
        """Remove a previously registered UI-state callback (no-op if absent)."""
        try:
            self._ui_state_listeners.remove(callback)
        except ValueError:
            pass

    @classmethod
    def _settings_descriptors(cls) -> dict[str, setting]:
        """Return all setting descriptors on this class, keyed by attribute name.

        Walks the MRO base-first, so inherited fields come before the ones a
        subclass declares. Internal; :func:`settings_fields` is the supported
        spelling outside the settings package.
        """
        result: dict[str, setting] = {}
        for klass in reversed(cls.__mro__):
            for name, val in klass.__dict__.items():
                if isinstance(val, setting):
                    result[name] = val
        return result


_BagT = TypeVar("_BagT", bound="Settings")


def bag(settings_cls: "type[_BagT]") -> _BagT:
    """Declare a settings bag on a node with a correctly-typed accessor.

    ::

        class MyStyle(NodeSettings):
            marker_size = setting[INT](3)

        @node(...)
        class MyNode(BaseNode):
            style = bag(MyStyle)          # self.style.marker_size types as int

    Returns the class while typing as an instance: ``@node`` collects bags by
    looking for ``NodeSettings`` subclasses in the class body, and
    ``NodeData.__init__`` then replaces each with a bound instance, so the
    attribute really does resolve to an instance at runtime.

    Declaring the bag at module level and aliasing it here lets several nodes
    share one bag — but alias a shared bag under the same accessor name on
    every node: the descriptors are shared objects and ``@node`` re-stamps
    ``_setting_key`` as ``f"{accessor}.{field}"`` per node, so two different
    names would make the storage key depend on decoration order.
    """
    return settings_cls  # type: ignore[return-value]


def settings_fields(bag_or_cls: "Settings | type[Settings]") -> dict[str, setting]:
    """Every ``setting`` descriptor on a bag, by field name, declaration order.

    The supported way to iterate a bag's fields — accepts an instance or the
    class. Walks the MRO base-first, so inherited fields come before the ones
    a subclass declares and a redeclared field keeps its base position.

    Typical use — mirroring a bag onto a wrapped library's object::

        for name in settings_fields(bag):
            setattr(target, name, getattr(bag, name))
    """
    cls = bag_or_cls if isinstance(bag_or_cls, type) else type(bag_or_cls)
    return cls._settings_descriptors()
