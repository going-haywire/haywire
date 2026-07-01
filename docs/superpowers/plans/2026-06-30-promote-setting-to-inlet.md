# Promote Setting To Inlet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user promote a plain node `setting()` into a real DATA inlet so graph logic can drive a value that was previously editable only in the Properties panel — via a node right-click "Promote setting ▸" submenu, with demote on the pin's right-click menu.

**Architecture:** A promoted inlet is an ordinary dynamic DATA port (created via the node's `rejig()` machinery) whose id `setting__<accessor>__<field>` is also its binding key. The setting descriptor's read path gains a top tier: if a linked promoted port exists for the field, return the port value; otherwise resolve normally. The port carries `store_strategy=NEVER` (its value never persists — the setting override remains the sole stored value). The promoted inlet renders **no widget** in v1 (edit in the Properties panel, wire on the canvas). A shared `FieldMetadata` Protocol names the label/type/default/widget contract that both `SettingDescriptor` and `DataPort` already satisfy.

**Tech Stack:** Python 3.10+, the haywire node/port/edge system (`rejig`, `DataPort`, `EdgeWrapper`), the settings descriptor, the `@panel`/`Focus` context-menu system (haybale-graph-editor), NiceGUI, pytest, ruff, mypy.

---

## Task 0: Verification Gate — confirm Plans 1 and 2 landed

**This plan depends on Plan 1 (types) AND Plan 2 (widgets/IType cutover). Do NOT edit until this passes.**

**Files:**

- Read: `docs/superpowers/plans/2026-06-28-type-floor-hoist-DEVIATIONS.md`
- Read: `docs/superpowers/plans/2026-06-29-widget-unification-DEVIATIONS.md`

- [ ] **Step 1: Read both deviations files**

Run:
```bash
cat docs/superpowers/plans/2026-06-28-type-floor-hoist-DEVIATIONS.md
cat docs/superpowers/plans/2026-06-29-widget-unification-DEVIATIONS.md
```
If either is missing, STOP — a prerequisite plan has not completed. Record: the type key pattern,
the `resolved_widget_key` property name, and whether `setting[IType]` is mandatory (Plan 2 cutover).
This plan assumes `setting[FLOAT]`-style declarations and `builtin:type:*` keys; substitute if the
deviations say otherwise.

- [ ] **Step 2: Probe live prerequisites**

Run:
```bash
uv run python -c "import haywire.core.graph.editor; \
from haywire.core.settings import NodeSettings, setting; \
from haywire.barn.builtin.types import FLOAT; \
print('IType settings OK')"
uv run python -c "import haywire.core.graph.editor; \
from haywire.core.node.data import NodeData; \
print('rejig' , hasattr(NodeData, 'rejig'))"
uv run pytest -m "not integration" -q
```
Expected: imports succeed, `rejig` present, suite green. If `setting[FLOAT]` import or the IType
cutover isn't in place, STOP — Plan 2 is incomplete.

- [ ] **Step 3: Confirm the integration surfaces exist**

Run:
```bash
grep -n "def rejig\|def add\b\|mark_as_structuraly_dirty" packages/haywire-core/src/haywire/core/node/data.py
grep -n "class StoreStrategy\|NEVER" packages/haywire-core/src/haywire/core/types/enums.py
grep -n "active_port\|active_node" barn/haybale-graph-editor/haybale_graph_editor/state/edit_state.py
grep -rn "@panel(" barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/port/port.py
grep -n "def __get__\|_resolve" packages/haywire-core/src/haywire/core/settings/descriptor.py
```
Expected: all present. If `rejig`/`StoreStrategy.NEVER`/`active_port`/the menu-panel pattern moved,
reconcile the relevant task before editing.

---

## Scope

**This plan (Plan 3 of 3)** implements promotion. Promotable = **plain `setting()` only** (not
`shadow()`/`watch()`). All ITypes are permissible (permissive — no allowlist). The promoted inlet
has **no widget** in v1. View-onto-setting on-card widget is explicitly OUT of scope.

---

## File Structure

**New — the promotion mechanism (framework):**
- `packages/haywire-core/src/haywire/core/node/promotion.py` — id encode/decode, promote/demote on `NodeData`, the linked-port read-tier helper
- `packages/haywire-core/src/haywire/core/types/field_metadata.py` — the `FieldMetadata` Protocol

**Modified — settings read path & promote flag:**
- `packages/haywire-core/src/haywire/core/settings/base.py` — add `_promoted_port_id: str | None = None`
- `packages/haywire-core/src/haywire/core/settings/descriptor.py` — read-tier: linked promoted port wins
- `packages/haywire-core/src/haywire/core/settings/settings.py` — expose the owning node for port lookup (if not already reachable)

**Modified — UI triggers (haybale-graph-editor plugin):**
- `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/node/promote.py` — new node-menu "Promote setting ▸" panel
- `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/port/port.py` — add "Detach from setting" to the pin menu
- the corresponding `*ContextActions` for promote/demote handlers

**Modified — panel reflects promoted state:**
- `packages/haywire-core/src/haywire/ui/panel/render_utils.py` — disabled/annotated row when a field is promoted

**Tests:**
- `tests/core/node/test_promotion_id.py`
- `tests/core/node/test_promote_demote.py`
- `tests/core/settings/test_promoted_read_tier.py`
- `tests/core/node/test_promotion_serialization.py`
- `tests/core/types/test_field_metadata_protocol.py`
- `tests/ui/panel/test_promoted_row_state.py`

---

## Pre-flight Baseline

- [ ] **Step 0: Baseline**

Run:
```sh
uv run ruff check packages/haywire-core/src/ barn/haybale-graph-editor/
uv run mypy packages/haywire-core/src/ barn/haybale-graph-editor/haybale_graph_editor/
uv run pytest -m "not integration" -q
```
Expected: clean. If not, STOP and reconcile with the user.

---

## Task 1: The binding-key codec (`setting__<accessor>__<field>`)

**Files:**
- Create: `packages/haywire-core/src/haywire/core/node/promotion.py`
- Test: `tests/core/node/test_promotion_id.py`

- [ ] **Step 1: Write the failing test**

`tests/core/node/test_promotion_id.py`:
```python
import haywire.core.graph.editor  # noqa: F401

from haywire.core.node.promotion import encode_promoted_port_id, decode_promoted_port_id, is_promoted_port_id


def test_encode():
    assert encode_promoted_port_id("filter", "threshold") == "setting__filter__threshold"


def test_decode():
    assert decode_promoted_port_id("setting__filter__threshold") == ("filter", "threshold")


def test_is_promoted():
    assert is_promoted_port_id("setting__filter__threshold") is True
    assert is_promoted_port_id("regular_inlet") is False


def test_roundtrip():
    for acc, fld in [("filter", "threshold"), ("output", "scale")]:
        assert decode_promoted_port_id(encode_promoted_port_id(acc, fld)) == (acc, fld)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/node/test_promotion_id.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the codec**

`packages/haywire-core/src/haywire/core/node/promotion.py`:
```python
"""Promote a node setting to a DATA inlet.

A promoted inlet is an ordinary dynamic port whose id encodes the setting it binds:
``setting__<accessor>__<field>``. The id IS the binding key (no separate back-reference).
"""

from __future__ import annotations

_PREFIX = "setting__"
_SEP = "__"


def encode_promoted_port_id(accessor: str, field: str) -> str:
    return f"{_PREFIX}{accessor}{_SEP}{field}"


def is_promoted_port_id(port_id: str) -> bool:
    return port_id.startswith(_PREFIX) and _SEP in port_id[len(_PREFIX):]


def decode_promoted_port_id(port_id: str) -> tuple[str, str]:
    if not is_promoted_port_id(port_id):
        raise ValueError(f"Not a promoted port id: {port_id!r}")
    body = port_id[len(_PREFIX):]
    accessor, field = body.split(_SEP, 1)
    return accessor, field
```
**Note:** accessor/field names are Python identifiers (no `__`) by the settings system's rules, so
`split(_SEP, 1)` is unambiguous. If a project allows `__` in accessor names, add validation in the
promote path (Task 3) rejecting such names — but the settings accessor is a class name, so this is
safe.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/node/test_promotion_id.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/node/promotion.py tests/core/node/test_promotion_id.py
git commit -m "feat(promotion): binding-key codec for promoted setting ports

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: The `FieldMetadata` Protocol

**Files:**
- Create: `packages/haywire-core/src/haywire/core/types/field_metadata.py`
- Test: `tests/core/types/test_field_metadata_protocol.py`

- [ ] **Step 1: Write the failing test**

`tests/core/types/test_field_metadata_protocol.py`:
```python
import haywire.core.graph.editor  # noqa: F401

from haywire.core.types.field_metadata import FieldMetadata


def test_setting_descriptor_satisfies_protocol():
    from haywire.core.settings import NodeSettings, setting
    from haywire.barn.builtin.types import FLOAT

    class bag(NodeSettings):
        x = setting[FLOAT](1.0, label="X", description="d")
    d = bag.__dict__["x"]
    assert isinstance(d, FieldMetadata)  # runtime_checkable structural check


def test_extract_for_port_spec():
    """A helper projects a setting's metadata into a PortSpec-shaped dict."""
    from haywire.core.types.field_metadata import metadata_to_port_kwargs
    from haywire.core.settings import NodeSettings, setting
    from haywire.barn.builtin.types import FLOAT

    class bag(NodeSettings):
        x = setting[FLOAT](1.0, label="X")
    kwargs = metadata_to_port_kwargs(bag.__dict__["x"])
    assert kwargs["label"] == "X"
    assert kwargs["type_cls"] is FLOAT
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/types/test_field_metadata_protocol.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the protocol + projection helper**

First read `SettingDescriptor` (`packages/haywire-core/src/haywire/core/settings/base.py`) for its
attribute names (`_label`, `_description`, `_type`, `_default`, `_order`) and `DataPort`
(`packages/haywire-core/src/haywire/core/types/port.py`) for the port-side names (`label`,
`description`, `order`, `type_cls`).

`packages/haywire-core/src/haywire/core/types/field_metadata.py`:
```python
"""FieldMetadata — the structural contract shared by SettingDescriptor and DataPort.

Both already carry label/description/type/default/order. This Protocol names that shared
shape so promotion can project a setting's metadata onto a new port without a shared base
class. No runtime coupling.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class FieldMetadata(Protocol):
    """Read-only display/type metadata common to settings and ports."""

    @property
    def field_label(self) -> str: ...
    @property
    def field_description(self) -> str: ...
    @property
    def field_type(self) -> type: ...


def metadata_to_port_kwargs(descriptor: Any) -> dict:
    """Project a SettingDescriptor's metadata into kwargs for a PortSpec (as_inlet).

    Reads the descriptor's underscore-prefixed attrs; returns the port-side names.
    """
    return {
        "label": getattr(descriptor, "_label", "") or getattr(descriptor, "_attr_name", ""),
        "description": getattr(descriptor, "_description", ""),
        "order": getattr(descriptor, "_order", 0),
        "type_cls": getattr(descriptor, "_type"),
    }
```
**Decision:** the `@runtime_checkable` Protocol checks methods/properties, not bare attributes.
Since `SettingDescriptor` exposes `_label` (not `field_label`), make the Protocol's checked members
match what BOTH actually have. Simplest: check the projection helper works (the second test) and
make the Protocol assert on attributes both share — read both classes and pick the common surface.
If a clean structural Protocol is awkward because the attribute names differ
(`_label` vs `label`), it is acceptable to make `FieldMetadata` a documentation-only Protocol and
rely on `metadata_to_port_kwargs` as the real bridge; adjust the first test to assert the helper
rather than `isinstance`. Record the choice for the deviations file.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/types/test_field_metadata_protocol.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/types/field_metadata.py tests/core/types/test_field_metadata_protocol.py
git commit -m "feat(promotion): FieldMetadata protocol + setting->port projection

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Promote / demote on `NodeData`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/node/promotion.py` (add `promote_setting`/`demote_setting`)
- Modify: `packages/haywire-core/src/haywire/core/settings/base.py` (add `_promoted_port_id`)
- Test: `tests/core/node/test_promote_demote.py`

- [ ] **Step 1: Write the failing test**

`tests/core/node/test_promote_demote.py`:
```python
import haywire.core.graph.editor  # noqa: F401
import pytest

# Build a minimal node with a promotable setting. Mirror an existing node-construction
# test in tests/core/node/ for the wrapper/instance setup.


@pytest.mark.integration
def test_promote_creates_inlet(make_node_with_setting):  # fixture: see Step 3 note
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting, encode_promoted_port_id

    promote_setting(node, "filter", "threshold")
    pid = encode_promoted_port_id("filter", "threshold")
    assert pid in node.ports
    assert node.ports[pid].is_inlet()


@pytest.mark.integration
def test_demote_removes_inlet(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting, demote_setting, encode_promoted_port_id

    promote_setting(node, "filter", "threshold")
    demote_setting(node, "filter", "threshold")
    assert encode_promoted_port_id("filter", "threshold") not in node.ports
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/node/test_promote_demote.py -v -m integration`
Expected: FAIL — `promote_setting` not defined (and the fixture must be written).

- [ ] **Step 3: Implement promote/demote**

Read `packages/haywire-core/src/haywire/core/node/data.py` for the `rejig`/`add` API and how a
`PortSpec` is built (`FLOAT.as_inlet(id, ...)` returns a spec). Read how `StoreStrategy.NEVER` is
passed to `as_inlet` (it is a kwarg per `enums.py`). Add to `promotion.py`:
```python
from haywire.core.types.enums import StoreStrategy, ShowWidgetStrategy
from haywire.core.types.field_metadata import metadata_to_port_kwargs


def _descriptor(node, accessor: str, field: str):
    bag = getattr(node, accessor)
    return type(bag).__dict__[field]  # the setting descriptor


def promote_setting(node, accessor: str, field: str) -> None:
    """Create a DATA inlet bound to a plain setting field. No-op if already promoted."""
    pid = encode_promoted_port_id(accessor, field)
    if pid in node.ports:
        return
    desc = _descriptor(node, accessor, field)
    if getattr(desc, "_mirror_key", ""):
        raise ValueError("shadow()/watch() fields are not promotable")
    kw = metadata_to_port_kwargs(desc)
    type_cls = kw.pop("type_cls")
    spec = type_cls.as_inlet(
        pid,
        store_strategy=StoreStrategy.NEVER,
        show_widget=ShowWidgetStrategy.NEVER,   # no widget on the promoted inlet (v1)
        **kw,
    )
    with node.rejig(include=[pid]):  # add without disturbing other ports
        node.add(spec)
    desc._promoted_port_id = pid


def demote_setting(node, accessor: str, field: str) -> None:
    pid = encode_promoted_port_id(accessor, field)
    if pid not in node.ports:
        return
    node.remove_port(pid)  # read data.py for the exact removal API name
    _descriptor(node, accessor, field)._promoted_port_id = None
```
**Verify before relying on it:** the exact methods on `NodeData` — `add`, `rejig`, and the
single-port removal call (the exploration found a `_pop`/removal path; read `data.py` and use the
public method, e.g. `remove_port` or a `rejig`-based removal). The `as_inlet(..., store_strategy=,
show_widget=)` kwargs must match `interface.py:225`'s signature. Adjust names to reality; do not
invent.

In `packages/haywire-core/src/haywire/core/settings/base.py`, add the flag to `SettingDescriptor`:
```python
_promoted_port_id: "str | None" = None
"""Set by promote_setting; the id of the DATA inlet bound to this field, else None."""
```

For the **fixture** (`make_node_with_setting`): write it in `tests/core/node/conftest.py` mirroring
an existing node-instance construction test. It must return a live `NodeData`-bearing instance with
a `class filter(NodeSettings): threshold = setting[FLOAT](0.5)` accessor.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/node/test_promote_demote.py -v -m integration`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/node/promotion.py packages/haywire-core/src/haywire/core/settings/base.py tests/core/node/
git commit -m "feat(promotion): promote/demote a setting to a DATA inlet via rejig

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Read-tier — linked promoted port overrides the resolution chain

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/descriptor.py`
- Test: `tests/core/settings/test_promoted_read_tier.py`

**Performance constraint (from design):** the new check must be a single `is None` test on a
per-descriptor attribute, inside the EXISTING extended-mode branch. Unpromoted settings must pay
~nothing.

- [ ] **Step 1: Write the failing test**

`tests/core/settings/test_promoted_read_tier.py`:
```python
import haywire.core.graph.editor  # noqa: F401
import pytest


@pytest.mark.integration
def test_connected_promoted_inlet_overrides_setting(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting, encode_promoted_port_id

    promote_setting(node, "filter", "threshold")
    pid = encode_promoted_port_id("filter", "threshold")

    # Simulate an upstream-driven value on the (linked) port.
    # Use the test harness's edge-link helper; mirror an existing edge test in tests/core/edge/.
    _link_and_push(node, pid, 0.9)   # helper: links an edge and pushes 0.9

    assert node.filter.threshold == 0.9   # port wins over the setting's resolved value


@pytest.mark.integration
def test_disconnected_promoted_inlet_falls_back_to_setting(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting

    promote_setting(node, "filter", "threshold")
    # not linked -> normal resolution
    assert node.filter.threshold == 0.5   # the setting default
```

- [ ] **Step 2: Run it to verify failure**

Run: `uv run pytest tests/core/settings/test_promoted_read_tier.py -v -m integration`
Expected: FAIL — the read path ignores the port.

- [ ] **Step 3: Insert the read-tier**

In `descriptor.py __get__`, inside the existing extended-mode branch
(`if self._setting_key and getattr(obj, "_registry", None) is not None:`), add the top tier BEFORE
`_resolve`:
```python
        if self._setting_key and getattr(obj, "_registry", None) is not None:
            pid = self._promoted_port_id            # one attribute read; None for unpromoted
            if pid is not None:
                node = getattr(obj, "_node", None)  # the owning NodeData; confirm the attr name
                port = node.ports.get(pid) if node is not None else None
                if port is not None and port.is_linked():
                    return port.get_value()
            return obj._resolve(self._setting_key, self._mirror_key, self._default)
```
**Verify:** how a `Settings` instance reaches its owning `NodeData`. Read `node_settings.py` /
`settings.py` — there is a node back-reference set at construction (the `@node` decorator binds the
bag to `self.<accessor>`). Use the real attribute; if none exists, add one in `node_settings.py`
where the bag is instantiated. Keep the unpromoted path to exactly one `is None` check.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/settings/test_promoted_read_tier.py -v -m integration`
Expected: PASS (both)

- [ ] **Step 5: Add a perf guard test (unpromoted path stays flat)**

Append a non-integration test asserting the unpromoted read does not touch ports:
```python
def test_unpromoted_read_does_not_touch_ports(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    # _promoted_port_id is None -> __get__ must not call node.ports.get
    node.ports = _RaiseOnGet()   # a stub whose .get raises
    assert node.filter.threshold == 0.5   # resolves without consulting ports
```
(Define `_RaiseOnGet` locally; if `node.ports` isn't directly settable, assert via a spy that
`ports.get` was never called instead.)

- [ ] **Step 6: Run + commit**

Run: `uv run pytest tests/core/settings/test_promoted_read_tier.py -v`
Expected: PASS.
```bash
git add packages/haywire-core/src/haywire/core/settings/ tests/core/settings/test_promoted_read_tier.py
git commit -m "feat(promotion): linked promoted inlet overrides setting resolution

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Serialization round-trip (port persists, value does not, re-bind on load)

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/node/base.py` (re-bind hook after `_deserialize_ports`)
- Test: `tests/core/node/test_promotion_serialization.py`

**Design rules:** the promoted port serializes as an ordinary dynamic port (existing machinery);
its **value never persists** (`store_strategy=NEVER`); on load, a hook re-sets each promoted
descriptor's `_promoted_port_id` from the restored ports (id ⇒ accessor/field via the codec).

- [ ] **Step 1: Write the failing test**

`tests/core/node/test_promotion_serialization.py`:
```python
import haywire.core.graph.editor  # noqa: F401
import pytest


@pytest.mark.integration
def test_promoted_port_roundtrips_and_rebinds(make_node_with_setting, reload_node):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting, encode_promoted_port_id

    promote_setting(node, "filter", "threshold")
    data = node._to_dict()

    pid = encode_promoted_port_id("filter", "threshold")
    # The port is serialized; its value is NOT (store_strategy=NEVER).
    assert any(p.get("id") == pid for p in data["ports"])

    restored = reload_node(data)   # helper: build a fresh node, _initialize_from_dict(data)
    assert pid in restored.ports
    # The descriptor was re-bound on load:
    desc = type(getattr(restored, "filter")).__dict__["threshold"]
    assert desc._promoted_port_id == pid
```

- [ ] **Step 2: Run it to verify failure**

Run: `uv run pytest tests/core/node/test_promotion_serialization.py -v -m integration`
Expected: FAIL — after load, `_promoted_port_id` is None (no re-bind hook).

- [ ] **Step 3: Add the re-bind hook**

In `packages/haywire-core/src/haywire/core/node/base.py` `_initialize_from_dict`, AFTER
`self._deserialize_ports(data["ports"])`, add a re-bind pass:
```python
        # Re-bind promoted-setting ports to their descriptors (id encodes accessor/field).
        from haywire.core.node.promotion import is_promoted_port_id, decode_promoted_port_id

        for port_id in self.ports:
            if not is_promoted_port_id(port_id):
                continue
            accessor, field = decode_promoted_port_id(port_id)
            bag = getattr(self, accessor, None)
            if bag is None:
                continue
            desc = type(bag).__dict__.get(field)
            if desc is not None:
                desc._promoted_port_id = port_id
```
Confirm `store_strategy=NEVER` already excludes the value from `_serialize_ports` (it does, per
`enums.py` `should_store`); no value-stripping code is needed. Verify by inspecting `data["ports"]`
in the test — the promoted port entry must carry no stored value field.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/node/test_promotion_serialization.py -v -m integration`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/node/base.py tests/core/node/test_promotion_serialization.py
git commit -m "feat(promotion): round-trip promoted ports, re-bind descriptors on load

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Node-menu "Promote setting ▸" + pin-menu "Detach from setting"

**Files:**
- Create: `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/node/promote.py`
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/port/port.py`
- Modify/Create: the matching `*ContextActions` handlers
- Test: `tests/ui/menu/test_promote_demote_menu.py`

**Background:** the menu-panel pattern is `@panel(actions=..., focus=NodeFocus|PinFocus, ...)` with
`poll()` + `draw()`. Read `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/port/port.py`
(the existing `PortInfoMenuPanel`) for the exact shape, and `.../focuses.py` for `NodeFocus`/`PinFocus`.

- [ ] **Step 1: Write the failing test**

`tests/ui/menu/test_promote_demote_menu.py`:
```python
import haywire.core.graph.editor  # noqa: F401
import pytest


def test_promote_panel_lists_plain_settings_only():
    """The promote submenu enumerates plain setting() fields, excluding shadow/watch
    and already-promoted ones."""
    from haybale_graph_editor.panels.graph.menu.node.promote import promotable_fields

    # Build a node with one plain setting, one watch() field.
    # Mirror tests/core/node fixtures.
    node = ...  # make_node_with_setting + a watch() field
    fields = promotable_fields(node)
    assert ("filter", "threshold") in fields
    assert all("watch" not in acc for acc, _ in fields)
```

- [ ] **Step 2: Run it to verify failure**

Run: `uv run pytest tests/ui/menu/test_promote_demote_menu.py -v`
Expected: FAIL — module/function missing.

- [ ] **Step 3: Implement `promotable_fields` + the node-menu panel**

`barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/node/promote.py`:
```python
"""Node right-click 'Promote setting ▸' submenu."""

from __future__ import annotations
from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

from haywire.core.node.promotion import promote_setting, encode_promoted_port_id

from .....focuses import NodeFocus
from .....state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


def promotable_fields(node) -> list[tuple[str, str]]:
    """(accessor, field) for every plain setting() that is not shadow/watch and not
    already promoted."""
    out: list[tuple[str, str]] = []
    for accessor in type(node)._settings_bags:           # confirm the attr name in base.py
        bag = getattr(node, accessor)
        for field, desc in type(bag).__dict__.items():
            if not hasattr(desc, "_setting_key"):
                continue
            if getattr(desc, "_mirror_key", ""):         # shadow/watch -> skip
                continue
            if getattr(desc, "_promoted_port_id", None): # already promoted -> skip (or mark)
                continue
            out.append((accessor, field))
    return out


@panel(actions=..., focus=NodeFocus, label="Promote setting", icon=hui.icon.add, order=50)
class PromoteSettingMenuPanel(BasePanel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        node = ctx.data[EditState].active_node
        return node is not None and bool(promotable_fields(node))

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        node = ctx.data[EditState].active_node
        if node is None:
            return
        with layout.container:
            for accessor, field in promotable_fields(node):
                label = f"{accessor}.{field}"
                hui.menu_item(label, on_click=lambda a=accessor, f=field: promote_setting(node, a, f))
```
**Verify:** the `@panel` `actions=` requirement (the port panel uses a `PortContextActions` marker —
create/reuse an analogous `NodeContextActions` or the existing node-menu actions class); the
`hui.menu_item`/click idiom (read how the existing node menu panels render clickable rows); and
`type(node)._settings_bags` (the attr listing accessors — confirm in `node/base.py`). After
`promote_setting`, the menu must trigger a node redraw so the new pin appears (read how other menu
actions request a redraw — likely via the context-menu action/close callback; do NOT mutate-and-
redraw the same container mid-draw — see `.insights/feedback_nicegui_redraw_deletes_handler_slot.md`).

- [ ] **Step 4: Add "Detach from setting" to the pin menu**

In `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/port/port.py`, add a panel (or a
row in the existing one) shown only when the active port is a promoted port:
```python
from haywire.core.node.promotion import is_promoted_port_id, decode_promoted_port_id, demote_setting

@panel(actions=PortContextActions, focus=PinFocus, label="Detach from setting", icon=hui.icon.delete, order=20)
class DetachSettingMenuPanel(BasePanel):
    @classmethod
    def poll(cls, ctx) -> bool:
        port = ctx.data[EditState].active_port
        return port is not None and is_promoted_port_id(port.id)

    def draw(self, ctx, layout) -> None:
        port = ctx.data[EditState].active_port
        node = ...  # the owning node from ctx (read how port.py reaches the node/active_node)
        with layout.container:
            def _detach():
                acc, fld = decode_promoted_port_id(port.id)
                demote_setting(node, acc, fld)
            hui.menu_item("Detach from setting", on_click=_detach)
```
Confirm how the pin menu reaches the owning node (via `active_node`, or `port._wrapper`).

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/ui/menu/test_promote_demote_menu.py -v`
Expected: PASS (complete the fixture in Step 1 mirroring node tests).

- [ ] **Step 6: Commit**

```bash
git add barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/ tests/ui/menu/
git commit -m "feat(promotion): node-menu promote submenu + pin-menu detach

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Properties row reflects promoted state

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/panel/render_utils.py`
- Test: `tests/ui/panel/test_promoted_row_state.py`

**Requirement (from design):** when a field is promoted, its panel row must show it as
driven-by-inlet (widget disabled / annotated) so the panel doesn't silently lie. No trigger lives
here — display only.

- [ ] **Step 1: Write the failing test**

`tests/ui/panel/test_promoted_row_state.py`:
```python
import haywire.core.graph.editor  # noqa: F401
import pytest

pytestmark = pytest.mark.integration


def test_promoted_field_row_is_marked(make_node_with_setting, render_settings_bag):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting

    promote_setting(node, "filter", "threshold")
    dom = render_settings_bag(node.filter)   # helper: render + return DOM/props
    row = dom.field("threshold")
    assert row.has_attr("data-promoted")     # the marker added in Step 3
```

- [ ] **Step 2: Run it to verify failure**

Run: `uv run pytest tests/ui/panel/test_promoted_row_state.py -v -m integration`
Expected: FAIL — no `data-promoted` marker.

- [ ] **Step 3: Mark promoted rows in `_render_reactive_field_row`**

In `render_utils.py` `_render_reactive_field_row`, detect promotion and annotate the row:
```python
    is_promoted = getattr(defn, "_promoted_port_id", None) is not None
    # on the row container, add the marker + disable the control when promoted:
    # ...props(f'data-field="{attr_name}"' + (' data-promoted="true"' if is_promoted else ''))
    # and, when is_promoted, render the widget disabled / append a "↳ driven by inlet" hint.
```
Reuse the existing label/widget build path; when `is_promoted`, pass a disabled flag to the widget
build (or overlay a non-interactive state) and append a small hint via `hui`. Keep the value display
live (it now shows the port-driven value through the read-tier from Task 4). Read the row-building
code around `_render_label`/`_build_field_widget` and thread a `disabled`/`promoted` flag through.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/ui/panel/test_promoted_row_state.py -v -m integration`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/panel/render_utils.py tests/ui/panel/test_promoted_row_state.py
git commit -m "feat(promotion): properties row reflects promoted (inlet-driven) state

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: End-to-end + full gate

**Files:**
- Test: `tests/ui/menu/test_promotion_e2e.py`

- [ ] **Step 1: Write the integration test**

`tests/ui/menu/test_promotion_e2e.py`:
```python
import pytest
import haywire.core.graph.editor  # noqa: F401

pytestmark = pytest.mark.integration


def test_full_promote_drive_demote_cycle(make_graph_with_two_nodes):
    """Promote a setting, wire an upstream outlet to the new inlet, confirm the worker
    reads the driven value, then demote."""
    # 1. promote node.filter.threshold -> inlet
    # 2. link upstream FLOAT outlet -> the promoted inlet
    # 3. run/evaluate; assert the node's worker saw the driven value (not the setting default)
    # 4. demote; assert the inlet is gone and the setting resolves normally again
    # Mirror an existing two-node execution test in tests/ for the harness.
    ...
```
Fill the body from an existing two-node execution integration test (search `tests/` for an edge-
link + evaluate harness). This is the proof the read-tier + assembly path actually drives a worker.

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/ui/menu/test_promotion_e2e.py -v -m integration`
Expected: PASS

- [ ] **Step 3: Full suite + boot**

Run:
```bash
uv run pytest -q
uv run haywire   # boot; right-click a node -> Promote setting; wire it; confirm; then stop
```
Expected: green suite; the promote submenu appears on nodes with plain settings; a wired inlet
drives the value; pin right-click detaches.

- [ ] **Step 4: Full quality gate**

Run:
```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ barn/haybale-graph-editor/haybale_graph_editor/
uv run pytest -q
```
Expected: all clean.

- [ ] **Step 5: Commit**

```bash
git add tests/ui/menu/test_promotion_e2e.py
git commit -m "test(promotion): end-to-end promote/drive/demote cycle

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review Notes

- **Promotable = plain `setting()` only.** `shadow()`/`watch()` are excluded (checked via
  `_mirror_key`); `watch()` is read-only by contract. The promote submenu filters them out.
- **No widget on the promoted inlet (v1):** `ShowWidgetStrategy.NEVER` at creation. Editing stays in
  the Properties panel; the row is marked promoted (Task 7). View-onto-setting on-card widget is OUT
  of scope.
- **Value never persists:** `StoreStrategy.NEVER`. The setting override remains the only stored
  value; the port re-binds on load via the codec (Task 5).
- **Perf:** the read-tier is one `is None` check inside the existing extended-mode branch (Task 4
  Step 3). The perf-guard test (Task 4 Step 5) asserts unpromoted reads never touch `node.ports`.
- **Depends on Plans 1 and 2.** Task 0 gates. The promote/demote handlers, the read-tier node
  back-reference, and the `_settings_bags`/`rejig`/`remove_port` API names are the most likely
  reality-vs-assumption gaps — each task says "read the source, use the real name, do not invent."
- **NiceGUI redraw trap:** the promote action adds a port and must redraw the node to show the pin —
  do this via the menu's close/action callback, never by mutating + redrawing the menu's own
  container mid-draw (`.insights/feedback_nicegui_redraw_deletes_handler_slot.md`).