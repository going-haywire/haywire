---
name: settings-have-no-absent-value
description: RESOLVED by ADR 0033 — absence is now a value expressed through the type (OPTIONAL[T], a WrapperType family); the three visiongraph sentinel workarounds are deleted
metadata:
  type: project
  status: resolved
---

# A setting cannot express "unset" — RESOLVED

> **Resolved 2026-09-09 by [ADR 0033](../../docs/adr/0033-absence-is-a-type.md).**
> Absence is a **value**, and a value's domain is its **IType**:
> `setting[OPTIONAL[FLOAT]](None, min=0.0, max=1.0)`. `OPTIONAL[T]` belongs to a
> new fourth IType family, `WrapperType`, deliberately **not** a `CompoundType`.
> The settings value model was not changed at all — `_set_keys`,
> `_to_dict`/`_from_dict`, `_reset`, mirrors and the `__set__` equality guard are
> untouched, so the mistake this handoff warned about is now structurally
> unavailable rather than a rule to remember.
>
> Where things live now:
>
> - `core/types/base.py` — `WrapperType`, `_absence_tolerant_field`, `_wrapped_identity`
> - `barn/builtin/types/optional.py` — `OPTIONAL`
> - `barn/builtin/widgets/optional_widget.py` — `OptionalWidget`
> - `core/settings/descriptor.py` — `_apply_wrapper_rules` (validator lifting + the promotion fence)
> - `docs/components/settings/setting-canon.md` §3aa — the authoring guide
> - Glossary: **absence**, **OPTIONAL**, **WrapperType**
> - Tests: `tests/core/test_types/test_wrapper_type.py`,
>   `tests/core/test_settings/test_optional_setting.py`,
>   `tests/ui/widget/test_optional_widget.py`
>
> **All three visiongraph workarounds are deleted** (0.0.40): the tri-state
> `CHOICES`, the `UNSET = -1` pair with its cross-file `hb_assign` translation,
> and `min_steps_alive` — which kept its `promotable=Promotable.CONFIG` face,
> because the fence landed at *pins*, not at ports.
>
> **Two things this did NOT resolve**, both named in the ADR's consequences:
>
> 1. **No inlet/outlet promotion.** "What does a `FLOAT` edge emit for absence?"
>    is a real open question; an `OPTIONAL[T] ↔ T` adapter is its prerequisite.
> 2. **No library-level graph migration hook.** Prehydration is a single
>    framework-owned version chain, so a library changing a field's stored
>    meaning still has no supported upgrade path. Graphs saved on visiongraph
>    0.0.39 read their old `-1` sentinels as literal values.

The original analysis follows, unchanged, because the reasoning about *why*
`is_locally_set()` cannot serve is still the thing to read before anyone
proposes changing that guard.

---

Identified 2026-09-08/09 while converting **haybale-visiongraph** to
settings-first node configuration (notes.md "Settings-first configuration",
shipped as 0.0.39). Three separate knobs in that one library needed a state
meaning *"do not pass this to the wrapped library at all"*, and the settings
model has no way to say it. Each got its own private workaround.

## The shape of it

Wrapping any library means mirroring its parameters onto settings fields. Real
libraries use `Optional[T]` for "leave this alone", and the *absence* is
semantically distinct from every value the parameter can take:

| Knob | Library default | Why absent ≠ any value |
|---|---|---|
| `annotate(show_bounding_box=...)` | **False** for landmark/pose, **True** for segmentation | passing our own default silently overrides one of them |
| `NMSOptions.eta` / `.top_k` | `None` | `None` disables the feature; any float/int enables it |
| `MotpyTracker.min_steps_alive` | `-1` sentinel | library's own sentinel, must round-trip |

A setting always holds a value. There is no null.

## Why `is_locally_set()` is not the answer

It looks like one — "if the user never touched it, omit the kwarg" — and it is
worse than merely incomplete: **the answer is path-dependent.** A write equal to
the value the field currently *resolves to* records nothing, so whether an
explicit choice is remembered depends on the route taken to it:

```python
a.flag = False                 # from pristine  -> flag False, locally_set False
b.flag = True; b.flag = False  # via True       -> flag False, locally_set True
```

Same field, same visible value, opposite answers. Two users with identical
configuration get different behaviour from anything keyed on `is_locally_set`.

The cause is deliberate and load-bearing —
`packages/haywire-core/src/haywire/core/settings/descriptor.py`, `setting.__set__`:

```python
old = self.__get__(obj, type(obj))
if value == old:
    return          # returns BEFORE obj._set_keys.add(...)
```

Its own comment explains why it must stay: a `shadow()`/`watch()` field with no
local override resolves to the **mirrored global**, not `_default`, so writing
that value back must not manufacture an override — that would defeat `reset()`.
The same guard also terminates the cross-tab echo loop at the model layer, so
the settings panel's setter needs no equality check of its own.

So this is not a bug to fix. **Do not "improve" `is_locally_set`.** Changing
that guard breaks mirror reset semantics and reintroduces the echo loop.

## The actual insight: there are two axes, and they are being conflated

- **opinion** — "does this tier have a view?" Already modelled: `_set_keys` for
  node bags, and `SettingValue(is_set=...)` for registry tiers
  (`core/settings/value.py` — *"a tier's stored opinion: either set or unset"*).
- **value** — what the field holds. Always present. There is no "absent".

`is_locally_set()` reads the *opinion* axis. What wrapper libraries need is an
**absent value** — a first-class member of the field's own domain, chosen by the
user, distinct from "never touched". The two axes are orthogonal: a user can
deliberately set a field to "none" (an opinion, whose value is absence).

Getting this wrong in the obvious way — reusing `is_locally_set` — produces
software that ignores an explicit user instruction. That is what motivated the
tri-state workaround below.

## What shipped in 0.0.39 (three private workarounds — now deleted)

All in `barn/haybale-visiongraph/haybale_visiongraph/nodes/`:

1. **`annotate_node.py`** — `show_bounding_box` is a tri-state `CHOICES`
   (`"Auto (per result type)"` / `"Always"` / `"Never"`); `AUTO` omits the
   kwarg. Verified end-to-end against real `InstanceSegmentationResult`s.
2. **`estimator_settings.py`** — `UNSET = -1` for `NmsSettings.eta` and
   `.top_k`, translated back to `None` in `BaseEstimatorNode.hb_assign`.
3. **`tracker_node.py`** — `min_steps_alive = -1`.

Each is invisible to the panel: the user sees a number field where `-1` means
"off" by private convention, with no affordance saying so. That is the UX cost.

## One thing that is easy to get wrong

Do not model absence as "the field is not in `_set_keys`". That is the opinion
axis, it is already spoken for by `reset()` and by mirror resolution, and
overloading it is exactly the mistake that produced the tri-state workaround.
An absent *value* must survive a save/load as an explicit user choice — which
"no local override" cannot, because on reload a mirror would resolve to the
global instead.
