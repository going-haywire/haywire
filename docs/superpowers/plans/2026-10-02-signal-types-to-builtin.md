# EXEC and CALLBACK into builtin (edge-kinds step 5, plan P) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `EXEC` and `CALLBACK` are builtin types (`haywire-core:type:EXEC`, `haywire-core:type:CALLBACK`), every importer in this repo and in haybale-visiongraph imports them from `haywire.barn.builtin.types`, and every saved graph in both repos names the new keys.

**Architecture:** The two classes move from `barn/haybale-core/haybale_core/types/specs.py` into the builtin types package, each in **its own module** — `exec.py` and `callback.py`, beside `fold.py` and `optional.py`, which are also one-type modules. `CALLBACK` subclasses `STRING`, so `callback.py` imports it from `.specs` the way `fold.py` imports `BOOL`. Their registry key follows from the library they belong to, not the module file, so the move changes the key but the split does not. There is no key alias and no re-export: a one-off script rewrites the saved graphs that hold the old keys, and the old import path stops working. The script and its tests are **deleted again in Task 5** once the rewrite has landed — they are a one-off, and keeping them would imply the old keys are still a thing. One lookup changes behaviour on the way: `TypeRegistry.get_type_for_python_type` prefers `haywire-core:` types, so after the move `EXEC` (a `PrimitiveType[dict]`) would win `dict` over haybale-core's `DICT`. It is fixed first.

**Tech Stack:** Python 3.12, pytest (+ xdist), uv, ruff, mypy. No UI or JS changes.

**Settled in:** the edge-kinds step 5 inquisition, decision Q6b (move before step 5, its own plan), and this plan's two questions on 2026-10-02: P-Q1 C (no alias, rewrite the files), P-Q2 A (update every importer, no re-export, visiongraph included). Two amendments on 2026-10-02 at the user's request: `EXEC` and `CALLBACK` get one module each rather than joining `specs.py`, and the migration script plus its tests are removed once they have done their job. Design context: [2026-10-02-wire-types.md](2026-10-02-wire-types.md) §P. Origin: [2026-09-24-new-node-wizard.md](2026-09-24-new-node-wizard.md), decision 8 and follow-on 2.

## Global Constraints

- Two git repos. This repo: `/Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo`. haybale-visiongraph: `/Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph`, linked into this repo as the symlink `barn/haybale-visiongraph`. Edit visiongraph files through the symlink path, run git for them in the visiongraph repo.
- Work on branch `signal-types-to-builtin` in both repos. Both are on `master` now: create the branch with `git switch -c signal-types-to-builtin` before the first commit in each. Never push; the user pushes.
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Uncommitted user changes exist and must not be committed by this plan: `graphs/oakNwebCam.haywire` in this repo and `uv.lock` in visiongraph. Task 3 rewrites `oakNwebCam.haywire`; it stops and asks the user first (Task 3, Step 1).
- Decisions to honour: no `TypeRegistry` key alias, no re-export from `haybale_core.types`, every importer updated in both repos. The Control, Event and Output node templates are out of scope; they stay with the new node wizard's follow-on.
- Out of scope: wire types (step 5.1). Do not touch `FlowType` beyond what Task 1 states.
- Docstrings and comments follow `.claude/rules/python-docs.md`. The class docstrings of `EXEC` and `CALLBACK` are displayed docstrings (registered components): Markdown, single backticks, no reST.
- "Ruff check" means both `uv run ruff check <path>` and `uv run ruff format --check <path>`; line length 109.
- Commit every change under `barn/haybale-testing/` before running the full suite: `tests/studio/test_docs/test_generate.py` runs `git checkout -- barn/haybale-testing` in its teardown.
- Pre-commit gate: `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"`, then `grep -E "^FAILED|^ERROR" /tmp/t.log`. Use a timeout of at least 600000 ms.
- A failing test outside the files a task names: stop and report it by name.

---

## File Structure

| File | Change |
|---|---|
| `packages/haywire-core/src/haywire/core/types/registry.py` | `get_type_for_python_type` considers value types only (Task 1) |
| `tests/core/test_types/test_type_for_python_type.py` | new: unit and integration tests for that lookup (Task 1) |
| `packages/haywire-core/src/haywire/barn/builtin/types/exec.py` | new: holds `EXEC` (Task 2) |
| `packages/haywire-core/src/haywire/barn/builtin/types/callback.py` | new: holds `CALLBACK` (Task 2) |
| `packages/haywire-core/src/haywire/barn/builtin/types/__init__.py` | exports them (Task 2) |
| `packages/haywire-core/src/haywire/barn/builtin/__init__.py` | module docstring names the real key prefix (Task 2) |
| `barn/haybale-core/haybale_core/types/specs.py` | loses `EXEC`, `CALLBACK` and the imports only they used (Task 2) |
| `barn/haybale-core/haybale_core/types/__init__.py` | stops exporting them (Task 2) |
| 20 node modules in `barn/`, 7 in visiongraph, 10 test modules | import from builtin (Task 2) |
| `tests/barn/test_signal_types.py` | reads the types from builtin, plus two new tests (Task 2) |
| `scripts/migrate_signal_type_keys.py` | new: rewrites saved graphs (Task 3), deleted again (Task 5) |
| `tests/scripts/test_migrate_signal_type_keys.py` | new (Task 3), deleted again (Task 5) |
| 13 files in `graphs/`, `barn/haybale-example/haybale_example/macros/NewMacroGroup.hwm`, visiongraph `graphs/webcam.haywire` | old keys rewritten (Task 3) |
| generated docs (`QUICKREF.md`, `OVERVIEW.md`, `docs/*.md`) of builtin, haybale-core, haybale-example, haybale-testing | regenerated (Task 4) |
| `tests/core/test_libraries/test_registry_remove_library.py`, `.insights/project_slow_test_outliers.md`, `tests/conftest.py` | stale explanations naming `EXEC`'s old home or an old key format (Task 4) |
| `docs/superpowers/plans/2026-09-24-new-node-wizard.md`, `docs/superpowers/plans/2026-09-28-edge-kinds.md` | status (Task 5) |

---

### Task 1: The Python-type lookup ignores signal types

`TypeRegistry.get_type_for_python_type(py_type)` returns the registered type whose `element_type_cls` is `py_type`, preferring a `haywire-core:` key. The settings registry uses it to give a TOML-defined setting its type (`SettingsRegistry._resolve_itype_for_python_type`, `packages/haywire-core/src/haywire/core/settings/registry.py:578-597`). Measured on 2026-10-02 with the full library system: `dict` resolves to `haybale-core:type:DICT` and `str` to `haywire-core:type:STRING`, both only because they register first. The `dict` candidates are `DICT` and `EXEC`, so once `EXEC` is `haywire-core:` the prefix preference hands a dict-valued setting the control type. A signal type is never a value a setting holds, so the lookup considers value types (`FlowType.DATA`) only.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/registry.py:119-136`
- Test: `tests/core/test_types/test_type_for_python_type.py` (create)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `TypeRegistry.get_type_for_python_type(py_type: type) -> type[IType] | None`, unchanged signature, now skipping types whose `class_identity.flow_type` is not `FlowType.DATA`. Step 5.1 changes that filter to `WireRole.DEPENDENT`.

- [ ] **Step 1: Create the branch**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
git switch -c signal-types-to-builtin
```

- [ ] **Step 2: Write the failing tests**

Create `tests/core/test_types/test_type_for_python_type.py`:

```python
"""``TypeRegistry.get_type_for_python_type`` resolves value types only."""

from dataclasses import replace

import pytest

from haywire.core.types import FlowType, PrimitiveType
from haywire.core.types import type as haywire_type
from haywire.core.types.registry import TypeRegistry


@haywire_type(flow_type=FlowType.DATA, label="Dict Value", default={"value": {}})
class _DictValue(PrimitiveType[dict]):
    """A value type wrapping `dict`."""


@haywire_type(flow_type=FlowType.CONTROL, label="Dict Signal", default={"value": {}})
class _DictSignal(PrimitiveType[dict]):
    """A signal type wrapping `dict`, as `EXEC` does."""


# The lookup prefers a haywire-core key, so the signal type gets one: it must lose anyway.
_DictSignal.class_identity = replace(_DictSignal.class_identity, registry_key="haywire-core:type:DictSignal")
_DictValue.class_identity = replace(_DictValue.class_identity, registry_key="some-library:type:DictValue")


@pytest.mark.unit
def test_a_signal_type_never_answers_for_a_python_type():
    registry = TypeRegistry()
    registry._register(_DictSignal.class_identity.registry_key, _DictSignal)
    registry._register(_DictValue.class_identity.registry_key, _DictValue)

    assert registry.get_type_for_python_type(dict) is _DictValue


@pytest.mark.unit
def test_a_python_type_only_signal_types_wrap_resolves_to_nothing():
    registry = TypeRegistry()
    registry._register(_DictSignal.class_identity.registry_key, _DictSignal)

    assert registry.get_type_for_python_type(dict) is None


@pytest.mark.integration
@pytest.mark.parametrize(
    ("py_type", "expected_key"),
    [
        (dict, "haybale-core:type:DICT"),
        (str, "haywire-core:type:STRING"),
        (int, "haywire-core:type:INT"),
        (float, "haywire-core:type:FLOAT"),
        (bool, "haywire-core:type:BOOL"),
    ],
)
def test_the_loaded_libraries_resolve_each_python_type_to_its_value_type(library_system, py_type, expected_key):
    from haywire.core.di.config import get_type_registry

    resolved = get_type_registry().get_type_for_python_type(py_type)

    assert resolved is not None
    assert resolved.class_identity.registry_key == expected_key
```

- [ ] **Step 3: Run the tests**

Run: `uv run pytest tests/core/test_types/test_type_for_python_type.py -q`
Expected: the two unit tests FAIL (`_DictSignal` is returned instead of `_DictValue`, and instead of `None`). The integration tests PASS: they guard the move in Task 2.

- [ ] **Step 4: Implement**

In `packages/haywire-core/src/haywire/core/types/registry.py`, add the import next to the others:

```python
from .enums import FlowType
```

Replace `get_type_for_python_type` (lines 119-136) with:

```python
    def get_type_for_python_type(self, py_type: type) -> type[IType] | None:
        """Find the registered value type whose ``element_type_cls`` is *py_type*.

        Inverse of the IType→Python-type relationship each type already declares
        (e.g. ``FLOAT.element_type_cls is float``). Used by the runtime/TOML
        settings path to resolve an inferred Python type to its IType without a
        hand-maintained mapping. Returns ``None`` if no registered value type matches.

        Exact match only (``element_type_cls is py_type``). Only ``FlowType.DATA``
        types are candidates: a signal type wrapping a Python type (``EXEC`` wraps
        ``dict``) is not a value a setting holds. A ``haywire-core:`` type is
        preferred when several libraries register the same Python type.
        """
        matches = [
            cls
            for cls in self._classes.values()
            if getattr(cls, "element_type_cls", None) is py_type
            and FlowType(cls.class_identity.flow_type) is FlowType.DATA
        ]
        if not matches:
            return None
        matches.sort(key=lambda c: 0 if c.class_identity.registry_key.startswith("haywire-core:") else 1)
        return matches[0]
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/core/test_types/test_type_for_python_type.py tests/core/test_settings -q -n 4`
Expected: PASS, no failures.

- [ ] **Step 6: Ruff and mypy**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/types/registry.py tests/core/test_types/test_type_for_python_type.py && uv run ruff format --check packages/haywire-core/src/haywire/core/types/registry.py tests/core/test_types/test_type_for_python_type.py && uv run mypy packages/haywire-core/src/haywire/core/types/registry.py tests/core/test_types/test_type_for_python_type.py`
Expected: no errors. (`class_identity` is a `ClassVar` on `IType`, so assigning it through the class type-checks.)

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/types/registry.py tests/core/test_types/test_type_for_python_type.py
git commit -m "fix(types): the Python-type lookup ignores signal types

EXEC wraps dict like haybale-core's DICT. Once EXEC is a haywire-core type,
the lookup's haywire-core preference would give a dict-valued TOML setting
the control type.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Move EXEC and CALLBACK into builtin, one module each

One atomic change: the old import path stops working at the moment the classes move, so every importer moves in the same commit (one commit per repo).

Each type gets its own module, like `fold.py` and `optional.py`. `exec` is a builtin *function* in Python 3, not a keyword, so `exec.py` is a legal module name; nothing in the package imports the builtin. The registry key comes from the owning library's name, not the module path (`decorator.py:180`), so the split does not affect the key — but the `module` field of a port's saved identity snapshot does name the module file, so Task 3's script must write the per-module names.

**Files:**
- Create: `packages/haywire-core/src/haywire/barn/builtin/types/exec.py`, `packages/haywire-core/src/haywire/barn/builtin/types/callback.py`
- Modify: `packages/haywire-core/src/haywire/barn/builtin/types/__init__.py`, `packages/haywire-core/src/haywire/barn/builtin/__init__.py:1-5`
- Modify: `barn/haybale-core/haybale_core/types/specs.py` (lines 1-3 and 72-118), `barn/haybale-core/haybale_core/types/__init__.py`
- Modify: every file in the import table in Step 6
- Test: `tests/barn/test_signal_types.py`

**Interfaces:**
- Consumes: Task 1's filtered lookup (the integration guard there must keep passing).
- Produces: `haywire.barn.builtin.types.EXEC` (module `haywire.barn.builtin.types.exec`) and `haywire.barn.builtin.types.CALLBACK` (module `haywire.barn.builtin.types.callback`), registry keys `haywire-core:type:EXEC` and `haywire-core:type:CALLBACK`. `haybale_core.types` no longer has `EXEC` or `CALLBACK`. Task 3's script maps the old keys and the old module to these.

- [ ] **Step 1: Baseline**

Run:
```bash
uv run ruff check barn/haybale-core barn/haybale-example barn/haybale-testing packages/haywire-core/src/haywire/barn/builtin tests && uv run ruff format --check barn/haybale-core barn/haybale-example barn/haybale-testing packages/haywire-core/src/haywire/barn/builtin tests
uv run mypy barn/haybale-core/haybale_core/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ packages/haywire-core/src/haywire/barn/ tests/
```
Expected: clean. If not, stop and report: CLAUDE.md treats a dirty baseline as a separate fix session with the user.

- [ ] **Step 2: Write the failing tests**

In `tests/barn/test_signal_types.py`, replace each of the three `from haybale_core.types import specs` lines with:

```python
    from haywire.barn.builtin import types as specs
```

(each use is `getattr(specs, type_name)`, and both names now live on the package, not on one module.)

Then append:

```python
# Each signal type owns a module named after it.
SIGNAL_MODULES = {"EXEC": "exec", "CALLBACK": "callback"}


@pytest.mark.parametrize(("type_name", "_expected"), SIGNAL_STRATEGIES)
def test_a_signal_type_is_a_builtin_type(type_name, _expected):
    from haywire.barn.builtin import types

    signal = getattr(types, type_name)
    assert signal.class_identity.registry_key == f"haywire-core:type:{type_name}"
    assert signal.__module__ == f"haywire.barn.builtin.types.{SIGNAL_MODULES[type_name]}"


@pytest.mark.parametrize(("type_name", "_expected"), SIGNAL_STRATEGIES)
def test_haybale_core_does_not_export_a_signal_type(type_name, _expected):
    import haybale_core.types

    assert not hasattr(haybale_core.types, type_name)
```

In `tests/barn/builtin/test_type_default_widget.py:23`, replace `from haybale_core.types.specs import CALLBACK` with `from haywire.barn.builtin.types import CALLBACK`.

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run pytest tests/barn/test_signal_types.py tests/barn/builtin/test_type_default_widget.py -q`
Expected: FAIL with `AttributeError: module 'haywire.barn.builtin.types.specs' has no attribute 'EXEC'` (and `CALLBACK`), and `ImportError: cannot import name 'CALLBACK' from 'haywire.barn.builtin.types'`.

- [ ] **Step 4: Move the classes, one module each**

Create `packages/haywire-core/src/haywire/barn/builtin/types/exec.py`:

```python
"""EXEC — the execution signal that sequences one node after another."""

from haywire.core.types import FlowType, PrimitiveType, StoreStrategy, type


@type(
    flow_type=FlowType.CONTROL,
    label="Execution Signal",
    description="Signal for controlling execution flow between nodes",
    color="#004cff",
    default={"value": {}},
    store_strategy=StoreStrategy.NEVER,
)
class EXEC(PrimitiveType[dict]):
    """Execution signal carrying an optional `dict` payload."""

    @classmethod
    def create_default(cls) -> "EXEC":
        return cls({})
```

Create `packages/haywire-core/src/haywire/barn/builtin/types/callback.py`:

```python
"""CALLBACK — the subscription name a listener registers under."""

from haywire.core.types import FlowType, StoreStrategy, type

from .specs import STRING


@type(
    flow_type=FlowType.CALLBACK,
    label="Callback Signal",
    description="Signal for callback execution between nodes",
    color="#ff3c00",
    default={"value": ""},
    # A signal, not an editable value: clears the TextWidget it would inherit from STRING.
    widget_key=None,
    # The node may set it; only a value the node set is worth storing.
    store_strategy=StoreStrategy.NODE_SET,
)
class CALLBACK(STRING):
    """Callback signal: the name a listener subscribes under.

    It travels like a `STRING`, has no widget, and a port stores it only when its
    node set it. An empty name means no subscription: an emitter drops it.
    """
```

`specs.py` is untouched by this task.

In `packages/haywire-core/src/haywire/barn/builtin/types/__init__.py`, add the two imports in alphabetical position among the existing `from .<module> import ...` lines:

```python
from .callback import CALLBACK
from .exec import EXEC
```

and add `"EXEC",` and `"CALLBACK",` to `__all__` after `"BOOL",`.

In `barn/haybale-core/haybale_core/types/specs.py`:
- delete lines 71-118 (the two blank lines after `DICT.from_dict` and the "Exec Types" and "Callback Types" sections, through the end of `CALLBACK`'s docstring), so the file ends with `DICT.from_dict`'s `return` line and one newline;
- change line 1 to `from haywire.core.types import type, FlowType, PrimitiveType` (`StoreStrategy` was used only by the two moved types);
- delete line 3, `from haywire.barn.builtin.types import STRING`, and the blank line after it (`CALLBACK` was its only user).

In `barn/haybale-core/haybale_core/types/__init__.py`, delete the lines `from .specs import EXEC` and `from .specs import CALLBACK`, and the entries `"CALLBACK",` and `"EXEC",` from `__all__`.

- [ ] **Step 5: Fix the builtin library's module docstring**

The docstring names a `builtin:` key prefix that has never been the real one (the overview's small items list it). Replace lines 1-5 of `packages/haywire-core/src/haywire/barn/builtin/__init__.py` with:

```python
"""Builtin Library: framework-owned types (primitives, vectors, colour, and the
EXEC and CALLBACK signal types), their basic adapters, and the reroute node and
skin. Loaded at Priority 1 before any entry-point plugin, so that
``haywire-core:type:*``, ``haywire-core:node:*`` and ``haywire-core:skin:*`` keys
resolve when graphs and plugins reference them.
"""
```

- [ ] **Step 6: Update every importer**

Every import below sits inside a function (`init()` or a test). Keep it there; change only the module it imports from. Rules, applied to each line in the table:

| Current import | Becomes |
|---|---|
| `from haybale_core.types import EXEC` | `from haywire.barn.builtin.types import EXEC` |
| `from ..types.specs import EXEC` | `from haywire.barn.builtin.types import EXEC` |
| `from haybale_core.types import CALLBACK` | `from haywire.barn.builtin.types import CALLBACK` |
| `from haybale_core.types import EXEC, CALLBACK` or `CALLBACK, EXEC` | `from haywire.barn.builtin.types import CALLBACK, EXEC` |
| `from haybale_core.types import EXEC, CALLBACK, PooledType` | `from haybale_core.types import PooledType` and, on the next line, `from haywire.barn.builtin.types import CALLBACK, EXEC` |
| `from haybale_core.types import EXEC, PooledType` | `from haybale_core.types import PooledType` and `from haywire.barn.builtin.types import EXEC` |
| `from haybale_core.types import CALLBACK, PooledType` | `from haybale_core.types import PooledType` and `from haywire.barn.builtin.types import CALLBACK` |

The lines (as of 2026-10-02):

| File | Line(s) |
|---|---|
| `barn/haybale-core/haybale_core/nodes/logger.py` | 27 |
| `barn/haybale-core/haybale_core/nodes/emits/tick_emit.py` | 36 |
| `barn/haybale-core/haybale_core/nodes/switch.py` | 39 |
| `barn/haybale-core/haybale_core/nodes/events/shutdown.py` | 62 |
| `barn/haybale-core/haybale_core/nodes/events/tick_event.py` | 27 |
| `barn/haybale-core/haybale_core/nodes/for_loop.py` | 39 |
| `barn/haybale-core/haybale_core/nodes/print.py` | 16 |
| `barn/haybale-core/haybale_core/nodes/events/begin_play.py` | 24 |
| `barn/haybale-example/haybale_example/nodes/emits/emit_callback.py` | 27 |
| `barn/haybale-example/haybale_example/nodes/emits/merge_callback.py` | 57 |
| `barn/haybale-example/haybale_example/nodes/emits/custom_callback.py` | 28 |
| `barn/haybale-testing/haybale_testing/nodes/testbed/print_node.py` | 27 |
| `barn/haybale-testing/haybale_testing/nodes/testbed/custom_callback_node.py` | 19 |
| `barn/haybale-testing/haybale_testing/nodes/benchmark/bench_exec_node.py` | 26 |
| `barn/haybale-testing/haybale_testing/nodes/testbed/control_payload_node.py` | 40 |
| `barn/haybale-testing/haybale_testing/nodes/testbed/edge_link_test.py` | 28 |
| `barn/haybale-testing/haybale_testing/nodes/testbed/begin_play_node.py` | 18 |
| `barn/haybale-testing/haybale_testing/nodes/testbed/test_performance.py` | 27 |
| `barn/haybale-testing/haybale_testing/nodes/testbed/emit_callback_node.py` | 17 |
| `barn/haybale-testing/haybale_testing/nodes/testbed/record_callback_nodes.py` | 17, 48 |
| `barn/haybale-visiongraph/haybale_visiongraph/nodes/tracker_node.py` | 270 |
| `barn/haybale-visiongraph/haybale_visiongraph/nodes/base_estimator_node.py` | 135 |
| `barn/haybale-visiongraph/haybale_visiongraph/nodes/oak_d_camera_node.py` | 420 |
| `barn/haybale-visiongraph/haybale_visiongraph/nodes/numpy_frame_event_node.py` | 145 |
| `barn/haybale-visiongraph/haybale_visiongraph/nodes/web_cam_node.py` | 193 |
| `barn/haybale-visiongraph/haybale_visiongraph/nodes/numpy_frame_display_node.py` | 42 |
| `barn/haybale-visiongraph/haybale_visiongraph/nodes/annotate_node.py` | 156 |
| `tests/core/test_types/test_callback_values.py` | 10, 15, 20, 31, 71, 103 |
| `tests/core/test_node/test_node_behavior_instance.py` | 126, 148 |
| `tests/core/test_graph/callback_group.py` | 36 |
| `tests/core/test_assembly/test_subgraph_execution_edges.py` | 85, 157, 234, 315 |
| `tests/core/test_graph/test_graph_node.py` | 83 |
| `tests/core/test_assembly/test_flat_view.py` | 87, 343, 494 |
| `tests/core/test_macro/test_macro_callback_interface.py` | 23 |
| `tests/core/test_undo/test_split_edge_reroute.py` | 409 |

Do **not** sort the imports with `ruff check --select I --fix`: `I` is not in this repo's `extend-select` (`pyproject.toml:121`), so enabling it rewrites the import block of every file it is pointed at — measured on 2026-10-02 as 489 files, 651 "fixes", none of them this plan's. Each rewritten import here is a single function-local line replacing another, so nothing needs sorting. Step 9's `ruff check` is the guard.

- [ ] **Step 7: Verify nothing still imports the old path**

Run:
```bash
grep -rnE "haybale_core\.types(\.specs)? import .*\b(EXEC|CALLBACK|specs)\b|from \.\.types\.specs import EXEC" --include="*.py" packages barn tests barn/haybale-visiongraph/
```
Expected: no output. (The trailing slash on the symlink makes grep descend into visiongraph.)

- [ ] **Step 8: Run the focused tests**

Run: `uv run pytest tests/barn/test_signal_types.py tests/barn/builtin/test_type_default_widget.py tests/core/test_types tests/core/test_assembly tests/core/test_graph/test_graph_node.py tests/core/test_macro/test_macro_callback_interface.py tests/core/test_undo/test_split_edge_reroute.py tests/core/test_node/test_node_behavior_instance.py -q -n 4`
Expected: PASS, including Task 1's integration guard (`dict` still resolves to `DICT`).

- [ ] **Step 9: Ruff and mypy**

Run the Step 1 commands again, adding visiongraph to ruff: `uv run ruff check barn/haybale-visiongraph/ && uv run ruff format --check barn/haybale-visiongraph/`.
Expected: clean.

- [ ] **Step 10: Commit this repo**

```bash
git add -u packages/haywire-core/src/haywire/barn/builtin barn/haybale-core barn/haybale-example barn/haybale-testing tests
git status --short   # must not list graphs/oakNwebCam.haywire as staged
git commit -m "refactor(types): EXEC and CALLBACK are builtin types

Moved from haybale-core to haywire.barn.builtin.types.specs; their keys are
now haywire-core:type:EXEC and haywire-core:type:CALLBACK. Every importer
moves with them; haybale_core.types no longer exports either.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 11: Commit visiongraph**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph
git switch -c signal-types-to-builtin
git add -u barn/haybale-visiongraph/haybale_visiongraph/nodes
git status --short   # uv.lock stays unstaged
git commit -m "refactor: import EXEC from haywire.barn.builtin.types

EXEC moved from haybale-core into the framework's builtin library.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
```

---

### Task 3: Rewrite saved graphs to the new keys

A saved port records its type twice: `recipe.registry_key` (resolved on load) and a snapshot of the type's identity in `kwargs` (`registry_key`, `module`, `class_name`, …), which `DataPort.from_spec` copies into the port's fields and `to_dict` writes back unchanged. Both must change. A recipe can nest (`PooledType[CALLBACK]` has `element_type: {"registry_key": "haybale-core:type:CALLBACK"}`). The `module` field changes only where `class_name` is `EXEC` or `CALLBACK`, and each gets a *different* new module (`…types.exec`, `…types.callback`): `BYTES`, `LIST` and `DICT` still live in `haybale_core.types.specs`.

Graphs save with `json.dumps(data, indent=2, ensure_ascii=False)` (`packages/haywire-core/src/haywire/core/graph/base.py:1170`) and macros with `json.dumps(..., indent=2)` (`packages/haywire-core/src/haywire/core/macro/promote.py:149`). The script detects which of these reproduces a file byte for byte and writes it back the same way, so a diff shows only the changed values. A file it cannot reproduce is reported and left alone.

**Deviation found while executing (2026-10-02):** `graphs/60nodes-edges.haywire` is not a studio save — it is compact (`indent=None`, 775KB) and its `filestem` says `10x300nodes`, so it is a hand-made dump. Reproducing it with `indent=2` would reformat it to 1.3MB, which is why the script refused it. `detect_format` therefore tries `indent=None` as well and returns `(indent, ensure_ascii, suffix)`; the compact form is covered by a fourth case in `test_a_file_keeps_its_formatting`. `indent=4` stays unreproducible, so the refusal test is unchanged.

**Files:**
- Create: `scripts/migrate_signal_type_keys.py`
- Test: `tests/scripts/test_migrate_signal_type_keys.py`
- Modify (data): `graphs/any_and_nonde.haywire`, `graphs/webcam.haywire`, `graphs/10x128n_5x112e.haywire`, `graphs/10x64n_56x5e.haywire`, `graphs/oakNwebCam.haywire`, `graphs/10x512n_5x448e.haywire`, `graphs/10x192n_5x168e.haywire`, `graphs/60nodes-edges.haywire`, `graphs/10x256n_5x224e.haywire`, `graphs/loop.haywire`, `graphs/10x200nodes.haywire`, `graphs/10x64n_sub.haywire`, `graphs/10x300nodes.haywire`, `barn/haybale-example/haybale_example/macros/NewMacroGroup.hwm`, and in visiongraph `graphs/webcam.haywire`

**Interfaces:**
- Consumes: the new keys and modules from Task 2 (`haywire-core:type:EXEC` in `haywire.barn.builtin.types.exec`, `haywire-core:type:CALLBACK` in `haywire.barn.builtin.types.callback`).
- Produces: `scripts.migrate_signal_type_keys` with `rewrite_document(doc: Any) -> int`, `detect_format(text: str) -> tuple[bool, str] | None`, `migrate_file(path: Path, *, check: bool = False) -> int`, `main(argv: list[str] | None = None) -> int`, and `FormatNotReproducibleError(ValueError)`. All of it is temporary: Task 5 deletes the script and its tests once the files are rewritten and committed.

- [ ] **Step 1: Check for the user's uncommitted graph**

Run: `git status --short graphs/`
If `graphs/oakNwebCam.haywire` is listed as modified, stop and ask the user to commit or stash it before continuing. Rewriting it would mix this plan's change into theirs.

- [ ] **Step 2: Write the failing tests**

Create `tests/scripts/test_migrate_signal_type_keys.py`:

```python
"""Tests for scripts/migrate_signal_type_keys.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import migrate_signal_type_keys as migrate


def _port(registry_key: str, class_name: str, module: str) -> dict:
    return {
        "kwargs": {"registry_key": registry_key, "class_name": class_name, "module": module},
        "recipe": {"registry_key": registry_key},
    }


def _graph() -> dict:
    return {
        "nodes": {
            "a": {
                "registry_key": "haybale-core:node:BeginPlayNode",
                "node_data": {
                    "ports": {
                        "exec": _port("haybale-core:type:EXEC", "EXEC", "haybale_core.types.specs"),
                        "table": _port("haybale-core:type:DICT", "DICT", "haybale_core.types.specs"),
                        "names": {
                            "kwargs": {
                                "registry_key": "haybale-core:type:PooledType",
                                "class_name": "PooledType",
                                "module": "haybale_core.types.pooled_type",
                            },
                            "recipe": {
                                "registry_key": "haybale-core:type:PooledType",
                                "element_type": {"registry_key": "haybale-core:type:CALLBACK"},
                            },
                        },
                    }
                },
            }
        }
    }


@pytest.mark.unit
def test_a_moved_type_gets_its_new_key_and_module():
    doc = _graph()

    count = migrate.rewrite_document(doc)

    port = doc["nodes"]["a"]["node_data"]["ports"]["exec"]
    assert port["recipe"]["registry_key"] == "haywire-core:type:EXEC"
    assert port["kwargs"]["registry_key"] == "haywire-core:type:EXEC"
    assert port["kwargs"]["module"] == "haywire.barn.builtin.types.exec"
    # exec: recipe key, kwargs key, module; names: the nested element key.
    assert count == 4


@pytest.mark.unit
def test_each_moved_class_gets_its_own_module():
    doc = {
        "ports": {
            "e": _port("haybale-core:type:EXEC", "EXEC", "haybale_core.types.specs"),
            "c": _port("haybale-core:type:CALLBACK", "CALLBACK", "haybale_core.types.specs"),
        }
    }

    migrate.rewrite_document(doc)

    assert doc["ports"]["e"]["kwargs"]["module"] == "haywire.barn.builtin.types.exec"
    assert doc["ports"]["c"]["kwargs"]["module"] == "haywire.barn.builtin.types.callback"


@pytest.mark.unit
def test_a_nested_element_key_is_rewritten():
    doc = _graph()

    migrate.rewrite_document(doc)

    names = doc["nodes"]["a"]["node_data"]["ports"]["names"]
    assert names["recipe"]["element_type"]["registry_key"] == "haywire-core:type:CALLBACK"
    assert names["kwargs"]["module"] == "haybale_core.types.pooled_type"


@pytest.mark.unit
def test_a_type_that_stayed_in_haybale_core_is_untouched():
    doc = _graph()

    migrate.rewrite_document(doc)

    table = doc["nodes"]["a"]["node_data"]["ports"]["table"]
    assert table == _port("haybale-core:type:DICT", "DICT", "haybale_core.types.specs")
    assert doc["nodes"]["a"]["registry_key"] == "haybale-core:node:BeginPlayNode"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("indent", "ensure_ascii", "suffix"),
    [(2, False, ""), (2, True, ""), (2, False, "\n"), (None, False, "")],
)
def test_a_file_keeps_its_formatting(tmp_path: Path, indent: int | None, ensure_ascii: bool, suffix: str):
    doc = _graph()
    doc["name"] = "Grüße"
    path = tmp_path / "g.haywire"
    path.write_text(json.dumps(doc, indent=indent, ensure_ascii=ensure_ascii) + suffix, encoding="utf-8")

    count = migrate.migrate_file(path)

    expected = _graph()
    expected["name"] = "Grüße"
    migrate.rewrite_document(expected)
    assert count == 4
    assert (
        path.read_text(encoding="utf-8")
        == json.dumps(expected, indent=indent, ensure_ascii=ensure_ascii) + suffix
    )


@pytest.mark.unit
def test_check_mode_counts_without_writing(tmp_path: Path):
    path = tmp_path / "g.haywire"
    original = json.dumps(_graph(), indent=2, ensure_ascii=False)
    path.write_text(original, encoding="utf-8")

    assert migrate.migrate_file(path, check=True) == 4
    assert path.read_text(encoding="utf-8") == original


@pytest.mark.unit
def test_a_file_whose_formatting_cannot_be_reproduced_is_refused(tmp_path: Path):
    path = tmp_path / "g.haywire"
    path.write_text(json.dumps(_graph(), indent=4), encoding="utf-8")

    with pytest.raises(migrate.FormatNotReproducibleError):
        migrate.migrate_file(path)


@pytest.mark.unit
def test_main_reports_remaining_keys_in_check_mode(tmp_path: Path):
    (tmp_path / "old.haywire").write_text(json.dumps(_graph(), indent=2, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "clean.hwm").write_text(json.dumps({"nodes": {}}, indent=2), encoding="utf-8")

    assert migrate.main(["--check", str(tmp_path)]) == 1
    assert migrate.main([str(tmp_path)]) == 0
    assert migrate.main(["--check", str(tmp_path)]) == 0
```

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run pytest tests/scripts/test_migrate_signal_type_keys.py -q`
Expected: FAIL with `ImportError: cannot import name 'migrate_signal_type_keys' from 'scripts'`.

- [ ] **Step 4: Write the script**

Create `scripts/migrate_signal_type_keys.py`:

```python
"""Rewrite saved graphs and macros from the haybale-core EXEC and CALLBACK keys to the builtin ones.

One-off: delete this script once every saved graph in the repo has been rewritten.

``EXEC`` and ``CALLBACK`` moved from haybale-core to the builtin library, which
changed their registry keys, and each now has its own module. A saved port names
its type in its ``recipe`` and in the identity snapshot of its ``kwargs``; this
rewrites both, and the snapshot's ``module`` for the two moved classes only. A
file is written back in the exact JSON formatting it was read in, so a diff shows
only the changed values.

Usage::

    uv run python -m scripts.migrate_signal_type_keys --check graphs barn/haybale-example
    uv run python -m scripts.migrate_signal_type_keys graphs barn/haybale-example

Directories are searched for ``*.haywire`` and ``*.hwm`` files. Exit status: 0 when
nothing is left to rewrite, 1 when ``--check`` found old keys, 2 when a file's
formatting could not be reproduced (that file is left unchanged).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

OLD_TO_NEW_KEYS = {
    "haybale-core:type:EXEC": "haywire-core:type:EXEC",
    "haybale-core:type:CALLBACK": "haywire-core:type:CALLBACK",
}
OLD_MODULE = "haybale_core.types.specs"
NEW_MODULES = {
    "EXEC": "haywire.barn.builtin.types.exec",
    "CALLBACK": "haywire.barn.builtin.types.callback",
}
SUFFIXES = (".haywire", ".hwm")


class FormatNotReproducibleError(ValueError):
    """The file's JSON formatting matches none of the formats the app writes."""


def rewrite_document(doc: Any) -> int:
    """Rewrite old keys and the moved classes' module in place; return the number of values changed."""
    count = 0
    if isinstance(doc, dict):
        # BYTES, LIST and DICT share the old module and stay in haybale-core.
        if doc.get("module") == OLD_MODULE and doc.get("class_name") in NEW_MODULES:
            doc["module"] = NEW_MODULES[doc["class_name"]]
            count += 1
        for key, value in doc.items():
            if isinstance(value, str) and value in OLD_TO_NEW_KEYS:
                doc[key] = OLD_TO_NEW_KEYS[value]
                count += 1
            else:
                count += rewrite_document(value)
    elif isinstance(doc, list):
        for index, value in enumerate(doc):
            if isinstance(value, str) and value in OLD_TO_NEW_KEYS:
                doc[index] = OLD_TO_NEW_KEYS[value]
                count += 1
            else:
                count += rewrite_document(value)
    return count


def _dump(doc: Any, indent: int | None, ensure_ascii: bool, suffix: str) -> str:
    return json.dumps(doc, indent=indent, ensure_ascii=ensure_ascii) + suffix


def detect_format(text: str) -> tuple[int | None, bool, str] | None:
    """Return the ``(indent, ensure_ascii, trailing suffix)`` that reproduces *text* exactly, or ``None``.

    ``indent=None`` is the compact form a hand-written dump produces; the app
    itself always writes ``indent=2``.
    """
    doc = json.loads(text)
    for indent in (2, None):
        for ensure_ascii in (False, True):
            for suffix in ("", "\n"):
                if _dump(doc, indent, ensure_ascii, suffix) == text:
                    return indent, ensure_ascii, suffix
    return None


def migrate_file(path: Path, *, check: bool = False) -> int:
    """Rewrite *path* in place (unless *check*) and return the number of values changed.

    Raises:
        FormatNotReproducibleError: The file's formatting matches no format the app writes.
    """
    text = path.read_text(encoding="utf-8")
    fmt = detect_format(text)
    if fmt is None:
        raise FormatNotReproducibleError(f"{path}: formatting not reproducible, left unchanged")
    doc = json.loads(text)
    count = rewrite_document(doc)
    if count and not check:
        path.write_text(_dump(doc, *fmt), encoding="utf-8")
    return count


def _files(paths: list[str]) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            found.extend(sorted(p for p in path.rglob("*") if p.suffix in SUFFIXES))
        else:
            found.append(path)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rewrite saved graphs to the builtin EXEC and CALLBACK keys.")
    parser.add_argument("paths", nargs="+", help="graph/macro files or directories to search")
    parser.add_argument("--check", action="store_true", help="report old keys without writing")
    args = parser.parse_args(argv)

    found_old = False
    unreproducible = False
    for path in _files(args.paths):
        try:
            count = migrate_file(path, check=args.check)
        except FormatNotReproducibleError as error:
            print(error, file=sys.stderr)
            unreproducible = True
            continue
        if count:
            found_old = True
            print(f"{path}: {count} value(s) {'to rewrite' if args.check else 'rewritten'}")
    if unreproducible:
        return 2
    return 1 if args.check and found_old else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/scripts/test_migrate_signal_type_keys.py -q`
Expected: PASS (8 tests, one parametrized into four, so 11 collected).

- [ ] **Step 6: Ruff**

Run: `uv run ruff check scripts/migrate_signal_type_keys.py tests/scripts/test_migrate_signal_type_keys.py && uv run ruff format --check scripts/migrate_signal_type_keys.py tests/scripts/test_migrate_signal_type_keys.py && uv run mypy tests/scripts/test_migrate_signal_type_keys.py`
Expected: clean.

- [ ] **Step 7: Rewrite this repo's files**

Run:
```bash
uv run python -m scripts.migrate_signal_type_keys --check graphs barn/haybale-example barn/haybale-core barn/haybale-testing
```
Expected: exit 1, listing exactly the 13 `graphs/*.haywire` files from **Files** and `NewMacroGroup.hwm`, and nothing on stderr. If any file is reported as not reproducible, stop and report it.

Then:
```bash
uv run python -m scripts.migrate_signal_type_keys graphs barn/haybale-example barn/haybale-core barn/haybale-testing
uv run python -m scripts.migrate_signal_type_keys --check graphs barn/haybale-example barn/haybale-core barn/haybale-testing; echo "exit=$?"
grep -rlE "haybale-core:type:(EXEC|CALLBACK)" graphs barn/haybale-example barn/haybale-core barn/haybale-testing
git diff --stat graphs barn/haybale-example
```
Expected: exit=0, grep prints nothing, and the diff touches only those 14 files. Spot-check one: `git diff graphs/loop.haywire | grep '^[-+] ' | sort | uniq -c` shows only `registry_key` and `module` lines.

- [ ] **Step 8: Load a rewritten graph**

Run:
```bash
uv run pytest tests -q -n 4 -k "loop or macro or callback" -m "not browser and not perf"
```
Expected: PASS. Then confirm a rewritten file loads without error nodes. Write this to the scratchpad as `check_load.py` and run it with `PYTHONPATH=. uv run pytest -p tests.conftest <scratchpad>/check_load.py -q --rootdir=. -o addopts=""`:

```python
import json
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.parametrize("name", ["loop.haywire", "any_and_nonde.haywire", "60nodes-edges.haywire"])
def test_a_rewritten_graph_loads_without_error_nodes(library_system, name):
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.scheduler import SyncScheduler

    graph = BaseGraph(filestem=name, validation_scheduler=SyncScheduler())
    assert graph.load_from_dict(json.loads(Path("graphs", name).read_text(encoding="utf-8")))
    broken = [nid for nid, wrapper in graph.node_wrappers.items() if wrapper.state.error_initialize]
    assert broken == []
```

Expected: 3 passed. Delete `check_load.py` afterwards; it is not committed.

- [ ] **Step 9: Commit this repo**

```bash
git add scripts/migrate_signal_type_keys.py tests/scripts/test_migrate_signal_type_keys.py graphs barn/haybale-example/haybale_example/macros/NewMacroGroup.hwm
git commit -m "chore(graphs): saved graphs name the builtin EXEC and CALLBACK keys

scripts/migrate_signal_type_keys.py rewrites the type keys and the moved
classes' module in recipes and port identity snapshots, keeping each file's
JSON formatting.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 10: Rewrite and commit visiongraph's graph**

```bash
uv run python -m scripts.migrate_signal_type_keys ../haybale-visiongraph/graphs
uv run python -m scripts.migrate_signal_type_keys --check ../haybale-visiongraph/graphs; echo "exit=$?"
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph
git add graphs/webcam.haywire
git status --short   # uv.lock stays unstaged
git commit -m "chore(graphs): name the builtin EXEC and CALLBACK keys

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
```
Expected: the first command rewrites `graphs/webcam.haywire`; the check prints exit=0.

---

### Task 4: Regenerate library docs and fix stale explanations

**Files:**
- Modify (generated): `QUICKREF.md`, `OVERVIEW.md` and `docs/*.md` of `packages/haywire-core/src/haywire/barn/builtin`, `barn/haybale-core/haybale_core`, `barn/haybale-example/haybale_example`, `barn/haybale-testing/haybale_testing`
- Modify: `tests/core/test_libraries/test_registry_remove_library.py:51-56`, `.insights/project_slow_test_outliers.md:79-83`, `tests/conftest.py:270`

**Interfaces:**
- Consumes: Tasks 2 and 3.
- Produces: generated docs that list `EXEC` and `CALLBACK` under builtin; nothing code depends on.

- [ ] **Step 1: Regenerate**

Run: `uv run haywire docs --all`
Expected: `barn/haybale-core/haybale_core/docs/haybale-core.type.EXEC.md` and `…CALLBACK.md` are deleted (the generator removes orphans), `packages/haywire-core/src/haywire/barn/builtin/docs/haywire-core.type.EXEC.md` and `…CALLBACK.md` are created, and node docs that embed `init()` source now show `from haywire.barn.builtin.types import …`. The run skips visiongraph, whose symlinked path resolves outside the repo; its generated docs do not embed these imports.

Run: `git status --short` and check the list matches that description.

- [ ] **Step 2: Fix the stale explanations**

In `tests/core/test_libraries/test_registry_remove_library.py`, the fixture docstring explains the prefix snapshot with `EXEC`, which no longer lives in haybale-core. Replace the paragraph's last sentence pair (lines 51-56, from "The snapshot is taken by PREFIX" to "causes the identity failure.") with:

```python
    The snapshot is taken by PREFIX rather than from a list of the keys these
    tests plant, because ``remove_library()`` ejects every ``haybale_core.*``
    submodule it finds, including ones the test never touched but the real
    package had already imported, such as ``haybale_core.types.pooled_type``.
    Listing only the planted keys leaves exactly the entry whose loss causes the
    identity failure.
```

The paragraph above it quotes `assert <class EXEC> is <class EXEC>` as the historical symptom; leave that sentence as it is.

In `.insights/project_slow_test_outliers.md`, replace lines 79-83 (the "Restoring only what you planted is not enough." bullet) with:

```markdown
- **Restoring only what you planted is not enough.** `remove_library()` ejects
  every `haybale_core.*` submodule by prefix, including ones the test never
  touched but the package had already imported (`haybale_core.types.pooled_type`,
  say). A fixture listing only the planted keys leaves exactly the entry whose
  loss causes the failure. Snapshot **by prefix**.
```

In `tests/conftest.py:270`, the `test_injector` docstring cites a key format that no longer exists: replace ``core:type:CALLBACK`` with ``haywire-core:type:CALLBACK``.

- [ ] **Step 3: Commit**

Commit before running the docs test: its teardown runs `git checkout -- barn/haybale-testing` and would discard the regenerated files there.

```bash
git add packages/haywire-core/src/haywire/barn/builtin barn/haybale-core barn/haybale-example barn/haybale-testing tests/core/test_libraries/test_registry_remove_library.py tests/conftest.py .insights/project_slow_test_outliers.md
git commit -m "docs: regenerate library docs for the builtin signal types

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 4: Run the docs test and the touched tests**

Run: `uv run pytest tests/studio/test_docs tests/core/test_libraries/test_registry_remove_library.py -q -n 4`
Expected: PASS, and `git status --short` is empty afterwards (except the user's files named in Global Constraints). A failure here means the generated docs are not what the generator produces: rerun Step 1, inspect the diff, and amend the commit with the fix.

---

### Task 5: Remove the migration script, verify, status

**Files:**
- Delete: `scripts/migrate_signal_type_keys.py`, `tests/scripts/test_migrate_signal_type_keys.py` (and `tests/scripts/` entirely if it holds nothing else)
- Modify: `docs/superpowers/plans/2026-09-28-edge-kinds.md` (status table, row P), `docs/superpowers/plans/2026-09-24-new-node-wizard.md` (follow-on 2)

- [ ] **Step 0: Delete the migration script and its tests**

The rewrite has landed in both repos (Task 3, Steps 9 and 10), so the script has no remaining job: no file in either repo carries an old key, and a future graph cannot acquire one. Re-confirm that before deleting — the check is the reason the deletion is safe, not a formality:

```bash
uv run python -m scripts.migrate_signal_type_keys --check graphs barn ../haybale-visiongraph/graphs; echo "exit=$?"
```
Expected: exit=0 and no output. If any file is still listed, stop: Task 3 is incomplete.

Then:
```bash
git rm scripts/migrate_signal_type_keys.py tests/scripts/test_migrate_signal_type_keys.py
ls tests/scripts 2>/dev/null   # if only __pycache__/ or nothing remains, remove the directory
```
If `tests/scripts/` held an `__init__.py` created for this plan and nothing else, remove the directory too. If it pre-existed with other tests, leave it.

Commit:
```bash
git commit -m "chore(scripts): drop the one-off signal-type key migration

Every saved graph in both repos names the builtin keys, so the script and
its tests have no remaining job.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 1: Ruff and mypy, whole repo**

Run:
```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-marketplace/haybale_marketplace/ barn/haybale-share/haybale_share/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-haystack/haybale_haystack/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```
Expected: clean.

- [ ] **Step 2: Pre-commit gate**

Run: `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"` (timeout ≥ 600000 ms), then `grep -E "^FAILED|^ERROR" /tmp/t.log`.
Expected: exit=0, no lines.

- [ ] **Step 3: Browser tier**

Run: `uv run pytest -m browser -n 4 -q > /tmp/b.log 2>&1; echo "exit=$?"`, then `grep -E "^FAILED|^ERROR" /tmp/b.log`.
Expected: exit=0.

- [ ] **Step 4: visiongraph tests**

Run: `uv run pytest ../haybale-visiongraph/tests -q`
Expected: PASS. visiongraph's tests do not cover the OAK-D path, which uses `EXEC`; tell the user it is worth one look in the running studio.

- [ ] **Step 5: Status**

In `docs/superpowers/plans/2026-09-28-edge-kinds.md`, change row P of the status table to:

```markdown
| P | `EXEC` and `CALLBACK` into builtin (precondition for 5; the new node wizard's follow-on 2) | **Landed** on branch `signal-types-to-builtin` (both repos), not merged | [2026-10-02-signal-types-to-builtin.md](2026-10-02-signal-types-to-builtin.md) | merge, then 5.1 |
```

In `docs/superpowers/plans/2026-09-24-new-node-wizard.md`, replace follow-on 2 (the item starting "**EXEC and CALLBACK into builtin**") with:

```markdown
2. **EXEC and CALLBACK into builtin**: done by
   [2026-10-02-signal-types-to-builtin.md](2026-10-02-signal-types-to-builtin.md),
   one module each, without a key alias (saved graphs were rewritten by a one-off
   script that the same plan then deleted). The Control, Event and Output templates
   remain.
```

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/plans/2026-09-28-edge-kinds.md docs/superpowers/plans/2026-09-24-new-node-wizard.md docs/superpowers/plans/2026-10-02-signal-types-to-builtin.md
git commit -m "docs(plans): plan P landed on its branch

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

Report to the user: the two branches, the commits in each, the uncommitted files left alone (`graphs/oakNwebCam.haywire` if it was stashed or committed by them, visiongraph `uv.lock`), and that moving this plan to `landed/` happens when they merge.
