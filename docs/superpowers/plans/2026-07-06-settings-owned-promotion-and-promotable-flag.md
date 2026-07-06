# Settings-Owned Promotion + Promotable-Flag Implementation Plan

> **✅ IMPLEMENTED (2026-07-06).** All tasks complete; full quality gate green (ruff, ruff format, mypy, unit + integration suites). Shipped: settings-owned promotion (ADR 0019, supersedes ADR 0014's amendment and ADR 0018's promoted-port half; ADR 0018's plain-port raise retained) + the `Promotable`/`promotable=` eligibility flag (merged in from the retired promotable-flag plan). Known follow-up NOT in this plan: `OakDCameraNode.mxid` (haybale-visiongraph repo) is deliberately left raising at construction and must be fixed there separately.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Merge note:** This plan merges two previously-separate plans — `2026-07-06-settings-owned-promotion` (promotion *state ownership + serialization*) and `2026-07-06-promotable-flag` (promotion *capability + eligibility*). They were merged because both edit `promote_setting`, `setting-canon.md`, and the OAK-D node, and promotable-flag's Task 2 patched `bind_promoted_ports` — which this plan renames to `regenerate_promoted_ports` and rewrites. Merging edits each shared surface exactly once. The old `2026-07-06-promotable-flag.md` plan is superseded by this file (Task 12 deletes it).

**Goal:** (1) Move promotion state out of the serialized port into `Settings` (`_promoted_keys: dict[str, PortType]`) so promoted ports are never serialized (regenerated on load), eliminating the `widget_config`-callable JSON crash for promoted ports; (2) raise loudly at construction for the plain-port callable case; (3) let a `setting()` declare which port directions it may be promoted to (`promotable=Promotable.NONE|INLET|OUTLET|ALL`) so restart-required fields (e.g. the OAK-D `depth` bag) can be marked non-promotable.

**Architecture:** Promotion becomes a per-instance, per-field opinion the settings bag owns — `_promoted_keys[storage_key] = direction` — mirroring `_set_keys`/`_ui_disabled_keys`. A bag serializes as `{"values": {...}, "promoted": {storage_key: "inlet"|"outlet"}}`. Promoted ports vanish from the serialized `ports` block; on load, one idempotent regen pass calls the existing `promote_setting()` per stored promotion. Plain ports validate `widget_config` via `is_cattrs_serializable()` at `DataPort.__post_init__`. Separately, a `Promotable` Flag enum on the descriptor plus a single `eligible_promotion_directions()` helper (declared `promotable` ∩ the read-only structural rule) gate which directions `promote_setting` allows and which the promote menu shows. This reverses ADR 0014's amendment (port-is-the-signal) and supersedes-in-part ADR 0018 (the plain-port raise is preserved).

**Tech Stack:** Python (`enum.Flag`), existing Haywire settings/promotion/port system (`haywire.core.settings.settings`/`descriptor`, `haywire.core.node.promotion`, `haywire.core.node.base`/`data`, `haywire.core.types.port`, `haywire.core.types.utils.is_cattrs_serializable`), the graph-editor promote menu (`barn/haybale-graph-editor/.../menu/node/promote.py`), `HaywireException` (`haywire.core.errors.haywire_exception`) for the reset-on-old-format notice.

## Global Constraints

- **Single source of truth:** `_promoted_keys: dict[str, PortType]` on each `Settings` instance is the ONLY authoritative record of what is promoted. Never derive promotion from port presence or from edges. `is_field_promoted` consults `_promoted_keys`.
- **Promoted ports are never serialized.** `DataPort.to_dict()` / the port-serialization loop emits NOTHING for a port whose `promoted` is `True`. They are regenerated from `_promoted_keys` on load via `promote_setting()`.
- **One creation path.** Both interactive promotion and load-time regeneration funnel through `promote_setting(node, accessor, field, direction)`, which is idempotent via its existing `if pid in node.ports: return` guard.
- **Demote clears the settings-side record.** `demote_setting` removes the port, unbinds the cell, AND clears `_promoted_keys[storage_key]`. Promote writes the key, demote clears it — mirror operations.
- **Serialized bag shape is `{"values": {...}, "promoted": {...}}`** — a hard, breaking format change. No backward compatibility with the old flat `{field: value}` shape.
- **Old-format load = reset-and-continue.** A settings dict lacking the `"values"`/`"promoted"` structure is treated as incompatible: the bag is left at descriptor defaults (effectively reset), the node loads and is fully functional, and a WARNING-severity `HaywireException` is attached to the node (renders via the existing `UINodeCard`/`render_error_details` surface).
- **Plain-port `widget_config` callables raise at construction.** `DataPort.__post_init__` runs `is_cattrs_serializable(self.widget_config)` when `self.promoted` is `False`; a non-serializable value raises `TypeError` naming the port id and the reason. Skipped entirely when `self.promoted` is `True`.
- **`_promoted_keys` is transient runtime state that DOES serialize** (into the bag's `"promoted"` section) — distinct from `_ui_disabled_keys`/`_set_keys` in that respect. It is NOT class metadata.
- **Direction reuses `PortType`.** `_promoted_keys` values are `PortType.INLET` / `PortType.OUTLET`. Serialized as the lowercase enum value string (`"inlet"`/`"outlet"`), restored via `PortType(<str>)`.
- **`OakDCameraNode.mxid` is left deliberately broken** by the plain-port raise (it's a plain `as_config` port with a callable). Its fix is a separate follow-up in the `haybale-visiongraph` repo — NOT in this plan. (This plan DOES touch that repo for the `depth`-bag `promotable=NONE` task, but not `mxid`.)
- **Demote-in-same-session widget_config gap** (a demoted port keeps its promoted-era `widget_config` because `__post_init__` doesn't re-run) is an accepted, documented known limitation — do not build against it.
- **Eligibility = `promotable` ∩ structural rules.** `Promotable` is a `Flag` (`NONE=0`/`INLET`/`OUTLET`/`ALL=INLET|OUTLET`), default `Promotable.ALL` (preserves today's behavior for every existing `setting()`). `read_only=True` still forces outlet-only regardless of `promotable`; contradictions (e.g. `read_only=True, promotable=INLET`) intersect to empty — not an error, just not promotable. `eligible_promotion_directions(descriptor) -> tuple[PortType, ...]` is the SINGLE source of truth, consumed by both `promote_setting` (raises for ineligible NEW promotions) and the promote menu (hides ineligible entries).
- **Eligibility enforced uniformly, no grandfathering.** `promote_setting` raises for any ineligible direction, whether called interactively or from the load-time regen pass. There are NO saved graphs with promoted ports yet, so there is nothing to grandfather — an ineligible promotion is always a live authoring mistake and should fail loudly. (If saved promoted ports ever exist and a library later narrows `promotable=`, a grandfather bypass can be added then; do not build it speculatively now.)
- **`promotable` is class-declaration metadata, never persisted** — distinct from `_promoted_keys` (which IS persisted, in the bag's `"promoted"` section). Do not conflate the capability (`promotable=`) with the current state (`_promoted_keys`).
- **Naming:** `promotable=` (the `setting()` kwarg), `_promotable` (descriptor attribute), `Promotable` (Flag enum, exported from `haywire.core.settings`), `eligible_promotion_directions(descriptor) -> tuple[PortType, ...]`.
- Ruff (`ruff check .`, `ruff format --check .`) and mypy must stay clean on every touched file, per CLAUDE.md. Baseline (`uv run ruff check <path>` / `uv run mypy <path>`) before each task's edits, re-run after.

---

## File Structure

| File | Responsibility |
|---|---|
| `packages/haywire-core/src/haywire/core/settings/settings.py` | Add `_promoted_keys: dict[str, PortType]` to `__init__`; `set_promoted`/`clear_promoted`/`get_promoted_direction`/`is_promoted` accessors; new `to_dict()` shape `{"values",  "promoted"}` + `from_dict()` reading it + `PromotedFormatError` on old shape. |
| `packages/haywire-core/src/haywire/core/settings/descriptor.py` | `Promotable` Flag enum; `promotable: Promotable = Promotable.ALL` kwarg on `setting.__init__`, stored as `self._promotable`. |
| `packages/haywire-core/src/haywire/core/settings/__init__.py` | Export `Promotable` (add to the `.descriptor` import line and `__all__`). |
| `packages/haywire-core/src/haywire/core/node/promotion.py` | `eligible_promotion_directions()` single source of truth; `promote_setting` writes `_promoted_keys` AND gates on eligibility (uniformly); `demote_setting` clears the key; `is_field_promoted` consults `_promoted_keys`; `bind_promoted_ports` becomes `regenerate_promoted_ports` (creates ports from `_promoted_keys` via `promote_setting`). |
| `packages/haywire-core/src/haywire/core/types/port.py` | `DataPort.__post_init__`: `is_cattrs_serializable` check on `widget_config` when not promoted. `to_dict()` already skips `field_data` for promoted — the port-loop skip lives in `data.py`. |
| `packages/haywire-core/src/haywire/core/node/data.py` | `_serialize_ports` skips promoted ports; `_bind_promoted_ports` renamed/rewired to call `regenerate_promoted_ports`. |
| `packages/haywire-core/src/haywire/core/node/base.py` | `_initialize_from_dict`: catch `PromotedFormatError` from a bag's `from_dict`, reset that bag, attach a WARNING `HaywireException`; call the regen pass (renamed). |
| `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/node/promote.py` | `promotable_fields` calls `eligible_promotion_directions` instead of re-deriving the rule; hides ineligible fields. |
| `tests/core/test_settings/test_promoted_keys.py` | New: `_promoted_keys` accessors, `to_dict`/`from_dict` new shape, `PromotedFormatError` on old shape, round-trip. No NiceGUI. |
| `tests/core/settings/test_promotable_eligibility.py` | New: `Promotable` enum/kwarg, `eligible_promotion_directions` matrix, promote-guard. |
| `tests/core/node/test_promotion_serialization.py` | Extend/rewrite: promoted port absent from serialized ports; round-trip regenerates the port; edge-into-promoted-inlet survives; demote clears the key. |
| `tests/core/node/test_promotion_reset_on_old_format.py` | New: old-shape settings dict → bag reset + WARNING `HaywireException` on node, node still loads. |
| `tests/ui/widget/test_widget_config_serializable.py` | New: plain port with callable `widget_config` raises `TypeError` at construction; promoted port with callable does NOT. |
| `tests/ui/menu/test_promote_demote_menu.py` | Extend: `promotable=NONE` field absent from menu; single-direction declarations collapse. |
| `docs/adr/0019-settings-owned-promotion.md` | New ADR (supersedes ADR 0014 amendment; supersedes-in-part ADR 0018). |
| `docs/reference/glossary.md` | Update `Promotion` and `live widget_config callable` entries to the new model. |
| `docs/components/settings/setting-canon.md` | Update the promotion serialization description; document `promotable=`. |
| `barn/haybale-visiongraph/haybale_visiongraph/nodes/oak_d_camera_node.py` | The six `depth`-bag fields get `promotable=Promotable.NONE`. (gitignored symlink — commit from the haybale-visiongraph repo.) |
| `barn/haybale-visiongraph/notes.md` | Record the `depth`-bag `promotable=NONE` decision. |
| `docs/superpowers/plans/2026-07-06-promotable-flag.md` | DELETED — merged into this plan (Task 12). |

---

### Task A: `Promotable` enum + `promotable=` kwarg on `setting()`

> **Ordering:** This is a foundational, standalone task (pure additive metadata). It comes before Task 1 because Task 3's merged `promote_setting` guard and Task B's menu both consume `Promotable`/`eligible_promotion_directions`. Labeled "A"/"B" (not renumbered) to keep the original settings-owned-promotion tasks 1-8 stable; execute in file order: A, 1, 2, 3, B, 4, 5, 6, ... (see the ordering note before Task 4).

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/descriptor.py` (enum near top; `setting.__init__` signature/docstring/storage)
- Modify: `packages/haywire-core/src/haywire/core/settings/__init__.py` (export)
- Test: `tests/core/settings/test_promotable_eligibility.py` (new — descriptor-level tests in this task)

**Interfaces:**
- Consumes: nothing new.
- Produces (relied on by Tasks 3, B, and the OAK-D task):
  - `haywire.core.settings.Promotable` — `Flag` with `NONE = 0`, `INLET`, `OUTLET`, `ALL = INLET | OUTLET`.
  - `setting(..., promotable: Promotable = Promotable.ALL)` stored as `self._promotable: Promotable`.

- [x] **Step 1: Baseline check**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/settings/ && uv run mypy packages/haywire-core/src/haywire/core/settings/`
Expected: both clean. If not, stop and raise it.

- [x] **Step 2: Write the failing tests (descriptor level)**

Create `tests/core/settings/test_promotable_eligibility.py`:

```python
# tests/core/settings/test_promotable_eligibility.py
"""
promotable= eligibility:

- Promotable Flag enum semantics and the setting() kwarg (this task)
- eligible_promotion_directions() matrix, promote_setting guard, and the
  promote guard (added in Task 3 of the merged plan)
- the promote menu consumes the same helper (tests/ui/menu/test_promote_demote_menu.py)
"""

# Per CLAUDE.md test trap: import editor before other haywire modules.
import haywire.core.graph.editor  # noqa: F401

import pytest

from haywire.barn.builtin.types import FLOAT
from haywire.core.settings import Promotable, setting


@pytest.mark.unit
class TestPromotableEnum:
    def test_all_is_inlet_or_outlet(self):
        assert Promotable.ALL == Promotable.INLET | Promotable.OUTLET

    def test_none_contains_nothing(self):
        assert Promotable.INLET not in Promotable.NONE
        assert Promotable.OUTLET not in Promotable.NONE

    def test_membership(self):
        assert Promotable.INLET in Promotable.ALL
        assert Promotable.OUTLET in Promotable.ALL
        assert Promotable.OUTLET not in Promotable.INLET


@pytest.mark.unit
class TestPromotableKwarg:
    def test_default_is_all(self):
        desc = setting(0.5, type_=FLOAT)
        assert desc._promotable is Promotable.ALL

    def test_kwarg_is_stored(self):
        desc = setting(0.5, type_=FLOAT, promotable=Promotable.NONE)
        assert desc._promotable is Promotable.NONE

    def test_single_direction_is_stored(self):
        desc = setting(0.5, type_=FLOAT, promotable=Promotable.OUTLET)
        assert desc._promotable is Promotable.OUTLET
```

- [x] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/core/settings/test_promotable_eligibility.py -v`
Expected: FAIL — `ImportError: cannot import name 'Promotable'`.

- [x] **Step 4: Add the enum and the kwarg**

In `packages/haywire-core/src/haywire/core/settings/descriptor.py`:

Add `Flag, auto` to the stdlib imports (a new import line near the top-of-file imports):

```python
from enum import Flag, auto
```

Add the enum after the imports, before the `setting` class definition:

```python
class Promotable(Flag):
    """Which DATA-port directions a ``setting()`` may be promoted to.

    Declared intent only — structural rules still intersect on top (a
    ``read_only``/``watch()`` field has no write path in, so it can never be
    an inlet regardless of this flag). ``eligible_promotion_directions()`` in
    ``haywire.core.node.promotion`` is the single place that combines both.

    ``NONE`` marks fields where a promotion would be *misleading* rather than
    ill-typed — e.g. restart-required device-pipeline parameters, where a port
    would imply live control the hardware can't deliver.
    """

    NONE = 0
    INLET = auto()
    OUTLET = auto()
    ALL = INLET | OUTLET
```

In `setting.__init__`, add the kwarg to the signature **after the `ui_disabled` parameter** (added by the reactive-panel-disabling plan, which has landed):

```python
        ui_disabled: bool = False,
        promotable: Promotable = Promotable.ALL,
    ) -> None:
```

Add the docstring entry **after the `ui_disabled` parameter doc block**:

```python
    promotable : Promotable
        Which port directions this field may be promoted to (default
        ``Promotable.ALL``). ``Promotable.NONE`` removes the field from the
        promote menu entirely and makes ``promote_setting()`` raise — use it
        for fields where a port would be misleading (e.g. restart-required
        pipeline parameters). Structural rules still apply on top:
        ``read_only=True`` remains outlet-only regardless.
```

Add the storage **after the `self._ui_disabled: bool = ui_disabled` line**:

```python
        self._promotable: Promotable = promotable
```

In `packages/haywire-core/src/haywire/core/settings/__init__.py`, extend the descriptor import line and `__all__`:

```python
from .descriptor import setting, shadow, watch, Promotable
```

and add `"Promotable",` to the `__all__` list (in the Node-author API group, after `"watch",`).

- [x] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/core/settings/test_promotable_eligibility.py -v`
Expected: PASS, all 6 tests green.

- [x] **Step 6: Full baseline re-check + settings suite**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/settings/ && uv run ruff format --check packages/haywire-core/src/haywire/core/settings/ && uv run mypy packages/haywire-core/src/haywire/core/settings/ && uv run pytest tests/core/test_settings/ tests/core/settings/ -q`
Expected: all clean, no regressions.

- [x] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/settings/descriptor.py packages/haywire-core/src/haywire/core/settings/__init__.py tests/core/settings/test_promotable_eligibility.py
git commit -m "feat(settings): Promotable flag enum and promotable= kwarg on setting()"
```

---

### Task 1: `_promoted_keys` state + accessors on `Settings`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/settings.py` (`__init__` after line 106; new accessors after the `_local_value` block ~line 120)
- Test: `tests/core/test_settings/test_promoted_keys.py` (new)

**Interfaces:**
- Consumes: `PortType` (`haywire.core.types.enums`), existing `_property_settings()`, `storage_key`.
- Produces (relied on by Tasks 2, 3, 4):
  - `Settings._promoted_keys: dict[str, PortType]` — instance state, `storage_key → direction`.
  - `Settings.set_promoted(field: str, direction: PortType) -> None` — records; warns+ignores unknown field.
  - `Settings.clear_promoted(field: str) -> None` — removes; silent for unknown/not-promoted.
  - `Settings.is_promoted(field: str) -> bool` — `False` for unknown.
  - `Settings.get_promoted_direction(field: str) -> PortType | None` — `None` if not promoted.

- [x] **Step 1: Baseline check**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/settings/settings.py && uv run mypy packages/haywire-core/src/haywire/core/settings/settings.py`
Expected: both clean. If not, stop and raise it.

- [x] **Step 2: Write the failing tests**

Create `tests/core/test_settings/test_promoted_keys.py`:

```python
# tests/core/test_settings/test_promoted_keys.py
"""
_promoted_keys state + accessors on Settings (Task 1 of settings-owned-promotion):

- set_promoted / clear_promoted / is_promoted / get_promoted_direction
- keyed by storage_key, storing a PortType direction
- unknown-field handling (warn+ignore on set, silent on clear/read)

Serialization (to_dict/from_dict new shape) is tested separately in Task 2's
additions to this file. Panel/port wiring is tested at higher layers.
"""

import logging

from haywire.core.settings import Settings, setting
from haywire.core.types.enums import PortType
from haywire.barn.builtin.types import BOOL, FLOAT


class PromoSettings(Settings):
    alpha = setting[FLOAT](1.0, label="Alpha")
    beta = setting[FLOAT](2.0, label="Beta")
    flag = setting[BOOL](True, label="Flag")


class TestPromotedAccessors:
    def test_field_starts_unpromoted(self):
        bag = PromoSettings()
        assert bag.is_promoted("alpha") is False
        assert bag.get_promoted_direction("alpha") is None

    def test_set_promoted_inlet(self):
        bag = PromoSettings()
        bag.set_promoted("alpha", PortType.INLET)
        assert bag.is_promoted("alpha") is True
        assert bag.get_promoted_direction("alpha") is PortType.INLET

    def test_set_promoted_outlet(self):
        bag = PromoSettings()
        bag.set_promoted("beta", PortType.OUTLET)
        assert bag.get_promoted_direction("beta") is PortType.OUTLET

    def test_clear_promoted(self):
        bag = PromoSettings()
        bag.set_promoted("alpha", PortType.INLET)
        bag.clear_promoted("alpha")
        assert bag.is_promoted("alpha") is False
        assert bag.get_promoted_direction("alpha") is None

    def test_reset_direction_by_re_setting(self):
        bag = PromoSettings()
        bag.set_promoted("alpha", PortType.INLET)
        bag.set_promoted("alpha", PortType.OUTLET)  # a field has at most one port
        assert bag.get_promoted_direction("alpha") is PortType.OUTLET

    def test_is_promoted_unknown_field_false(self):
        bag = PromoSettings()
        assert bag.is_promoted("nonexistent") is False
        assert bag.get_promoted_direction("nonexistent") is None

    def test_set_promoted_unknown_field_warns_and_ignores(self, caplog):
        bag = PromoSettings()
        with caplog.at_level(logging.WARNING):
            bag.set_promoted("nonexistent", PortType.INLET)
        assert any("nonexistent" in rec.message for rec in caplog.records)
        assert bag.is_promoted("nonexistent") is False

    def test_clear_promoted_unknown_or_unpromoted_is_silent(self):
        bag = PromoSettings()
        bag.clear_promoted("nonexistent")  # must not raise
        bag.clear_promoted("alpha")  # not promoted — must not raise
        assert bag.is_promoted("alpha") is False

    def test_promotion_does_not_affect_value(self):
        bag = PromoSettings()
        bag.set_promoted("alpha", PortType.INLET)
        assert bag.alpha == 1.0
        bag.alpha = 9.0
        assert bag.alpha == 9.0
        assert bag.is_promoted("alpha") is True
```

- [x] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_settings/test_promoted_keys.py -v`
Expected: FAIL — `AttributeError: 'PromoSettings' object has no attribute 'set_promoted'` (or `is_promoted`).

- [x] **Step 4: Add `_promoted_keys` to `__init__` and the accessors**

In `packages/haywire-core/src/haywire/core/settings/settings.py`:

Add the import to the existing imports (find the block importing from `haywire.core.types`; if none, add a top-level import). The file already references `PortType`-adjacent types only in TYPE_CHECKING — add a real import near the top-level imports:

```python
from haywire.core.types.enums import PortType
```

Add the state to `__init__`, right after the `self._node: "NodeData | None" = node` line (currently line 111):

```python
        # Promotion state — the SINGLE source of truth for which fields are
        # currently promoted to a DATA port and in which direction. Mirrors the
        # per-instance, storage_key-keyed shape of _set_keys/_ui_disabled_keys,
        # but (unlike those) DOES serialize — into this bag's "promoted" block —
        # because a promoted port is regenerated from here on load rather than
        # persisted in the ports block. A field has at most one promoted port
        # (its id IS the storage_key), so this is a single direction per key,
        # never a set. See ADR 0019 and haywire.core.node.promotion.
        self._promoted_keys: dict[str, PortType] = {}
```

Add the accessors right after the `_local_value` method (currently ending ~line 120):

```python
    def set_promoted(self, name: str, direction: PortType) -> None:
        """Record that field *name* is promoted to a port in *direction*.

        The single source of truth for promotion. Called by
        ``promote_setting`` (interactive AND load-time regen). Unknown *name*:
        logs a warning and ignores (catches typos / stale field names).
        Purely a promotion record — does not touch the field's value cell.
        """
        fields = type(self)._property_settings()
        if name not in fields:
            logger.warning(
                "set_promoted: unknown field %r on %s — ignored", name, type(self).__name__
            )
            return
        self._promoted_keys[fields[name].storage_key] = direction

    def clear_promoted(self, name: str) -> None:
        """Clear field *name*'s promotion record (no-op if absent/unknown).

        Called by ``demote_setting``. Mirror of :meth:`set_promoted`."""
        fields = type(self)._property_settings()
        if name not in fields:
            return
        self._promoted_keys.pop(fields[name].storage_key, None)

    def is_promoted(self, name: str) -> bool:
        """True if field *name* is currently promoted. False for unknown names."""
        fields = type(self)._property_settings()
        if name not in fields:
            return False
        return fields[name].storage_key in self._promoted_keys

    def get_promoted_direction(self, name: str) -> PortType | None:
        """The direction field *name* is promoted to, or None if not promoted."""
        fields = type(self)._property_settings()
        if name not in fields:
            return None
        return self._promoted_keys.get(fields[name].storage_key)
```

- [x] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_settings/test_promoted_keys.py -v`
Expected: PASS, all 9 tests green.

- [x] **Step 6: Full baseline re-check + settings suite**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/settings/settings.py && uv run ruff format --check packages/haywire-core/src/haywire/core/settings/settings.py && uv run mypy packages/haywire-core/src/haywire/core/settings/settings.py && uv run pytest tests/core/test_settings/ -q`
Expected: all clean, no regressions.

- [x] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/settings/settings.py tests/core/test_settings/test_promoted_keys.py
git commit -m "feat(settings): _promoted_keys state + accessors (single source of truth for promotion)"
```

---

### Task 2: New `Settings.to_dict()`/`from_dict()` shape + `PromotedFormatError`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/settings.py` (`to_dict` lines 315-333, `from_dict` lines 335-355; new exception near top)
- Test: `tests/core/test_settings/test_promoted_keys.py` (extend)

**Interfaces:**
- Consumes: `_promoted_keys` (Task 1), existing `_is_locally_set`/`_local_value`/`_write_local`, `PortType`.
- Produces (relied on by Tasks 3, 4):
  - `Settings.to_dict() -> dict` now returns `{"values": {field: value, ...}, "promoted": {storage_key: "inlet"|"outlet", ...}}`.
  - `Settings.from_dict(data: dict) -> None` reads that shape; restores `_promoted_keys`; raises `PromotedFormatError` if `data` is non-empty and lacks the `"values"` key (old flat shape).
  - `haywire.core.settings.settings.PromotedFormatError(Exception)` — raised on an incompatible (pre-refactor) settings dict.

- [x] **Step 1: Baseline check**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/settings/settings.py && uv run mypy packages/haywire-core/src/haywire/core/settings/settings.py`
Expected: both clean.

- [x] **Step 2: Write the failing tests**

Append to `tests/core/test_settings/test_promoted_keys.py`:

```python
from haywire.core.settings.settings import PromotedFormatError
import pytest


class TestSerializationShape:
    def test_to_dict_new_shape_empty(self):
        bag = PromoSettings()
        d = bag.to_dict()
        assert d == {"values": {}, "promoted": {}}

    def test_to_dict_includes_values_and_promotions(self):
        bag = PromoSettings()
        bag.alpha = 5.0  # locally set, differs from default
        bag.set_promoted("beta", PortType.OUTLET)
        d = bag.to_dict()
        assert d["values"] == {"alpha": 5.0}
        # promoted is keyed by storage_key; for a plain field storage_key == attr name
        assert d["promoted"] == {"beta": "outlet"}

    def test_from_dict_restores_values_and_promotions(self):
        bag = PromoSettings()
        bag.from_dict({"values": {"alpha": 7.0}, "promoted": {"beta": "inlet"}})
        assert bag.alpha == 7.0
        assert bag.is_promoted("beta") is True
        assert bag.get_promoted_direction("beta") is PortType.INLET

    def test_round_trip(self):
        bag = PromoSettings()
        bag.beta = 42.0
        bag.set_promoted("alpha", PortType.INLET)
        restored = PromoSettings()
        restored.from_dict(bag.to_dict())
        assert restored.beta == 42.0
        assert restored.get_promoted_direction("alpha") is PortType.INLET

    def test_from_dict_old_flat_shape_raises(self):
        bag = PromoSettings()
        with pytest.raises(PromotedFormatError):
            bag.from_dict({"alpha": 5.0})  # pre-refactor flat shape

    def test_from_dict_empty_is_not_an_error(self):
        bag = PromoSettings()
        bag.from_dict({})  # a bag that serialized nothing — must not raise
        assert bag.alpha == 1.0

    def test_from_dict_missing_promoted_section_defaults_empty(self):
        bag = PromoSettings()
        bag.from_dict({"values": {"alpha": 3.0}})  # no "promoted" key
        assert bag.alpha == 3.0
        assert bag._promoted_keys == {}
```

- [x] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_settings/test_promoted_keys.py::TestSerializationShape -v`
Expected: FAIL — `ImportError: cannot import name 'PromotedFormatError'` (collection error), or shape assertions fail.

- [x] **Step 4: Add `PromotedFormatError` and rewrite `to_dict`/`from_dict`**

In `packages/haywire-core/src/haywire/core/settings/settings.py`:

Add the exception near the top of the module, after the imports and before the `Settings` class:

```python
class PromotedFormatError(Exception):
    """A settings dict is in the pre-promotion-refactor flat ``{field: value}``
    shape and cannot be restored by the current ``{"values", "promoted"}``
    loader. Raised by ``Settings.from_dict``; the node loader catches it,
    resets the bag to defaults, and attaches a WARNING to the node (see
    ``BaseNode._initialize_from_dict``). Hard breaking change — no migration
    (ADR 0019)."""
```

Replace `to_dict` (currently lines 315-333):

```python
    def to_dict(self) -> dict:
        """Serialize to ``{"values": {...}, "promoted": {...}}``.

        ``values``: only fields whose value differs from the descriptor default
        and are locally set (read_only/mirrored fields are never serialized) —
        same value-selection rule as before, now nested under a key.
        ``promoted``: this bag's promotion records, ``storage_key → direction``
        (``"inlet"``/``"outlet"``). A promoted port is regenerated from this on
        load — it is NOT persisted in the node's ports block (ADR 0019).
        """
        fields = type(self)._property_settings()
        values: dict = {}
        for name, descriptor in fields.items():
            if descriptor._read_only:
                continue
            if not self._is_locally_set(descriptor):
                continue
            val = self._local_value(descriptor)
            if val != descriptor._default:
                values[name] = val
        promoted = {key: direction.value for key, direction in self._promoted_keys.items()}
        return {"values": values, "promoted": promoted}

    def from_dict(self, data: dict) -> None:
        """Restore from the ``{"values", "promoted"}`` shape (trusted graph load).

        Values restore exactly as before (direct cell write via ``_write_local``,
        no validator, marked locally set). Promotion records restore into
        ``_promoted_keys``; the node loader then regenerates the actual ports
        (``regenerate_promoted_ports``). Unknown value keys and read_only fields
        are skipped without error (forward compatibility within the new shape).

        Raises ``PromotedFormatError`` if *data* is non-empty but lacks the
        ``"values"`` key — the pre-refactor flat shape. An empty ``{}`` (a bag
        that serialized nothing) is valid and restores nothing.
        """
        if data and "values" not in data:
            raise PromotedFormatError(
                f"{type(self).__name__}: settings dict is in the pre-promotion-refactor "
                f"flat format (no 'values' key); expected {{'values', 'promoted'}}. "
                f"This graph predates ADR 0019 and its settings for this bag cannot be "
                f"restored; the node will load with default settings."
            )
        fields = type(self)._property_settings()
        for attr_name, value in data.get("values", {}).items():
            if attr_name not in fields:
                continue
            descriptor = fields[attr_name]
            if descriptor._read_only:
                continue
            self._write_local(descriptor, value)
        for key, direction_str in data.get("promoted", {}).items():
            self._promoted_keys[key] = PortType(direction_str)
```

- [x] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_settings/test_promoted_keys.py -v`
Expected: PASS, all tests green (Task 1's + Task 2's).

- [x] **Step 6: Run the full settings suite for regressions**

Run: `uv run pytest tests/core/test_settings/ -q`
Expected: EXPECT FAILURES here in any existing test that asserts the OLD flat `to_dict()` shape or calls `from_dict` with a flat dict. These are legitimate breakage from the format change. Fix each such test to use the new `{"values", "promoted"}` shape. Re-run until green. (Do not "fix" by reverting the format — the format change is the deliverable.)

- [x] **Step 7: Full baseline re-check**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/settings/settings.py && uv run ruff format --check packages/haywire-core/src/haywire/core/settings/settings.py && uv run mypy packages/haywire-core/src/haywire/core/settings/settings.py`
Expected: all clean.

- [x] **Step 8: Commit**

```bash
git add packages/haywire-core/src/haywire/core/settings/settings.py tests/core/test_settings/
git commit -m "feat(settings): {values, promoted} to_dict shape + PromotedFormatError (breaking)"
```

---

### Task 3: Promotion wiring — `_promoted_keys` state + `eligible_promotion_directions` guard; regen replaces bind

> **Merged task:** This combines the settings-owned-promotion wiring (state write/clear, regen) with promotable-flag's eligibility gate (`eligible_promotion_directions` + `promote_setting` guard), because both edit `promote_setting`/`regenerate_promoted_ports`. Task A (the `Promotable` enum) is a prerequisite.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/node/promotion.py` (`is_field_promoted` lines 24-35; new `eligible_promotion_directions` after `_descriptor` ~line 55; `promote_setting` guard+param+write; `demote_setting` lines 180-186; replace `bind_promoted_ports` lines 99-117 with `regenerate_promoted_ports`)
- Modify: `packages/haywire-core/src/haywire/core/node/data.py` (`_serialize_ports` lines 914-924; `_bind_promoted_ports` lines 958-963)
- Test: `tests/core/node/test_promotion_serialization.py` (rewrite/extend); `tests/core/settings/test_promotable_eligibility.py` (extend — eligibility matrix, promote guard)

**Interfaces:**
- Consumes: `Settings.set_promoted`/`clear_promoted`/`is_promoted`/`get_promoted_direction` (Task 1); `Promotable`/`desc._promotable` (Task A); existing `promote_setting` body, `_descriptor`, `_bind_port`, `PortType`.
- Produces (relied on by Tasks 4, B):
  - `eligible_promotion_directions(descriptor: "setting") -> tuple[PortType, ...]` — ordered `(INLET, OUTLET)` subset; empty = not promotable. THE single eligibility source of truth.
  - `promote_setting(...)` — raises for ineligible promotions (uniformly; no bypass); writes `bag.set_promoted(field, direction)`.
  - `demote_setting(node, port_id)` now also calls `bag.clear_promoted(field)`.
  - `is_field_promoted(bag, field) -> bool` now returns `bag.is_promoted(field)`.
  - `regenerate_promoted_ports(node) -> None` — iterates every bag's `_promoted_keys`, calls `promote_setting` for each (idempotent). Replaces `bind_promoted_ports`.
  - `NodeData._serialize_ports` omits ports whose `promoted` is `True`.

- [x] **Step 1: Baseline check**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/node/promotion.py packages/haywire-core/src/haywire/core/node/data.py && uv run mypy packages/haywire-core/src/haywire/core/node/promotion.py packages/haywire-core/src/haywire/core/node/data.py`
Expected: both clean.

- [x] **Step 2: Write the failing tests**

Rewrite `tests/core/node/test_promotion_serialization.py` (read the existing file first; preserve any node-building fixture/helpers it defines and adapt assertions to the new model). The new behavioral contract to assert:

```python
# tests/core/node/test_promotion_serialization.py
"""
Settings-owned promotion serialization (ADR 0019):

- a promoted port is ABSENT from the serialized ports block
- promotion is recorded in the owning bag's "promoted" section instead
- round-trip regenerates the live port from _promoted_keys via promote_setting
- an edge into a promoted inlet survives round-trip (port exists before edges wire)
- demote clears both the port AND the settings-side _promoted_keys record

Uses the existing node/graph fixtures in this test module; only the assertions
change from the old "promoted port serializes value-less in ports block" model.
"""

# Per CLAUDE.md test trap: import editor before other haywire modules.
import haywire.core.graph.editor  # noqa: F401

import pytest

from haywire.core.node.promotion import promote_setting, demote_setting, is_field_promoted
from haywire.core.types.enums import PortType

pytestmark = pytest.mark.integration

# NOTE to implementer: reuse the module's existing helper for building a node
# with a settings bag + a graph (grep the current file for its fixture, e.g.
# a `make_promotable_node` / graph-load helper). The tests below assume:
#   node       — a live node with bag accessor "filter" and field "threshold"
#   serialize  — node._to_dict()
#   reload     — round-trip a node dict back into a fresh node instance
# Adapt names to whatever the existing file provides.


class TestPromotedPortNotSerialized:
    def test_promoted_port_absent_from_ports_block(self, promotable_node):
        node = promotable_node
        promote_setting(node, "filter", "threshold", PortType.INLET)
        d = node._to_dict()
        pid = type(node.filter).__dict__["threshold"].storage_key
        assert pid not in d["ports"], "a promoted port must not serialize in the ports block"

    def test_promotion_recorded_in_settings_block(self, promotable_node):
        node = promotable_node
        promote_setting(node, "filter", "threshold", PortType.OUTLET)
        d = node._to_dict()
        pid = type(node.filter).__dict__["threshold"].storage_key
        assert d["settings"]["filter"]["promoted"] == {pid: "outlet"}


class TestRoundTripRegeneratesPort:
    def test_reload_regenerates_the_promoted_port(self, promotable_node, reload_node):
        node = promotable_node
        promote_setting(node, "filter", "threshold", PortType.INLET)
        pid = type(node.filter).__dict__["threshold"].storage_key
        reloaded = reload_node(node)
        assert pid in reloaded.ports, "reload must regenerate the promoted port"
        assert reloaded.ports[pid].promoted is True
        assert reloaded.ports[pid].is_inlet() is True
        assert is_field_promoted(reloaded.filter, "threshold") is True


class TestEdgeIntoPromotedInletSurvives:
    def test_edge_to_promoted_inlet_round_trips(self, promotable_node_in_graph, reload_graph):
        graph, src_node, sink_node = promotable_node_in_graph
        promote_setting(sink_node, "filter", "threshold", PortType.INLET)
        pid = type(sink_node.filter).__dict__["threshold"].storage_key
        # wire an edge from src outlet into the promoted inlet, then reload the graph
        graph.create_edge_wrapper(src_node.node_id, "out", sink_node.node_id, pid)
        reloaded = reload_graph(graph)
        # the regenerated port exists and the edge resolved to it
        reloaded_sink = reloaded.get_node(sink_node.node_id)
        assert pid in reloaded_sink.ports
        assert any(
            e.edge.inlet_port_id == pid for e in reloaded.edge_wrappers.values()
        ), "the edge into the promoted inlet must survive round-trip"


class TestDemoteClearsRecord:
    def test_demote_clears_promoted_keys(self, promotable_node):
        node = promotable_node
        promote_setting(node, "filter", "threshold", PortType.INLET)
        pid = type(node.filter).__dict__["threshold"].storage_key
        demote_setting(node, pid)
        assert pid not in node.ports
        assert node.filter.is_promoted("threshold") is False
        assert node.filter._promoted_keys == {}
```

If the existing test file lacks fixtures like `promotable_node`/`reload_node`/`reload_graph`, add them as module-level pytest fixtures built on whatever node/graph construction the surrounding test suite already uses (grep `tests/core/node/` for an existing node-with-settings-bag + graph-round-trip helper and reuse it; do not invent a new node type if one exists).

- [x] **Step 2b: Write the eligibility tests (append to `test_promotable_eligibility.py`)**

Append to `tests/core/settings/test_promotable_eligibility.py` (created in Task A). These cover `eligible_promotion_directions` and the `promote_setting` guard:

```python
@pytest.mark.unit
class TestEligibleDirections:
    """The eligibility matrix: declared promotable= ∩ structural read_only rule."""

    def _dirs(self, **kwargs):
        from haywire.core.node.promotion import eligible_promotion_directions

        return eligible_promotion_directions(setting(0.5, type_=FLOAT, **kwargs))

    def test_default_plain_field_both_directions(self):
        from haywire.core.types.enums import PortType

        assert self._dirs() == (PortType.INLET, PortType.OUTLET)

    def test_none_yields_empty(self):
        assert self._dirs(promotable=Promotable.NONE) == ()

    def test_inlet_only(self):
        from haywire.core.types.enums import PortType

        assert self._dirs(promotable=Promotable.INLET) == (PortType.INLET,)

    def test_outlet_only(self):
        from haywire.core.types.enums import PortType

        assert self._dirs(promotable=Promotable.OUTLET) == (PortType.OUTLET,)

    def test_read_only_intersects_to_outlet(self):
        from haywire.core.types.enums import PortType

        assert self._dirs(read_only=True) == (PortType.OUTLET,)

    def test_read_only_plus_inlet_only_intersects_to_empty(self):
        assert self._dirs(read_only=True, promotable=Promotable.INLET) == ()


@pytest.mark.integration
class TestPromoteGuard:
    """promote_setting raises for ineligible promotions (interactive OR load-time)."""

    def test_promote_none_field_raises(self, promotable_node):
        from haywire.core.node.promotion import promote_setting
        from haywire.core.types.enums import PortType

        node = promotable_node
        # Stamp this instance's descriptor NONE (fresh bag class per fixture — no leak).
        type(node.filter).__dict__["threshold"]._promotable = Promotable.NONE
        for direction in (PortType.INLET, PortType.OUTLET):
            with pytest.raises(ValueError, match="cannot be promoted"):
                promote_setting(node, "filter", "threshold", direction)
        pid = type(node.filter).__dict__["threshold"].storage_key
        assert pid not in node.ports

    def test_promote_outlet_only_field_to_inlet_raises(self, promotable_node):
        from haywire.core.node.promotion import promote_setting
        from haywire.core.types.enums import PortType

        node = promotable_node
        type(node.filter).__dict__["threshold"]._promotable = Promotable.OUTLET
        with pytest.raises(ValueError, match="cannot be promoted"):
            promote_setting(node, "filter", "threshold", PortType.INLET)
        promote_setting(node, "filter", "threshold", PortType.OUTLET)  # allowed
```

(Import `PortType` at the top of the guard test's method bodies as shown, or add a module-level `from haywire.core.types.enums import PortType` to the file — match the file's existing import style. `promotable_node` is the same fixture Task 3 Step 2 relies on. NOTE: there is deliberately no grandfather test — there are no saved graphs with promoted ports yet, so a load-time ineligible promotion cannot occur, and `promote_setting` enforces uniformly.)

- [x] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/core/node/test_promotion_serialization.py tests/core/settings/test_promotable_eligibility.py -v`
Expected: FAIL — promoted ports still serialize in the ports block; `bag.is_promoted` not yet written by `promote_setting`; `demote` doesn't clear; `eligible_promotion_directions` not yet defined; no eligibility guard. (Task A's enum tests still PASS.)

- [x] **Step 4: Wire `promote_setting`/`demote_setting`/`is_field_promoted`**

In `packages/haywire-core/src/haywire/core/node/promotion.py`:

Replace `is_field_promoted` (lines 24-35):

```python
def is_field_promoted(bag: "Settings", field: str) -> bool:
    """True if ``<bag>.<field>`` is currently promoted to a port.

    Consults the bag's ``_promoted_keys`` — the single source of truth (ADR
    0019). False for a field that is not promoted or does not exist."""
    return bag.is_promoted(field)
```

**Add `eligible_promotion_directions()` (the single source of truth for eligibility), after the `_descriptor` function (~line 55):**

```python
def eligible_promotion_directions(descriptor: "setting") -> tuple[PortType, ...]:
    """The single source of truth for promotion eligibility.

    Two orthogonal contributions, intersected:

    1. **Declared intent** — ``setting(promotable=...)``, default ``ALL``.
       ``NONE`` marks fields where a port would be misleading (e.g.
       restart-required pipeline parameters).
    2. **Structural** — a ``read_only`` (``watch()``) field has no write path
       in, so it can never be an inlet regardless of declaration.

    Consumed by ``promote_setting`` (raises for ineligible promotions) and the
    promote menu's ``promotable_fields`` (hides ineligible entries).
    """
    from haywire.core.settings.descriptor import Promotable

    declared = getattr(descriptor, "_promotable", Promotable.ALL)
    directions: list[PortType] = []
    if Promotable.INLET in declared and not getattr(descriptor, "_read_only", False):
        directions.append(PortType.INLET)
    if Promotable.OUTLET in declared:
        directions.append(PortType.OUTLET)
    return tuple(directions)
```

**Merge the eligibility guard into `promote_setting` and add the record write.**

Replace the read-only guard block (currently lines 155-157, under `# Flag check 1: a read-only (watch) field can only be an outlet.`):

```python
    # Flag check 1: a read-only (watch) field can only be an outlet.
    if getattr(desc, "_read_only", False) and direction is not PortType.OUTLET:
        raise ValueError("a read-only (watch) setting can only be promoted to an outlet")
```

with the eligibility gate (this folds the read-only rule into `eligible_promotion_directions`):

```python
    # Eligibility — the single source of truth shared with the promote menu
    # (declared promotable= ∩ the read-only structural rule). Applies to every
    # promotion, including the load-time regen path: there are no saved graphs
    # with promoted ports yet, so there is nothing to grandfather — an ineligible
    # promotion is always a live authoring mistake and should fail loudly.
    eligible = eligible_promotion_directions(desc)
    if direction not in eligible:
        raise ValueError(
            f"setting {field!r} cannot be promoted to {direction.name.lower()} "
            f"(eligible: {', '.join(d.name.lower() for d in eligible) or 'none'})"
        )
```

And update `promote_setting`'s docstring "Eligibility is TWO orthogonal flag checks" paragraph's item 1 to:

```
    1. ``eligible_promotion_directions(desc)`` — declared ``promotable=`` ∩
       the read-only structural rule (``watch()`` ⇒ outlet only). Raises for
       any ineligible promotion, interactive or load-time.
```

Add the record write right after the `_bind_port(port, bag, desc)` call (currently line 177):

```python
    _bind_port(port, bag, desc)
    # Record the promotion in the bag — the single source of truth. This is what
    # serializes (the port itself never does) and what regenerate_promoted_ports
    # reads on load. Idempotent-safe: an early return above (pid already in
    # node.ports) means we never reach here for an already-promoted field.
    bag.set_promoted(field, direction)
```

Replace `demote_setting` (lines 180-186):

```python
def demote_setting(node: "NodeData", port_id: str) -> None:
    """Remove the promoted port ``port_id``, release its cell binding, and clear
    the settings-side promotion record.

    Mirror of ``promote_setting``: promote writes ``_promoted_keys``, demote
    clears it (ADR 0019 — the port is no longer the promotion signal, so the
    record must be maintained explicitly)."""
    if port_id not in node.ports:
        return
    try:
        bag, desc = _resolve_promoted(node, port_id)
        bag.clear_promoted(desc._attr_name)
    except KeyError:
        pass  # port matches no setting (library changed) — just remove the port
    node.ports[port_id].unbind_field()
    with node.rejig(include=[port_id]):
        pass
```

Replace `bind_promoted_ports` (lines 99-117) with `regenerate_promoted_ports`:

```python
def regenerate_promoted_ports(node: "NodeData") -> None:
    """Regenerate every promoted port on *node* from its bag's ``_promoted_keys``
    (load-time pass, ADR 0019).

    Settings bags are already restored (BaseNode._initialize_from_dict runs
    settings before this), so each bag's ``_promoted_keys`` holds the loaded
    promotions. This walks them and calls ``promote_setting`` — the SAME path an
    interactive promotion takes — so there is one creation path for both. The
    ``if pid in node.ports: return`` guard inside ``promote_setting`` makes this
    idempotent. Runs before edges wire (two-phase graph load), so a regenerated
    promoted inlet exists in ``node.ports`` before any edge resolves against it.
    """
    for accessor in type(node)._settings_bags:
        bag = getattr(node, accessor)
        # Snapshot: promote_setting mutates node.ports (not _promoted_keys), but
        # iterate a copy to be safe against any future re-entrancy.
        fields = type(bag)._property_settings()
        # storage_key -> attr name, to translate the key back to promote_setting's
        # (accessor, field) arguments.
        key_to_field = {desc.storage_key: name for name, desc in fields.items()}
        for storage_key, direction in list(bag._promoted_keys.items()):
            field = key_to_field.get(storage_key)
            if field is None:
                logger.warning(
                    "Promoted key %r on node %r bag %r matches no field "
                    "(library changed?); skipping regeneration.",
                    storage_key,
                    node.node_id,
                    accessor,
                )
                continue
            promote_setting(node, accessor, field, direction)
```

- [x] **Step 5: Update the port-serialization loop and the load pass to use the new name**

In `packages/haywire-core/src/haywire/core/node/data.py`:

Replace `_serialize_ports` (lines 914-924):

```python
    def _serialize_ports(self, include_data: bool = True) -> Dict[str, Any]:
        """
        Serialize all NON-promoted ports to dictionary, optionally with data.

        Promoted ports are deliberately omitted (ADR 0019): promotion is
        recorded in the owning settings bag's "promoted" block and the port is
        regenerated on load via regenerate_promoted_ports. Serializing it here
        too would be a second, drifting source of truth.

        Args:
            include_data: If True, includes field values

        Returns:
            Dictionary mapping port IDs to PortSpec-format dicts (promoted ports excluded)
        """
        return {
            port_id: port.to_dict(include_data=include_data)
            for port_id, port in self.ports.items()
            if not port.promoted
        }
```

Replace `_bind_promoted_ports` (lines 958-963):

```python
    def _regenerate_promoted_ports(self) -> None:
        """Regenerate promoted ports from settings — delegates to
        haywire.core.node.promotion (ADR 0019; replaces the old bind-only pass)."""
        from haywire.core.node.promotion import regenerate_promoted_ports

        regenerate_promoted_ports(self)
```

- [x] **Step 6: Point the node loader at the renamed pass**

In `packages/haywire-core/src/haywire/core/node/base.py`, in `_initialize_from_dict` (line 384), replace:

```python
        self._bind_promoted_ports()
```

with:

```python
        self._regenerate_promoted_ports()
```

Also update the comment block just above it (lines 377-383) to reflect regeneration rather than binding:

```python
        # Deserialize the NON-promoted ports (promoted ports are not in the
        # ports block anymore — ADR 0019). Then regenerate promoted ports from
        # the already-restored settings bags. This runs before edges wire
        # (two-phase graph load), so a regenerated promoted inlet exists before
        # any edge resolves against it.
        if "ports" in data:
            self._deserialize_ports(data["ports"])

        self._regenerate_promoted_ports()
```

(Remove the now-stale earlier comment at lines 366-371 that says "_bind_promoted_ports() below binds each promoted port's cell by reference" — replace its intent with the settings-first ordering note; the ordering reason still holds, only the mechanism name changes.)

- [x] **Step 7: Grep for any remaining callers of the old name**

Run: `grep -rn "bind_promoted_ports\|_bind_promoted_ports" packages/ barn/ tests/ | grep -v __pycache__`
Expected: only the definitions/tests you just changed. Update any stragglers (docs strings, other call sites) to `regenerate_promoted_ports` / `_regenerate_promoted_ports`. If a test asserted on `bind_promoted_ports` directly, adapt it.

- [x] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/core/node/test_promotion_serialization.py tests/core/settings/test_promotable_eligibility.py -v`
Expected: PASS, all tests green (serialization + eligibility + promote guard).

- [x] **Step 9: Run the promotion + graph-load suites for regressions**

Run: `uv run pytest tests/core/node/ tests/core/test_settings/ tests/core/settings/ tests/ui/panel/test_promoted_row_state.py -q`
Expected: PASS. Fix any test that asserted the old "promoted port in ports block", the old bind-pass name, or the old two-flag eligibility rule — those are legitimate breakage from this task.

- [x] **Step 10: Full baseline re-check**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/node/ && uv run ruff format --check packages/haywire-core/src/haywire/core/node/ && uv run mypy packages/haywire-core/src/haywire/core/node/`
Expected: all clean.

- [x] **Step 11: Commit**

```bash
git add packages/haywire-core/src/haywire/core/node/promotion.py packages/haywire-core/src/haywire/core/node/data.py packages/haywire-core/src/haywire/core/node/base.py tests/core/node/test_promotion_serialization.py tests/core/settings/test_promotable_eligibility.py
git commit -m "feat(promotion): settings-owned promotion + eligible_promotion_directions guard (ADR 0019)"
```

---

### Task B: Promote menu consumes the shared eligibility helper

> **Merged from promotable-flag Task 3.** Placed after Task 3 because it consumes `eligible_promotion_directions`. Editor/UI package.

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/node/promote.py` (`promotable_fields` + docstrings)
- Test: `tests/ui/menu/test_promote_demote_menu.py` (extend)

**Interfaces:**
- Consumes: `eligible_promotion_directions` (Task 3).
- Produces: `promotable_fields(node)` keeps returning `(accessor, field, directions)` tuples; fields with empty `directions` are now omitted.

- [x] **Step 1: Baseline check**

Run: `uv run ruff check barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/node/promote.py && uv run mypy barn/haybale-graph-editor/`
Expected: both clean.

- [x] **Step 2: Write the failing tests**

Append to `tests/ui/menu/test_promote_demote_menu.py`:

```python
@pytest.mark.integration
def test_promotable_none_field_hidden_from_menu(make_node_with_setting):
    """promotable=NONE removes the field from the promote submenu entirely
    (hidden, not greyed — consistent with promoted-field omission)."""
    from haywire.core.settings import Promotable
    from haybale_graph_editor.panels.graph.menu.node.promote import promotable_fields

    node = make_node_with_setting(accessor="filter", field="threshold")
    type(node.filter).__dict__["threshold"]._promotable = Promotable.NONE

    assert not any(acc == "filter" and fld == "threshold" for acc, fld, _ in promotable_fields(node))


@pytest.mark.integration
def test_single_direction_declaration_collapses_menu_entry(make_node_with_setting):
    """promotable=OUTLET yields a single-direction entry — same rendering path
    a watch() field already takes (labeled leaf, no direction flyout)."""
    from haywire.core.settings import Promotable
    from haywire.core.types.enums import PortType
    from haybale_graph_editor.panels.graph.menu.node.promote import promotable_fields

    node = make_node_with_setting(accessor="filter", field="threshold")
    type(node.filter).__dict__["threshold"]._promotable = Promotable.OUTLET

    fields = {(acc, fld): dirs for acc, fld, dirs in promotable_fields(node)}
    assert fields[("filter", "threshold")] == (PortType.OUTLET,)
```

(Reuse the existing `make_node_with_setting` fixture the menu test file already provides; grep it. Import `PortType` per the file's convention.)

- [x] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/ui/menu/test_promote_demote_menu.py -v`
Expected: the two new tests FAIL (`promotable_fields` still offers both directions); pre-existing tests PASS.

- [x] **Step 4: Rewire `promotable_fields`**

In `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/node/promote.py`:

Add the import alongside the existing `from haywire.core.types.enums import PortType`:

```python
from haywire.core.node.promotion import eligible_promotion_directions
```

In `promotable_fields`, replace the inline rule (currently lines 60-63, the `if getattr(desc, "_read_only", False): ... else: ...` block that appends `(accessor, field, directions)`):

```python
            if getattr(desc, "_read_only", False):
                directions: tuple[PortType, ...] = (PortType.OUTLET,)
            else:
                directions = (PortType.INLET, PortType.OUTLET)
            out.append((accessor, field, directions))
```

with:

```python
            directions = eligible_promotion_directions(desc)
            if not directions:
                continue  # promotable=NONE (or read_only ∩ INLET): hidden entirely
            out.append((accessor, field, directions))
```

Update the module + `promotable_fields` docstrings that state the old two-flag rule to reference `eligible_promotion_directions` (single source of truth, shared with `promote_setting`); note ineligible fields are hidden.

- [x] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/ui/menu/test_promote_demote_menu.py -v`
Expected: PASS, all tests green (old + 2 new).

- [x] **Step 6: Full baseline re-check + fast suite**

Run: `uv run ruff check barn/haybale-graph-editor/ && uv run ruff format --check barn/haybale-graph-editor/ && uv run pytest -m integration tests/ui/menu/ -q`
Expected: all clean/passing.

- [x] **Step 7: Commit**

```bash
git add barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/node/promote.py tests/ui/menu/test_promote_demote_menu.py
git commit -m "feat(menu): promote submenu uses shared eligibility; promotable=NONE fields hidden"
```

---

### Task 4: Reset-and-warn on an old-format settings dict

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/node/base.py` (`_initialize_from_dict` settings-restore loop, lines 372-375)
- Test: `tests/core/node/test_promotion_reset_on_old_format.py` (new)

**Interfaces:**
- Consumes: `PromotedFormatError` (Task 2); `HaywireException` + `ErrorSeverity` (`haywire.core.errors.haywire_exception`); the node's error-attach surface.
- Produces: on a `PromotedFormatError` from any bag's `from_dict`, that bag stays at defaults (no restore) and a WARNING-severity `HaywireException` is attached to the node (renders via existing `UINodeCard`/`render_error_details`).

- [x] **Step 1: Baseline check + confirm the error-attach API**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/node/base.py && uv run mypy packages/haywire-core/src/haywire/core/node/base.py`
Expected: both clean.

Then confirm how a node attaches a non-fatal `HaywireException`/warning that renders. Read `packages/haywire-core/src/haywire/core/node/node_wrapper.py` around `NodeWrapperState` (the `error_custom`/`warnings`/`add_warning` fields) and `packages/haywire-core/src/haywire/core/errors/haywire_exception.py` for `ErrorSeverity`. Use whichever attach path renders TODAY (per the investigation: `error_custom`/`HaywireException` fields DO render via `UINodeCard`; `NodeWarning` does not yet). Prefer setting a WARNING-severity `HaywireException` on `self.wrapper.state.error_custom` (or the nearest rendering field) — verify the exact attribute name against the file before writing Step 4.

- [x] **Step 2: Write the failing test**

Create `tests/core/node/test_promotion_reset_on_old_format.py`:

```python
# tests/core/node/test_promotion_reset_on_old_format.py
"""
Old-format (pre-ADR-0019) settings dict on load = reset-and-continue:

- the bag is left at descriptor defaults (not restored from the incompatible dict)
- the node still loads and is fully functional
- a WARNING-severity HaywireException is attached to the node so the user sees it

Uses the same node/graph construction helpers as test_promotion_serialization.py.
"""

# Per CLAUDE.md test trap: import editor before other haywire modules.
import haywire.core.graph.editor  # noqa: F401

import pytest

from haywire.core.errors.haywire_exception import ErrorSeverity

pytestmark = pytest.mark.integration


class TestResetOnOldFormat:
    def test_old_flat_settings_dict_resets_bag_and_warns(self, promotable_node, node_dict_of):
        node = promotable_node
        node.filter.threshold = 5.0  # a non-default value we expect to be RESET
        data = node_dict_of(node)
        # Corrupt the settings block into the OLD flat shape for the "filter" bag.
        data["settings"]["filter"] = {"threshold": 99.0}  # pre-refactor flat form

        reloaded = node.__class__(node.node_id, node.wrapper)  # adapt to real ctor
        reloaded._initialize_from_dict(data)

        # Bag reset to default (not 99.0, not the old 5.0).
        assert reloaded.filter.threshold == type(reloaded.filter).__dict__["threshold"]._default
        # A WARNING is attached and rendering-visible.
        errs = reloaded.wrapper.state.get_errors()  # adapt to real accessor
        assert any(
            getattr(e, "severity", None) == ErrorSeverity.WARNING
            and "settings" in str(e).lower()
            for e in errs
        )

    def test_node_still_functional_after_reset(self, promotable_node, node_dict_of):
        node = promotable_node
        data = node_dict_of(node)
        data["settings"]["filter"] = {"threshold": 99.0}  # old flat shape
        reloaded = node.__class__(node.node_id, node.wrapper)
        reloaded._initialize_from_dict(data)
        # Writable, usable — a reset is a recovery, not a broken node.
        reloaded.filter.threshold = 12.0
        assert reloaded.filter.threshold == 12.0
```

(Adapt `node_dict_of`, the constructor call, and `wrapper.state.get_errors()` to the real fixtures/APIs — grep the existing node tests for how a node dict is produced and how wrapper errors are read. The behavioral assertions are the contract; the plumbing names may differ.)

- [x] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/core/node/test_promotion_reset_on_old_format.py -v`
Expected: FAIL — today a `PromotedFormatError` from `from_dict` propagates out of `_initialize_from_dict` (uncaught) rather than being turned into a reset+warning.

- [x] **Step 4: Catch `PromotedFormatError`, reset the bag, attach a WARNING**

In `packages/haywire-core/src/haywire/core/node/base.py`, replace the settings-restore loop in `_initialize_from_dict` (lines 372-375):

```python
        for bag_name, bag_data in data.get("settings", {}).items():
            bag = getattr(self, bag_name, None)
            if isinstance(bag, Settings):
                bag.from_dict(bag_data)
```

with (adjust the import path and the exact error-attach attribute to what Step 1 confirmed):

```python
        from haywire.core.settings.settings import PromotedFormatError
        from haywire.core.errors.haywire_exception import HaywireException, ErrorSeverity

        for bag_name, bag_data in data.get("settings", {}).items():
            bag = getattr(self, bag_name, None)
            if not isinstance(bag, Settings):
                continue
            try:
                bag.from_dict(bag_data)
            except PromotedFormatError:
                # Reset-and-continue (ADR 0019): the bag stays at descriptor
                # defaults (nothing restored), the node loads and stays fully
                # functional, and the user is told via a WARNING that renders on
                # the node card. A one-click node reset already, effectively —
                # they lose this node's individually-saved settings, which is
                # the accepted price of the hard format cutover.
                logger.warning(
                    "Node %r bag %r: incompatible (pre-ADR-0019) settings format; "
                    "reset to defaults.",
                    self.node_id,
                    bag_name,
                )
                self.wrapper.state.error_custom = HaywireException(
                    message=(
                        f"Settings for '{bag_name}' were saved in an old format and have "
                        f"been reset to defaults. Re-save the graph to update it."
                    ),
                    severity=ErrorSeverity.WARNING,
                )
```

- [x] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/core/node/test_promotion_reset_on_old_format.py -v`
Expected: PASS.

- [x] **Step 6: Regression + baseline**

Run: `uv run pytest tests/core/node/ -q && uv run ruff check packages/haywire-core/src/haywire/core/node/base.py && uv run ruff format --check packages/haywire-core/src/haywire/core/node/base.py && uv run mypy packages/haywire-core/src/haywire/core/node/base.py`
Expected: all clean/passing.

- [x] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/node/base.py tests/core/node/test_promotion_reset_on_old_format.py
git commit -m "feat(node): reset-and-warn on pre-ADR-0019 settings format instead of crashing"
```

---

### Task 5: Plain-port `widget_config` serializability guard at construction

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/port.py` (`__post_init__`, after the `widget` merge block, after line 189)
- Test: `tests/ui/widget/test_widget_config_serializable.py` (new)

**Interfaces:**
- Consumes: `is_cattrs_serializable` (`haywire.core.types.utils`), existing `self.widget_config`, `self.promoted`, `self.id`.
- Produces: `DataPort.__post_init__` raises `TypeError` when `self.promoted` is `False` and `self.widget_config` is not cattrs/JSON serializable; no-op when `promoted` is `True` or `widget_config` is serializable.

- [x] **Step 1: Baseline check**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/types/port.py && uv run mypy packages/haywire-core/src/haywire/core/types/port.py`
Expected: both clean.

- [x] **Step 2: Write the failing tests**

Create `tests/ui/widget/test_widget_config_serializable.py`:

```python
# tests/ui/widget/test_widget_config_serializable.py
"""
Plain (non-promoted) ports reject a non-serializable widget_config at
construction time (ADR 0019 / ADR 0018 plain-port half):

- a callable (bound method / lambda) in widget_config on a PLAIN port raises
  TypeError at DataPort.__post_init__ (i.e. when node.add(...) runs), naming
  the port — not nine frames deep in json.dumps at save time
- the SAME callable on a PROMOTED port does NOT raise (its widget_config is
  never serialized; it round-trips through the descriptor, ADR 0019)
- a serializable widget_config (list/dict options) constructs fine
"""

# Per CLAUDE.md test trap: import editor before other haywire modules.
import haywire.core.graph.editor  # noqa: F401

import pytest

from haywire.barn.builtin.types import CHOICES
from haywire.core.types.enums import PortType


def _dynamic_options():
    return ["a", "b", "c"]


class TestPlainPortRejectsCallable:
    def test_callable_widget_config_raises_on_plain_port(self):
        spec = CHOICES.as_config(
            "mode",
            widget_config={"options": _dynamic_options},  # a live callable
        )
        with pytest.raises(TypeError, match="mode"):
            # node.add would run this; from_spec/DataPort(**kwargs) triggers __post_init__
            from haywire.core.types.port import DataPort
            from haywire.core.di.context import get_type_registry

            DataPort.from_spec(spec, get_type_registry(), None, None)

    def test_nested_callable_under_properties_raises(self):
        spec = CHOICES.as_config(
            "mode",
            widget_config={"properties": {"options": _dynamic_options}},
        )
        with pytest.raises(TypeError, match="mode"):
            from haywire.core.types.port import DataPort
            from haywire.core.di.context import get_type_registry

            DataPort.from_spec(spec, get_type_registry(), None, None)


class TestSerializableWidgetConfigOk:
    def test_list_options_construct_fine(self):
        spec = CHOICES.as_config("mode", widget_config={"options": ["a", "b"]})
        from haywire.core.types.port import DataPort
        from haywire.core.di.context import get_type_registry

        port = DataPort.from_spec(spec, get_type_registry(), None, None)
        assert port.widget_config["options"] == ["a", "b"]


class TestPromotedPortAllowsCallable:
    def test_callable_widget_config_ok_on_promoted_port(self):
        spec = CHOICES.as_inlet(
            "mode",
            promoted=True,
            widget_config={"options": _dynamic_options},
        )
        from haywire.core.types.port import DataPort
        from haywire.core.di.context import get_type_registry

        # Must NOT raise: promoted ports never serialize widget_config.
        port = DataPort.from_spec(spec, get_type_registry(), None, None)
        assert port.promoted is True
```

Note: the exact DI accessor for the type registry (`get_type_registry`) and `from_spec` signature must match the codebase — grep `tests/ui/widget/` and `tests/core/` for how existing tests construct a bare `DataPort` from a spec, and mirror that construction (some suites use a fixture that supplies the registry). Adjust the four construction sites accordingly; keep the behavioral asserts.

- [x] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/ui/widget/test_widget_config_serializable.py -v`
Expected: FAIL — the plain-port cases do NOT raise today (construction succeeds; the crash only happens later at `json.dumps`).

- [x] **Step 4: Add the guard to `__post_init__`**

In `packages/haywire-core/src/haywire/core/types/port.py`, add the check right after the `widget` merge block closes — after `self.widget = None` (line 189), before the `if self.type_cls is None:` block:

```python
        # A live callable in widget_config (e.g. {"options": self.method} for a
        # dynamic dropdown) is intentional and works at render time, but it
        # cannot survive JSON serialization. A promoted port never serializes
        # its widget_config (it round-trips through the descriptor — ADR 0019),
        # so a callable there is always safe. A plain port IS its own only copy,
        # so a callable would crash json.dumps at save time, nine frames deep.
        # Fail here instead — at construction (node.add during init()), naming
        # the port and key. Reuses the same serializability check
        # normalize_and_validate_default uses for default= values.
        if not self.promoted and self.widget_config:
            from haywire.core.types.utils import is_cattrs_serializable

            ok, error_msg = is_cattrs_serializable(self.widget_config)
            if not ok:
                raise TypeError(
                    f"DataPort {self.id!r}: 'widget_config' must be JSON serializable. "
                    f"Got {self.widget_config!r} which is not serializable: {error_msg}\n"
                    f"A live callable in widget_config (e.g. a dynamic-options method) is "
                    f"only safe on a setting() field promoted to a port — the descriptor is "
                    f"re-applied fresh on every load, so the callable is never serialized. "
                    f"A plain (non-promoted) port has no such fallback: use a literal value, "
                    f"or move this field into a Settings bag and promote it."
                )
```

- [x] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/ui/widget/test_widget_config_serializable.py -v`
Expected: PASS, all tests green.

- [x] **Step 6: Regression — this can break existing nodes/tests that use a callable in a plain-port widget_config**

Run: `uv run pytest -m "not integration" -q`
Expected: PASS, EXCEPT for any test that constructs a plain port with a callable `widget_config` (it now correctly raises). The one known production instance is `OakDCameraNode.mxid` (a `barn/haybale-visiongraph` node, gitignored symlink — NOT fixed here, per Global Constraints; its own repo handles it in a follow-up). If a *core/test* node hits this, it's the same class of latent bug — fix that node/test to use a literal or a promoted setting, don't weaken the guard. Note any hits in the commit message.

- [x] **Step 7: Full baseline re-check**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/types/port.py && uv run ruff format --check packages/haywire-core/src/haywire/core/types/port.py && uv run mypy packages/haywire-core/src/haywire/core/types/port.py`
Expected: all clean.

- [x] **Step 8: Commit**

```bash
git add packages/haywire-core/src/haywire/core/types/port.py tests/ui/widget/test_widget_config_serializable.py
git commit -m "feat(port): raise at construction for non-serializable widget_config on plain ports"
```

---

### Task 6: Documentation — ADR 0019 (new) + reconcile ADR 0014/0018, glossary, setting-canon

**Files:**
- Create: `docs/adr/0019-settings-owned-promotion.md`
- Modify: `docs/adr/0014-promotion-as-direction.md` (superseded-status marker on the amendment; forward-pointer to 0019 — do NOT rewrite the decision body)
- Modify: `docs/adr/0018-port-widget-config-serialization-boundary.md` (frontmatter `status:` + superseded-in-part marker pointing to 0019 — do NOT rewrite the decision body)
- Modify: `docs/reference/glossary.md` (`Promotion` entry line 256; `live widget_config callable` entry line 253)
- Modify: `docs/components/settings/setting-canon.md` (promotion serialization description)

**Interfaces:**
- Consumes: the finished, tested behavior from Tasks 1-5.
- Produces: documentation only.

**Convention note (READ FIRST):** Per this repo's ADR discipline, a superseded ADR is NEVER rewritten to erase what it decided — its body is the historical "why the code got here" record. Reconciliation means adding a **status/superseded marker + forward-pointer to the replacing ADR** at the top of the affected section, leaving the original decision prose intact. ADR 0014 already models this with its inline `**Supersedes**` sections and the "Supersedes-in-part" parenthetical on its amendment; match that style.

- [x] **Step 1: Write ADR 0019**

Create `docs/adr/0019-settings-owned-promotion.md`:

```markdown
---
status: accepted
see-also: ADR-0014, ADR-0018
---

# Promotion state lives in Settings; promoted ports are regenerated on load, never serialized

**Supersedes** the [ADR 0014 amendment](0014-promotion-as-direction.md#amendment--a-promoted-ports-id-is-the-settings-storage_key) ("the port IS the promotion signal; settings stay oblivious"). **Supersedes in part** [ADR 0018](0018-port-widget-config-serialization-boundary.md): its promoted-port mechanism (exclude `widget_config` from `to_dict`, re-apply from the descriptor in `_bind_port`) is replaced by "promoted ports are not serialized at all"; its plain-port mechanism (construction-time `is_cattrs_serializable` raise) is **retained**.

**Context.** ADR 0014's amendment made a promoted port the sole promotion signal: it serialized into the node's `ports` block (id + `promoted` flag + `recipe` + display kwargs, no `field_data`), and `_bind_promoted_ports` re-bound its cell on load. That put the port's `widget_config` — which can legitimately hold a live callable for dynamic dropdowns (`{"options": self.method}`, resolved at render time) — into the serialized output, where `json.dumps` crashes on the callable (the `OakDCameraNode` save bug). ADR 0018 patched this by excluding a promoted port's `widget_config` from `to_dict` and re-applying it from the live descriptor. That works, but leaves promotion recorded in two structurally-coupled places (the serialized port stub AND the descriptor it defers to) and keeps a value-less port stub in every saved graph.

**Decision.** Promotion becomes a per-instance, per-field opinion owned by the settings bag, mirroring `_set_keys`/`_ui_disabled_keys`:

- **`Settings._promoted_keys: dict[str, PortType]`** — `storage_key → direction`, the single source of truth. A field has at most one promoted port (its id IS its `storage_key`), so this is one direction per key, never a set.
- **Serialization.** Each bag's `to_dict()` returns `{"values": {...}, "promoted": {storage_key: "inlet"|"outlet"}}`. **Promoted ports are absent from the node's `ports` block entirely** — `_serialize_ports` skips `port.promoted`. The `widget_config`-callable crash is thus *structurally impossible* for promoted ports: there is no serialized port to hold a callable.
- **One creation path.** On load, `regenerate_promoted_ports` (replacing `bind_promoted_ports`) walks each bag's `_promoted_keys` and calls `promote_setting(node, accessor, field, direction)` — the identical path an interactive promotion takes — after settings restore and before edges wire (two-phase graph load guarantees the regenerated inlet exists before any edge resolves to it). `promote_setting`'s existing `if pid in node.ports: return` makes it idempotent.
- **Demote clears the record.** `demote_setting` removes the port, unbinds the cell, and clears `_promoted_keys[storage_key]`. Promote writes the key; demote clears it — mirror operations. This is the deliberate cost of the reversal: the amendment's "nothing to clean up on demote" is given up for a single, symmetric sync point.
- **`is_field_promoted` consults `_promoted_keys`**, not port presence — one oracle.
- **Hard breaking format change, reset-and-continue on old graphs.** A pre-refactor flat `{field: value}` settings dict raises `PromotedFormatError` in `from_dict`; the node loader catches it, leaves the bag at descriptor defaults, and attaches a WARNING-severity `HaywireException` (renders on the node card). The node loads and stays fully functional; the user loses that node's individually-saved settings — the accepted price of the cutover (matches ADR 0011/0012/0014's "hard cutover, no migration"). An edge into a promoted port whose promotion was reset simply dangles — already-documented, already-handled behavior.

**Plain ports (retained from ADR 0018).** A plain (non-promoted) port has no descriptor to fall back on, so a callable in its `widget_config` IS the only copy. `DataPort.__post_init__` runs `is_cattrs_serializable(self.widget_config)` when `self.promoted` is `False` and raises `TypeError` at construction — the moment `node.add(...)` runs — naming the port and key, instead of crashing later in `json.dumps`. Skipped when `promoted` is `True` (a promoted port's `widget_config` is never serialized, so a callable there is provably safe). `OakDCameraNode.mxid` is left deliberately broken by this; its fix is a separate follow-up in `haybale-visiongraph`.

**Consequences.**
- The `widget_config` serialization crash is eliminated for promoted ports by construction (no serialized port) and surfaced early for plain ports (construction-time raise).
- Promotion has a single source of truth (`_promoted_keys`), not two (port stub + descriptor).
- Demote gains one line (clear the record); this is the reversal's honest cost.
- `Settings.to_dict()`/`from_dict()` change shape — a breaking `.haywire` format change (and clipboard format, since copy/paste serializes the same way). No migration; old graphs reset the affected bag and warn.
- A demoted port in the same live session keeps its promoted-era `widget_config` (`__post_init__` doesn't re-run) — an accepted, documented narrow gap, unchanged from ADR 0018.
```

- [x] **Step 2: Update the `Promotion` glossary entry**

In `docs/reference/glossary.md`, the `Promotion` entry (line 256) currently says "The port stays the promotion signal (serialized in the ports block); demote just removes it." Replace that clause with:

```markdown
Promotion state lives in the owning settings bag (`Settings._promoted_keys`, `storage_key → direction`) — the single source of truth. The promoted port is **regenerated from settings on load, never serialized** in the ports block (ADR 0019); `promote_setting` records the promotion and `demote_setting` clears it (mirror operations).
```

And change its trailing ADR reference from "See [ADR 0014]..." to "See [ADR 0014](../adr/0014-promotion-as-direction.md) (direction model + one-cell-two-views) and [ADR 0019](../adr/0019-settings-owned-promotion.md) (settings-owned state + non-serialized regeneration, superseding 0014's amendment)".

- [x] **Step 3: Update the `live widget_config callable` glossary entry**

In `docs/reference/glossary.md`, the `live widget_config callable` entry (line 253) currently says a promoted port's copy "is excluded from `DataPort.to_dict()` and re-applied fresh from the live descriptor on every bind (`_bind_port`)". Replace that clause with:

```markdown
Safe on a **`setting()` field** and on a **promoted port** — `Settings.to_dict()` never serializes `widget_config`, and a promoted port is not serialized at all (regenerated from settings on load, ADR 0019), so the callable never needs to survive a save/load cycle. **Unsafe on a plain (non-promoted) port** — the port has no descriptor to fall back on, so the callable IS the only copy; `DataPort.__post_init__` raises `TypeError` at construction time (via `is_cattrs_serializable`) rather than letting it reach `to_dict()`/`json.dumps` later.
```

Update its ADR reference to cite both 0018 and 0019.

- [x] **Step 4: Update setting-canon.md — promotion serialization + document `promotable=`**

In `docs/components/settings/setting-canon.md`:

First, find the promotion section's description of how a promoted setting serializes (grep for "promoted" / "ports block" / "serial"). Update any statement that a promoted port serializes into the ports block to: promotion is recorded in the bag's `{"values", "promoted"}` serialized form and the port is regenerated on load (cite ADR 0019). If the canon has no such statement, add a one-paragraph note in the promotion subsection.

Then append a `promotable=` subsection to the promotion section:

```markdown
**Restricting promotion (`promotable=`).** By default every writable setting can be promoted to an inlet or an outlet, and a `watch()` field to an outlet only. A field can narrow or remove that with the `promotable=` kwarg:

```python
from haywire.core.settings import NodeSettings, Promotable, setting
from haywire.barn.builtin.types import CHOICES

class depth(NodeSettings):
    # Restart-required pipeline parameter: a port would imply live control
    # the hardware can't deliver — remove it from the promote menu entirely.
    preset_mode = setting[CHOICES](
        "HIGH_DENSITY",
        label="Preset Mode",
        promotable=Promotable.NONE,
    )
```

`Promotable` is a Flag: `NONE` / `INLET` / `OUTLET` / `ALL` (default). Effective eligibility is the intersection of the declaration and the structural rules (`read_only=True` stays outlet-only regardless; `read_only` + `promotable=INLET` intersects to nothing). The single source of truth is `eligible_promotion_directions()` in `haywire.core.node.promotion` — the promote menu hides ineligible entries and `promote_setting()` raises `ValueError` for them, whether the call is interactive or from the load-time regeneration pass.
```

- [x] **Step 5: Reconcile ADR 0014 — mark the amendment superseded (do NOT rewrite its body)**

In `docs/adr/0014-promotion-as-direction.md`, the amendment section begins (line ~58-60):

```markdown
## Amendment — a promoted port's id is the setting's storage_key

*(Originally ADR 0015. Supersedes-in-part the Decision section above: the direction model and one-cell-two-views stand; only the id-encoding + set-tracking mechanism is replaced.)*
```

Insert a superseded marker immediately after that parenthetical (a new line before the amendment's `**Context.**`), leaving all existing amendment prose intact:

```markdown
> **⚠️ Superseded by [ADR 0019](0019-settings-owned-promotion.md) (2026-07-06).** The amendment's core principle — "the port IS the promotion signal (serialized in the ports block); settings stay oblivious" — no longer describes the code. Promotion state now lives in `Settings._promoted_keys`; promoted ports are regenerated from settings on load and are **not serialized** in the ports block. `demote_setting` now clears the settings-side record (the amendment's "no settings-side record to clean up" property was deliberately given up). The direction model and one-cell-two-views (in the Decision section above) still stand. This amendment's prose is retained as the historical record of the intermediate design.
```

Do not edit the amendment's Decision/Consequences prose — the marker alone reconciles it. (If the top-of-file summary at lines 1-11 states the port-is-the-signal mechanism as current, add a one-line "see the amendment's superseded marker — ADR 0019 now owns promotion state" pointer there too; do not rewrite it.)

- [x] **Step 6: Reconcile ADR 0018 — status marker + superseded-in-part note (do NOT rewrite its body)**

In `docs/adr/0018-port-widget-config-serialization-boundary.md`, update the frontmatter (lines 1-4) from:

```markdown
---
status: accepted
see-also: ADR-0014, ADR-0017
---
```

to:

```markdown
---
status: superseded-in-part by ADR-0019
see-also: ADR-0014, ADR-0017, ADR-0019
---
```

Then insert a marker immediately after the H1 title line (before the `**Context.**` paragraph), leaving the decision body intact:

```markdown
> **⚠️ Promoted-port half superseded by [ADR 0019](0019-settings-owned-promotion.md) (2026-07-06).** This ADR's promoted-port mechanism — exclude `widget_config` from `DataPort.to_dict()`, re-apply it from the descriptor in `_bind_port` — was **never implemented as described**: ADR 0019 supersedes it with "promoted ports are not serialized at all" (regenerated from `Settings._promoted_keys` on load), which makes the exclusion moot. **The plain-port half of this ADR — the construction-time `is_cattrs_serializable` raise in `DataPort.__post_init__` — is RETAINED and is what shipped.** Read the plain-port Decision bullet and the demote-gap note as current; read the promoted-port Decision bullet as superseded history.
```

Do not delete or rewrite ADR 0018's Decision/Consequences prose — the frontmatter status and this marker reconcile it against the code.

- [x] **Step 7: Preview the docs site**

Run: `uv run mkdocs serve`, visit `http://127.0.0.1:8000`, check the settings canon page and that ADR 0019 renders under the ADR index, and that the superseded markers on 0014/0018 render. Stop the server (Ctrl+C).

- [x] **Step 8: Commit**

```bash
git add docs/adr/0019-settings-owned-promotion.md docs/adr/0014-promotion-as-direction.md docs/adr/0018-port-widget-config-serialization-boundary.md docs/reference/glossary.md docs/components/settings/setting-canon.md
git commit -m "docs(promotion): ADR 0019 + reconcile 0014/0018 superseded markers; glossary + canon"
```

---

### Task C: OAK-D consumer — `depth` bag becomes non-promotable

> **Merged from promotable-flag Task 5.** Terminal consumer of `promotable=`. This edits the `haybale-visiongraph` repo (gitignored symlink) — run its commands AND the `git add`/`git commit` from `/Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph`, NEVER from haywire-repo (a `git add` from haywire-repo silently hits the ignore rule).

**Files:**
- Modify: `barn/haybale-visiongraph/haybale_visiongraph/nodes/oak_d_camera_node.py`
- Modify: `barn/haybale-visiongraph/notes.md`

**Interfaces:**
- Consumes: `Promotable` (Task A), enforced end-to-end by Tasks 3 + B.
- Produces: nothing — terminal consumer.

- [x] **Step 1: Baseline check**

Run:
```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph
uv run ruff check barn/haybale-visiongraph/haybale_visiongraph/nodes/oak_d_camera_node.py
uv run mypy barn/haybale-visiongraph/haybale_visiongraph/nodes/oak_d_camera_node.py
```
Expected: clean (2 pre-existing `import-untyped` errors on the `visiongraph.*` imports are the known baseline — anything new is yours).

- [x] **Step 2: Mark the six depth fields**

In `oak_d_camera_node.py`, extend the settings import:

```python
from haywire.core.settings import NodeSettings, Promotable, setting
```

Add `promotable=Promotable.NONE,` as the last kwarg of each of the six `setting(...)` calls in `class depth(NodeSettings)` — `preset_mode`, `median_filter`, `left_right_check`, `subpixel`, `extended_disparity`, `frame_alignment` — e.g.:

```python
        preset_mode = setting[CHOICES](
            "HIGH_DENSITY",
            label="Preset Mode",
            category="Depth",
            description="Stereo depth quality/speed preset. Requires a device restart to apply.",
            widget_config={"options": list(_DEPTH_PRESET_MODES.keys())},
            promotable=Promotable.NONE,
        )
```

(The module docstring's claim that depth settings are "never promotable to a port" — written aspirationally earlier — becomes true with this change; no docstring edit needed.)

- [x] **Step 3: Verify in the running app**

From haywire-repo: `uv run haywire`. Create an `OAK-D Camera` node, right-click → Promote Setting. Expected: the `depth` bag is absent from the flyout entirely (all its fields ineligible → the bag category is omitted); `ir`/`color` fields still offer inlet/outlet.

- [x] **Step 4: Full baseline re-check + fast suite**

Run (from haybale-visiongraph): the Step 1 commands plus `uv run ruff format --check barn/haybale-visiongraph/haybale_visiongraph/nodes/oak_d_camera_node.py`.
Run (from haywire-repo): `uv run pytest -m "not integration" -q`.
Expected: all clean/passing (same baseline; this change only adds a kwarg to six declarations).

- [x] **Step 5: Record in notes.md and commit — in the haybale-visiongraph repo**

Append to `barn/haybale-visiongraph/notes.md`:

```markdown
## Depth settings are promotable=NONE (BUILT)

The `depth` bag is restart-required pipeline configuration; a promoted port
would imply live control the hardware can't deliver. The framework's
`promotable=` flag (see setting-canon.md) now enforces what the module
docstring only promised: all six depth fields are `Promotable.NONE` — hidden
from the promote menu, rejected by `promote_setting()`.
```

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph
git add barn/haybale-visiongraph/haybale_visiongraph/nodes/oak_d_camera_node.py barn/haybale-visiongraph/notes.md
git commit -m "feat(oak-d): depth settings promotable=NONE (restart-required, no live port)"
```

---

### Task 7: Full-suite regression sweep

**Files:**
- Modify: any test/fixture files still asserting the old serialization shape (as surfaced).

**Interfaces:**
- Consumes: everything from Tasks 1-6.
- Produces: a green full suite.

- [x] **Step 1: Run the whole fast suite**

Run: `uv run pytest -m "not integration" -q`
Expected: PASS. Any remaining failure is a test still coded to the old flat `Settings.to_dict()` shape, the old promoted-port-in-ports-block model, or the old `bind_promoted_ports` name. Fix each to the new model (do NOT revert behavior). Common fixes: update hardcoded settings dicts to `{"values": {...}, "promoted": {...}}`; stop asserting a promoted port appears in a serialized `ports` dict; rename `bind_promoted_ports` references.

- [x] **Step 2: Run the integration suite**

Run: `uv run pytest -m integration -q`
Expected: PASS. Same triage as Step 1 for any promotion/settings-serialization integration test.

- [x] **Step 3: Full repo quality gate**

Run:
```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/
```
Expected: all clean.

- [x] **Step 4: Commit any sweep fixes**

```bash
git add -A
git commit -m "test: update fixtures/assertions to settings-owned promotion serialization"
```

---

### Task 8: Mark the plan implemented

**Files:**
- Modify: `docs/superpowers/plans/2026-07-06-settings-owned-promotion-and-promotable-flag.md` (this plan)
- Delete: `docs/superpowers/plans/2026-07-06-promotable-flag.md` (merged into this plan)

**Interfaces:**
- Consumes: the completed, green work from all prior tasks.
- Produces: the plan file marked implemented — the durable record that this plan shipped.

This is the terminal task. Run it only after Tasks 1-7 are all complete and the full quality gate (Task 7 Step 3) is green.

- [x] **Step 1: Confirm every prior task's checkboxes are checked**

Skim Tasks A, 1, 2, 3, B, 4, 5, 6, C, 7 in this file. Every `- [ ]` should be `- [x]`. If any remain unchecked, the plan is not done — stop and finish that task first.

- [x] **Step 2: Add an implemented banner to the plan header**

At the very top of this file, immediately under the H1 title line, insert:

```markdown
> **✅ IMPLEMENTED (2026-07-06).** All tasks complete; full quality gate green (ruff, ruff format, mypy, unit + integration suites). Shipped: settings-owned promotion (ADR 0019, supersedes ADR 0014's amendment and ADR 0018's promoted-port half; ADR 0018's plain-port raise retained) + the `Promotable`/`promotable=` eligibility flag (merged in from the retired promotable-flag plan). Known follow-up NOT in this plan: `OakDCameraNode.mxid` (haybale-visiongraph repo) is deliberately left raising at construction and must be fixed there separately.
```

- [x] **Step 3: Delete the superseded promotable-flag plan**

This plan merged and replaced `2026-07-06-promotable-flag.md`. Remove it so the plans directory doesn't carry a stale, now-contradictory plan:

```bash
git rm docs/superpowers/plans/2026-07-06-promotable-flag.md
```

(If that plan file was never committed — check `git status` — just delete it: `rm docs/superpowers/plans/2026-07-06-promotable-flag.md`.)

- [x] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-07-06-settings-owned-promotion-and-promotable-flag.md
git commit -m "docs(plans): mark settings-owned-promotion+promotable-flag implemented; remove merged plan"
```

---

## Self-Review

**Spec coverage** (against the settled inquisition Q15-Q27):
- ✅ `_promoted_keys: dict[str, PortType]` on the bag, single source of truth (Q15/Q16/Q17) — Task 1.
- ✅ `{"values", "promoted"}` serialized shape; promoted ports absent from ports block (Q18/Q19/Q25) — Tasks 2, 3.
- ✅ Hard breaking format change, no back-compat (Q19-revised) — Task 2 (`PromotedFormatError`).
- ✅ Reset-and-continue + WARNING `HaywireException` on old format (Q20/Q21) — Task 4.
- ✅ One idempotent creation path via `promote_setting`; `regenerate_promoted_ports` replaces `bind_promoted_ports` (Q22) — Task 3.
- ✅ Demote clears `_promoted_keys` (Q23) — Task 3.
- ✅ `is_field_promoted` consults `_promoted_keys` (Q24) — Task 3.
- ✅ Dangling-edge-on-missing-promotion accepted (Q26) — asserted by the edge-round-trip test (Task 3) + documented in ADR (Task 6).
- ✅ Plain-port construction-time `is_cattrs_serializable` raise; skipped when promoted (Q6/Q8/Q27) — Task 5.
- ✅ `mxid` left deliberately broken, separate follow-up (Q13/Q27) — Global Constraints + Task 5 Step 6.
- ✅ ADR 0019 folded into the plan, supersedes 0014-amendment + 0018-in-part; glossary + canon updated (Q25 ADR decision) — Task 6.
- ✅ Demote-in-session widget_config gap documented, not built against (Q10) — Global Constraints + ADR.
- ✅ Property-editor promote/demote UI explicitly OUT of scope — Global Constraints (separate later plan).
- ✅ Existing ADRs (0014 amendment, 0018) reconciled with superseded markers so the docs don't describe decisions not in the code — Task 6 Steps 5-6 (marker-only, decision bodies preserved per repo ADR discipline).
- ✅ Plan marked implemented as the terminal task; merged-in promotable-flag plan deleted — Task 8.

**Merged promotable-flag coverage** (against its original spec):
- ✅ `Promotable` NONE/INLET/OUTLET/ALL enum + `promotable=` kwarg, default ALL — Task A.
- ✅ Single source of truth `eligible_promotion_directions()` replacing the duplicated rule — Task 3 (guard) + Task B (menu).
- ✅ `read_only` intersection semantics (incl. contradiction → empty) — Task 3 Step 2b matrix tests.
- ✅ Eligibility enforced uniformly, NO grandfathering — Task 3 (`promote_setting` gates every call, regen included; no `enforce_eligibility` bypass). DELIBERATE deviation from promotable-flag's original grandfather design: there are no saved graphs with promoted ports yet, so nothing to grandfather — an ineligible promotion is always a live authoring mistake and fails loudly. A grandfather bypass can be added later if saved promoted ports ever exist and a library narrows `promotable=`.
- ✅ Menu hides (not greys) ineligible fields — Task B.
- ✅ Backward compatibility (menu behavior): default `ALL` reproduces the old rule bit-for-bit; pre-existing menu tests run unmodified as the regression proof — Task B Step 6.
- ✅ Docs (`promotable=`) — Task 6 Step 4. OAK-D `depth`=NONE consumer + repo-correct commit — Task C.

**Placeholder scan:** No TBD/TODO. Each code step shows literal code. Test tasks (3, 4, 5) explicitly flag where the implementer must adapt fixture/accessor names to the existing suite (`promotable_node`, `reload_node`, `node_dict_of`, the type-registry DI accessor, the `wrapper.state` error field) — these are honest "match the real API" instructions with the behavioral contract fully specified, not vague placeholders. Task 4 Step 1 requires confirming the exact error-attach attribute before writing Step 4's code (the investigation flagged `NodeWarning` has no renderer while `HaywireException`/`error_custom` does — the implementer must verify the precise field name).

**Type consistency:** `_promoted_keys: dict[str, PortType]` is consistent across Tasks 1-3. Accessors `set_promoted(name, direction)`/`clear_promoted(name)`/`is_promoted(name)`/`get_promoted_direction(name)` match their call sites in `promote_setting`/`demote_setting`/`regenerate_promoted_ports` (Task 3) and every test. `to_dict() -> {"values", "promoted"}` shape matches `from_dict`'s reader and the node-level `_to_dict`/`_initialize_from_dict` (which pass each bag's sub-dict through unchanged). `PortType` values serialize as `direction.value` (`"inlet"`/`"outlet"`) and restore via `PortType(<str>)` — consistent in `to_dict`/`from_dict` (Task 2) and asserted in tests. `regenerate_promoted_ports`/`_regenerate_promoted_ports` replace `bind_promoted_ports`/`_bind_promoted_ports` at all call sites (Task 3 Steps 4-7, base.py Step 6). `PromotedFormatError` defined in Task 2, consumed in Task 4. `is_cattrs_serializable(value) -> tuple[bool, str | None]` matches its use in Task 5 (`ok, error_msg = ...`).
```
