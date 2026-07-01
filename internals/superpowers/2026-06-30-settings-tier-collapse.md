# Settings Tier Collapse / Drop OVERRIDE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the settings resolution model from a 6-case / 2-strength chain (global/workspace/local × EXPLICIT/OVERRIDE) down to **highest-priority-set-wins** with no `OVERRIDE` strength, so every tier value is simply *set* or *unset*.

**Architecture:** Today a tier value is a `SettingValue(mode, value)` where `mode ∈ {INHERIT, EXPLICIT, OVERRIDE}`. `INHERIT` means "unset / no opinion," `EXPLICIT` means "set," and `OVERRIDE` means "forced — beats everything below including a local instance value." This plan **drops `OVERRIDE` entirely**: `SettingValue` keeps its `value` but its three-way `mode` is replaced by a two-state `is_set` boolean (`SettingValue.unset()` / `SettingValue.of(value)`). Resolution becomes a strict priority walk with no forcing tier: **workspace-set → global-set → local-set → default** for the registry's own effective value, and for a node field **local-set → workspace-set → global-set → default**. The "global OVERRIDE beats my local override" behaviour and the `{override = true, value = …}` TOML inline-table form are removed. `SettingMode` becomes vestigial and is deleted at the end of the plan. This is plan **P2** of a 5-plan arc (canonical-key → **tier-collapse** → TOML→JSON → single-cell → promotion-as-direction); P1 (`storage_key`) has landed on this same branch and P2 builds on it.

**Tech Stack:** Python 3, `pytest`, `ruff`, `mypy`. Haywire monorepo (`uv run` for all tooling).

## Global Constraints

- Line length 109 (`ruff`, configured in repo).
- CI runs BOTH `ruff check` AND `ruff format --check` — run both locally; they catch disjoint problems.
- mypy scope for this plan: `uv run mypy packages/haywire-core/src/`.
- In test files, import `haywire.core.graph.editor` before other haywire modules to avoid circular import errors.
- Stay on branch `feat/type-floor-hoist`. Do NOT merge to master between plans (per the roadmap). The gate is "committed + green on this branch."
- **Do NOT bundle later-plan work:** no TOML→JSON (that is P3 — `save_to_toml`/`load_from_toml` keep their names and TOML format here, only the OVERRIDE branch is removed), no single-cell / `_local_store` removal (P4), no promotion changes (P5). Touch only the tier-collapse surface.
- The whole arc is reference: `internals/ideas/settings-datafield-unification-DECISIONS.md` (§A is this plan's authority) and `internals/ideas/settings-datafield-unification-ROADMAP.md` (P2 section).

---

## The decision this plan locks (DECISIONS.md §A)

After collapse, a tier value has exactly two states:

| Old `SettingMode` | New state | Meaning |
| --- | --- | --- |
| `INHERIT` | **unset** (`is_set=False`) | tier has no opinion → defer down the priority order |
| `EXPLICIT` | **set** (`is_set=True`) | tier holds a value → eligible to win |
| `OVERRIDE` | — **GONE** — | the "forced" strength is removed entirely |

**Resolution (registry effective value)** — highest-priority *set* tier wins, else default:

```
workspace-set  →  global-set  →  (default)
```

**Resolution (a node/instance field via `Settings._resolve`)** — the local instance value sits ABOVE the global tiers (it is the per-node override), so:

```
local-set  →  workspace-set  →  global-set  →  default
```

This is exactly the old chain with steps 1 (global OVERRIDE) and 2 (workspace OVERRIDE) deleted — old steps 3/4/5/6 become new 1/2/3/4. The relative order of local vs workspace vs global below the (now-removed) override tier is **unchanged**, so a graph with no OVERRIDE on disk resolves identically before and after this plan.

**`_on_field_change` "unset tracks / set ignores" rule (DECISIONS.md §A reactive-default):**
- Before: a mirrored global change is suppressed when the instance has a local override, UNLESS the incoming change is a global `OVERRIDE` (which always re-fires).
- After: a mirrored global change is suppressed when the instance has a local override, **full stop** (no OVERRIDE escape hatch). When the cell is unset the field re-resolves and the callback fires.

---

## File Structure

| File | Responsibility | Change |
| --- | --- | --- |
| `packages/haywire-core/src/haywire/core/settings/value.py` | `SettingValue` carrier. Replace `mode`/`is_inherit`/`is_explicit`/`is_override` with `is_set` + `unset()`/`of()` constructors. | Modify |
| `packages/haywire-core/src/haywire/core/settings/registry.py` | `resolve()` (6→4 cases), `_effective_value` (5→2 cases), `set_global`/`reset_global` (drop `mode` param), tier-init/notify (`SettingValue.unset()`), `save_to_toml` (drop override inline-table), `_parse_config_dict`/`_process_entry` (drop override parse). | Modify |
| `packages/haywire-core/src/haywire/core/settings/settings.py` | `_resolve` (local SettingValue uses `of()`), `_on_field_change` (drop OVERRIDE escape → plain "set ignores"). | Modify |
| `packages/haywire-core/src/haywire/core/settings/enums.py` | Delete `SettingMode` (last task, once unreferenced). | Modify (delete class) |
| `packages/haywire-core/src/haywire/core/settings/__init__.py` | Drop `SettingMode` from imports + `__all__`. | Modify |
| `packages/haywire-core/src/haywire/core/debug/configurator.py` | `sv.mode == INHERIT` → `not sv.is_set`. | Modify |
| `packages/haywire-core/src/haywire/core/di/config.py` | `_print_settings_status` override/explicit counts → `is_set`; `set_setting(override=…)` wrapper loses `override`. | Modify |
| `packages/haywire-core/src/haywire/core/di/test_config.py` | `SettingsTestContext.set_override` deleted; `set`/`reset`/restore + `create_test_settings_registry` re-expressed against `is_set`. | Modify |
| `tests/core/test_settings/test_settings.py` | `test_global_override_fires_callback_even_with_local_override` rewritten as the new "set ignores" rule. | Modify |
| `tests/core/test_settings/test_tier_collapse.py` | NEW — asserts 4-case resolution, no-OVERRIDE, set/unset round-trip, removed-`SettingMode` guard. | Create |
| `docs/architecture/settings/settings-arch.md` | §1–4 rewritten to the 2-tier / set-or-unset model; §5 worked example updated. | Modify |
| `docs/reference/glossary.md` | "Three-tier resolution" entry + the two persona Q&A lines rewritten to the collapsed model. | Modify |
| `docs/adr/00NN-collapse-settings-tiers.md` | NEW — ADR-A, written LAST against landed code. | Create |

**Out of scope (do not touch):** `descriptor.py`'s `__get__`/`__set__` (no mode logic there — the local-store keying is P1-landed and the promoted read-tier is P5), `persistent_setting.__set__` (calls `set_global(key, value)` positionally — unaffected by dropping the `mode` keyword as long as the signature keeps `value` as the second positional), `pipe.py`, `port.py`, promotion.

---

## Pre-edit baseline (run once before Task 1)

Per CLAUDE.md, establish the baseline so post-edit failures are attributable.

```sh
uv run ruff check packages/haywire-core/src/haywire/core/settings packages/haywire-core/src/haywire/core/di packages/haywire-core/src/haywire/core/debug
uv run mypy packages/haywire-core/src/
uv run pytest tests/core/test_settings/ packages/haywire-core/src/haywire/core/di/ -q
```

Expected: all clean (the codebase has no errors per CLAUDE.md). If anything fails here, STOP and surface it to the user — it is pre-existing and not yours to silently absorb.

---

### Task 1: Collapse `SettingValue` to set/unset

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/value.py`
- Test: `tests/core/test_settings/test_tier_collapse.py` (Create)

**Interfaces:**
- Produces:
  - `SettingValue(is_set: bool = False, value: T | None = None)` — dataclass.
  - classmethods `SettingValue.unset() -> SettingValue` and `SettingValue.of(value: T) -> SettingValue`.
  - `SettingValue.to_dict() -> dict` returns `{"value": value}` when set, `{}` when unset.
  - `SettingValue.from_dict(data: dict) -> SettingValue` — `of(data["value"])` if `"value"` present, else `unset()`.
  - NO `mode`, NO `is_inherit`/`is_explicit`/`is_override`.
- Consumes: nothing (leaf change — but `enums.SettingMode` import is dropped here).

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_settings/test_tier_collapse.py`:

```python
# tests/core/test_settings/test_tier_collapse.py
"""Tests for the P2 tier-collapse: OVERRIDE dropped, tiers are set-or-unset."""

import haywire.core.graph.editor  # noqa: F401  (circular-import guard, per CLAUDE.md)

from haywire.core.settings.value import SettingValue


class TestSettingValueSetUnset:
    def test_unset_is_not_set(self):
        sv = SettingValue.unset()
        assert sv.is_set is False
        assert sv.value is None

    def test_of_is_set(self):
        sv = SettingValue.of(42)
        assert sv.is_set is True
        assert sv.value == 42

    def test_default_construction_is_unset(self):
        assert SettingValue().is_set is False

    def test_roundtrip_set(self):
        sv = SettingValue.of("#aabbcc")
        assert SettingValue.from_dict(sv.to_dict()) == sv

    def test_roundtrip_unset(self):
        sv = SettingValue.unset()
        assert sv.to_dict() == {}
        assert SettingValue.from_dict({}) == sv

    def test_no_mode_attribute(self):
        assert not hasattr(SettingValue.of(1), "mode")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_settings/test_tier_collapse.py::TestSettingValueSetUnset -v`
Expected: FAIL — `SettingValue.unset` / `.of` don't exist; `test_no_mode_attribute` fails because `mode` still exists.

- [ ] **Step 3: Rewrite `value.py`**

Replace the entire body of `packages/haywire-core/src/haywire/core/settings/value.py` with:

```python
# haywire/core/settings/value.py
"""
SettingValue — a tier's stored opinion: either set (carries a value) or unset.

The pre-P2 model had a three-way ``SettingMode`` (INHERIT/EXPLICIT/OVERRIDE).
The OVERRIDE "forced" strength was dropped (DECISIONS.md §A); a tier value is
now simply set-or-unset, and resolution is highest-priority-set-wins.
"""

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class SettingValue(Generic[T]):
    """A tier's stored state: ``is_set`` plus an optional ``value``.

    Construct via :meth:`unset` / :meth:`of` rather than the raw fields.
    """

    is_set: bool = False
    value: T | None = None

    @classmethod
    def unset(cls) -> "SettingValue[T]":
        """A tier with no opinion — defers to the next tier in priority order."""
        return cls(is_set=False, value=None)

    @classmethod
    def of(cls, value: T) -> "SettingValue[T]":
        """A tier holding *value* — eligible to win resolution."""
        return cls(is_set=True, value=value)

    def to_dict(self) -> dict:
        """Serialize for storage. Unset values serialize to ``{}``."""
        return {"value": self.value} if self.is_set else {}

    @classmethod
    def from_dict(cls, data: dict) -> "SettingValue":
        """Deserialize from storage."""
        if "value" in data:
            return cls.of(data["value"])
        return cls.unset()

    def __repr__(self) -> str:
        if not self.is_set:
            return "SettingValue(unset)"
        return f"SettingValue({self.value!r})"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_settings/test_tier_collapse.py::TestSettingValueSetUnset -v`
Expected: PASS (all 6).

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/settings/value.py tests/core/test_settings/test_tier_collapse.py
git commit -m "refactor(settings): collapse SettingValue to set/unset, drop SettingMode dependency

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Collapse the registry resolution & effective value

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/registry.py`
- Test: `tests/core/test_settings/test_tier_collapse.py`

**Interfaces:**
- Consumes: `SettingValue.unset()`/`.of()`/`.is_set` (Task 1).
- Produces:
  - `resolve(name, local: SettingValue | None = None) -> tuple[Any, str]` — `source ∈ {'local','workspace','global','default'}` (no more `*_override`).
  - `_effective_value(name) -> SettingValue` — workspace-set beats global-set, else `unset()`.
  - `set_global(name, value, tier='workspace') -> None` — **`mode` param removed.**
  - `reset_global(name, tier='workspace') -> None` — unchanged signature, writes `unset()`.

- [ ] **Step 1: Write the failing test**

Append to `tests/core/test_settings/test_tier_collapse.py`:

```python
import pytest

from haywire.core.settings.registry import SettingsRegistry
from haywire.barn.builtin.types import INT


def _reg_with(name="exec.threads", default=4):
    reg = SettingsRegistry()
    reg.define(name, default, type_=INT)
    return reg, name


class TestResolutionCollapse:
    def test_default_when_no_tier_set(self):
        reg, name = _reg_with()
        assert reg.resolve(name) == (4, "default")

    def test_global_set_beats_default(self):
        reg, name = _reg_with()
        reg.set_global(name, 8, tier="global")
        assert reg.resolve(name) == (8, "global")

    def test_workspace_set_beats_global_set(self):
        reg, name = _reg_with()
        reg.set_global(name, 8, tier="global")
        reg.set_global(name, 16, tier="workspace")
        assert reg.resolve(name) == (16, "workspace")

    def test_local_beats_workspace(self):
        reg, name = _reg_with()
        reg.set_global(name, 16, tier="workspace")
        assert reg.resolve(name, local=SettingValue.of(32)) == (32, "local")

    def test_unset_local_falls_through(self):
        reg, name = _reg_with()
        reg.set_global(name, 16, tier="workspace")
        assert reg.resolve(name, local=SettingValue.unset()) == (16, "workspace")

    def test_set_global_rejects_mode_kwarg(self):
        reg, name = _reg_with()
        with pytest.raises(TypeError):
            reg.set_global(name, 8, mode="anything")  # type: ignore[call-arg]

    def test_reset_global_returns_to_default(self):
        reg, name = _reg_with()
        reg.set_global(name, 8, tier="workspace")
        reg.reset_global(name, tier="workspace")
        assert reg.resolve(name) == (4, "default")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_settings/test_tier_collapse.py::TestResolutionCollapse -v`
Expected: FAIL — `set_global` still requires the `mode` import path / accepts `mode`; `resolve` still returns `*_override` sources and imports `SettingMode`.

- [ ] **Step 3: Edit `registry.py`**

3a. **Top imports** — remove `from .enums import SettingMode` (line ~23). Leave everything else.

3b. **`_store_definition`** (~line 222) — replace the two `SettingValue(mode=SettingMode.INHERIT)` tier-init lines and the `_notify_subscribers` sentinel:

```python
        if name not in self._global_tier_values:
            self._global_tier_values[name] = SettingValue.unset()
        if name not in self._workspace_tier_values:
            self._workspace_tier_values[name] = SettingValue.unset()
        ...
        if is_new:
            self._notify_subscribers({name: SettingValue.unset()})
```

3c. **`_effective_value`** (~line 863) — collapse 5 cases to 2:

```python
    def _effective_value(self, name: str) -> SettingValue:
        """Return the merged effective global value: workspace-set beats global-set, else unset.

        Used internally for change detection and by get_global().
        """
        workspace_sv = self._workspace_tier_values.get(name, SettingValue.unset())
        if workspace_sv.is_set:
            return workspace_sv
        global_sv = self._global_tier_values.get(name, SettingValue.unset())
        if global_sv.is_set:
            return global_sv
        return SettingValue.unset()
```

3d. **`set_global`** (~line 902) — drop the `mode` param and the OVERRIDE-aware validate guard:

```python
    def set_global(
        self,
        name: str,
        value: Any,
        tier: str = "workspace",
    ) -> None:
        """Set a tier value programmatically (marks the tier *set*).

        Args:
            name:  Full setting key (e.g. 'ui.node.bg_color').
            value: New value.
            tier:  'workspace' (default, saved by UI) or 'global' (hand-edited).
        """
        tier_dict = self._workspace_tier_values if tier == "workspace" else self._global_tier_values

        with self._lock:
            if name not in self._definitions:
                raise KeyError(f"Unknown setting: {name}")

            defn = self._definitions[name]
            if not defn.validate(value):
                raise ValueError(f"Invalid value for '{name}': {value}")

            old_effective = (self._effective_value(name).is_set, self._effective_value(name).value)
            tier_dict[name] = SettingValue.of(value)
            new_effective = self._effective_value(name)

            if (new_effective.is_set, new_effective.value) != old_effective:
                self._notify_subscribers({name: new_effective})
```

3e. **`reset_global`** (~line 935) — `SettingValue(mode=SettingMode.INHERIT)` → `SettingValue.unset()` and the effective tuple uses `is_set`:

```python
    def reset_global(self, name: str, tier: str = "workspace") -> None:
        """Reset a value to *unset* in the specified tier."""
        tier_dict = self._workspace_tier_values if tier == "workspace" else self._global_tier_values

        with self._lock:
            if name in tier_dict:
                old_effective = (self._effective_value(name).is_set, self._effective_value(name).value)
                tier_dict[name] = SettingValue.unset()
                new_effective = self._effective_value(name)

                if (new_effective.is_set, new_effective.value) != old_effective:
                    self._notify_subscribers({name: new_effective})
```

3f. **`resolve`** (~line 958) — collapse 6 cases to 4:

```python
    def resolve(self, name: str, local: SettingValue | None = None) -> tuple[Any, str]:
        """Resolve the final value for a setting given an optional local override.

        Resolution order (highest-priority set tier wins):
            1. local SET            → per-node/per-instance override
            2. workspace tier SET   → workspace default (set via UI)
            3. global tier SET      → user global default (hand-edited)
            4. definition default

        Returns (resolved_value, source) where source is one of:
        'local', 'workspace', 'global', 'default'.
        """
        defn = self._definitions.get(name)
        if not defn:
            raise KeyError(f"Unknown setting: {name}")

        local = local or SettingValue.unset()
        if local.is_set:
            return local.value, "local"

        workspace_sv = self._workspace_tier_values.get(name, SettingValue.unset())
        if workspace_sv.is_set:
            return workspace_sv.value, "workspace"

        global_sv = self._global_tier_values.get(name, SettingValue.unset())
        if global_sv.is_set:
            return global_sv.value, "global"

        default = defn._default() if callable(defn._default) else defn._default
        return default, "default"
```

3g. **`_reload_from_file`** (~line 353) and **`_repopulate_from_toml_for_keys`** (~line 392) — these snapshot `old_effective` as `(sv.mode, sv.value)` and reset tier entries to `SettingValue(mode=SettingMode.INHERIT)`. Change the snapshot tuples to `(self._effective_value(name).is_set, self._effective_value(name).value)` and the reset to `SettingValue.unset()`. (`_notify_changes` at line ~603 compares those same tuples — update it in lockstep in Task 4 step on `_process_entry`/`_notify_changes`; for now only fix the reset line and the snapshot tuple shape.)

In `_reload_from_file`:
```python
            old_effective = {
                name: (self._effective_value(name).is_set, self._effective_value(name).value)
                for name in self._definitions
            }
            ...
            for name in self._definitions:
                tier_dict[name] = SettingValue.unset()
```

In `_repopulate_from_toml_for_keys`:
```python
            old_effective = {
                name: (self._effective_value(name).is_set, self._effective_value(name).value)
                for name in keys
                if name in self._definitions
            }
```

3h. **`_notify_changes`** (~line 603) — its `old` default sentinel and comparison use `(mode, value)`:

```python
    def _notify_changes(self, old_effective: dict[str, tuple]) -> None:
        all_names = set(old_effective.keys()) | set(self._definitions.keys())
        changed: dict[str, SettingValue] = {}
        for name in all_names:
            old = old_effective.get(name, (False, None))
            new = self._effective_value(name)
            if (new.is_set, new.value) != old:
                changed[name] = new
        if changed:
            self._notify_subscribers(changed)
```

3i. **`_unregister_schema_fields`** (~line 254) and **`undefine`** (~line 840) — their `_notify_subscribers({k: SettingValue(mode=SettingMode.INHERIT)…})` sentinels become `SettingValue.unset()`.

- [ ] **Step 4: Run the new resolution tests**

Run: `uv run pytest tests/core/test_settings/test_tier_collapse.py::TestResolutionCollapse -v`
Expected: PASS (all 7).

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/settings/registry.py tests/core/test_settings/test_tier_collapse.py
git commit -m "refactor(settings): collapse registry resolution to highest-set-wins, drop OVERRIDE

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Drop the OVERRIDE inline-table from TOML read/write

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/registry.py`
- Test: `tests/core/test_settings/test_tier_collapse.py`

**Interfaces:**
- Consumes: Task 1/2 (`SettingValue.of/.is_set`).
- Produces: `save_to_toml` writes bare values only; `_parse_config_dict`/`_process_entry` no longer recognise `override`/`mode` keys; round-trip is still TOML (P3 changes the format — NOT here).

- [ ] **Step 1: Write the failing test**

Append to `tests/core/test_settings/test_tier_collapse.py`:

```python
from pathlib import Path


class TestTomlNoOverride:
    def test_save_writes_bare_value(self, tmp_path: Path):
        reg, name = _reg_with("exec.threads", 4)
        reg.set_global(name, 16, tier="workspace")
        out = tmp_path / "settings.toml"
        reg.save_to_toml(out)
        import toml

        data = toml.load(out)
        # nested under exec.threads, bare scalar — never an {override,value} table
        assert data["exec"]["threads"] == 16

    def test_load_ignores_override_key_as_plain_set(self, tmp_path: Path):
        # A legacy {override=true, value=…} table loads as a *set* value, not a forced one.
        out = tmp_path / "settings.toml"
        out.write_text('[exec]\nthreads = { override = true, value = 99 }\n')
        reg, name = _reg_with("exec.threads", 4)
        reg.load_from_toml(out, tier="workspace")
        # value comes through; no OVERRIDE semantics remain (it's just a workspace set)
        assert reg.resolve(name) == (99, "workspace")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_settings/test_tier_collapse.py::TestTomlNoOverride -v`
Expected: FAIL — `save_to_toml` references `SettingMode`; the override table currently parses to an OVERRIDE-mode value.

- [ ] **Step 3: Edit `registry.py` TOML paths**

3a. **`save_to_toml`** (~line 645) — the write loop drops the INHERIT-skip-via-mode and the override branch:

```python
        with self._lock:
            for name, sv in sorted(self._workspace_tier_values.items()):
                if not sv.is_set:
                    continue
                self._set_nested(data, name, sv.value)
```

3b. **`_process_entry`** (~line 470) — a bare scalar is just a set value; a dict entry no longer carries a mode:

```python
    def _process_entry(self, name: str, entry: Any, tier_dict: dict[str, SettingValue]) -> None:
        """Process a single TOML entry into the given tier dict."""
        if isinstance(entry, dict):
            parsed = self._parse_config_dict(name, entry)
        else:
            parsed = {"value": entry}

        if name not in self._definitions:
            self._auto_define(name, parsed)

        if "value" in parsed:
            tier_dict[name] = SettingValue.of(parsed["value"])
```

3c. **`_parse_config_dict`** (~line 488) — delete the override/mode block; keep value + metadata passthrough:

```python
    def _parse_config_dict(self, name: str, config: dict) -> dict:
        """Parse a configuration dict from TOML (legacy {override,value} → bare value)."""
        result: dict = {}

        # Legacy compatibility: a {override=true, value=X} table from a pre-P2
        # file is read as a plain set value X. The 'override' flag is ignored.
        if "value" in config:
            result["value"] = config["value"]

        for key in [
            "default",
            "type",
            "label",
            "category",
            "description",
            "min_value",
            "max_value",
            "choices",
            "ui_widget",
            "ui_order",
        ]:
            if key in config:
                result[key] = config[key]

        return result
```

3d. **`_flatten_toml`** (~line 436) — its `setting_keys` recognises `'override'`/`'mode'`. Leave `'override'`/`'mode'` in that set so a legacy `{override=…}` dict is still treated as a *setting entry* (not a namespace) and routes through `_parse_config_dict` for the legacy→bare conversion. No change needed here; add a one-line comment noting why they stay.

- [ ] **Step 4: Run the TOML tests + whole tier-collapse file**

Run: `uv run pytest tests/core/test_settings/test_tier_collapse.py -v`
Expected: PASS (all classes).

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/settings/registry.py tests/core/test_settings/test_tier_collapse.py
git commit -m "refactor(settings): drop OVERRIDE inline-table from TOML; legacy tables read as plain set

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Collapse `Settings._resolve` and the `_on_field_change` rule

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/settings.py`
- Test: `tests/core/test_settings/test_settings.py`

**Interfaces:**
- Consumes: `SettingValue.of`, `resolve()`'s new 4-case sources (Tasks 1–2).
- Produces: `_resolve` builds the local `SettingValue` via `of(...)`; `_on_field_change` suppresses the callback whenever the field is locally set (no OVERRIDE escape).

- [ ] **Step 1: Rewrite the OVERRIDE test as the "set ignores" rule**

In `tests/core/test_settings/test_settings.py`, replace `test_global_override_fires_callback_even_with_local_override` (lines ~295–306) with:

```python
    def test_global_change_ignored_when_local_set_no_override_escape(self):
        """Post-P2: with a local override, ANY global change is suppressed.

        The pre-P2 OVERRIDE escape hatch (a forced global re-firing the callback
        despite a local override) is gone — there is no OVERRIDE strength anymore.
        """
        registry, bag, key = _make_mirror_bag(predefined_local={"color": "#ff0000"})
        calls = []
        bag.subscribe(lambda name, val, old: calls.append((name, val)))

        registry.set_global(key, "#aabbcc", tier="workspace")

        assert calls == [], "a local override suppresses every global change post-P2"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/core/test_settings/test_settings.py::TestMirrorCallbacks::test_global_change_ignored_when_local_set_no_override_escape -v`

(If the class name differs, find it: `grep -n "def test_global_change_suppressed_when_local_override_exists" tests/core/test_settings/test_settings.py` and use that class.)
Expected: FAIL — `set_global` still accepts/needs `mode`, and `_on_field_change` still imports `SettingMode`.

- [ ] **Step 3: Edit `settings.py`**

3a. **`_resolve`** (~line 79) — drop the `SettingMode` import and build the local value with `of()`:

```python
    def _resolve(self, field_key: str, mirror_key: str, default: Any) -> Any:
        """Resolution chain (extended mode): local SET > workspace SET > global SET > default."""
        from haywire.core.settings.value import SettingValue

        registry = self._registry
        assert registry is not None  # _resolve only called from extended mode
        key = mirror_key if mirror_key else field_key
        local_sv = (
            SettingValue.of(self._local_store[field_key]) if field_key in self._local_store else None
        )

        def _resolve_default(d: Any) -> Any:
            return d() if callable(d) else d

        try:
            value, source = registry.resolve(key, local=local_sv)
            if source == "default" and not mirror_key:
                return _resolve_default(default)
            return value
        except KeyError:
            return _resolve_default(self._local_store.get(field_key, default))
```

3b. **`_on_field_change`** (~line 120) — drop the OVERRIDE escape; suppress on any local set:

```python
    def _on_field_change(self, full_key: str, value: "SettingValue") -> None:
        """Dispatched by the registry when a mirrored field's effective value changes.

        "Unset tracks; set ignores" (DECISIONS.md §A): when the instance has a
        local override the resolved value is unchanged, so the callback is
        suppressed. With no local override the field re-resolves and fires.
        """
        if self._cleaned_up:
            return
        for attr_name, descriptor in type(self)._property_settings().items():
            if descriptor._mirror_key != full_key:
                continue
            field_key = descriptor.storage_key
            if field_key in self._local_store:
                continue
            new_val = getattr(self, attr_name)
            self._on_property_change(attr_name, new_val, None, descriptor._on_change or "")
```

(Remove the `from haywire.core.settings.enums import SettingMode` line and the `and value.mode != SettingMode.OVERRIDE` clause.)

- [ ] **Step 4: Run the mirror-callback tests**

Run: `uv run pytest tests/core/test_settings/test_settings.py -v -k "global_change or override or mirror or suppress"`
Expected: PASS — the new "set ignores" test passes; `test_global_change_suppressed_when_local_override_exists` and `test_global_change_fires_callback_when_no_local_override` still pass.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/settings/settings.py tests/core/test_settings/test_settings.py
git commit -m "refactor(settings): collapse _resolve + _on_field_change to set-ignores rule

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Update the registry consumers in `di/` and `debug/`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/debug/configurator.py`
- Modify: `packages/haywire-core/src/haywire/core/di/config.py`
- Modify: `packages/haywire-core/src/haywire/core/di/test_config.py`
- Test: existing `packages/haywire-core/src/haywire/core/di/` suite + `tests/`

**Interfaces:**
- Consumes: `SettingValue.is_set`, `set_global(name, value, tier=…)` (no `mode`).
- Produces: `SettingsTestContext` without `set_override`; `set_setting()` wrapper without `override`.

- [ ] **Step 1: Edit `configurator.py`**

`packages/haywire-core/src/haywire/core/debug/configurator.py` — remove `from ..settings.enums import SettingMode` (line ~12) and change the `_apply` branch (line ~135):

```python
        if not sv.is_set:
            # No tier value — apply default (inherit)
            self._apply_library_level(name, "")
        else:
            self._apply_library_level(name, str(sv.value) if sv.value else "")
```

- [ ] **Step 2: Edit `di/config.py`**

2a. `_print_settings_status` (~line 457) — drop `SettingMode` import; count set values, no override count:

```python
        custom_values = 0
        for name in definitions:
            sv = registry.get_global(name)
            if sv.is_set:
                custom_values += 1

        print(f"   Total settings:     {len(definitions)}")
        print(f"   Categories:         {len(categories)}")
        print(f"   Custom values:      {custom_values}")
```

(Delete the `overrides` counter and the `Global overrides:` print line entirely.)

2b. `set_setting` wrapper (~line 788) — drop the `override` param and the `SettingMode` import:

```python
    def set_setting(self, name: str, value: Any) -> None:
        """Set a global setting value.

        Args:
            name: Setting name
            value: Value to set
        """
        registry = self.get_settings_registry()
        registry.set_global(name, value)
```

Then `grep -rn "set_setting(" packages barn tests` — confirm no caller passes `override=`. (Baseline grep already showed zero `override=True` callers.)

- [ ] **Step 3: Edit `di/test_config.py`**

3a. `create_test_settings_registry` (~lines 166/169) — drop the `SettingMode.EXPLICIT` arg:

```python
            if registry.has_definition(name):
                registry.set_global(name, value, tier="global")
            else:
                registry.define(name, value, type_=_py_to_itype.get(type(value), STRING))
                registry.set_global(name, value, tier="global")
```

3b. `SettingsTestContext` — rewrite `__exit__`, `set`, delete `set_override`, fix `_save_original`:

```python
    def __exit__(self, exc_type, exc_val, exc_tb):
        for name, original in self._original_values.items():
            if original is None or not original.is_set:
                self.registry.reset_global(name, tier="workspace")
            else:
                self.registry.set_global(name, original.value, tier="workspace")
        return False

    def set(self, name: str, value: Any) -> None:
        """Set a setting value."""
        self._save_original(name)
        self.registry.set_global(name, value)

    def reset(self, name: str) -> None:
        """Reset a setting to unset."""
        self._save_original(name)
        self.registry.reset_global(name)

    def _save_original(self, name: str) -> None:
        if name not in self._original_values:
            sv = self.registry.get_global(name)
            self._original_values[name] = (
                SettingValue(is_set=sv.is_set, value=sv.value) if sv else None
            )
```

Delete the `set_override` method entirely. Remove `SettingMode` from the imports at the top of `test_config.py` (line ~16). Keep `SettingValue` imported.

3c. `grep -rn "set_override\|SettingMode" packages barn tests` — there must be ZERO production hits after this task (only the to-be-deleted-in-Task-7 `enums.py` definition, the new `test_tier_collapse.py` `test_no_mode_attribute`/removed-symbol guard, and any ADR text). If a test outside this plan calls `set_override`, fix it to a plain `set` (an OVERRIDE no longer differs from a set).

- [ ] **Step 4: Run the di + full settings suites**

Run: `uv run pytest packages/haywire-core/src/haywire/core/di/ tests/core/test_settings/ -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/debug/configurator.py packages/haywire-core/src/haywire/core/di/config.py packages/haywire-core/src/haywire/core/di/test_config.py
git commit -m "refactor(settings): drop OVERRIDE from di/debug consumers and test context

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Delete `SettingMode` and purge its exports

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/enums.py`
- Modify: `packages/haywire-core/src/haywire/core/settings/__init__.py`
- Test: `tests/core/test_settings/test_tier_collapse.py`

**Interfaces:**
- Produces: `SettingMode` no longer importable from `haywire.core.settings`.

- [ ] **Step 1: Add the removed-symbol guard test**

Append to `tests/core/test_settings/test_tier_collapse.py`:

```python
class TestSettingModeRemoved:
    def test_settingmode_not_exported(self):
        import haywire.core.settings as s

        assert not hasattr(s, "SettingMode")

    def test_settingmode_enum_gone(self):
        with pytest.raises(ImportError):
            from haywire.core.settings.enums import SettingMode  # noqa: F401
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/core/test_settings/test_tier_collapse.py::TestSettingModeRemoved -v`
Expected: FAIL — `SettingMode` still exists and is exported.

- [ ] **Step 3: Delete the symbol**

3a. `enums.py` — if `SettingMode` is the only thing in the file, replace the whole file with a stub that documents the removal:

```python
# haywire/core/settings/enums.py
"""
Settings enums.

``SettingMode`` (INHERIT/EXPLICIT/OVERRIDE) was removed in the P2 tier
collapse — a tier value is now simply set-or-unset (see
``SettingValue.is_set``). This module is intentionally left empty; remove it
once nothing imports from it.
"""
```

(First run `grep -rn "settings.enums\|from .enums\|from ..settings.enums" packages barn tests` to confirm no remaining importers before leaving the stub. If there genuinely are none across the repo, you may delete the file and remove `from .enums import …` lines instead — but the stub is the safe default since `__init__` may not be the only importer.)

3b. `settings/__init__.py` — remove `from .enums import SettingMode` (line ~23) and `"SettingMode",` from `__all__` (line ~48).

- [ ] **Step 4: Run the guard + full settings + di suites**

Run: `uv run pytest tests/core/test_settings/ packages/haywire-core/src/haywire/core/di/ -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/settings/enums.py packages/haywire-core/src/haywire/core/settings/__init__.py tests/core/test_settings/test_tier_collapse.py
git commit -m "refactor(settings): delete vestigial SettingMode enum and its exports

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Full-suite verification + lint/type gate

**Files:** none (verification task).

- [ ] **Step 1: Full repo grep for stragglers**

```bash
grep -rn "SettingMode\|is_override\|is_inherit\|is_explicit\|global_override\|workspace_override\|set_override\|\.mode == SettingMode\|override = true\|{ override" packages barn tests docs
```

Expected: hits ONLY in (a) `docs/architecture/settings/settings-arch.md` + `docs/reference/glossary.md` (rewritten in Task 8), (b) `test_tier_collapse.py` guard tests, (c) the `enums.py` stub docstring. Any hit in `packages/`/`barn/` runtime code is a miss — fix it.

- [ ] **Step 2: Lint + format**

```bash
uv run ruff check .
uv run ruff format --check .
```

Expected: clean. If format drifts: `uv run ruff format .` then re-stage.

- [ ] **Step 3: Type check (full plan scope)**

```bash
uv run mypy packages/haywire-core/src/
```

Expected: clean.

- [ ] **Step 4: Full test suite**

```bash
uv run pytest -q
```

Expected: all green. (If an unrelated barn/UI test imported `SettingMode` or `set_override`, the Step-1 grep already caught it; fix and re-run.)

- [ ] **Step 5: Commit any fixups**

```bash
git add -A
git commit -m "test(settings): green full suite after tier collapse

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

(Skip the commit if Steps 1–4 produced no changes.)

---

### Task 8: Docs — rewrite settings-arch §1–5 and the glossary entry

**Files:**
- Modify: `docs/architecture/settings/settings-arch.md`
- Modify: `docs/reference/glossary.md`

**Interfaces:** none (documentation). Architecture docs the CURRENT solution only; the superseded 6-tier model lives in ADR-A (Task 9).

- [ ] **Step 1: Rewrite `settings-arch.md` §1–5**

- §1 Motivation: drop the "shared lab machine / admin forces #222" claim and the "five claims" framing. The story is now four claims: author default, user global, workspace, per-node local. (The admin-force capability was deliberately removed — point at ADR-A.)
- §2 The picture: keep the global/workspace/local tiers; remove the "force" arrow.
- §3 "How a tier expresses its opinion": replace the `SettingMode` block + the `{override=true}` TOML example with: a tier value is **set or unset**; presence in the tier dict (`SettingValue.is_set`) IS the opinion. No strength axis.
- §4 "The resolution chain": six cases → four. Rewrite the numbered list to: local → workspace-set → global-set → default. Update the frontmatter `scope:` line (it says "six-step resolution chain").
- §5 Worked example: delete the "Admin appends OVERRIDE" step and the `global_override` line; keep the default→global→workspace→local progression.

- [ ] **Step 2: Update the frontmatter scope line**

`settings-arch.md` line ~4 currently reads `... six-step resolution chain, TOML format ...`. Change to `... four-step resolution chain (set-or-unset tiers), TOML format ...`.

- [ ] **Step 3: Rewrite the glossary entries**

In `docs/reference/glossary.md`:
- The **"Three-tier resolution"** entry (line ~254): rewrite the precedence to "local instance value → workspace TOML set → global TOML set → descriptor default" and drop both "override" mentions.
- The two persona Q&A lines (~461, ~466): drop "override wins" / "global TOML override wins" phrasing; describe the collapsed 4-step order. The **mirrors** entry (~250) keeps "per-node override capability" (that's the local-cell override, which survives).

- [ ] **Step 4: Preview build (optional but recommended)**

```bash
uv run mkdocs build --strict 2>&1 | tail -20
```

Expected: no broken-link/warning regressions introduced by the edits.

- [ ] **Step 5: Commit**

```bash
git add docs/architecture/settings/settings-arch.md docs/reference/glossary.md
git commit -m "docs(settings): rewrite arch + glossary for collapsed set-or-unset tiers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: ADR-A — Collapse settings tiers; drop OVERRIDE/SettingMode

**Files:**
- Create: `docs/adr/00NN-collapse-settings-tiers.md` (NN = next number; scan `docs/adr/` at write time).

**Interfaces:** none. This is the FINAL task — written against landed code, citing real file/line evidence (DECISIONS.md §E).

- [ ] **Step 1: Find the next ADR number**

```bash
ls docs/adr/ | grep -E '^[0-9]{4}-' | sort | tail -3
```

Use the next integer.

- [ ] **Step 2: Write the ADR**

Match the structure of an existing ADR (e.g. `docs/adr/0007-widget-unification-basewidget.md`). Content:
- **Status:** Accepted.
- **Context:** the pre-P2 6-case / 2-strength chain (cite the now-deleted `resolve()` cases and the `{override=true,value=…}` TOML form from git history / the superseded settings-arch §4). The OVERRIDE strength existed for "admin forces a value on a shared lab machine."
- **Decision:** collapse to highest-priority-set-wins; drop `OVERRIDE` and `SettingMode`; a tier value is set-or-unset (`SettingValue.is_set`). Cite the landed `resolve()` (4 cases) and `SettingValue.unset()/of()` in `value.py`.
- **Consequences:** lost capability — an admin can no longer force a value that beats per-node overrides; the workspace/global tiers are now "defaults," never "forces." Simpler resolution; the per-node local override always wins over both global tiers. Legacy `{override=true}` TOML tables load as plain set values (forward-compat). Supersedes settings-arch §1–4.
- **Note:** this is P2 of the settings↔DataField unification arc; P3 (TOML→JSON) and P4/P5 build on it.

- [ ] **Step 3: Build docs strict**

```bash
uv run mkdocs build --strict 2>&1 | tail -20
```

Expected: ADR picked up, no warnings.

- [ ] **Step 4: Commit**

```bash
git add docs/adr/00NN-collapse-settings-tiers.md
git commit -m "docs(adr): ADR-A collapse settings tiers, drop OVERRIDE/SettingMode

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 5: Update the roadmap status table**

In `internals/ideas/settings-datafield-unification-ROADMAP.md`, mark P2 **LANDED** with the commit range and this plan's filename, mirroring the P1 row. Commit:

```bash
git add internals/ideas/settings-datafield-unification-ROADMAP.md
git commit -m "docs(roadmap): mark P2 (tier collapse) landed

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review notes (for the executor)

- **Spec coverage (DECISIONS.md §A):** drop OVERRIDE (Tasks 1–3), two tiers + cell??default (Tasks 2/4), reactive "unset tracks / set ignores" (Task 4), ADR-A (Task 9), glossary rewrite (Task 8). ✅
- **`SettingValue` shape:** the dataclass keeps `value`; `mode` → `is_set`. Every construction site uses `unset()`/`of()`. The `to_dict`/`from_dict` change is the seam P3 will switch to JSON — keep it minimal here.
- **The `persistent_setting.__set__` call** `registry.set_global(self._setting_key, value)` is POSITIONAL (key, value) — dropping the `mode` keyword from `set_global` does not touch it. Verify by grep in Task 5 step 2.
- **Order independence:** Tasks 1→6 are strictly ordered (each consumes the prior). Tasks 7 (verify), 8 (docs), 9 (ADR) follow. Do not reorder 1–6.
- **The UI override-chrome** (`render_utils.py` reset button) already keys off `is_locally_set`/`is_mirrored`, NOT `SettingMode` — it needs NO change in P2 (its `.mode` references are `BindingMode`, unrelated). Confirmed in the pre-plan survey; do not edit it.
