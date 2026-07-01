# Settings Canonical Key Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the scattered `_setting_key if _setting_key else name` dual-keying conditional throughout the settings system with a single canonical `storage_key` accessor, with no behaviour change.

**Architecture:** A `setting` descriptor is addressed two ways today: by `_attr_name` (short, always set) when no registry namespace exists, and by `_setting_key` (fully-qualified `namespace.accessor.field`) when a namespacing path has run. Six call sites hand-write the `_setting_key if _setting_key else name` fallback. This plan centralises that fallback into one read-only property, `setting.storage_key`, and routes every local-store key derivation through it. The `_setting_key` empty-string sentinel KEEPS its current meaning ("not namespaced → not registry-eligible") — only the *local-store keying* is unified. This is plan **P1** of a 5-plan arc (canonical-key → tier-collapse → TOML→JSON → single-cell → promotion-as-direction); it is a pure prerequisite refactor and lands as a behavioural no-op.

**Tech Stack:** Python 3, `pytest`, `ruff`, `mypy`. Haywire monorepo (`uv run` for all tooling).

## Global Constraints

- Line length 109 (`ruff`, configured in repo).
- CI runs BOTH `ruff check` and `ruff format --check` — run both locally.
- mypy scope for this plan: `uv run mypy packages/haywire-core/src/`.
- In test files, import `haywire.core.graph.editor` before other haywire modules to avoid circular import errors.
- This plan must not change any observable behaviour. Every existing test must stay green; the new tests assert that the two keying paths produce identical results.
- Do NOT touch the `_setting_key` empty-string sentinel semantics: an empty `_setting_key` still means "this field is not namespaced and must not be registered into the global `SettingsRegistry` definitions." Only local-store key derivation is being unified.

---

## File Structure

| File | Responsibility | Change |
| --- | --- | --- |
| `packages/haywire-core/src/haywire/core/settings/descriptor.py` | The `setting` descriptor. Add `storage_key` property; route `__set__` through it. | Modify |
| `packages/haywire-core/src/haywire/core/settings/settings.py` | The `Settings` container. Route `to_dict`/`from_dict`/`reset`/`is_locally_set`/`_on_field_change` local-store keying through `storage_key`. | Modify |
| `tests/core/test_settings/test_canonical_key.py` | New test file asserting `storage_key` equivalence and that all five container methods key identically across simple/extended mode. | Create |

**Out of scope (later plans):** removing the `_registry is None` dual-mode (P4), `SettingMode`/OVERRIDE (P2), TOML→JSON (P3). Do not remove any `_registry is None` branch in this plan.

---

### Task 1: Add the `storage_key` property to `setting`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/descriptor.py` (add property near the other `@property` accessors, after `resolved_widget_config` ~line 298)
- Test: `tests/core/test_settings/test_canonical_key.py`

**Interfaces:**
- Consumes: `setting._setting_key` (str, `""` when not namespaced), `setting._attr_name` (str, set by `__set_name__`).
- Produces: `setting.storage_key` → `str`. Returns `_setting_key` when non-empty, else `_attr_name`. This is THE canonical local-store key, used by every container method in Task 2.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_settings/test_canonical_key.py`:

```python
# Import order guard (see Global Constraints)
import haywire.core.graph.editor  # noqa: F401

from haywire.barn.builtin.types import FLOAT
from haywire.core.settings import NodeSettings, setting


def _descriptor_for(bag_cls: type, field: str) -> setting:
    """Pull the class-level descriptor object for a field off a Settings subclass."""
    return bag_cls.__dict__[field]


def test_storage_key_falls_back_to_attr_name_when_not_namespaced():
    class plain(NodeSettings):
        strength = setting[FLOAT](0.5)

    desc = _descriptor_for(plain, "strength")
    # No @node has run → _setting_key is empty → storage_key is the attr name.
    assert desc._setting_key == ""
    assert desc._attr_name == "strength"
    assert desc.storage_key == "strength"


def test_storage_key_uses_setting_key_when_namespaced():
    class plain(NodeSettings):
        strength = setting[FLOAT](0.5)

    desc = _descriptor_for(plain, "strength")
    # Simulate a namespacing path assigning the fully-qualified key.
    desc._setting_key = "pkg.node.plain.strength"
    assert desc.storage_key == "pkg.node.plain.strength"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_settings/test_canonical_key.py -v`
Expected: FAIL — `AttributeError: 'setting' object has no attribute 'storage_key'`

- [ ] **Step 3: Write minimal implementation**

In `descriptor.py`, add this property to the `setting` class (place it directly after the `resolved_widget_config` property, before the `__get__` overloads):

```python
    @property
    def storage_key(self) -> str:
        """Canonical key for this field in a ``Settings`` instance's ``_local_store``.

        The fully-qualified ``_setting_key`` (``namespace.accessor.field``) once a
        namespacing path (@node / @settings / schema __init_subclass__) has run,
        otherwise the short ``_attr_name`` set by ``__set_name__``. This single
        accessor replaces the ``_setting_key if _setting_key else name`` fallback
        that was previously hand-written at every local-store call site.

        NOTE: this does NOT change the meaning of an empty ``_setting_key`` — that
        still signals "not namespaced, not registry-eligible" to SettingsRegistry.
        Only local-store keying is unified here.
        """
        return self._setting_key or self._attr_name
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_settings/test_canonical_key.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/settings/descriptor.py tests/core/test_settings/test_canonical_key.py
git commit -m "feat(settings): add setting.storage_key canonical-key accessor

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Route `setting.__set__` through `storage_key`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/descriptor.py:345` (the `key = self._setting_key if self._setting_key else self._attr_name` line inside `setting.__set__`)
- Test: `tests/core/test_settings/test_canonical_key.py`

**Interfaces:**
- Consumes: `setting.storage_key` (from Task 1).
- Produces: no new symbols. `setting.__set__` now writes `obj._local_store[self.storage_key]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/core/test_settings/test_canonical_key.py`:

```python
def test_set_writes_under_storage_key_simple_mode():
    class plain(NodeSettings):
        strength = setting[FLOAT](0.5)

    bag = plain()  # no registry → simple mode → storage_key == attr name
    bag.strength = 0.9
    desc = _descriptor_for(plain, "strength")
    # The write must land under the canonical storage_key.
    assert desc.storage_key == "strength"
    assert bag._local_store["strength"] == 0.9
```

- [ ] **Step 2: Run test to verify it fails (or passes trivially) — confirm baseline**

Run: `uv run pytest tests/core/test_settings/test_canonical_key.py::test_set_writes_under_storage_key_simple_mode -v`
Expected: PASS already (the old conditional yields the same key in simple mode). This test pins behaviour BEFORE the refactor so Step 4 proves no regression. If it does not pass, stop — the baseline is wrong.

- [ ] **Step 3: Apply the refactor**

In `descriptor.py`, inside `setting.__set__`, replace:

```python
        key = self._setting_key if self._setting_key else self._attr_name
        obj._local_store[key] = value
```

with:

```python
        obj._local_store[self.storage_key] = value
```

- [ ] **Step 4: Run test to verify it still passes**

Run: `uv run pytest tests/core/test_settings/test_canonical_key.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/settings/descriptor.py tests/core/test_settings/test_canonical_key.py
git commit -m "refactor(settings): route setting.__set__ through storage_key

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Route the five `Settings` container methods through `storage_key`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/settings.py` at lines `137` (`_on_field_change`), `201` (`to_dict`), `233` (`from_dict`), `248` (`reset`), `279` (`is_locally_set`)
- Test: `tests/core/test_settings/test_canonical_key.py`

**Interfaces:**
- Consumes: `setting.storage_key` (Task 1).
- Produces: no new symbols. All five methods derive their local-store key via `descriptor.storage_key` instead of the inline conditional.

**Note for the implementer:** all five sites currently read like `key = descriptor._setting_key if descriptor._setting_key else <name-or-attr_name>` (and line 137 reads `field_key = descriptor._setting_key or attr_name`). They are semantically identical to `descriptor.storage_key` because `<name>` IS the attr name in every case (the loop variable is the field's attribute name from `_property_settings()`). Replace each with `descriptor.storage_key`.

- [ ] **Step 1: Write the failing test**

Append to `tests/core/test_settings/test_canonical_key.py`:

```python
def test_container_methods_key_consistently_simple_mode():
    class plain(NodeSettings):
        strength = setting[FLOAT](0.5)

    bag = plain()
    bag.strength = 0.9

    # to_dict surfaces the override under the attr name (public shape unchanged)
    assert bag.to_dict() == {"strength": 0.9}
    # is_locally_set reads the same key the setter wrote
    assert bag.is_locally_set("strength") is True
    # reset removes it
    bag.reset("strength")
    assert bag.is_locally_set("strength") is False
    assert bag.strength == 0.5
    # from_dict restores it
    bag.from_dict({"strength": 0.7})
    assert bag.strength == 0.7
    assert bag.is_locally_set("strength") is True
```

- [ ] **Step 2: Run test to verify the baseline passes**

Run: `uv run pytest tests/core/test_settings/test_canonical_key.py::test_container_methods_key_consistently_simple_mode -v`
Expected: PASS (pins current behaviour before the refactor)

- [ ] **Step 3: Apply the refactor at all five sites**

In `settings.py`:

Line ~137 in `_on_field_change`, replace:

```python
            field_key = descriptor._setting_key or attr_name
```

with:

```python
            field_key = descriptor.storage_key
```

Line ~201 in `to_dict`, replace:

```python
            key = descriptor._setting_key if descriptor._setting_key else name
```

with:

```python
            key = descriptor.storage_key
```

Line ~233 in `from_dict`, replace:

```python
                key = descriptor._setting_key if descriptor._setting_key else attr_name
```

with:

```python
                key = descriptor.storage_key
```

Line ~248 in `reset`, replace:

```python
        key = descriptor._setting_key if descriptor._setting_key else name
```

with:

```python
        key = descriptor.storage_key
```

Line ~279 in `is_locally_set`, replace:

```python
        key = descriptor._setting_key if descriptor._setting_key else name
```

with:

```python
        key = descriptor.storage_key
```

- [ ] **Step 4: Run the new test plus the full settings suite**

Run: `uv run pytest tests/core/test_settings/ -v`
Expected: PASS (all — including `test_settings.py`, `test_persistent_setting.py`, `test_itype_cutover.py`, etc.). These exercise both simple and extended mode; green here proves the refactor is behaviour-preserving across both keying paths.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/settings/settings.py tests/core/test_settings/test_canonical_key.py
git commit -m "refactor(settings): route container methods through storage_key

Replaces the hand-written `_setting_key if _setting_key else name` fallback
in to_dict/from_dict/reset/is_locally_set/_on_field_change with the single
storage_key accessor. No behaviour change.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Verify extended-mode equivalence and lock in the no-op guarantee

**Files:**
- Test: `tests/core/test_settings/test_canonical_key.py`

**Interfaces:**
- Consumes: `FrameworkSettings` from `haywire.core.settings`, `create_test_settings_registry` from `haywire.core.di.test_config` (settings-arch §9.1).
- Produces: no new symbols.

**Note:** Tasks 1–3 tested simple mode (no registry). This task proves the refactor is also a no-op in EXTENDED mode, where `storage_key` returns the fully-qualified key rather than the attr name. A `FrameworkSettings` subclass with `namespace=` is used DELIBERATELY because it is the path that populates `_setting_key` (`schema.py` `__init_subclass__`). `create_test_bag`'s default bag is a plain `Settings` subclass with NO namespace, so its `_setting_key` is empty — it would NOT exercise the full-key branch. Do not use `create_test_bag` here.

- [ ] **Step 1: Write the failing test**

Append to `tests/core/test_settings/test_canonical_key.py`:

```python
from haywire.core.di.test_config import create_test_settings_registry
from haywire.barn.builtin.types import INT
from haywire.core.settings import FrameworkSettings


def test_storage_key_extended_mode_uses_full_key():
    # A FrameworkSettings subclass with namespace= populates _setting_key on its
    # descriptors at class-definition time (schema.py __init_subclass__). This is
    # the EXTENDED-mode keying path where storage_key == the fully-qualified key.
    class _CanonKeyProbe(FrameworkSettings, namespace="test.canonkey"):
        font_size = setting[INT](12, min=8, max=72, label="Font Size")

    registry = create_test_settings_registry()
    bag = _CanonKeyProbe(registry=registry)

    desc = type(bag).__dict__["font_size"]
    # Extended mode: _setting_key is populated, so storage_key is the full key.
    assert desc._setting_key == "test.canonkey.font_size"
    assert desc.storage_key == desc._setting_key

    # A local override must round-trip through the storage_key-routed container
    # methods using the full key, not the attr name.
    bag.font_size = 20
    assert bag.font_size == 20
    assert bag.is_locally_set("font_size") is True
    assert "test.canonkey.font_size" in bag._local_store
    bag.reset("font_size")
    assert bag.is_locally_set("font_size") is False
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest tests/core/test_settings/test_canonical_key.py::test_storage_key_extended_mode_uses_full_key -v`
Expected: PASS — confirms `storage_key` returns the full key in extended mode and the container methods round-trip a local override correctly.

- [ ] **Step 3: Run the full affected suites (regression gate)**

Run: `uv run pytest tests/core/test_settings/ tests/core/node/ -q`
Expected: PASS. `tests/core/node/` exercises real `@node`-wired settings bags (extended mode with `_wire_settings_schemas` having run), the path where `_setting_key` is fully-qualified — the strongest end-to-end check that no keying regressed.

- [ ] **Step 4: Lint + type-check the touched files**

Run:
```bash
uv run ruff check packages/haywire-core/src/haywire/core/settings/ tests/core/test_settings/test_canonical_key.py
uv run ruff format --check packages/haywire-core/src/haywire/core/settings/ tests/core/test_settings/test_canonical_key.py
uv run mypy packages/haywire-core/src/
```
Expected: clean (no new errors vs. the pre-edit baseline). If `ruff format --check` reports drift on your new test file, run `uv run ruff format` on it and re-commit.

- [ ] **Step 5: Commit**

```bash
git add tests/core/test_settings/test_canonical_key.py
git commit -m "test(settings): verify storage_key no-op in extended mode

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage (against DECISIONS.md idea #2 "one canonical key always"):**
- "Assign one canonical key always… used by store, registry, serialization, and promotion alike" → `storage_key` property (Task 1), routed through `__set__` (Task 2) and the five container methods (Task 3). Registry keying is deliberately untouched (it uses `_setting_key` for namespace-eligibility, which must keep the empty sentinel — documented in Global Constraints and Task 1's docstring). Promotion keying is a later plan (P5).
- The idea-doc warning "the conditional is a bug surface (the promotion codec had to dodge `__` in names)" → eliminated by removing all six hand-written conditionals.

**Known boundary (not a gap):** this plan does NOT make `_setting_key` always-non-empty, because four namespacing paths (`node/decorator.py:42`, `decorator.py:112`, `schema.py:96/162`, `registry.py:574/818`) and three registry guards (`registry.py:166/188/242`) rely on the empty sentinel meaning "not namespaced." Unifying those is entangled with the tier model and is explicitly out of scope. `storage_key` achieves the idea's *local-store* unification without disturbing registry semantics.

**Placeholder scan:** none — every step shows exact code and exact commands.

**Type consistency:** `storage_key` returns `str` everywhere; all five replaced sites previously produced `str`. The `_on_field_change` site renamed nothing (`field_key` stays `field_key`). No signature changes.

---

## Execution Handoff

**Plan complete and saved to `internals/superpowers/2026-06-30-settings-canonical-key.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
