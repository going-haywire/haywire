# Promotable Flag Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a `setting()` declare which port directions it may be promoted to (`promotable=Promotable.NONE|INLET|OUTLET|ALL`), so restart-required fields like the OAK-D `depth` bag can be marked "never promotable" instead of silently offering a promotion that would imply live control the hardware can't deliver.

**Architecture:** One new `Promotable` Flag enum + kwarg on the descriptor, and one new function `eligible_promotion_directions(descriptor)` in `promotion.py` that becomes the **single source of truth** for eligibility — computed as *declared `promotable` ∩ (outlet-only if `read_only`)*. Today that rule lives in two places that must agree (`promote_setting`'s guard and the promote menu's `promotable_fields`); both are rewired to call the helper. Already-promoted ports in saved graphs are **grandfathered** on load (never auto-demoted) — only *new* promotions are blocked.

**Tech Stack:** Python (`enum.Flag`), existing Haywire settings descriptor + promotion system (`haywire.core.settings.descriptor`, `haywire.core.node.promotion`), the graph-editor promote menu (`barn/haybale-graph-editor/.../menu/node/promote.py`).

## Global Constraints

- **Sequencing:** this plan runs AFTER the reactive-panel-disabling rev-2 plan (`2026-07-05-reactive-panel-disabling-rev2.md`) — both edit `descriptor.py`, `setting-canon.md`, and the OAK-D node. All anchors below are text anchors, not raw line numbers, because rev 2 shifts lines.
- Eligibility = `promotable` ∩ structural rules. `read_only=True` still forces outlet-only regardless of `promotable`; contradictions (e.g. `read_only=True, promotable=Promotable.INLET`) intersect to empty — not an error, the field is simply not promotable.
- **Grandfather, never auto-demote:** `bind_promoted_ports` keeps binding a saved promoted port whose descriptor is no longer eligible (log `INFO`, keep the port). Ripping ports out of a user's graph on a library update is worse than a stale port. Only `promote_setting` (new promotions) enforces.
- The menu **hides** ineligible fields/directions (consistent with how it already omits promoted fields and empty bags) — no greyed-out entries.
- Default `Promotable.ALL` preserves today's behavior exactly for every existing `setting()` in every library.
- No serialization changes — `promotable` is class-declaration metadata, never persisted.
- Naming: `promotable=` (the `setting()` kwarg), `_promotable` (descriptor attribute), `Promotable` (Flag enum: `NONE`/`INLET`/`OUTLET`/`ALL`, exported from `haywire.core.settings`), `eligible_promotion_directions(descriptor) -> tuple[PortType, ...]`.
- Ruff (`ruff check .`, `ruff format --check .`) and mypy must stay clean on every touched file, per CLAUDE.md. Baseline before each task's edits, re-run after.

---

## File Structure

| File | Responsibility |
|---|---|
| `packages/haywire-core/src/haywire/core/settings/descriptor.py` | `Promotable` Flag enum; `promotable: Promotable = Promotable.ALL` kwarg on `setting.__init__`, stored as `self._promotable`. |
| `packages/haywire-core/src/haywire/core/settings/__init__.py` | Export `Promotable`. |
| `packages/haywire-core/src/haywire/core/node/promotion.py` | New `eligible_promotion_directions()`; `promote_setting` guard rewired to it; grandfather `INFO` log in `bind_promoted_ports`. |
| `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/node/promote.py` | `promotable_fields` calls the shared helper instead of re-deriving the rule; docstring updates. |
| `tests/core/settings/test_promotable_eligibility.py` | New: enum/kwarg storage, eligibility matrix, promote guard, grandfather-on-load. |
| `tests/ui/menu/test_promote_demote_menu.py` | Extend: `promotable=NONE` field absent from the menu; single-direction declarations collapse correctly. |
| `docs/components/settings/setting-canon.md` | Document `promotable=` in the promotion section. |
| `barn/haybale-visiongraph/haybale_visiongraph/nodes/oak_d_camera_node.py` | All six `depth` bag fields get `promotable=Promotable.NONE` (restart-required). |
| `barn/haybale-visiongraph/notes.md` | Record the decision. |

---

### Task 1: `Promotable` enum + `promotable=` kwarg on `setting()`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/descriptor.py` (enum near top; `setting.__init__` signature/docstring/storage)
- Modify: `packages/haywire-core/src/haywire/core/settings/__init__.py` (export)
- Test: `tests/core/settings/test_promotable_eligibility.py` (new file, descriptor-level tests only in this task)

**Interfaces:**
- Consumes: nothing new.
- Produces (relied on by Tasks 2, 3, 5):
  - `haywire.core.settings.Promotable` — `Flag` with `NONE = 0`, `INLET`, `OUTLET`, `ALL = INLET | OUTLET`.
  - `setting(..., promotable: Promotable = Promotable.ALL)` stored as `self._promotable: Promotable`.

- [ ] **Step 1: Baseline check**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/settings/ && uv run mypy packages/haywire-core/src/haywire/core/settings/`
Expected: both clean. If not, stop and raise it.

- [ ] **Step 2: Write the failing tests (descriptor level)**

Create `tests/core/settings/test_promotable_eligibility.py`:

```python
# tests/core/settings/test_promotable_eligibility.py
"""
promotable= eligibility:

- Promotable Flag enum semantics and the setting() kwarg (this task)
- eligible_promotion_directions() matrix, promote_setting guard, and the
  grandfather-on-load rule (added in Task 2 of the promotable-flag plan)
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

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/core/settings/test_promotable_eligibility.py -v`
Expected: FAIL — `ImportError: cannot import name 'Promotable'`.

- [ ] **Step 4: Add the enum and the kwarg**

In `packages/haywire-core/src/haywire/core/settings/descriptor.py`:

Add `Flag, auto` to the existing `enum`-less import block (add a new stdlib import line alongside the existing top-of-file imports):

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

In `setting.__init__`, add the kwarg to the signature **after the `ui_disabled` parameter** (which the rev-2 disabling plan added after `metadata`):

```python
        ui_disabled: bool = False,
        promotable: Promotable = Promotable.ALL,
    ) -> None:
```

Add the docstring entry **after the `ui_disabled` parameter doc block** (also from rev 2):

```python
    promotable : Promotable
        Which port directions this field may be promoted to (default
        ``Promotable.ALL``). ``Promotable.NONE`` removes the field from the
        promote menu entirely and makes ``promote_setting()`` raise — use it
        for fields where a port would be misleading (e.g. restart-required
        pipeline parameters). Structural rules still apply on top:
        ``read_only=True`` remains outlet-only regardless. Existing promoted
        ports in saved graphs are grandfathered on load, never auto-demoted.
```

Add the storage **after the `self._ui_disabled: bool = ui_disabled` line** (from rev 2):

```python
        self._promotable: Promotable = promotable
```

In `packages/haywire-core/src/haywire/core/settings/__init__.py`, extend the existing descriptor import line:

```python
from .descriptor import setting, shadow, watch, Promotable
```

and add `"Promotable"` to the `__all__` list.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/core/settings/test_promotable_eligibility.py -v`
Expected: PASS, all 6 tests green.

- [ ] **Step 6: Full baseline re-check + settings suite**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/settings/ && uv run ruff format --check packages/haywire-core/src/haywire/core/settings/ && uv run mypy packages/haywire-core/src/haywire/core/settings/ && uv run pytest tests/core/test_settings/ tests/core/settings/ -q`
Expected: all clean, no regressions.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/settings/descriptor.py packages/haywire-core/src/haywire/core/settings/__init__.py tests/core/settings/test_promotable_eligibility.py
git commit -m "feat(settings): Promotable flag enum and promotable= kwarg on setting()"
```

---

### Task 2: `eligible_promotion_directions()` — single source of truth + guard + grandfather

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/node/promotion.py`
- Test: `tests/core/settings/test_promotable_eligibility.py` (extend)

**Interfaces:**
- Consumes: `Promotable` / `desc._promotable` from Task 1; existing `_descriptor`, `bind_promoted_ports`, `promote_setting`.
- Produces (relied on by Task 3): `eligible_promotion_directions(descriptor: "setting") -> tuple[PortType, ...]` — ordered `(INLET, OUTLET)` subset; empty tuple = not promotable.

- [ ] **Step 1: Baseline check**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/node/promotion.py && uv run mypy packages/haywire-core/src/haywire/core/node/promotion.py`
Expected: both clean.

- [ ] **Step 2: Write the failing tests**

Append to `tests/core/settings/test_promotable_eligibility.py`:

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
    def test_promote_none_field_raises(self, make_node_with_setting):
        from haywire.core.node.promotion import promote_setting
        from haywire.core.types.enums import PortType

        node = make_node_with_setting(accessor="filter", field="threshold")
        # The fixture builds a FRESH bag class per call, so stamping its
        # descriptor cannot leak across tests.
        type(node.filter).__dict__["threshold"]._promotable = Promotable.NONE

        for direction in (PortType.INLET, PortType.OUTLET):
            with pytest.raises(ValueError, match="cannot be promoted"):
                promote_setting(node, "filter", "threshold", direction)
        assert "threshold" not in {p.id.split(".")[-1] for p in node.ports.values()}

    def test_promote_outlet_only_field_to_inlet_raises(self, make_node_with_setting):
        from haywire.core.node.promotion import promote_setting
        from haywire.core.types.enums import PortType

        node = make_node_with_setting(accessor="filter", field="threshold")
        type(node.filter).__dict__["threshold"]._promotable = Promotable.OUTLET

        with pytest.raises(ValueError, match="cannot be promoted"):
            promote_setting(node, "filter", "threshold", PortType.INLET)
        promote_setting(node, "filter", "threshold", PortType.OUTLET)  # allowed

    def test_read_only_error_still_raised_via_helper(self, make_node_with_setting):
        """The old dedicated read-only guard is folded into the helper — the
        behavior (raise on read_only→inlet) must survive the rewiring."""
        from haywire.core.node.promotion import promote_setting
        from haywire.core.types.enums import PortType

        node = make_node_with_setting(accessor="filter", field="threshold", with_watch=True)
        with pytest.raises(ValueError, match="cannot be promoted"):
            promote_setting(node, "filter", "threshold_watched", PortType.INLET)


@pytest.mark.integration
class TestGrandfatherOnLoad:
    def test_bind_promoted_ports_keeps_no_longer_eligible_port(
        self, make_node_with_setting, caplog
    ):
        """A saved graph may hold a promoted port for a field that later became
        promotable=NONE. Load must keep + rebind it (INFO log), never demote."""
        import logging

        from haywire.core.node.promotion import bind_promoted_ports, promote_setting

        node = make_node_with_setting(accessor="filter", field="threshold")
        promote_setting(node, "filter", "threshold")
        pid = type(node.filter).__dict__["threshold"].storage_key

        # Simulate the library changing the declaration after the graph was saved.
        type(node.filter).__dict__["threshold"]._promotable = Promotable.NONE

        node.ports[pid].unbind_field()  # what a fresh load starts from
        with caplog.at_level(logging.INFO):
            bind_promoted_ports(node)

        assert pid in node.ports, "grandfather: the port must survive"
        assert node.ports[pid].promoted is True
        assert any("grandfathered" in rec.message for rec in caplog.records)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/core/settings/test_promotable_eligibility.py -v`
Expected: the Task 1 classes PASS; every new test FAILS with `ImportError: cannot import name 'eligible_promotion_directions'`.

- [ ] **Step 4: Implement the helper, rewire the guard, add the grandfather log**

In `packages/haywire-core/src/haywire/core/node/promotion.py`:

Add the helper **after the `_descriptor` function** (the small resolver ending around line 55):

```python
def eligible_promotion_directions(descriptor: "setting") -> tuple[PortType, ...]:
    """The single source of truth for promotion eligibility.

    Two orthogonal contributions, intersected:

    1. **Declared intent** — ``setting(promotable=...)``, default ``ALL``.
       ``NONE`` marks fields where a port would be misleading (e.g.
       restart-required pipeline parameters).
    2. **Structural** — a ``read_only`` (``watch()``) field has no write path
       in, so it can never be an inlet regardless of declaration.

    Consumed by ``promote_setting`` (raises for ineligible NEW promotions) and
    the promote menu's ``promotable_fields`` (hides ineligible entries).
    ``bind_promoted_ports`` deliberately does NOT enforce it — saved graphs
    are grandfathered (see its INFO log).
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

In `promote_setting`, replace the read-only guard (the two lines under `# Flag check 1: a read-only (watch) field can only be an outlet.`):

```python
    # Flag check 1: a read-only (watch) field can only be an outlet.
    if getattr(desc, "_read_only", False) and direction is not PortType.OUTLET:
        raise ValueError("a read-only (watch) setting can only be promoted to an outlet")
```

with:

```python
    # Eligibility — the single source of truth shared with the promote menu
    # (declared promotable= ∩ read-only structural rule).
    eligible = eligible_promotion_directions(desc)
    if direction not in eligible:
        raise ValueError(
            f"setting {field!r} cannot be promoted to {direction.name.lower()} "
            f"(eligible: {', '.join(d.name.lower() for d in eligible) or 'none'})"
        )
```

Also update `promote_setting`'s docstring: the "Eligibility is TWO orthogonal flag checks" paragraph's item 1 now reads:

```
    1. ``eligible_promotion_directions(desc)`` — declared ``promotable=`` ∩
       the read-only structural rule (``watch()`` ⇒ outlet only). Raises for
       ineligible NEW promotions; saved graphs are grandfathered by
       ``bind_promoted_ports``.
```

In `bind_promoted_ports`, add the grandfather log after the successful `_resolve_promoted` (between the `except KeyError` block's `continue` and the `_bind_port(port, bag, desc)` call):

```python
        direction = PortType.INLET if port.is_inlet() else PortType.OUTLET
        if direction not in eligible_promotion_directions(desc):
            logger.info(
                "Promoted port %r on node %r is no longer promotable to %s per its "
                "descriptor (promotable= changed since the graph was saved); "
                "keeping the existing port (grandfathered).",
                port.id,
                node.node_id,
                direction.name.lower(),
            )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/core/settings/test_promotable_eligibility.py -v`
Expected: PASS, all 16 tests green.

- [ ] **Step 6: Run the promotion-adjacent suites for regressions**

Run: `uv run pytest tests/core/settings/ tests/ui/menu/test_promote_demote_menu.py tests/ui/panel/test_promoted_row_state.py tests/ui/graph_canvas/test_context_menu_actions.py -q`
Expected: PASS — in particular the existing menu tests still pass untouched, because the default `ALL` reproduces the old two-flag rule exactly.

- [ ] **Step 7: Full baseline re-check**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/node/promotion.py && uv run ruff format --check packages/haywire-core/src/haywire/core/node/promotion.py && uv run mypy packages/haywire-core/src/haywire/core/node/promotion.py`
Expected: all clean.

- [ ] **Step 8: Commit**

```bash
git add packages/haywire-core/src/haywire/core/node/promotion.py tests/core/settings/test_promotable_eligibility.py
git commit -m "feat(promotion): eligible_promotion_directions single source of truth; grandfather saved ports"
```

---

### Task 3: Promote menu consumes the shared helper

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/node/promote.py` (`promotable_fields` + module/func docstrings)
- Test: `tests/ui/menu/test_promote_demote_menu.py` (extend)

**Interfaces:**
- Consumes: `eligible_promotion_directions` from Task 2.
- Produces: no signature changes — `promotable_fields(node)` keeps returning `(accessor, field, directions)` tuples; fields with empty `directions` are now omitted entirely.

- [ ] **Step 1: Baseline check**

Run: `uv run ruff check barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/node/promote.py && uv run mypy barn/haybale-graph-editor/haybale_graph_editor/`
Expected: both clean.

- [ ] **Step 2: Write the failing tests**

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
    from haybale_graph_editor.panels.graph.menu.node.promote import promotable_fields

    node = make_node_with_setting(accessor="filter", field="threshold")
    type(node.filter).__dict__["threshold"]._promotable = Promotable.OUTLET

    fields = {(acc, fld): dirs for acc, fld, dirs in promotable_fields(node)}
    assert fields[("filter", "threshold")] == (PortType.OUTLET,)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/ui/menu/test_promote_demote_menu.py -v`
Expected: the two new tests FAIL (`promotable_fields` still offers both directions); all pre-existing tests PASS.

- [ ] **Step 4: Rewire `promotable_fields`**

In `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/node/promote.py`:

Add the import alongside the existing `from haywire.core.types.enums import PortType`:

```python
from haywire.core.node.promotion import eligible_promotion_directions
```

In `promotable_fields`, replace the inline rule:

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

Update the two docstrings that state the old rule so they reference the shared helper instead:

- Module docstring: replace "per the eligibility rule: a read-only ``watch()`` field is outlet-only; ``shadow()`` and plain fields can be promoted either way." with "per ``eligible_promotion_directions()`` — the shared eligibility rule (declared ``promotable=`` ∩ read-only structural rule); ineligible fields are hidden."
- `promotable_fields` docstring: replace the "two-flag rule" bullet list with "where *directions* come from ``haywire.core.node.promotion.eligible_promotion_directions`` (single source of truth, shared with ``promote_setting``'s guard). Fields with no eligible direction are omitted."

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/ui/menu/test_promote_demote_menu.py -v`
Expected: PASS, all tests green (old + 2 new).

- [ ] **Step 6: Full baseline re-check + fast suite**

Run: `uv run ruff check barn/haybale-graph-editor/ && uv run ruff format --check barn/haybale-graph-editor/ && uv run pytest -m "not integration" -q && uv run pytest -m integration tests/ui/menu/ -q`
Expected: all clean/passing.

- [ ] **Step 7: Commit**

```bash
git add barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/node/promote.py tests/ui/menu/test_promote_demote_menu.py
git commit -m "feat(menu): promote submenu uses shared eligibility; promotable=NONE fields hidden"
```

---

### Task 4: Documentation — `setting-canon.md`

**Files:**
- Modify: `docs/components/settings/setting-canon.md`

**Interfaces:**
- Consumes: the finished API from Tasks 1-3.
- Produces: documentation only.

- [ ] **Step 1: Extend the promotion section**

In `docs/components/settings/setting-canon.md`, find the "**Promoting a setting to a port**" section (immediately before the `ui_disabled`/`enabled_when` section that rev 2 added). Append to that section:

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

`Promotable` is a Flag: `NONE` / `INLET` / `OUTLET` / `ALL` (default). Effective eligibility is the intersection of the declaration and the structural rules (`read_only=True` stays outlet-only regardless; `read_only` + `promotable=INLET` intersects to nothing). The single source of truth is `eligible_promotion_directions()` in `haywire.core.node.promotion` — the promote menu hides ineligible entries and `promote_setting()` raises `ValueError` for them.

**Saved graphs are grandfathered:** if a library changes a field to `promotable=NONE`, graphs that already promoted it keep their port on load (an `INFO` log notes the mismatch); only new promotions are blocked. Demote manually to converge.
```

- [ ] **Step 2: Preview the docs site**

Run: `uv run mkdocs serve`, check the settings canon page renders correctly, then stop the server.

- [ ] **Step 3: Commit**

```bash
git add docs/components/settings/setting-canon.md
git commit -m "docs(settings): document promotable= and the grandfather rule"
```

---

### Task 5: OAK-D consumer — depth bag becomes non-promotable

**Files:**
- Modify: `barn/haybale-visiongraph/haybale_visiongraph/nodes/oak_d_camera_node.py`
- Modify: `barn/haybale-visiongraph/notes.md`

> **Repo note:** `barn/haybale-visiongraph` is a gitignored symlink into the separate haybale-visiongraph repository. Run this task's quality commands AND the `git add`/`git commit` from `/Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph`, never from haywire-repo.

**Interfaces:**
- Consumes: `Promotable` from Task 1 (already enforced end-to-end by Tasks 2-3).
- Produces: nothing — terminal consumer.

- [ ] **Step 1: Baseline check**

Run:
```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph
uv run ruff check barn/haybale-visiongraph/haybale_visiongraph/nodes/oak_d_camera_node.py
uv run mypy barn/haybale-visiongraph/haybale_visiongraph/nodes/oak_d_camera_node.py
```
Expected: clean.

- [ ] **Step 2: Mark the six depth fields**

In `oak_d_camera_node.py`, extend the settings import:

```python
from haywire.core.settings import NodeSettings, Promotable, setting
```

Add `promotable=Promotable.NONE,` to each of the six fields in `class depth(NodeSettings)` — `preset_mode`, `median_filter`, `left_right_check`, `subpixel`, `extended_disparity`, `frame_alignment` — as the last kwarg of each `setting(...)` call, e.g.:

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

(The module docstring's claim that depth settings are "never promotable to a port" — written aspirationally in a prior round — becomes true with this change; no docstring edit needed.)

- [ ] **Step 3: Verify in the running app**

From haywire-repo: `uv run haywire`. Create an `OAK-D Camera` node, right-click → Promote Setting. Expected: the `depth` bag is absent from the flyout entirely (all its fields ineligible → the bag category is omitted); `ir`/`color` fields still offer inlet/outlet.

- [ ] **Step 4: Full baseline re-check + fast suite**

Run (from haybale-visiongraph): the Step 1 commands plus `uv run ruff format --check barn/haybale-visiongraph/haybale_visiongraph/nodes/oak_d_camera_node.py`.
Run (from haywire-repo): `uv run pytest -m "not integration" -q`.
Expected: all clean/passing.

- [ ] **Step 5: Record in notes.md and commit — in the haybale-visiongraph repo**

Append to `barn/haybale-visiongraph/notes.md`:

```markdown
## Depth settings are promotable=NONE (BUILT)

The `depth` bag is restart-required pipeline configuration; a promoted port
would imply live control the hardware can't deliver. The framework's
`promotable=` flag (see setting-canon.md) now enforces what the module
docstring only promised: all six depth fields are `Promotable.NONE` — hidden
from the promote menu, rejected by `promote_setting()`. Saved graphs that
promoted one before this change keep their port on load (grandfathered).
```

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph
git add barn/haybale-visiongraph/haybale_visiongraph/nodes/oak_d_camera_node.py barn/haybale-visiongraph/notes.md
git commit -m "feat(oak-d): depth settings promotable=NONE (restart-required, no live port)"
```

---

## Self-Review

**Spec coverage:**
- ✅ `Promotable` NONE/INLET/OUTLET/ALL enum + `promotable=` kwarg, default ALL — Task 1.
- ✅ Single source of truth `eligible_promotion_directions()` replacing the duplicated rule — Task 2 (guard) + Task 3 (menu).
- ✅ `read_only` intersection semantics (incl. the contradiction → empty case) — Task 2 matrix tests.
- ✅ Grandfather on load, never auto-demote, INFO log — Task 2 `bind_promoted_ports` + `TestGrandfatherOnLoad`.
- ✅ Menu hides (not greys) ineligible fields; empty bags already omitted by existing grouping — Task 3.
- ✅ Backward compatibility: default ALL reproduces the old rule bit-for-bit; the pre-existing menu tests are run unmodified as the regression proof — Task 3 Step 6.
- ✅ Docs — Task 4. OAK-D consumer + repo-correct commit — Task 5.

**Placeholder scan:** none; every step carries literal code. Text anchors used instead of raw line numbers by design (this plan is sequenced after rev 2, which shifts `descriptor.py` and `setting-canon.md`).

**Type consistency:** `eligible_promotion_directions(descriptor) -> tuple[PortType, ...]` matches all three call sites (guard, grandfather check, menu) and every test; `Promotable` import paths are `haywire.core.settings` (public, Tasks 3/5 and tests) and `haywire.core.settings.descriptor` (inside promotion.py's helper, avoiding the package-init import at module scope); descriptor stamping in tests uses `type(node.filter).__dict__["threshold"]` — the same access pattern the existing menu test file already uses for `storage_key`.
