---
name: absence-is-a-type
description: A setting that can hold "no value" expresses it through its IType (OPTIONAL[T], a new WrapperType family), not through a flag on setting() or the set-or-unset opinion axis
status: accepted
see-also: ADR-0013, ADR-0014, ADR-0017, ADR-0019
level: architectural
---

# Absence is a value, and a value's domain is its type

**Context.** A settings field always holds a value; there is no null. Wrapping
an external library means mirroring its parameters onto settings, and real
libraries use `Optional[T]` for "leave this alone", where the *absence* is
semantically distinct from every value the parameter can take. Converting
**haybale-visiongraph** to settings-first configuration hit this three times in
one library, and each knob invented a private workaround:

| Knob | Library shape | What shipped instead |
|---|---|---|
| `annotate(show_bounding_box=…)` | `Optional[bool]`, defaults differ per result subtype | a tri-state `CHOICES` of three display strings |
| `NMSOptions.eta` / `.top_k` | `Optional[float]` / `Optional[int]`, `None` disables | `UNSET = -1`, translated back in `hb_assign` |
| `MotpyTracker.min_steps_alive` | `-1` is the library's own sentinel | `-1`, with the meaning only in `description=` |

Each cost something different. The tri-state stored a **display label** as the
graph value, so rewording a label breaks saved graphs, and promoting the field
produced a `STRING`-typed port no `BOOL` could drive. The `UNSET` pair had to
**widen the declared range** (`eta`'s real domain is 0..1, declared `min=-1.0`)
so the sentinel was reachable at all — admitting `-0.5`, which is neither a
valid `eta` nor the sentinel — and leaked a name-keyed special case into
`base_estimator_node.hb_assign`, coupled to the declarations in another module
by string literals.

`is_locally_set()` looks like the answer — "if the user never touched it, omit
the kwarg" — and is **worse than incomplete: the answer is path-dependent.** A
write equal to the value a field currently resolves to records nothing
(`setting.__set__`'s equality guard), so:

```python
a.flag = False                 # from pristine  -> flag False, locally_set False
b.flag = True; b.flag = False  # via True       -> flag False, locally_set True
```

Two users with identical configuration get different behaviour. That guard is
load-bearing — it stops a mirror field manufacturing a local override when the
mirrored global is written back, which would defeat `reset()`, and it terminates
the cross-tab echo loop at the model layer. **It must not be "fixed".**

The insight is that two orthogonal axes were being conflated:

- **opinion** — does this tier have a view? Already modelled (`_set_keys`,
  `SettingValue(is_set=…)`).
- **value** — what the field holds. A user can deliberately set a field *to*
  absence: an opinion whose value is absence.

**Decision.** Absence is a **value**, and a value's domain is described by its
**IType**. A field that can hold absence says so in its type:

```python
eta = setting[OPTIONAL[FLOAT]](None, min=0.0, max=1.0, label="Eta")
```

`OPTIONAL[T]` mirrors `Optional[T]` in the wrapped library's signature 1:1, and
the declared `min`/`max` stay the parameter's **real** range — absence lives
outside the value domain and never has to be smuggled into it.

The consequence that made this the right axis: **the settings value model
changes not at all.** `_set_keys`, `_to_dict`/`_from_dict`, `_reset`, mirror
resolution and the `__set__` equality guard are untouched, because absence is
something a cell already physically stores (`PrimitiveField._value` may be
`None`) and `_cell_for` passes the seed through without inspecting it. The
mistake this ADR exists to prevent — modelling absence as "not in `_set_keys`" —
becomes structurally unavailable rather than a rule to remember.

## `OPTIONAL` is a new family, deliberately not a `CompoundType`

`WrapperType` joins `PrimitiveType` / `BaseType` / `CompoundType`: **exactly one
value of another IType, or absence.** It parameterizes like a compound
(`OPTIONAL[INT]`, cached, element round-tripping through
`serialize_element_type`'s `recipe`) and reuses `PrimitiveField`-derived storage.

Reusing `CompoundType` for the parameterization machinery was the obvious move
and is wrong, because that predicate is **behavioural**, not structural
bookkeeping. Two subsystems dispatch on it:

- `AdapterFactory` — `OPTIONAL[FLOAT] → FLOAT` would land in "scalar ↔ compound
  mismatch" and be refused, while `OPTIONAL[FLOAT] → OPTIONAL[INT]` would build
  an **element-wise chain**, adapting a zero-or-one value as if it were a
  collection.
- `pin_render` — an optional pin would get **collection iconography** and look
  like an array pin.

Both are silent, and both would surface only once such a value reached a port —
the moment a future round lifts the promotion fence, i.e. the worst possible
timing. A `WrapperType` answers `False` at both sites and is treated as a
scalar, which is correct. The cost of the family is two one-line widenings
(`serialize_element_type`'s recursion, the decorator's `_parameterized_cache`
init); every other dispatch site is right by default instead of by exception.

A wrapper also **does not** share the parent's `class_identity`, where a
compound does. `OPTIONAL[VEC3F]` stamps a per-parameterization identity that
keeps the wrapper's `registry_key` and `widget_key` but takes the element's
colour and declared widget properties — without which `VecWidget` never receives
the `vec_meta` it cannot render without.

## ADR-0017 re-examined

ADR-0017 rejected **per-base `*_SEL` types** as "type proliferation … plus an
adapter matrix … for a distinction that belongs per-use, not per-type". A
reader arriving at `OPTIONAL[T]` will reasonably ask whether this ADR reverses
that. It does not, for two reasons:

1. **Optionality is per-type; options are per-use.** Which values a dropdown
   offers is a property of one declaration site. Whether a parameter admits "no
   value" is a property of the parameter's domain — it is literally spelled in
   the wrapped library's own type annotation. ADR-0017's rule is intact.
2. **Parameterization is not proliferation.** `*_SEL` meant one hand-written
   `@type` subclass per primitive. `OPTIONAL` is *one* type; `OPTIONAL[INT]` is
   generated and cached, exactly as `ArrayType[FLOAT]` already is.

The stamped-widget invariant also holds: `widget_key` is stamped once, from the
wrapper's identity, and never re-resolved at render time. `OptionalWidget`
resolves the *inner* widget from the element's own declared `widget_key` — the
same stamped contract every other surface reads.

## Considered and rejected

- **A `optional=True` flag on `setting()`.** Puts absence on the descriptor,
  where it must then be threaded through serialization, `reset()`, mirrors and
  every widget — and sits one attribute away from `_set_keys`, inviting exactly
  the conflation this ADR forbids.
- **Reusing `is_locally_set()`.** Path-dependent; see above.
- **A shared `UNSET` sentinel blessed as a convention.** Leaves the value-range
  corruption and the invisible panel affordance unfixed.
- **`OPTIONAL` as a `CompoundType`.** See above — silently wrong at two
  dispatch sites.

## Consequences

- **Promotion is fenced at pins, not at ports.** No adapter maps `OPTIONAL[T]`
  to `T`, so an inlet or outlet pin would refuse every edge; those raise at
  class-definition time. `Promotable.CONFIG` is the **seed**, because a config
  port is pinless by construction — never linked, never edge-driven — so the
  missing adapter cannot reach it. Drawing the fence at `NONE` would have been
  one step wider than its own justification, and would have cost
  `MotpySettings.min_steps_alive` the config face every other field in its bag
  has. Lifting the rest ("what does a `FLOAT` edge emit for absence?") is a
  separate design.
- **A validator constrains the *present* domain only.** It is lifted once at
  declaration to `v is None or user(v)`, so all three callers of `validate()` —
  including `SettingsRegistry.set_global` on a mirrored field — agree. Without
  this, a validator written for the wrapped type raises `TypeError` from inside
  a plain attribute assignment.
- **Reset and "set to none" become different verbs** once a default may itself
  be a value. Both appear in the Setting-row menu; "Set to none" is hidden when
  the declared default is already absence, since there the two are one act, and
  each carries a tooltip naming where it lands when both are shown. The widget
  therefore offers **no clear control of its own** — it would duplicate one of
  those two entries in every case. Leaving absence needs an affordance in the
  row (there is no widget to type into), so the `none` cell is clickable; entering
  absence is reset-shaped and belongs to the menu.
- **A per-use `restore` widget property** carries what clicking the `none` cell
  produces: an explicit `widget_config={"restore": …}`, else the field's own
  non-absent default, else the element IType's default. Deliberately stateless
  rather than "the last value you had", which would die on every panel redraw
  and reintroduce path-dependence at the UI layer.
- **No migration for graphs saved before a field was converted.** Prehydration
  is a single framework-owned format-version chain; there is **no library-level
  migration hook**. A graph holding `top_k: -1` against a now-`OPTIONAL[INT]`
  field reads `-1` as the literal value. Accepted for the visiongraph conversion
  (three fields, one young library); a library changing a field's stored meaning
  has no supported upgrade path today, and that gap is now this ADR's to name.
- **`OPTIONAL[T]` is restricted to `PrimitiveField`-stored elements.** "Absence"
  means a bare value or `None` in an unwrapped slot; a `BaseField` element has
  nowhere to put it, and is refused at parameterization time rather than failing
  later.
- **Wrapping a wrapper raises.** Absence has no degrees.
- If a second wrapper type ever appears (`RESULT[T]`, `LAZY[T]`), it belongs in
  this family. If none does, `WrapperType` stays a one-member family — justified
  by the two mis-dispatches above, not by symmetry.
