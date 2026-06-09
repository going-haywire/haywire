---
status: accepted
---

# Widget unification — one canonical `BaseWidget` with a floor + `bind()` sugar

Haywire had two widget base classes: `SimpleWidget` (a fast, single-element
primitive binder used by all 7 production widgets) and `BaseWidget` (a
declarative multi-binding base used only by the demo library). We collapse them
into **one canonical `BaseWidget`** and delete `SimpleWidget`. The unified base
exposes a two-layer authoring model — a general **floor** (`build()` plus an
overridable `on_model_changed()` hook, giving an author full manual access to
build any NiceGUI tree for any `BaseType` and sync it however they want) and a
**`bind()` sugar** layer on top for the common flat-scalar case
(`self.bind(element, to="x")`). A primitive widget is the degenerate case
(`to="value"`, the default), which is what lets the two classes merge.

## Why now / why this shape

The motivating roadmap is real multi-element widgets — Vector2/3/4, Quaternion,
Matrix3x3/4x4, ColorRGB/RGBA — which `SimpleWidget` structurally cannot serve
(it is hardwired to one element, one binding). That is the only irreducible
reason to keep a sophisticated base; with it confirmed, maintaining two bases is
no longer justified.

The design was validated against the one genuinely complex production widget,
`OpencvViewerWidget`, which today bypasses **both** base classes and implements
`IWidget` directly. On the unified base it becomes a floor-only widget
(`build()` returns a streaming card, `on_model_changed()` pushes frames, no
`bind()` call) and shrinks — evidence the two-class system was incomplete and
the floor is a genuine need, not speculation.

## Key sub-decisions and their reasons

- **No fast-path.** Measurement (`docs/plans/widget-unification-perf-verification.md`,
  Finding B) showed the `SimpleWidget`-vs-`BaseWidget` sync delta is
  perf-irrelevant: `render_widget` is ~13% of render and the sync delta is a
  fraction of that. The verification plan's YELLOW fast-path was contingent on a
  regression measurement did not find, so the unified base has a single sync path
  with no special-casing.
- **Nested-property navigation is kept** (`source_property != "value"`). A prior
  audit filed it as dead "Pile B", correct under its zero-roadmap premise; the
  Vector/Matrix roadmap flips that premise — it is the binding spine for
  composite component fields.
- **Override safety via template method.** Base public methods (`cleanup`,
  model-change dispatch) are final; subclasses override protected hooks
  (`_on_cleanup()`, `on_model_changed()`) and cannot skip base teardown. This
  prevents the silent `on_changed` subscription-leak class (cf. the
  `expects_arguments` handler-leak fix).
- **Double-activation designed out.** The latent double-activation in the old
  `add_binding` (masked only by `PropertyBinding._is_active`) is eliminated by
  the new `bind()`/`build()` timing — bindings register inline and activate once,
  centrally. The old `add_binding` path is deleted, not patched.
- **Agnostic boundary held at `haywire.core` vs `haywire.ui`.** The widget API
  lives in `haywire.ui`, speaks NiceGUI natively, and mirrors NiceGUI's
  `bind_value` mental model. UI-agnosticism is enforced by the namespace
  boundary (`haywire.core` stays NiceGUI-free, reached only through `DataPort`'s
  neutral surface), not by abstracting NiceGUI out of the widget layer.

## Considered alternatives

- **Keep both base classes.** `SimpleWidget` as a deliberate fast path — rejected:
  measurement retired the perf justification, leaving only duplication.
- **Field-map (`FIELDS = {...}`) authoring instead of `bind()`.** Shortest for
  uniform grids (Vector3) but forces a second paradigm plus a spec mini-language
  the moment a widget is irregular (ColorRGBA = swatch + channels + hex, labeled
  matrices). `bind()` keeps one mental model across uniform and irregular cases.
- **Move `BaseWidget` + converters out to the demo library.** The honest move
  *if* no multi-element widgets were coming; the named roadmap makes them core.
- **Keep the `validation`/`on_error` callback path.** Cut — zero callers and
  cleanly re-addable as additive `bind()` kwargs if a widget ever needs
  reject-with-feedback (clamp-in-converter stays).
- **Strangler migration / deprecated `SimpleWidget` shim.** Rejected: the entire
  widget population (8 widgets) is in-repo and enumerated, with a parity test as
  the gate — big-bang reaches the clean end state without a transitional
  two-base period.

## Consequences

- `SimpleWidget` is deleted; its 7 widgets and `OpencvViewerWidget` migrate to
  `BaseWidget` (`build()` + `bind()`/floor) in one change.
- The `UI_PROPERTY` / `UI_EVENT` / `IS_READONLY` class attributes are replaced by
  bind-site arguments (`prop=`, `event=`, `one_way=`).
- "Pile B" is deleted: debounce/`UpdateTrigger` variants, four orphan converters,
  and the binding-level `validation`/`on_error` callbacks.
- Authors override `on_model_changed()` (calling `super()` to keep `bind()`-ings
  live, or owning sync entirely) for whole-value or non-field-mapped widgets.
- `widget-canon.md` must be rewritten — its current "use `SimpleWidget` first,
  graduate to `BaseWidget`" guidance is reversed by this decision.
