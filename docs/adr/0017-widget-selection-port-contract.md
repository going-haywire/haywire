---
name: widget-selection-port-contract
description: A setting field's widget_key/widget_config is stamped once at descriptor-creation time and read identically by every rendering surface
status: accepted
see-also: ADR-0013, ADR-0014
level: architectural
---

# Widget selection is a port contract: one stamped `widget_key`/`widget_config`, options per-use

**Context.** A `setting()` field's panel widget was picked by up to three
overlapping channels, each with its own resolution rule. A string `widget=`
hint (`widget="color"`, `widget="label"`) short-circuited to a hardcoded
widget-name lookup. A `choices=` parameter (list, `{value: label}` dict, or
zero-arg callable) desugared into a dropdown, with its own resolution branch
at render time (`resolved_widget_key`/`resolved_widget_config`/`_choices`
properties recomputing on every panel draw). And the field's IType carried no
declared default widget at all — inference fell back to ad-hoc type checks
(`Color = str` special-cased, `bool` → toggle, `int`/`float` → NumberDrag).
Three channels meant three things to keep synchronized whenever a field's
type or authoring style changed, and `choices=`'s callable form meant a
setting's panel row and a promoted port's row could, in principle, resolve to
different widgets for the same value — there was no single contract a port
and its promoting setting both read.

**Alternatives weighed.**

- **Keep `choices=` as sugar over IType + widget_config.** Rejected — it
  would still be a second resolution rule sitting in front of the IType
  contract instead of expressing itself *through* it, defeating the point of
  unifying on one channel.
- **`widget=SelectWidget.config(...)` at every declaration site.** Rejected —
  it forces every engine-layer module that declares a `CHOICES`-shaped field
  (including `haywire.core` IType declarations, which must stay NiceGUI-free)
  to import a NiceGUI-backed widget class just to name a key, breaking the
  `haywire.core` vs `haywire.ui` agnostic boundary that ADR 0007 holds.
- **Per-base `*_SEL` types** (e.g. a family of enum-like types, one per base
  type needing a dropdown). Rejected — type proliferation (a `_SEL` variant
  per primitive that might want a dropdown) plus an adapter matrix between
  each `_SEL` type and its base type, for a distinction (options attached to
  the type) that belongs per-use, not per-type.

**Decision.** Widget selection is a **port contract**, stamped once and never
resolved again at render time.

- Every `setting()` descriptor computes plain `widget_key: str` and
  `widget_config: dict` attributes exactly once, via `_stamp_widget()`. For a
  class-body field this runs from `__set_name__` (once the IType is known
  from the `setting[T]` subscript); for a registry-constructed field
  (`registry.define(...)`, file auto-define) it runs at the end of
  `__init__`, since those descriptors never receive `__set_name__`.
- **Precedence**: an explicit `widget=` dict — the `{"key", "config"}` shape
  produced by `WidgetCls.config(...)` — wins outright. Otherwise the widget
  comes from the field's IType's declared identity (`@type(widget_key=...,
  widget_config=...)`, engine-layer, zero NiceGUI imports —
  `haywire.barn.builtin.widget_keys` is a leaf module of plain string
  constants for exactly this). `min`/`max` fold into
  `widget_config["properties"]` alongside the IType's declared properties and
  any `widget_config=` override, in that layering order.
- **Options live per-use, never on the type.** `CHOICES(STRING)` is the one
  builtin IType that carries a select-shaped identity (`widget_key =
  widget_keys.SELECT_WIDGET`) — but zero options. Every declaration site
  supplies its own via `widget_config={"options": [...] | {value: label} |
  callable}`. `SelectWidget.build()` resolves a callable at build time
  (`if callable(options): options = options()`), so a dynamic list (e.g. from
  a registry) still refreshes on every widget instance build without the type
  itself knowing anything dynamic exists.
- Identity STRING↔CHOICES adapters (both directions, pure passthrough) let a
  plain string port connect to — or be promoted from — a CHOICES-typed one
  without a special case in the promotion or edge-adapter path.
- `SettingsFileStore` (ADR-adjacent to this decision but not part of it — see
  the registry/persistence split note in settings-arch.md) is unaffected: the
  JSON file dialect still speaks a bare `"choices"` key for auto-defined
  fields, which the registry's `_auto_define` now projects onto
  `type_=CHOICES, widget_config={"options": ...}` rather than a removed
  `choices=` parameter.

**Consequences.**

- **Hard cutover, no migration.** A promoted STRING port whose setting used
  to desugar `choices=` is now backed by a CHOICES-typed cell; an old
  serialized graph round-trips through the identity adapters rather than a
  compatibility shim. There is no dual-read path for the old `choices=` shape
  on a `setting()` call — it is a constructor error.
- **Deleted, no aliases**: `choices=` and string `widget=` params on
  `setting()`; the `resolved_widget_key` / `resolved_widget_config` /
  `_choices` / `choices` properties (nothing resolves at render time
  anymore); the `ui_widget` file-format knob and `define(choices=...,
  ui_widget=...)` registry parameters.
- **~26 call sites migrated**: every `choices=`/`widget="color"`/
  `widget="label"` declaration in the codebase now reads
  `setting[CHOICES](..., widget_config={"options": [...]})` /
  `setting[COLOR](...)` / `widget=SimpleLabelWidget.config()`. See
  `debug_settings.py` for a representative `CHOICES` migration (log-level
  dropdowns) — every field there dropped its own `choices=` in favor of
  `setting[CHOICES]` + `widget_config={"options": ...}`.
- **A latent, unrelated `_rehydrate_entry` double-wrap bug** (pre-dating this
  plan) surfaced and was fixed incidentally while touching the file
  auto-define path.
- **A VecWidget row-alignment regression** (vector setting fields lost their
  top-aligned label CSS once `_stamp_widget` became the only path setting
  `widget_config`) was found and fixed by adding `orientation: "column"` to
  `vectors.py`'s shared `_vec_widget_config()` helper, matching VecWidget's
  own internal default.
- **One stamped contract, read by both surfaces.** A setting's panel row and
  its promoted port's row (Ports Panel, node card) resolve the same
  `widget_key`/`widget_config` from the same descriptor — there is exactly
  one place either surface can diverge from (an explicit `widget=` override
  on the descriptor), not three.
