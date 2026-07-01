# Settings TOML → JSON Persistence Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the settings registry's TOML persistence with JSON, serializing each tier value through its IType's `to_dict()`/`from_dict()` **at the disk edge**, so complex ITypes (`COLOR`, `VEC2I`, `VEC3F`, …) round-trip losslessly instead of being mangled or silently reset.

**Architecture:** Today the registry stores a raw Python value per tier (`SettingValue.of(value)`) and writes it directly with `toml.dump`. Multi-component ITypes (`Vec2i`, etc.) only survive by accident (they subclass `list`) and lose their type on read, and `COLOR`/`VEC*` `from_dict` is outright broken (returns the type default, discarding the saved value). This plan: (1) fixes the broken `from_dict` overrides on `COLOR` and the six `VEC*` types; (2) swaps the registry's two file paths and I/O from `.toml`/`toml` to `.json`/`json`; (3) serializes a tier value via its **descriptor's `_type`** — `_type(value).to_dict()` on write, `_type.from_dict(raw)` on read — keeping the **in-memory tier value and `resolve()` unchanged** (they still hold/return the live Python value). It is a **hard cutover with no migration**: existing `.toml` files are not read or converted. `ADR-B` records the reversal of the "TOML for hand-editability" choice.

**Tech Stack:** Python 3, `pytest`, `ruff`, `mypy`. Haywire monorepo (`uv run` for all tooling).

## Global Constraints

- Line length 109 (`ruff`, configured in repo).
- CI runs BOTH `ruff check` AND `ruff format --check` — run both locally; they catch disjoint problems.
- mypy scope for this plan: `uv run mypy packages/haywire-core/src/`.
- In test files, import `haywire.core.graph.editor` before other haywire modules to avoid circular import errors.
- Settings tests share a `conftest.py` autouse fixture (`_reset_framework_settings_registry`) that resets `FrameworkSettings._registry`/`_pending_global` between tests. Do NOT remove it; new settings tests inherit it automatically.
- Stay on branch `feat/type-floor-hoist`. Do NOT merge to master between plans. The gate is "committed + green on this branch" (pytest + ruff + ruff format + mypy clean).
- **Reference:** `internals/ideas/settings-datafield-unification-DECISIONS.md` (§D is this plan's authority) and `internals/ideas/settings-datafield-unification-ROADMAP.md` (P3 section). P2 (tier collapse) has landed on this branch and P3 builds on it (`SettingValue` is set-or-unset; there is no `OVERRIDE`/`SettingMode`).

## DELIBERATE DEVIATION from DECISIONS.md §D (read before Task 1)

DECISIONS.md §D says "a tier **stores** the IType's `to_dict` output; `resolve()` returns that **raw serialized form**; the consuming field rehydrates via `from_dict`." This plan deliberately serializes **only at the disk edge** instead: the in-memory tier keeps the live Python value, `resolve()` is unchanged, and `to_dict`/`from_dict` run inside `save_to_json`/`load_from_json`.

**Why:** the field-rehydrates-from-raw-dict step is P4 work (the value moving into a `DataField` cell). Making `resolve()` return raw dicts now would break every reader (`setting.__get__`, the panel widgets, the `persistent_setting.__set__` echo-guard `value == self.__get__(...)`) until P4 lands a rehydration hook — i.e. it would ship a broken state across a plan boundary, which the "green between plans" rule forbids. Disk-edge serialization fixes the real fragility (the format) completely while keeping every commit green; the §D tier-value-form lands in P4 alongside the cell. **`ADR-B` (Task 8) documents the disk-edge contract as P3's actual decision and notes the §D value-form is deferred to P4.**

---

## What is and isn't in scope

| In scope | Out of scope (later plan / untouched) |
| --- | --- |
| Fix `from_dict` on `COLOR` + 6 `VEC*` types (Task 1) | Any change to `resolve()`'s return value or `setting.__get__` (P4) |
| `registry.py` file paths `.toml`→`.json`, `toml`→`json` (Tasks 2–4) | `_local_store`→`DataField` cell collapse (P4) |
| Serialize tier values via descriptor `_type` at the disk edge (Tasks 3–4) | Promotion / ports (P5) |
| `di/config.py` + `test_config.py` path constants `.toml`→`.json` (Task 5) | The marketplace `_global_path()` in `barn/haybale-marketplace/` — **unrelated concept, do NOT touch** |
| Rename public methods `load_from_toml`/`save_to_toml*`→`*_json` + all callers (Task 6) | `save_to_toml_debounced`'s debounce/threading mechanics (keep as-is, only rename) |
| Hard-cutover ship notice + ADR-B + docs (Tasks 7–8) | TOML backward-read / migration (explicitly NOT done — §D) |

**The ~6 registry I/O sites (grep by symbol; line numbers may have drifted):**
- `import toml` (top of `registry.py`)
- `load_from_toml` (the public loader; sets `_global_path`/`_workspace_path`)
- `_reload_from_file` (`toml.load`)
- `_repopulate_from_toml_for_keys` (`toml.load`)
- `save_to_toml` (`toml.dump`) + `save_to_toml_debounced`
- the `~/.haywire/settings.toml` / `<ws>/.haywire/settings.toml` path strings in docstrings + `di/config.py`/`test_config.py`

---

## Pre-edit baseline (run once before Task 1)

```sh
uv run ruff check packages/haywire-core/src/haywire/core/settings packages/haywire-core/src/haywire/core/di packages/haywire-core/src/haywire/barn/builtin/types
uv run mypy packages/haywire-core/src/
uv run pytest tests/core/test_settings/ packages/haywire-core/src/haywire/core/di/ tests/core/test_types/ -q
```

Expected: all clean. If anything fails here, STOP and surface it — it is pre-existing.

---

### Task 1: Fix `from_dict` on `COLOR` and the six `VEC*` ITypes

The base `PrimitiveType.from_dict` is a stub that returns `class_identity.default` and discards the supplied data (`packages/haywire-core/src/haywire/core/types/base.py:128-152`). `INT`/`FLOAT`/`STRING`/`BOOL` override it (`barn/builtin/types/specs.py`); `COLOR` (`color.py`) and all `VEC*` (`vectors.py`) do **not**, so they silently reset to the type default on `from_dict`. The JSON cutover routes tier reads through `from_dict`, so these must round-trip first or the cutover regresses exactly the types it exists to support.

**Files:**
- Modify: `packages/haywire-core/src/haywire/barn/builtin/types/color.py`
- Modify: `packages/haywire-core/src/haywire/barn/builtin/types/vectors.py`
- Test: `tests/core/test_types/test_itype_roundtrip.py` (Create)

**Interfaces:**
- Produces: `COLOR.from_dict({"value": "#abc"}) -> "#abc"` (a `str`); `VEC2I.from_dict({"value": [1,2]}) -> Vec2i([1,2])` (and the 3/4-component, int/float variants). `to_dict()` shape stays `{"value": <jsonable>}`.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_types/test_itype_roundtrip.py`:

```python
# tests/core/test_types/test_itype_roundtrip.py
"""IType to_dict/from_dict must round-trip the actual value (P3 prerequisite).

The base PrimitiveType.from_dict stub returns the type default; COLOR and the
VEC* types relied on it and silently dropped their value. The JSON settings
cutover routes tier reads through from_dict, so these must round-trip.
"""

import haywire.core.graph.editor  # noqa: F401  (circular-import guard, per CLAUDE.md)

import pytest

from haywire.barn.builtin.types import COLOR, VEC2I, VEC3I, VEC4I, VEC2F, VEC3F, VEC4F
from haywire.core.settings.types import Vec2i, Vec3i, Vec4i, Vec2f, Vec3f, Vec4f


def test_color_roundtrips_value():
    assert COLOR.from_dict(COLOR("#abcdef").to_dict()) == "#abcdef"


@pytest.mark.parametrize(
    "itype, raw",
    [
        (VEC2I, Vec2i([1, 2])),
        (VEC3I, Vec3i([1, 2, 3])),
        (VEC4I, Vec4i([1, 2, 3, 4])),
        (VEC2F, Vec2f([1.5, 2.5])),
        (VEC3F, Vec3f([1.5, 2.5, 3.5])),
        (VEC4F, Vec4f([1.5, 2.5, 3.5, 4.5])),
    ],
)
def test_vec_roundtrips_value(itype, raw):
    restored = itype.from_dict(itype(raw).to_dict())
    assert list(restored) == list(raw)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_types/test_itype_roundtrip.py -v`
Expected: FAIL — `COLOR.from_dict` returns `"#ffffff"`; `VEC*.from_dict` returns the zero vector.

- [ ] **Step 3: Add `from_dict`/`to_dict` overrides to `COLOR`**

In `packages/haywire-core/src/haywire/barn/builtin/types/color.py`, give the `COLOR` class an explicit body (mirroring `STRING` in `specs.py`):

```python
class COLOR(PrimitiveType[ColorStr]):
    """Color data type."""

    def to_dict(self) -> dict:
        return {"value": str(self._value)}

    @classmethod
    def from_dict(cls, data: dict) -> str:
        return str(data.get("value", "#ffffff"))
```

- [ ] **Step 4: Add a `from_dict`/`to_dict` mixin to the `VEC*` types**

In `packages/haywire-core/src/haywire/barn/builtin/types/vectors.py`, add a small helper and give each `VEC*` class an explicit body. The value is a `Vec_` (a `list` subclass), so `to_dict` stores a plain list and `from_dict` rebuilds the right `Vec_` subclass. Add near the top (after the existing imports):

```python
from typing import ClassVar


class _VecSerialize:
    """Mixin: to_dict stores a plain list; from_dict rebuilds the Vec_ subclass.

    ``_vec_cls`` is the framework Vec_ list-subclass this IType wraps.
    """

    _vec_cls: ClassVar[type]

    def to_dict(self) -> dict:
        return {"value": list(self._value)}  # type: ignore[attr-defined]

    @classmethod
    def from_dict(cls, data: dict):
        return cls._vec_cls(data.get("value", []))
```

Then set `_vec_cls` and inherit the mixin on each class, e.g.:

```python
class VEC2I(_VecSerialize, PrimitiveType[Vec2i]):
    """2D integer vector."""

    _vec_cls = Vec2i
```

Apply the same to `VEC3I` (`_vec_cls = Vec3i`), `VEC4I` (`Vec4i`), `VEC2F` (`Vec2f`), `VEC3F` (`Vec3f`), `VEC4F` (`Vec4f`). Keep each `@type_decorator(...)` block exactly as-is; only the base list and the `_vec_cls` line change.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/core/test_types/test_itype_roundtrip.py -v`
Expected: PASS (7 cases).

- [ ] **Step 6: Lint + type-check the touched types, then commit**

```sh
uv run ruff check packages/haywire-core/src/haywire/barn/builtin/types/ tests/core/test_types/test_itype_roundtrip.py
uv run ruff format packages/haywire-core/src/haywire/barn/builtin/types/ tests/core/test_types/test_itype_roundtrip.py
uv run mypy packages/haywire-core/src/haywire/barn/builtin/types/
```

Expected: clean.

```bash
git add packages/haywire-core/src/haywire/barn/builtin/types/color.py packages/haywire-core/src/haywire/barn/builtin/types/vectors.py tests/core/test_types/test_itype_roundtrip.py
git commit -m "fix(types): COLOR + VEC* from_dict round-trip their value (P3 prerequisite)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Add the JSON serialize/deserialize helpers to the registry

Introduce two private helpers that convert between a tier's live Python value and its JSON-able form, keyed by the setting's declared IType. They are the single seam every read/write path routes through, so the format choice lives in exactly one place.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/registry.py`
- Test: `tests/core/test_settings/test_json_persistence.py` (Create)

**Interfaces:**
- Produces:
  - `_value_to_jsonable(self, name: str, value: Any) -> Any` — wrap `value` in the definition's `_type` and return `IType(value).to_dict()`; if the key has no definition or the `_type` has no `class_identity` (auto-defined / plain scalar), return `value` unchanged.
  - `_value_from_jsonable(self, name: str, raw: Any) -> Any` — inverse: if `raw` is a `{"value": …}` dict and the definition's `_type` has `from_dict`, return `IType.from_dict(raw)`; else return `raw` unchanged.
- Consumes: `self._definitions[name]._type` (the IType class), `SettingValue` (P2).

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_settings/test_json_persistence.py`:

```python
# tests/core/test_settings/test_json_persistence.py
"""P3: settings persist as JSON; complex ITypes round-trip via to_dict/from_dict."""

import haywire.core.graph.editor  # noqa: F401  (circular-import guard, per CLAUDE.md)

from pathlib import Path

from haywire.barn.builtin.types import COLOR, INT, VEC2I
from haywire.core.settings.registry import SettingsRegistry
from haywire.core.settings.types import Vec2i


class TestJsonableSeam:
    def test_scalar_passthrough(self):
        reg = SettingsRegistry()
        reg.define("ui.threads", 4, type_=INT)
        # INT serializes through its to_dict shape; round-trips back to the int.
        raw = reg._value_to_jsonable("ui.threads", 8)
        assert reg._value_from_jsonable("ui.threads", raw) == 8

    def test_color_roundtrip(self):
        reg = SettingsRegistry()
        reg.define("ui.tint", "#ffffff", type_=COLOR)
        raw = reg._value_to_jsonable("ui.tint", "#abcdef")
        assert reg._value_from_jsonable("ui.tint", raw) == "#abcdef"

    def test_vec_roundtrip(self):
        reg = SettingsRegistry()
        reg.define("ui.offset", Vec2i([0, 0]), type_=VEC2I)
        raw = reg._value_to_jsonable("ui.offset", Vec2i([3, 4]))
        restored = reg._value_from_jsonable("ui.offset", raw)
        assert list(restored) == [3, 4]

    def test_unknown_key_passthrough(self):
        reg = SettingsRegistry()
        # No definition → value passes through untouched (auto-defined TOML keys).
        assert reg._value_to_jsonable("not.defined", 7) == 7
        assert reg._value_from_jsonable("not.defined", 7) == 7
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_settings/test_json_persistence.py::TestJsonableSeam -v`
Expected: FAIL — `_value_to_jsonable` / `_value_from_jsonable` don't exist.

- [ ] **Step 3: Add the helpers to `registry.py`**

Add these two methods to `SettingsRegistry` (place them just above `_effective_value`, in the "Value Access" region):

```python
    def _value_to_jsonable(self, name: str, value: Any) -> Any:
        """Convert a live tier value to its JSON-able form via the IType's to_dict.

        Keyed by the setting's declared ``_type``. Unknown keys (auto-defined
        from a file, no code definition) and ITypes without a ``class_identity``
        pass the value through unchanged — a plain JSON scalar.
        """
        defn = self._definitions.get(name)
        itype = getattr(defn, "_type", None) if defn else None
        if itype is None or not hasattr(itype, "class_identity"):
            return value
        try:
            return itype(value).to_dict()
        except Exception:
            return value

    def _value_from_jsonable(self, name: str, raw: Any) -> Any:
        """Inverse of _value_to_jsonable: rehydrate the live value via from_dict.

        A ``{"value": ...}`` dict from a typed key is run through the IType's
        ``from_dict``; anything else (plain scalar, unknown key) passes through.
        """
        defn = self._definitions.get(name)
        itype = getattr(defn, "_type", None) if defn else None
        if itype is None or not hasattr(itype, "from_dict") or not isinstance(raw, dict):
            return raw
        try:
            return itype.from_dict(raw)
        except Exception:
            return raw
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_settings/test_json_persistence.py::TestJsonableSeam -v`
Expected: PASS (4).

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/settings/registry.py tests/core/test_settings/test_json_persistence.py
git commit -m "feat(settings): add IType-keyed JSON serialize/deserialize seam to registry

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Switch `save_to_toml` → `save_to_json` (write path)

Rename the writer, swap `toml.dump` for `json.dump`, and route each set value through `_value_to_jsonable`. Keep the nested-dict layout (`_set_nested`) and the workspace-only / debounce behaviour. The method rename ripples to callers in Task 6; here keep a thin `save_to_toml` alias is NOT wanted — rename outright and fix the in-file debounce reference.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/registry.py`
- Test: `tests/core/test_settings/test_json_persistence.py`

**Interfaces:**
- Consumes: `_value_to_jsonable` (Task 2), `_set_nested` (unchanged).
- Produces:
  - `save_to_json(self, path: Path | str | None = None) -> None` — writes the workspace tier as nested JSON; values are `to_dict`-form for typed keys.
  - `save_to_json_debounced(self, path: Path | str | None = None) -> None` — same debounce semantics as before; its `threading.Timer` now targets `save_to_json`.
  - `import json` replaces `import toml` (after Task 4 removes the last `toml` use).

- [ ] **Step 1: Write the failing test**

Append to `tests/core/test_settings/test_json_persistence.py`:

```python
class TestSaveJson:
    def test_save_writes_nested_json(self, tmp_path: Path):
        reg = SettingsRegistry()
        reg.define("exec.threads", 4, type_=INT)
        reg.set_global("exec.threads", 16, tier="workspace")
        out = tmp_path / "settings.json"
        reg.save_to_json(out)

        import json

        data = json.loads(out.read_text())
        # INT to_dict shape, nested under exec.threads
        assert data["exec"]["threads"] == {"value": 16}

    def test_save_writes_color_to_dict(self, tmp_path: Path):
        reg = SettingsRegistry()
        reg.define("ui.tint", "#ffffff", type_=COLOR)
        reg.set_global("ui.tint", "#abcdef", tier="workspace")
        out = tmp_path / "settings.json"
        reg.save_to_json(out)

        import json

        data = json.loads(out.read_text())
        assert data["ui"]["tint"] == {"value": "#abcdef"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_settings/test_json_persistence.py::TestSaveJson -v`
Expected: FAIL — `save_to_json` does not exist.

- [ ] **Step 3: Edit `registry.py` write path**

3a. Add `import json` at the top of `registry.py`, directly above `import toml` (leave `import toml` for now — Task 4 removes it once `_reload_from_file`/`_repopulate` no longer use it).

3b. Rename `save_to_toml` → `save_to_json` and rewrite its body:

```python
    def save_to_json(self, path: Path | str | None = None) -> None:
        """
        Save current workspace-tier values to JSON.

        Only the workspace tier is saved — the global tier is hand-edited by the
        user and is never overwritten by the application. Only *set* values are
        written, each as its IType's to_dict-form (see _value_to_jsonable).
        """
        path = Path(path).expanduser().resolve() if path else self._workspace_path
        if not path:
            raise ValueError("No workspace path configured and no path argument provided")

        data: dict[str, Any] = {}

        with self._lock:
            for name, sv in sorted(self._workspace_tier_values.items()):
                if not sv.is_set:
                    continue
                self._set_nested(data, name, self._value_to_jsonable(name, sv.value))

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)

        logger.info(f"Settings saved to {path}")
```

3c. Rename `save_to_toml_debounced` → `save_to_json_debounced` and update its `threading.Timer(... self.save_to_toml ...)` reference to `self.save_to_json`:

```python
    def save_to_json_debounced(self, path: Path | str | None = None) -> None:
        """Schedule a debounced ``save_to_json()`` call. (semantics unchanged)"""
        if path is None and self._workspace_path is None:
            return

        timer = getattr(self, "_save_timer", None)
        if timer is not None:
            timer.cancel()
        self._save_timer = threading.Timer(self._SAVE_DEBOUNCE, self.save_to_json, args=(path,))
        self._save_timer.daemon = True
        self._save_timer.start()
```

- [ ] **Step 4: Run the save tests**

Run: `uv run pytest tests/core/test_settings/test_json_persistence.py::TestSaveJson -v`
Expected: PASS (2).

(`save_to_toml*` callers outside this file are now broken — that is expected; Task 6 fixes them. Do NOT run the full settings suite yet.)

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/settings/registry.py tests/core/test_settings/test_json_persistence.py
git commit -m "feat(settings): save_to_json writes nested JSON via the IType to_dict seam

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Switch the read path `load_from_toml` → `load_from_json`

Rename the loader, swap `toml.load` for `json.load` in both `_reload_from_file` and `_repopulate_from_toml_for_keys`, route each loaded entry through `_value_from_jsonable`, and remove the last `import toml`. The legacy `{override=true}` handling and the `_flatten_toml`/`_process_entry`/`_parse_config_dict` machinery are kept for now (they flatten nested JSON identically) — only the file read and the value-rehydration change.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/registry.py`
- Test: `tests/core/test_settings/test_json_persistence.py`

**Interfaces:**
- Consumes: `_value_from_jsonable` (Task 2), `_flatten_toml`/`_process_entry` (unchanged behaviour — they now receive a dict parsed from JSON).
- Produces:
  - `load_from_json(self, path: Path | str, tier: str = "workspace", watch: bool = False) -> None`.
  - `_reload_from_file` / `_repopulate_from_toml_for_keys` parse JSON (keep their names — they are private; renaming them is churn beyond this plan's seam).
  - No remaining `import toml` / `toml.` reference in `registry.py`.

- [ ] **Step 1: Write the failing test (full round-trip via disk)**

Append to `tests/core/test_settings/test_json_persistence.py`:

```python
class TestLoadJson:
    def test_roundtrip_color_through_disk(self, tmp_path: Path):
        out = tmp_path / "settings.json"

        reg1 = SettingsRegistry()
        reg1.define("ui.tint", "#ffffff", type_=COLOR)
        reg1.set_global("ui.tint", "#abcdef", tier="workspace")
        reg1.save_to_json(out)

        reg2 = SettingsRegistry()
        reg2.define("ui.tint", "#ffffff", type_=COLOR)
        reg2.load_from_json(out, tier="workspace")
        assert reg2.resolve("ui.tint") == ("#abcdef", "workspace")

    def test_roundtrip_vec_through_disk(self, tmp_path: Path):
        out = tmp_path / "settings.json"

        reg1 = SettingsRegistry()
        reg1.define("ui.offset", Vec2i([0, 0]), type_=VEC2I)
        reg1.set_global("ui.offset", Vec2i([3, 4]), tier="workspace")
        reg1.save_to_json(out)

        reg2 = SettingsRegistry()
        reg2.define("ui.offset", Vec2i([0, 0]), type_=VEC2I)
        reg2.load_from_json(out, tier="workspace")
        value, source = reg2.resolve("ui.offset")
        assert list(value) == [3, 4]
        assert source == "workspace"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_settings/test_json_persistence.py::TestLoadJson -v`
Expected: FAIL — `load_from_json` does not exist.

- [ ] **Step 3: Edit `registry.py` read path**

3a. Rename `load_from_toml` → `load_from_json` (signature and body otherwise unchanged; it still sets `_global_path`/`_workspace_path` and calls `_reload_from_file`). Update its docstring `.toml` → `.json`.

3b. In `_reload_from_file`, replace the parse:

```python
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to parse settings file: {e}")
            return
```

and route the value through the rehydration seam — change the `_process_entry` call site so the value is rehydrated. The simplest seam: after `flat = self._flatten_toml(data)`, rehydrate in the loop:

```python
            flat = self._flatten_toml(data)
            for name, entry in flat.items():
                self._process_entry(name, self._rehydrate_entry(name, entry), tier_dict)
```

3c. Apply the identical `json.load` + rehydrate change in `_repopulate_from_toml_for_keys`.

3d. Add the small `_rehydrate_entry` helper next to the seam helpers from Task 2:

```python
    def _rehydrate_entry(self, name: str, entry: Any) -> Any:
        """Rehydrate a flattened JSON entry into the live value for _process_entry.

        ``_process_entry`` expects either a bare scalar or a {"value": …} dict.
        For a typed key whose entry is a {"value": …} dict, run from_dict so the
        tier stores the live Python value (Vec2i, etc.); otherwise pass through.
        """
        if isinstance(entry, dict) and "value" in entry:
            return {"value": self._value_from_jsonable(name, entry)}
        return entry
```

(Rationale: `_process_entry` already unwraps a `{"value": …}` dict via `_parse_config_dict` and stores `SettingValue.of(parsed["value"])`. By replacing the inner `value` with the `from_dict`-rehydrated live value, the tier ends up holding `Vec2i([3,4])` rather than the raw list — `resolve()` stays unchanged and returns the live value, per the disk-edge deviation.)

3e. Remove `import toml` from the top of `registry.py` (confirm with grep — Step 4).

- [ ] **Step 4: Verify no `toml` references remain in registry.py**

Run: `grep -n "toml" packages/haywire-core/src/haywire/core/settings/registry.py`
Expected: hits only in method/helper NAMES that still say `toml` (`_reload_from_file` has none; `_repopulate_from_toml_for_keys`, `_flatten_toml`, `save_to_*` were renamed in Task 3 / kept-private here). There must be **zero** `import toml` and zero `toml.load` / `toml.dump`. If `_repopulate_from_toml_for_keys` / `_flatten_toml` names bother you, leave them — renaming private helpers is out of scope; only the `import` and `toml.` calls must be gone.

- [ ] **Step 5: Run the load tests**

Run: `uv run pytest tests/core/test_settings/test_json_persistence.py -v`
Expected: PASS (all classes).

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/core/settings/registry.py tests/core/test_settings/test_json_persistence.py
git commit -m "feat(settings): load_from_json reads JSON and rehydrates via the IType seam; drop toml import

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Switch default file paths `.toml` → `.json` in DI + test config

The registry now reads/writes JSON; point the default paths at `.json` and fix the `di/config.py` reload path + the test temp-settings path. The `_reload_from_file` calls in `reload_settings` keep working (they parse whatever `_global_path`/`_workspace_path` points to — now `.json`).

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/di/config.py`
- Modify: `packages/haywire-core/src/haywire/core/di/test_config.py`
- Test: existing `packages/haywire-core/src/haywire/core/di/` suite

**Interfaces:**
- Consumes: `load_from_json`/`save_to_json` (Tasks 3–4).

- [ ] **Step 1: Edit `di/config.py`**

1a. Default global path (currently `Path.home() / ".haywire" / "settings.toml"`):

```python
            self.settings_path = Path.home() / ".haywire" / "settings.json"
```

1b. Both `load_from_toml` calls in `provide_settings_registry` → `load_from_json`; the workspace path string `".haywire" / "settings.toml"` → `"settings.json"`:

```python
        registry.load_from_json(self.settings_path, tier="global", watch=self.watch_settings)

        workspace_settings = Path(self.workspace_root) / ".haywire" / "settings.json"
        registry.load_from_json(workspace_settings, tier="workspace", watch=self.watch_settings)
```

1c. `save_settings` (`registry.save_to_toml()`) → `registry.save_to_json()`.

1d. The docstring lines mentioning `~/.haywire/settings.toml` (init order comment, `settings_path` param docs at the two call-doc spots) → `.json`.

(`_reload_from_file(registry._global_path, ...)` in `reload_settings` is unchanged — it now parses JSON since the paths are `.json`.)

- [ ] **Step 2: Edit `test_config.py`**

The temp-settings path:

```python
        settings_path = str(Path(temp_dir) / "settings.json")
```

- [ ] **Step 3: Run the di + settings suites**

Run: `uv run pytest packages/haywire-core/src/haywire/core/di/ tests/core/test_settings/ -q`
Expected: still has failures from the not-yet-renamed callers in Task 6 IF any di test calls `save_to_toml`/`load_from_toml` — check the failure list. The di config itself should import and run. If the ONLY failures are `AttributeError: 'SettingsRegistry' object has no attribute 'save_to_toml'/'load_from_toml'` in tests, that is expected and fixed in Task 6.

- [ ] **Step 4: Commit**

```bash
git add packages/haywire-core/src/haywire/core/di/config.py packages/haywire-core/src/haywire/core/di/test_config.py
git commit -m "refactor(settings): point default settings paths at .json; di uses load/save_to_json

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Rename remaining callers (`descriptor`, `render_utils`, tests)

The public method rename ripples to every caller. Grep the repo and fix each. The persistent-setting write path (`descriptor.py`) is the most important — it is the live write seam.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/descriptor.py`
- Modify: `packages/haywire-core/src/haywire/ui/panel/render_utils.py`
- Modify: `tests/core/test_settings/test_schema_rebasing.py`
- Modify: `tests/core/test_settings/test_schema_reregister_repopulate.py`
- Modify: `tests/core/test_settings/test_persistent_setting.py`
- Modify: `tests/core/test_settings/test_settings_file_watcher.py`
- Modify: any other hit from the grep below.

**Interfaces:**
- Consumes: `load_from_json`/`save_to_json`/`save_to_json_debounced`.

- [ ] **Step 1: Find every caller**

Run:
```sh
grep -rn "load_from_toml\|save_to_toml" packages barn tests
```
Expected hits: `descriptor.py` (`save_to_toml_debounced()` in `persistent_setting.__set__` + 2 docstrings), `render_utils.py` (`save_to_toml_debounced()`), and the test files listed above. **No hit should remain in `registry.py`** (renamed in Tasks 3–4).

- [ ] **Step 2: Rename each call site**

- `descriptor.py`: `registry.save_to_toml_debounced()` → `registry.save_to_json_debounced()`. Update the two docstrings that say `.haywire/settings.toml` / `save_to_toml_debounced` to `.json` / `save_to_json_debounced`.
- `render_utils.py`: `registry.save_to_toml_debounced()` → `registry.save_to_json_debounced()`.
- In each test file: `registry.load_from_toml(` → `registry.load_from_json(`. The local `tmp_path / "settings.toml"` fixture filenames may stay `.toml` (they are arbitrary tmp names) OR be renamed to `.json` for clarity — rename them to `.json` to avoid confusing future readers, since the loader now parses JSON. The fixtures that `write_text('[section]\n...')` TOML literals must be rewritten as JSON (see Step 3).
- **`test_schema_rebasing.py` is special:** its one TOML test (a) guards on `importlib.util.find_spec("toml")` and skips if toml is absent, and (b) writes a `NamedTemporaryFile(suffix=".toml")` with `"[auto]\nval = 123\n"` to prove auto-define from a bare scalar. Remove the `import toml` and the `find_spec("toml")` skip guard, change `suffix=".toml"` → `suffix=".json"`, write `'{"auto": {"val": 123}}'` instead of the TOML literal, and call `load_from_json`. The assertions (`auto.val` auto-defined, `_default == 123`) are unchanged — auto-define from a bare JSON scalar exercises the same `_process_entry` path.

- [ ] **Step 3: Convert TOML-literal fixtures to JSON**

`test_schema_reregister_repopulate.py` and `test_schema_rebasing.py` write TOML literals (e.g. `path.write_text('[testlib]\nlast_name = "my-session"\n')`). The loader now parses JSON, so these must become JSON. Convert each:

```python
# was: path.write_text('[testlib]\nlast_name = "my-session"\n')
import json
path.write_text(json.dumps({"testlib": {"last_name": "my-session"}}))
```

Apply to every `write_text(<toml literal>)` in those two files (global.toml `[testlib] last_name = "from-global"`, the `[alpha]/[beta]` workspace fixtures, the `[alpha]/[beta]/[gamma]` repopulate fixture). The `bad.toml` "unparseable" fixture in `test_repopulate` can stay arbitrary garbage — it must still fail to parse as JSON (it does: `not = valid = toml` is invalid JSON), but rename the variable/file to `bad.json` and keep asserting the error path.

- [ ] **Step 4: Run the full settings + di suites**

Run: `uv run pytest tests/core/test_settings/ packages/haywire-core/src/haywire/core/di/ -q`
Expected: PASS (all green).

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/settings/descriptor.py packages/haywire-core/src/haywire/ui/panel/render_utils.py tests/core/test_settings/
git commit -m "refactor(settings): rename load/save_to_toml callers to *_json; JSON test fixtures

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Full-suite verification + hard-cutover ship notice

**Files:**
- Modify: `CHANGELOG.md` (or the repo's release-notes file — find it in Step 2)

- [ ] **Step 1: Repo-wide straggler grep**

```sh
grep -rn "save_to_toml\|load_from_toml\|import toml\|settings\.toml" packages barn tests
```

Expected: ZERO hits in runtime code (`packages/`, `barn/`). Allowed leftovers: none in `registry.py`; the private helper names `_repopulate_from_toml_for_keys` / `_flatten_toml` (kept) contain the substring "toml" but are not calls — they will match `_..._toml...`; that is acceptable (private helper names, no behaviour). Any `import toml` or `*.settings.toml` path is a miss — fix it. (The marketplace `_global_path()` in `barn/haybale-marketplace/` is unrelated and will NOT match these patterns.)

- [ ] **Step 2: Add the hard-cutover ship notice**

This is a **no-migration breaking change** (DECISIONS.md §D): existing `~/.haywire/settings.toml` and `<ws>/.haywire/settings.toml` are silently ignored; users lose hand-edited settings unless they re-enter them. Surface it. Find the changelog:

```sh
ls CHANGELOG.md docs/changelog.md docs/CHANGELOG.md 2>/dev/null
```

Add an entry under the unreleased/next section, e.g.:

```markdown
### Breaking
- **Settings now persist as JSON** (`~/.haywire/settings.json`, `<workspace>/.haywire/settings.json`).
  The old `.toml` files are **not** read or migrated — re-enter any hand-edited global settings.
  Complex setting types (colors, vectors) now round-trip losslessly. See ADR 0012.
```

If no changelog file exists, note it in the ADR (Task 8) Consequences instead and skip this step.

- [ ] **Step 3: Lint + format + type + full suite**

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/
uv run pytest -q
```

Expected: all clean / all green.

- [ ] **Step 4: Commit any fixups**

```bash
git add -A
git commit -m "docs(settings): note JSON hard-cutover; green full suite

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

(Skip if Steps 1–3 produced no changes.)

---

### Task 8: Docs — settings-arch persistence section + ADR-B

**Files:**
- Modify: `docs/architecture/settings/settings-arch.md`
- Create: `docs/adr/0012-settings-json-persistence.md` (confirm next number at write time)

- [ ] **Step 1: Update `settings-arch.md`**

- Frontmatter `scope:` line: `TOML format` → `JSON format`.
- The module/tier prose and any `[ui.node] bg_color = "#f0f0f0"` TOML example → the JSON shape:

```json
{ "ui": { "node": { "bg_color": { "value": "#f0f0f0" } } } }
```

- The §6.3 write-path note (`save_to_toml_debounced`) and §8.1 API examples (`load_from_toml`/`save_to_toml`) → the `*_json` names.
- Note the disk-edge serialization contract: tiers hold live values; `to_dict`/`from_dict` run at load/save; complex ITypes round-trip. Point at ADR 0012.

- [ ] **Step 2: Find the next ADR number**

```sh
ls docs/adr/ | grep -E '^[0-9]{4}-' | sort | tail -3
```

Use the next integer (expected `0012`, since `0011` is P2's ADR).

- [ ] **Step 3: Write ADR-B**

Match the prose style of `docs/adr/0011-collapse-settings-tiers.md`. Content:
- **Status:** Accepted.
- **Context:** TOML was chosen for hand-editability; but `LibrarySettings` already declares `setting[COLOR]`/`setting[VEC2I]`/`setting[VEC3F]` and the registry wrote `sv.value` raw via `toml.dump` — `Vec_` survived only as a bare list and lost its type on read; `COLOR`/`VEC*` `from_dict` was the unoverridden base stub that discarded the value entirely (cite `types/base.py:128` and the pre-fix `color.py`/`vectors.py`). The format change is real, not cosmetic.
- **Decision:** persist both tiers as JSON (`settings.json`); serialize each tier value through its IType's `to_dict`/`from_dict` **at the disk edge** (cite `registry.py` `save_to_json`/`load_from_json` + `_value_to_jsonable`/`_value_from_jsonable`). Fix `from_dict` on `COLOR` + `VEC*`. **Hard cutover, no migration** — old `.toml` ignored.
- **Deliberate scoping vs DECISIONS.md §D:** §D specifies the *tier* stores the `to_dict` form and `resolve()` returns the raw dict; this ADR serializes at the disk edge instead (in-memory tier + `resolve()` keep live values) so every commit stays green. The §D tier-value-form lands in P4 with the `DataField` cell + field rehydration. Record this explicitly.
- **Consequences:** lossless complex types; one serialization contract (same `to_dict`/`from_dict` as graph JSON); users lose un-migrated hand-edited `.toml` (ship notice); supersedes the "TOML for hand-editability" choice in settings-arch.
- **Note:** P3 of the settings↔DataField arc; P4/P5 build on it.

- [ ] **Step 4: Build docs strict**

```sh
uv run mkdocs build --strict 2>&1 | tail -20
```

Expected: ADR picked up; **no NEW** warnings vs the pre-edit baseline (the repo has ~58 pre-existing strict warnings in `archive/`, `components/states`, `haybale/`, glossary `signals/*.py` — those are not yours; confirm your edited files add none, e.g. your ADR link from settings-arch resolves).

- [ ] **Step 5: Commit**

```bash
git add docs/architecture/settings/settings-arch.md docs/adr/0012-settings-json-persistence.md
git commit -m "docs(adr): ADR 0012 settings JSON persistence; arch persistence section

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 6: Mark P3 landed in the roadmap**

In `internals/ideas/settings-datafield-unification-ROADMAP.md`, mark the P3 row **LANDED** with the commit range and this plan's filename (mirror the P1/P2 rows), and add a `[LANDED]` marker + one-line summary to the `## P3` section header (mirroring P2). Note the disk-edge deviation and that the §D tier-value-form is deferred to P4. Commit:

```bash
git add internals/ideas/settings-datafield-unification-ROADMAP.md
git commit -m "docs(roadmap): mark P3 (TOML→JSON cutover) landed

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review notes (for the executor)

- **Spec coverage (DECISIONS.md §D):** both tiers JSON (Tasks 3–5), tier value via IType to_dict/from_dict (Tasks 2–4, at the disk edge — deviation documented), OVERRIDE/SettingMode already gone (P2 — nothing to do), hard cutover + ship notice (Task 7), ADR-B (Task 8). ✅
- **The §D deviation is the one judgment call** — disk-edge vs tier-stored serialization. It is documented in the plan header, Task 4's rationale, and ADR-B. If a reviewer insists on literal §D, that work belongs in P4 (it needs the cell + the `_resolve` rehydration hook), not here.
- **Prerequisite bug (Task 1):** the JSON cutover would regress `COLOR`/`VEC*` (their `from_dict` is the broken base stub) — Task 1 fixes them FIRST, with its own round-trip test, before any registry change depends on `from_dict`.
- **Method renames ripple:** `save_to_toml`→`save_to_json`, `save_to_toml_debounced`→`save_to_json_debounced`, `load_from_toml`→`load_from_json`. Callers: `descriptor.py` (live write seam), `render_utils.py` (panel setter), `di/config.py` (boot + reload + save_settings), ~5 test files. Task 6's grep is the safety net; Task 7's grep is the final guard.
- **Do NOT touch:** `barn/haybale-marketplace/.../_global_path()` (unrelated marketplace concept), `resolve()`/`setting.__get__`/`_local_store` (P4), promotion (P5), the private helper names `_reload_from_file`/`_repopulate_from_toml_for_keys`/`_flatten_toml` (renaming is churn — only their `toml.load`→`json.load` bodies change).
- **Order:** Tasks 1→6 are strictly ordered (each consumes the prior; the suite is intentionally red between Tasks 3 and 6 because the rename is mid-flight). Tasks 7 (verify), 8 (docs/ADR/roadmap) follow. Tasks 3–4 only run the scoped `test_json_persistence.py`; the full settings suite is first run green at Task 6 Step 4.
```
