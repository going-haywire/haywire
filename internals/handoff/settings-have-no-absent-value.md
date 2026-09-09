---
name: settings-have-no-absent-value
description: Handoff — a setting can hold any value but cannot hold "no value", so every Optional[T] parameter of a wrapped library needs a hand-rolled sentinel; is_locally_set() looks like the answer and provably is not
metadata:
  type: project
  status: open
---

# A setting cannot express "unset"

Identified 2026-09-08/09 while converting **haybale-visiongraph** to
settings-first node configuration (notes.md "Settings-first configuration",
shipped as 0.0.39). Three separate knobs in that one library needed a state
meaning *"do not pass this to the wrapped library at all"*, and the settings
model has no way to say it. Each got its own private workaround.

This is the deepest of the gaps that conversion surfaced, and the only one
that cannot be worked around in library code — hence its own session.

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

## What shipped instead (three private workarounds to delete)

All in `barn/haybale-visiongraph/haybale_visiongraph/nodes/`, 0.0.39:

1. **`annotate_node.py`** — `show_bounding_box` is a tri-state `CHOICES`
   (`"Auto (per result type)"` / `"Always"` / `"Never"`); `AUTO` omits the
   kwarg. Verified end-to-end against real `InstanceSegmentationResult`s.
2. **`estimator_settings.py`** — `UNSET = -1` for `NmsSettings.eta` and
   `.top_k`, translated back to `None` in `BaseEstimatorNode.hb_assign`.
3. **`tracker_node.py`** — `min_steps_alive = -1`.

Each is invisible to the panel: the user sees a number field where `-1` means
"off" by private convention, with no affordance saying so. That is the UX cost.

## The change not made

Something along the lines of:

```python
top_k = setting[INT](UNSET, unset_value=UNSET, label="Top K")
```

where the panel renders an explicit unset affordance (a clear button, a
"— none —" option) and the worker reads `None`. The declaration says once what
three call sites currently encode by convention.

That shape is a guess, not a decision. **The design work is real** and touches:

- **serialization** — how does absence round-trip through the graph JSON and
  TOML, distinctly from "no local override"?
- **panel rendering** — every widget kind needs an unset presentation, and
  `widget_key` is stamped once at class-definition time (ADR 0017), so the
  affordance cannot be resolved at render time.
- **`reset()`** — reset-to-default vs set-to-absent are now different verbs.
- **type/IType interaction** — is absence a property of the *field* or of the
  *IType*? `Optional[FLOAT]` as a type would be the other design.
- **mirrors** — what does a `shadow()` of an absent-capable field resolve to?
- every existing `setting[T]`, which must keep behaving exactly as now.

This is ADR-shaped: hard to reverse, surprising without context, and there are
genuine alternatives (field-level flag vs an IType, sentinel vs true `None`).

## Why it was deferred

It adds an axis to the value model. Bundling it with the ergonomics work
(`promote_default=`, `bag()`, `settings_fields()`, the underscore namespace
rule — see below) would have put a semantic change to every setting in the
framework inside a session about boilerplate.

## Where to start

- `core/settings/descriptor.py` — `setting.__init__` (the parameter list),
  `setting.__set__` (the guard above; **read its comment before touching it**)
- `core/settings/value.py` — `SettingValue`, the existing set/unset modelling
  for tiers. Whatever is built should be recognisably a sibling of this, not a
  competing spelling.
- `core/settings/settings.py` — `_set_keys`, `_is_locally_set`, `reset`,
  `to_dict`/`from_dict`
- `ui/panel/render_utils.py` — where a row decides its widget; the unset
  affordance lands here
- `docs/components/settings/setting-canon.md` — §"Live vs rebuild-category
  settings" and the `promotable=` section were written in the same pass and
  describe the surrounding conventions
- `barn/haybale-visiongraph/notes.md` — "Settings-first configuration
  (sixth inquisition)", prerequisite 5, records the reasoning in situ

**Reproduce the path-dependence** (framework only — no library needed):

```bash
uv run python -c "
from haywire.core.di.test_config import create_test_settings_registry
from haywire.core.settings import NodeSettings, setting
from haywire.barn.builtin.types import BOOL
class Bag(NodeSettings):
    flag = setting[BOOL](False)
def fresh(): return Bag(registry=create_test_settings_registry())
a = fresh(); a.flag = False
b = fresh(); b.flag = True; b.flag = False
print('pristine -> False      :', a.flag, a._is_locally_set('flag'))
print('via True -> False      :', b.flag, b._is_locally_set('flag'))"
```

Expected today: `False False` then `False True` — same value, different answer.

(Spelled `_is_locally_set` because the namespace-separation change has landed
— see "State of the surrounding work" below.)

## State of the surrounding work

A companion session **has landed** four ergonomics changes to the same area:
`promote_default=` on `setting()`, a `bag()` typed accessor, a module-level
`settings_fields()`, and moving **all** framework methods on `Settings` behind
`_` so the attribute namespace belongs to the author's fields.

So as you read this: every `Settings` method is `_`-prefixed (`bag._to_dict()`,
`bag._is_locally_set()`, …), a field name may not start with `_`
(`Settings.__init_subclass__` enforces it), and `settings_fields(bag)` is the
public way to iterate fields. None of it constrains this design — it was
sequenced first because it is mechanical and this is not.

## One thing that is easy to get wrong

Do not model absence as "the field is not in `_set_keys`". That is the opinion
axis, it is already spoken for by `reset()` and by mirror resolution, and
overloading it is exactly the mistake that produced the tri-state workaround.
An absent *value* must survive a save/load as an explicit user choice — which
"no local override" cannot, because on reload a mirror would resolve to the
global instead.
