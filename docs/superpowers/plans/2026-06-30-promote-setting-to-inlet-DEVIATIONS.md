# Plan 3 (Promote Setting To Inlet) — Landed-State Deviations

Concrete names/decisions where the plan's assumptions differed from reality.

## Pre-flight: one pre-existing error fixed
`barn/haybale-graph-editor/.../state/edit_state.py` imported `DataPort` from
`haywire.core.node.base` (no such attribute) — a pre-existing baseline mypy error
(committed in `aeab39c2`). Corrected to `from haywire.core.types import DataPort`
(type-only, under `TYPE_CHECKING`). Baseline is otherwise clean.

## `_promoted_port_id` lives on `SettingDescriptor` (base.py), not `setting` (descriptor.py)
The plan said "add to `SettingDescriptor` in base.py" in one place and referenced
`descriptor.py` elsewhere. The descriptor class hierarchy is `setting(SettingDescriptor)`.
The flag was added as a class attribute on `SettingDescriptor` (`base.py`) so both
`setting` and `persistent_setting` inherit it. Default `None`; assigned per-descriptor.

**Note (class-shared flag):** descriptors are shared across all instances of a node class.
`_promoted_port_id` is therefore class-level state, but the read-tier gates on **per-node
port presence** (`node.ports.get(pid)`), so an unpromoted sibling instance with the flag
set (but no port) correctly falls back. This is acceptable for v1.

## `FieldMetadata` Protocol dropped; projection helper folded into `promotion.py`
The plan flagged the `_label` vs `label` mismatch and allowed a documentation-only Protocol.
It was initially added that way (with a `metadata_to_port_kwargs` bridge in a new
`core/types/field_metadata.py`), then both were reconsidered:

- The Protocol was **deleted** — nothing imported it (no annotation, no `isinstance` in
  production); it was inert.
- The bridge had a single caller (`promote_setting`) and is a promotion concern, not a types
  utility, so it was **moved into `core/node/promotion.py`** as the module-private
  `_metadata_to_port_kwargs(descriptor)` and `field_metadata.py` was removed entirely. It
  returns `{label, description, order, type_cls}` for `IType.as_inlet(...)`, falling back to
  the field's attr name when no label is set. Tests live in
  `tests/core/node/test_promotion_id.py`.

## Node back-reference for the read-tier: `_node` set in `NodeData.__init__`
The settings bag had **no** node back-reference. Added one in `node/data.py` where bags
are instantiated: `object.__setattr__(_bag_instance, "_node", self)`. The read-tier reads
`getattr(obj, "_node", None)`.

## Port removal: `rejig`, not `remove_port`
`NodeData` has no `remove_port`. `demote_setting` removes the inlet with
`with node.rejig(include=[pid]): pass` (flag-and-drop via `_pop`). `promote_setting` adds
with `with node.rejig(include=[pid]): node.add(spec)`.

## Serialized ports are a **dict** keyed by id, not a list
`_serialize_ports` returns `{port_id: spec_dict}`. Tests assert `pid in data["ports"]`
(not `any(p["id"] == pid ...)`). The re-bind hook iterates `for port_id in self.ports`.

## UI wiring: provider verbs + `ElementRedrawEvent`, no new events

**Critical focus correction (post-implementation):** a normal node right-click fires
`on_selection_context`, which opens the menu with **`SelectionFocus` + `SelectionContextActions`**
— NOT `NodeFocus`/`NodeContextActions`. `NodeFocus`/`NodeContextActions` is only reached by
`on_custom_context` (the skin extension point, DOM `data-hw-custom-menu-focus-id`). The promote
panel was initially registered against `NodeFocus` and never appeared on a node right-click.

Landed wiring:
- `SelectionContextActions.promote_setting(node_id, accessor, field)` — takes `node_id`
  explicitly (mirrors `dissolve_reroute`). `NodeContextActions` stays an **empty marker**.
- `PortContextActions.demote_setting(accessor, field)` — the pin menu (`on_port_context`)
  correctly uses `PinFocus`/`PortContextActions`, so the detach panel was right all along.
- Provider verbs look up the wrapper by id from `active_graph`, call the framework function,
  then emit the existing `ElementRedrawEvent(nodes=[id], edges=[])` to refresh pins. No new events.

Panels (auto-discovered by the `panels/` folder scan):
- `panels/graph/menu/node/promote.py` — `PromoteSettingMenuPanel` (`focus=SelectionFocus`,
  `actions=SelectionContextActions`) + `promotable_fields(node)`. `poll()` shows it only for a
  **single-node** selection (no edges, exactly one node) with promotable fields.
- `panels/graph/menu/port/port.py` — `DetachSettingMenuPanel` (`focus=PinFocus`), polls
  `is_promoted_port_id(active_port.id)`.

## Promoted inlet creation kwargs
`type_cls.as_inlet(pid, store_strategy=StoreStrategy.NEVER,
show_widget=ShowWidgetStrategy.NEVER, label=, description=, order=)`. NEVER store ⇒ value
never persists; NEVER widget ⇒ no on-card widget (v1).

## Properties row marker
`render_utils._render_reactive_field_row` adds `data-promoted="true"` to the row props and
a `data-promoted-hint="true"` "↳ driven by inlet" label when
`defn._promoted_port_id is not None`.

## Test fixtures
- `make_node_with_setting(accessor, field, with_watch=False)` lives in the **root**
  `tests/conftest.py` (shared by `tests/core/*` and `tests/ui/*`). Depends on
  `library_system`. It re-asserts the loaded type/settings registries as the ambient
  context (`set_type_registry`/`set_settings_registry`) before building the node, because a
  function-scoped `test_injector` elsewhere in the suite can swap the module globals,
  otherwise leaving the node to cache a registry without the builtin types.
- `watch(plain, type_=FLOAT)`: `type_` must be passed explicitly — `plain`'s generic arg
  isn't resolved until its own `__set_name__` runs (after the `watch()` call).
- The e2e test lives in `tests/core/node/test_promotion_e2e.py` (NOT `tests/ui/menu/`):
  under `tests/ui/` the `graph_with_library_system` fixture trips a marketplace state
  container that calls `get_workspace_root()` with no ambient workspace root.

## Pre-existing format drift (not mine)
`tests/ui/harness/test_external_sync.py` has trailing-blank-line drift committed in
`55a3e900` — `ruff format --check .` flags it. Untouched by this plan.
