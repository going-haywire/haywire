---
name: wrapper-nodes-hand-roll-live-vs-rebuild
description: Handoff — every node wrapping an external library re-invents "which knobs are settable now vs only at construction" and the loop that pushes a settings bag onto a foreign object; three hand-rolled variants exist in haybale-visiongraph alone
metadata:
  type: project
  status: open
---

# Wrapper nodes hand-roll live-vs-rebuild, three times over

Identified 2026-09-08/09 while converting **haybale-visiongraph** to
settings-first node configuration (shipped as 0.0.39). Every node in that
library is an adapter between a settings bag and a foreign object's attributes,
and the framework has no vocabulary for that relationship — so each node
invented its own.

Unlike its sibling handoff ([settings-have-no-absent-value](settings-have-no-absent-value.md)),
this one **can** be solved in library space. That is the recommended path: prove
the helper in `haybale-visiongraph`, promote to core only once its shape has
stopped moving.

## The shape of it

Wrapping a camera, a model, or a tracker means every setting is one of two
kinds, and which kind it is, is a **fact about the wrapped library** — found at
the attribute's read site, not a judgement call:

| | Read by the library | Consequence |
|---|---|---|
| **live** | inside a per-frame `process()` / `read()` | settable any time; an edge can genuinely drive it |
| **rebuild** | inside a constructor or `setup()` | an edge would silently do nothing until restart |

The taxonomy already governs real decisions: rebuild-category fields declare
`Promotable.CONFIG` (a pinless face widget is honest; an edge-driven inlet is
not). That rule is documented in `setting-canon.md` §"Live vs rebuild-category
settings" — but it is only prose. Nothing in the API knows about it.

## What it costs — three variants of one idea

All in `barn/haybale-visiongraph/haybale_visiongraph/nodes/`:

1. **`base_estimator_node.py`** — `ModelSpec.rebuild_fields: frozenset[str]`,
   per model, because liveness is per *backend*: `min_score` is read in
   `process()` by Ultralytics/MoveNet/SSD/MaskRCNN but consumed by `setup()` by
   MediaPipe. Plus `hb_apply_build_settings` / `hb_apply_live_settings`, two
   near-identical loops differing only by a set-membership test.
2. **`tracker_node.py`** — `_BACKEND_BAGS: dict[str, tuple[accessor, frozenset]]`
   and a single `hb_apply_settings(tracker, backend, build_time: bool)`. Same
   idea, different data shape, written a day apart.
3. **`oak_d_camera_node.py`** (predates the conversion) — a third spelling:
   `_IR_ATTR_MAP` for name translation, `hb_apply_live_settings` for the
   apply-on-open pass, and `hb_on_ir_changed` / `hb_on_color_changed`
   subscriptions for the live pushes.

The common core, written three times:

```python
for name in type(bag)._settings_descriptors():        # private API; see note below
    if (name in rebuild_fields) is build_time:
        setattr(target, name, getattr(bag, name))
```

(Use the module-level `settings_fields(bag)` — it landed in the companion
session and is the supported spelling. `_settings_descriptors()` is internal.)

Plus, in every case, a hand-written **name/shape translation** layer, because a
settings field rarely maps 1:1 onto the library's attribute:

- `ir.laser_intensity` → `OakDInput.ir_laser_dot_projector_intensity`
- `nms.enabled` / `.nms_threshold` / … → nested `estimator.nms_options.<field>`
- `nms.eta` / `.top_k` → `None` when `-1` (see the absent-value handoff)
- `nms.batch_mode` → `NMSBatchMode[str(value)]` (string ↔ enum bridging)
- OakD's `_AWB_MODES` / `_ANTI_BANDING_MODES` / `_EFFECT_MODES` / `_DEPTH_*` —
  five more string↔enum tables

## The change not made

Roughly:

```python
class NmsSettings(NodeSettings):
    nms_threshold = setting[FLOAT](0.3, applies="live",    target="nms_options.nms_threshold")
    engine        = setting[CHOICES](..., applies="rebuild")
```

with a helper doing the push:

```python
bag.apply_to(estimator, phase="rebuild")   # between create() and setup()
bag.apply_to(estimator, phase="live")      # before process()
```

Two properties worth keeping if this is built:

- **`applies="rebuild"` should imply `Promotable.CONFIG`.** That is the rule the
  last inquisition had to reason out by hand and then apply to 20-odd fields
  one at a time; deriving it removes a whole class of "we forgot on this one".
- **`target="a.b.c"`** subsumes `_IR_ATTR_MAP` and the nested `nms_options`
  special-case in `BaseEstimatorNode.hb_assign`. The enum bridging probably
  does *not* belong here — an IType or a per-field coercion hook is the more
  honest home, and jamming it into `target=` would make it a mini-language.

## Dependency worth knowing before you start

The apply loop's real signature is *"push these fields onto that object,
**skipping the ones the user wants left alone**"*. That skip is exactly the
absent-value concept in
[settings-have-no-absent-value](settings-have-no-absent-value.md), which does
not exist yet. Today the three implementations dodge it with private sentinels.

So: a mirroring helper built *before* absent values will bake those sentinels
into its interface. Either sequence absent-values first, or design
`apply_to` so the skip predicate is pluggable and can be replaced later without
changing call sites.

## Why it was deferred

Two reasons, both still true:

1. It is mostly a **helper**, not a semantic change — so unlike the promotion and
   namespace work it does not have to live in core to be useful. A
   `haybale-visiongraph`-local `apply_to` would already delete the duplication
   between its own three variants and prove the shape against a second wrapper
   library before anything is frozen.
2. Only `applies=` genuinely wants to be on the descriptor (so the
   `Promotable.CONFIG` implication can be derived). Everything else is a
   function over a bag and a target object.

## Where to start

- `barn/haybale-visiongraph/haybale_visiongraph/nodes/base_estimator_node.py` —
  `ModelSpec.rebuild_fields`, `hb_apply_build_settings`, `hb_apply_live_settings`,
  `hb_assign`
- `.../nodes/tracker_node.py` — `_BACKEND_BAGS`, `hb_apply_settings`
- `.../nodes/oak_d_camera_node.py` — `_IR_ATTR_MAP`, `hb_apply_live_settings`,
  the five enum tables
- `docs/components/settings/setting-canon.md` — §"Live vs rebuild-category
  settings" is the prose this would make executable
- `tests/barn/test_visiongraph_settings_first.py` — pins the current behaviour
  (bag gating per backend, per-spec `rebuild_fields`, seeded promotions); a
  refactor onto a helper must keep these green

**The seam that makes rebuild-category reachable at all:** the node owns the
window between construction and `setup()`. `ModelSpec.build()` returns after
`create()`, and `hb_ensure_estimator` calls `estimator.setup()` separately —
attributes written in between are picked up. Anything consumed inside
`__init__` itself is *unreachable* (visiongraph's `engine` is the example: the
enum is turned into an engine object immediately, and `create()` takes only a
config variant). A helper must not promise to reach those.

## One thing that is easy to get wrong

Do not make `rebuild_fields` a node-level list. Liveness is a property of the
**backend**, not the node: `PoseEstimatorNode` has `min_score` rebuild-bound
under MediaPipe and live under MoveNet, in the same node, switched by a
dropdown. A node-level list forces the pessimistic answer everywhere and makes
a slider reload the model on backends where it did not need to.
`tests/barn/test_visiongraph_settings_first.py::test_min_score_change_releases_the_estimator_only_when_rebuild_bound`
exists to catch precisely that regression.
