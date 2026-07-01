# Plan 2 (Widget Unification) — Landed-State Deviations

> Plan 3 (promote-setting-to-inlet) MUST read this before its Task 0 verification gate.
> Every concrete name below is the **actual** landed name; substitute it for whatever
> Plan 3's tasks assume.

## Settings → widget model adapter (Task 6, approach a)

Approach **(a)** was taken: `BaseWidget` binds to a structural **`WidgetModel`**, not to a
concrete `DataPort`. The panel renders a setting by wrapping it in an adapter that satisfies
that protocol.

- **Protocol:** `haywire.core.types.widget_model.WidgetModel` (a `typing.Protocol`), re-exported
  from `haywire.core.types`. Surface:
  ```python
  class WidgetModel(Protocol):
      id: str
      widget_config: dict[str, Any]
      @property
      def data(self) -> DataField: ...
      def get_value(self) -> Any: ...
      def set_value(self, value: Any) -> None: ...
  ```
  `DataPort` satisfies this **structurally** (no inheritance, no registration) — that is why
  the same `BaseWidget` serves both ports and settings.

- **Settings adapter:** `haywire.ui.panel.setting_widget_model.SettingWidgetModel`. Signature:
  ```python
  SettingWidgetModel(
      field_id: str,
      itype: type[IType],
      value: Any,
      widget_config: dict[str, Any],
      make_setter: Callable[[Callable[[Any], Any]], Callable[[Any], None]],
  )
  ```
  It owns a real `DataField` (`itype.create_field(default_override={"value": value})`) seeded
  with the current value; `set_value` writes the field **and** forwards to the owning `Settings`
  via `make_setter`. External setting changes are pushed back with `apply_external(value)` (the
  panel's per-row `apply` updater calls this).

  **For Plan 3:** if the promoted-inlet on-card widget ever needs a non-port, non-setting backing,
  build another `WidgetModel`-satisfying adapter the same way — do **not** subclass `DataPort`.

## `BaseWidget.__init__` did gain a settings-backed path — indirectly

`BaseWidget.__init__(self, port: WidgetModel)` (was `port: DataPort`). It now accepts **anything**
satisfying `WidgetModel`, so there is no separate "settings constructor" — the adapter above is the
settings-backed path. `IWidget.__init__` was widened to `WidgetModel` to match. Plan 3's optional
on-card widget reuses this exact constructor with whatever `WidgetModel` it builds.

## Resolved widget property names (Task 5, on the `setting` descriptor)

On `haywire.core.settings.descriptor.setting`:
- `resolved_widget_key -> str` — precedence: `widget="label"` → `SimpleLabelWidget`;
  `widget="color"` → `builtin:widget:ColorWidget`; `choices` set → `builtin:widget:SelectWidget`;
  else the IType's default `widget_key`.
- `resolved_widget_config -> dict` — `{"properties": {...}}`, merging the type's own
  `widget_config["properties"]` (e.g. vec meta) under desugared `options`/`min`/`max`.

Panel entry point: `haywire.ui.panel.render_utils._resolve_widget_instance(defn, value, make_setter)`
→ `get_widget_class(defn.resolved_widget_key)` → builds a `SettingWidgetModel` → `widget.render()` →
returns the per-row `apply` callable (= `model.apply_external`). Falls back to `_build_label_widget`
when the key resolves to no registered widget (never a silent blank).

## Widget event binding: `ui.input` uses `update:value`, NOT `update:modelValue`

**Load-bearing gotcha discovered in Task 6.5.** NiceGUI's `ui.input` emits its value-sync event as
**`update:value`**; custom Vue components (NumberDrag) and the Quasar-wrapped value elements
(`ui.checkbox`/`ui.switch`/`ui.select`/`ui.color_input`) emit **`update:modelValue`**. `BaseWidget.bind()`
defaults `event="update:modelValue"`, so `TextWidget` must pass `event="update:value"` explicitly —
otherwise every in-browser string edit is silently dropped (the binding subscribes to an event the
input never fires). Any future `ui.input`-based widget needs the same. Documented in
`.insights/project_nicegui_input_update_value_event.md`.

## New rule: CONTROL/CALLBACK flow types reject widgets

Giving the scalar types a default `widget_key` exposed a latent bug: `CALLBACK(STRING)`
**inherited** STRING's `TextWidget`. A widget on a signal pin flips `has_widget=True` in
`StoreStrategy.should_store`, so a callback port's `None`-valued field got serialized and crashed
(`CALLBACK() missing required argument: 'value'`). Fixed two ways, both of which Plan 3 must respect:

- `@type` (`haywire.core.types.decorator`) now **raises `TypeError`** if a `CONTROL` or `CALLBACK`
  flow type ends up with a `widget_key` — passed directly *or* inherited via `asdict(parent)`. A
  signal pin is never editable, so it must be widget-less. To clear an inherited widget, pass
  `widget_key=None` explicitly (as `CALLBACK` now does in `haybale_core/types/specs.py`).
- Any new CONTROL/CALLBACK type derived from a widgeted scalar must pass `widget_key=None`.

## Harness test contract changed (data-value assertions retired)

The panel no longer hosts raw `ui.*` controls, so the old per-type `data-value` DOM mirror is gone.
The harness (`tests/ui/harness/`) now asserts:
- **wiring/structure** via `data-field` rows and per-widget DOM (`[data-number_drag]`, `[role=switch]`,
  `.q-select`, `input`);
- **validation** uniformly via the panel's `[data-error="true"]` container (not Quasar inline messages);
- **numeric mirror values** via NumberDrag's self-emitted `data-value` (its own Vue component, still
  emits it independent of the panel host).
Plan 3 should follow the same conventions; do not reintroduce panel-level `data-value` on text widgets.

## Commit boundaries / suite color

The IType cutover (Task 4) + sweep (Task 7) could not follow the planned red-between-commits split —
the cutover touched ~189 sites (far more than the plan's "~20"), and a runtime
`define()`/`_auto_define` Python-type-inference path also needed reworking, so a half-applied commit
was not coherent. Plan 2 ultimately landed as three commits split by layer rather than by task:
`feat(widgets): unify panel + ports …` (framework), `refactor(barn): convert all setting[pytype] …`
(consumers), `test(widgets): cover widget unification …` (tests). Because the framework commit makes
`setting[pytype]` raise, the framework and consumer commits are individually red; only the tip is
green. The follow-up fixes (CALLBACK guard, fresh perf graphs) landed as their own `fix(...)` commits.

`registry.define(name, value)` was restructured to require an IType and to resolve Python types via
`get_type_for_python_type` (new, in `haywire.core.types.registry`) with a builtin fallback map.

## Out of scope (unchanged)

Promote-to-inlet (Plan 3) was not started. The on-card widget for a promoted inlet is still deferred;
Task 6's adapter is for the **panel**, not the node card — but Plan 3 can reuse the `WidgetModel`
pattern verbatim for any card-side widget it eventually needs.

## Test failures surfaced and fixed (not background noise)

An earlier draft of this doc listed several failures as "pre-existing background noise." That was
wrong — most were real regressions from this plan's type move, now fixed. The default suite is green
(`uv run pytest`); the perf suite is green (`uv run pytest -m perf`).

- `test_store_strategy_survives_round_trip` — **was a real regression**, not a DI-env issue: the
  inherited `CALLBACK` widget (see the CONTROL/CALLBACK section above). Fixed.
- `test_benchmarks_smoke[graph_loop]`, `test_widget_cost_attribution`,
  `test_expects_arguments_cache_speedup`, `test_skin_render_profile::*` — all loaded **frozen
  `.haywire` graph files** whose serialized port-type keys went stale when the primitives moved to
  `builtin` (`core:type:INT` → `builtin:type:INT`). Fixed by building those graphs **fresh** from the
  live registry: `benchmarks/cases.py::_build_loop_graph` and `tests/ui/widget/conftest.py::
  build_perf_graph`, both referencing node types **by class** (registry_key resolved at build time) so
  a future move fails loudly instead of rotting silently. The frozen files were deleted.

**Lesson for Plan 3:** do not freeze `.haywire` fixtures that embed `*:type:*` / `*:node:*` keys — a
library move re-keys them and the load fails silently. Build test graphs from class references.

Pre-existing NiceGUI slot-stack pollution (the autouse `Slot.stacks` reset leaving the 2nd perf test
with no slot) was also fixed via an opt-in `nicegui_slot_context` fixture in the widget conftest.
