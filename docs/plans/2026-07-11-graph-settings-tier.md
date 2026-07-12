# Graph-level Settings Tier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Graphs own a settings bag (`graph.props`) so interposed fields resolve framework < graph < node — concretely: a per-graph default node skin that unset nodes track live.

**Architecture:** A fourth Settings flavour (`GraphSettings`, parallel to `NodeSettings`) holds graph-local cells. Chained mirrors realize the tier: the graph bag's field `shadow()`s the framework setting (existing registry-key mirror), and the node field declares `graph(src=...)` — a new **graph mirror** factory that marks the descriptor explicitly (`is_graph_mirror`) and validates its src eagerly. At wiring time the node bag locates the graph bag through one seam (`BaseGraph.settings_bag_for()`) and syncs cell-to-cell: the node keeps its OWN cell and *listens* (never borrows — a locally-set node value must diverge). "Unset tracks, set ignores" applies per hop and composes transitively. **Detachment contract:** a graph-mirror field on a bag with no reachable graph holds its descriptor default and is not live — there is no registry fallback (no production path constructs such a bag; a `NodeWrapper`'s graph is a non-optional constructor argument). All propagation rides the existing cell-event machinery (ADR 0013); `SettingsRegistry.resolve()` and the workspace/global tiers are untouched.

**Tech Stack:** Python 3.12, uv workspace monorepo, pytest (markers: `unit`, `integration`), ruff, mypy, NiceGUI panels (graph-editor haybale).

**Source docs:** Spec `.scratch/issues/graph-settings-tier.md` (Implementation Decisions binding; NOTE two amendments settled after the spec was written and recorded here + in the ADR: the explicit `graph()` factory replaces src-kind inference, and the headless terminal-key fallback was dropped in favour of the detachment contract above). Tickets `.scratch/graph-settings-tier/issues/01…05`. Settings internals: `docs/architecture/settings/settings-arch.md`, ADRs 0013/0014/0019/0020.

> **Amendment (post-implementation, see ADR 0022):** every code snippet below
> that imports `NodeDefaultSkinSettings` / `_node_skin_choices` from
> `haywire.ui.skin.settings` reflects a pre-existing core→ui layering
> violation this plan initially reproduced rather than fixed (`graph/properties.py`
> importing from `haywire.ui.skin.settings`, mirroring the same violation
> already present in `node/properties.py`). On review this was corrected at
> the root: `haywire.ui.skin.settings` — despite its path, a pure
> `FrameworkSettings` schema with no NiceGUI/rendering dependency, unlike its
> sibling `ui/skin/base.py` — was moved to `haywire.core.skin.settings`. Every
> import shown below as `from haywire.ui.skin.settings import ...` should be
> read as `from haywire.core.skin.settings import ...` in the actual, final
> code.

## Global Constraints

- Test imports: `import haywire.core.graph.editor  # noqa: F401` must be the first haywire import in every new test file (circular-import guard, CLAUDE.md).
- Quality gates after every task, all must pass with no new findings:
  - `uv run pytest`
  - `uv run ruff check .`
  - `uv run ruff format --check .` (run `uv run ruff format .` to fix drift)
  - `uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/`
- Ruff line-length = 109.
- Settings are IType-only; never bypass `_cell_for`; never infer set-ness from cell values (`_set_keys` carries the opinion).
- Do NOT modify `SettingsRegistry.resolve()`, the tier dicts, or JSON persistence.
- The framework key used in tier tests is `ui.node.default.skin.studio_skin` (namespace `NAMESPACE_UI_NODE_DEFAULT_SKIN = "ui.node.default.skin"` in `haywire/core/namespaces.py`).
- The next free ADR number is **0022** (0021 is taken by `0021-watch-as-shadow-preset.md` — verify with `ls docs/adr/` before writing).
- Commit after every task. Messages: `feat(settings): …` / `feat(graph): …` / `docs: …` as given per task.

**Pre-flight baseline (run once before Task 1):**

```sh
uv run ruff check packages/haywire-core/src/haywire/core/settings/ packages/haywire-core/src/haywire/core/graph/ packages/haywire-core/src/haywire/core/node/
uv run mypy packages/haywire-core/src/
uv run pytest tests/core/test_settings tests/core/test_graph -q
```

Expected: all clean (the codebase has no pre-existing errors; if not, STOP and report instead of proceeding).

---

### Task 1: `GraphSettings` flavour, `GraphProperties` bag, and the `graph()` factory

One reviewable unit: the flavour, the one framework bag, and the declaration API that points node fields at it. The graph→framework hop uses the EXISTING registry-key mirror — nothing new fires there. The `graph()` factory needs `GraphSettings` for its eager validation, which is why flavour and factory land together.

**Files:**
- Create: `packages/haywire-core/src/haywire/core/settings/graph_settings.py`
- Create: `packages/haywire-core/src/haywire/core/graph/properties.py`
- Modify: `packages/haywire-core/src/haywire/core/settings/base.py` (`_owner_cls` recording in `__set_name__`)
- Modify: `packages/haywire-core/src/haywire/core/settings/descriptor.py` (`_graph_mirror` flag, `is_graph_mirror` property, `graph()` factory)
- Modify: `packages/haywire-core/src/haywire/core/settings/__init__.py` (exports)
- Test: `tests/core/test_settings/test_graph_settings.py` (new)

**Interfaces:**
- Consumes: `Settings.__init__(registry, node)`; `shadow()`; `NodeDefaultSkinSettings.studio_skin` + `_node_skin_choices` from `haywire.ui.skin.settings` (same import `node/properties.py` already does).
- Produces: `GraphSettings(Settings)` with `__init__(registry=None, graph=None)`, `_graph` backref, `_node` always `None`. `GraphProperties(GraphSettings)` with field `default_skin`. `SettingDescriptor._owner_cls: type | None`. `setting.is_graph_mirror -> bool` (property over the `_graph_mirror` flag). `graph(src, **kwargs) -> setting` factory (raises `TypeError` unless src lives on a `GraphSettings` subclass). Exported: `from haywire.core.settings import GraphSettings, graph`. Tasks 2–5 rely on these exact names.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_settings/test_graph_settings.py`:

```python
"""GraphSettings flavour + GraphProperties bag + graph() factory (ADR 0022, ticket 01).

The graph→framework hop is the EXISTING registry-key mirror; these tests
prove it works on a graph-owned bag (unset tracks, set wins, reset resumes)
and that the graph() declaration API validates eagerly.
"""

import haywire.core.graph.editor  # noqa: F401  (circular-import guard, per CLAUDE.md)

import pytest

from haywire.core.di.test_config import create_test_settings_registry
from haywire.core.graph.properties import GraphProperties
from haywire.core.settings import GraphSettings, NodeSettings, graph
from haywire.ui.skin.settings import NodeDefaultSkinSettings

pytestmark = [pytest.mark.unit, pytest.mark.core]

SKIN_KEY = "ui.node.default.skin.studio_skin"


def _make_bag():
    registry = create_test_settings_registry()  # registers builtin FrameworkSettings
    bag = GraphProperties(registry=registry, graph=None)
    bag._subscribe_settings()
    return registry, bag


def test_flavour_shape():
    registry, bag = _make_bag()
    assert isinstance(bag, GraphSettings)
    assert bag._node is None          # promotion guard keys on this
    assert bag._graph is None         # standalone bag; BaseGraph sets it (Task 2)


def test_owner_cls_recorded_by_set_name():
    assert GraphProperties.default_skin._owner_cls is GraphProperties
    assert NodeDefaultSkinSettings.studio_skin._owner_cls is NodeDefaultSkinSettings


def test_graph_factory_sets_flag():
    class NB(NodeSettings):
        f = graph(src=GraphProperties.default_skin)

    assert NB.f.is_graph_mirror is True
    # The graph bag's own field is a plain registry-key mirror, NOT a graph mirror.
    assert GraphProperties.default_skin.is_graph_mirror is False
    assert GraphProperties.default_skin.is_mirror is True


def test_graph_factory_rejects_non_graphsettings_src():
    with pytest.raises(TypeError, match="GraphSettings"):
        graph(src=NodeDefaultSkinSettings.studio_skin)  # a FrameworkSettings field


def test_unset_tracks_framework_value():
    registry, bag = _make_bag()
    registry.set_global(SKIN_KEY, "skin-A")
    assert bag.default_skin == "skin-A"
    registry.set_global(SKIN_KEY, "skin-B")
    assert bag.default_skin == "skin-B"


def test_local_set_wins_and_reset_resumes_tracking():
    registry, bag = _make_bag()
    registry.set_global(SKIN_KEY, "skin-A")
    bag.default_skin = "skin-local"
    assert bag.default_skin == "skin-local"
    assert bag.is_locally_set("default_skin")
    registry.set_global(SKIN_KEY, "skin-C")
    assert bag.default_skin == "skin-local"   # set ignores
    bag.reset("default_skin")
    assert bag.default_skin == "skin-C"       # back on the chain
    registry.set_global(SKIN_KEY, "skin-D")
    assert bag.default_skin == "skin-D"       # tracking resumed


def test_subscribe_fires_on_framework_change():
    registry, bag = _make_bag()
    seen: list[tuple] = []
    bag.subscribe(lambda name, value, old: seen.append((name, value)))
    registry.set_global(SKIN_KEY, "skin-E")
    assert ("default_skin", "skin-E") in seen


def test_promotion_unavailable():
    registry, bag = _make_bag()
    from haywire.core.types.enums import PortType

    with pytest.raises(ValueError):
        bag.promote("default_skin", PortType.INLET)


def test_cleanup_detaches_registry_subscription():
    registry, bag = _make_bag()
    registry.set_global(SKIN_KEY, "skin-A")
    bag.cleanup()
    registry.set_global(SKIN_KEY, "skin-Z")
    # The dead bag must not have been re-synced (cell untouched after cleanup).
    desc = type(bag)._property_settings()["default_skin"]
    assert bag._cell_for(desc).get_value() == "skin-A"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_settings/test_graph_settings.py -v`
Expected: FAIL — `ImportError: cannot import name 'GraphSettings'` (via the settings-package import).

- [ ] **Step 3: Implement — owner recording in base.py**

In `packages/haywire-core/src/haywire/core/settings/base.py`, add a class attribute next to `_attr_name` (after line 31's docstring):

```python
    _owner_cls: "type | None" = None
    """Class this descriptor was declared on, recorded by ``__set_name__``.
    Graph mirrors use it to locate 'the instance of that bag on my graph'
    (``BaseGraph.settings_bag_for``). ADR 0022."""
```

And in `__set_name__` (line 68), directly after `self._attr_name = name`:

```python
        self._owner_cls = owner
```

- [ ] **Step 4: Implement — the flavour**

Create `packages/haywire-core/src/haywire/core/settings/graph_settings.py`:

```python
# haywire/core/settings/graph_settings.py
"""
GraphSettings — base class for graph-owned settings bags.

The fourth Settings flavour (ADR 0022), parallel to NodeSettings:

- Per-instance DataField cells; never registered with SettingsRegistry.
- Owned by a BaseGraph (``graph.props``), serialized into the graph JSON
  (restored BEFORE nodes on load, so node-bag graph mirrors seed correctly).
- Carries a ``_graph`` backref instead of a node backref. ``_node`` stays
  None, which keeps every node-only surface — promotion, the setting-row
  menu's promote entries — structurally disabled.
- Fields may ``shadow()`` framework/library settings exactly like node
  bags; node-bag fields may in turn declare ``graph(src=<field here>)``
  (a graph mirror), giving the framework < graph < node resolution chain.
"""

from typing import TYPE_CHECKING

from .settings import Settings

if TYPE_CHECKING:
    from haywire.core.graph.base import BaseGraph
    from haywire.core.settings.registry import SettingsRegistry


class GraphSettings(Settings):
    """Base class for graph-local settings bags.

    Instantiated by ``BaseGraph`` with the DI registry; never registered
    with SettingsRegistry as a class. A graph has no ports, so promotion
    is structurally unavailable (``_node`` is always None).
    """

    def __init__(
        self,
        registry: "SettingsRegistry | None" = None,
        graph: "BaseGraph | None" = None,
    ) -> None:
        super().__init__(registry=registry, node=None)
        # Back-reference to the owning graph (None for standalone/test
        # bags). The graph-side analogue of Settings._node.
        self._graph: "BaseGraph | None" = graph
```

- [ ] **Step 5: Implement — the `graph()` factory + flag**

In `packages/haywire-core/src/haywire/core/settings/descriptor.py`:

(a) In `setting.__init__` (~line 265), next to `self._attr_name = ""`:

```python
        self._graph_mirror: bool = False  # set True by the graph() factory (ADR 0022)
```

(b) Directly after the existing `is_mirror` property (~line 330):

```python
    @property
    def is_graph_mirror(self) -> bool:
        """True for a field declared via the ``graph()`` factory — a mirror
        of a field on the owning graph's settings bag (GraphSettings).

        Wired cell-to-cell against the graph bag's live cell ('unset tracks,
        set ignores', per hop) — NOT through the registry-key channel
        (``is_mirror`` is False for these: the src has no ``_setting_key``).
        ADR 0022."""
        return self._graph_mirror
```

(c) After the `watch()` factory (end of file):

```python
def graph(src: "setting[T]", **kwargs: Any) -> "setting[T]":
    """Mirror of a field on the owning graph's settings bag (GraphSettings).

    The graph-tier analogue of ``shadow()``: while unset, the field tracks
    the graph bag's live value; a local set wins; ``reset()`` returns to the
    graph's CURRENT value. Requires a graph-attached bag (node → wrapper →
    graph) to be live; a detached bag (tests, standalone construction) holds
    the descriptor default and does not track — there is no registry
    fallback (ADR 0022).

    Validates eagerly: *src* must be a field declared on a ``GraphSettings``
    subclass (e.g. ``GraphProperties.default_skin``). For framework/library
    settings use ``shadow()``/``watch()``.
    """
    from haywire.core.settings.graph_settings import GraphSettings

    owner = getattr(src, "_owner_cls", None)
    if not (isinstance(owner, type) and issubclass(owner, GraphSettings)):
        raise TypeError(
            f"graph(src=...) requires a field declared on a GraphSettings subclass; "
            f"got {src!r} (owner: {owner!r}). For framework/library settings use shadow()."
        )
    s = setting(mirrors=src, **kwargs)
    s._graph_mirror = True
    return s
```

- [ ] **Step 6: Implement — the bag**

Create `packages/haywire-core/src/haywire/core/graph/properties.py`:

```python
# haywire/core/graph/properties.py
"""
GraphProperties — framework-provided per-graph props (``graph.props``).

The graph-side analogue of NodeProperties. Fields here interpose the graph
tier between framework defaults and per-node opinions: each field shadows
a framework setting (registry-key mirror), and node-bag fields may declare
``graph(src=<field here>)`` (graph mirror), yielding framework < graph <
node.

Serialized under the ``'props'`` key in graph JSON; restored before nodes
on load. ADR 0022.
"""

from haywire.core.settings.descriptor import shadow
from haywire.core.settings.graph_settings import GraphSettings
from haywire.ui.skin.settings import NodeDefaultSkinSettings, _node_skin_choices


class GraphProperties(GraphSettings):
    """Framework props available on every graph as ``graph.props``."""

    default_skin = shadow(
        src=NodeDefaultSkinSettings.studio_skin,
        label="Default Node Skin",
        description=(
            "Default skin for nodes in THIS graph. Overrides the studio "
            "default; a node's own skin setting overrides this."
        ),
        category="appearance",
        order=10,
        # Mirrors inherit IType (-> CHOICES/SELECT_WIDGET) from src, but NOT
        # its per-setting widget_config — options must be re-supplied here.
        widget_config={"options": _node_skin_choices},
    )
```

- [ ] **Step 7: Export flavour + factory**

In `packages/haywire-core/src/haywire/core/settings/__init__.py`: after `from .node_settings import NodeSettings` add

```python
from .graph_settings import GraphSettings
```

change the descriptor import line to

```python
from .descriptor import setting, shadow, watch, graph, Promotable, UiState
```

and add `"GraphSettings",` (after `"NodeSettings",`) and `"graph",` (after `"watch",`) to `__all__`. (Do NOT export `GraphProperties` from the settings package — it lives in the graph package, like `NodeProperties` lives in the node package.)

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_settings/test_graph_settings.py -v`
Expected: PASS (9 tests). If `test_unset_tracks_framework_value` fails with a KeyError on `SKIN_KEY`, the builtin schemas didn't register — check `create_test_settings_registry()` drained `_pending_global` (it must; `NodeDefaultSkinSettings` is a `FrameworkSettings`).

- [ ] **Step 9: Gates + commit**

Run the Global Constraints gates. Then:

```bash
git add packages/haywire-core/src/haywire/core/settings/graph_settings.py packages/haywire-core/src/haywire/core/graph/properties.py packages/haywire-core/src/haywire/core/settings/base.py packages/haywire-core/src/haywire/core/settings/descriptor.py packages/haywire-core/src/haywire/core/settings/__init__.py tests/core/test_settings/test_graph_settings.py
git commit -m "feat(settings): GraphSettings flavour, GraphProperties bag, graph() mirror factory (ADR 0022)"
```

---

### Task 2: `BaseGraph` owns the bag — `graph.props`, `settings_bag_for()`, `cleanup()`

> **Amendment (post-implementation, see ADR 0022's "Rejected alternatives"):** the
> `settings_registry=` constructor parameter and its try/except-tolerant-of-no-DI
> body described in this task's steps below were REMOVED on review — a
> `BaseGraph`-only injection mechanism added for test convenience, when
> `NodeData.__init__` (the sibling class) has no such parameter and solves the
> same problem by requiring `set_settings_registry(...)` to be called on the
> ambient DI context before construction. The steps below are left as originally
> written for historical record; the actual, final contract is:
> `BaseGraph.__init__` takes no `settings_registry` parameter, calls
> `get_settings_registry()` unconditionally (raises `RuntimeError` if DI isn't
> configured — same precondition as `NodeData.__init__`, no bare no-DI
> construction path), and every test needing an isolated registry calls
> `set_settings_registry(registry)` before constructing a graph, restoring the
> DI context's module-global slot afterward via an autouse fixture.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/graph/base.py` (`__init__` ~line 86–134; new methods near `clear()` ~line 825)
- Modify: `packages/haywire-core/src/haywire/core/node/node_wrapper.py` (public `graph` property, next to the `node_id` property ~line 223)
- Test: extend `tests/core/test_settings/test_graph_settings.py`

**Interfaces:**
- Consumes: `GraphProperties` (Task 1); `haywire.core.di.context.get_settings_registry` (raises `RuntimeError` when DI unconfigured — bare unit-test graphs must survive).
- Produces: `BaseGraph.props: GraphProperties`; `BaseGraph.settings_bag_for(owner_cls: type) -> GraphSettings | None` (THE lookup seam — Task 4's mirror wiring calls it); `BaseGraph.cleanup() -> None`; `NodeWrapper.graph` property returning `self._graph`. `BaseGraph.__init__` gains keyword `settings_registry: Optional["SettingsRegistry"] = None` (explicit wins over DI; tests use it).

- [ ] **Step 1: Write the failing tests**

Append to `tests/core/test_settings/test_graph_settings.py`:

```python
def test_base_graph_owns_props_bag_headless():
    """A bare BaseGraph (no DI) still carries a props bag, unwired."""
    from haywire.core.graph.base import BaseGraph

    graph_obj = BaseGraph(graph_id="g", name="G")
    assert isinstance(graph_obj.props, GraphProperties)
    assert graph_obj.props._graph is graph_obj


def test_base_graph_accepts_explicit_registry():
    from haywire.core.graph.base import BaseGraph

    registry = create_test_settings_registry()
    graph_obj = BaseGraph(graph_id="g", name="G", settings_registry=registry)
    registry.set_global(SKIN_KEY, "skin-A")
    assert graph_obj.props.default_skin == "skin-A"


def test_settings_bag_for_is_the_lookup_seam():
    from haywire.core.graph.base import BaseGraph

    graph_obj = BaseGraph(graph_id="g", name="G")
    assert graph_obj.settings_bag_for(GraphProperties) is graph_obj.props
    assert graph_obj.settings_bag_for(GraphSettings) is graph_obj.props  # isinstance match

    class UnrelatedBag(GraphSettings):
        pass

    assert graph_obj.settings_bag_for(UnrelatedBag) is None


def test_graph_cleanup_releases_bag():
    from haywire.core.graph.base import BaseGraph

    registry = create_test_settings_registry()
    graph_obj = BaseGraph(graph_id="g", name="G", settings_registry=registry)
    registry.set_global(SKIN_KEY, "skin-A")
    graph_obj.cleanup()
    registry.set_global(SKIN_KEY, "skin-Z")
    desc = type(graph_obj.props)._property_settings()["default_skin"]
    assert graph_obj.props._cell_for(desc).get_value() == "skin-A"
```

(Local variable is `graph_obj`, not `graph` — the settings package now exports a factory named `graph`, imported at the top of this test file.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_settings/test_graph_settings.py -v -k "base_graph or bag_for or graph_cleanup"`
Expected: FAIL — `AttributeError: 'BaseGraph' object has no attribute 'props'` / unexpected keyword `settings_registry`.

- [ ] **Step 3: Implement — BaseGraph**

In `packages/haywire-core/src/haywire/core/graph/base.py`:

(a) Add to the `__init__` signature (after `validation_scheduler`):

```python
        settings_registry: "Optional[SettingsRegistry]" = None,
```

with `if TYPE_CHECKING:` import `from haywire.core.settings.registry import SettingsRegistry` at the top of the file (alongside the existing TYPE_CHECKING imports).

(b) In the `__init__` body, after the canvas-dimension block (~line 123) and before the managers block:

```python
        # Graph-owned settings bag — the graph tier (ADR 0022). The registry
        # comes from the DI context exactly like node bags (NodeData.__init__);
        # an explicit settings_registry parameter wins (tests). A bare graph
        # with no DI configured keeps an UNWIRED bag: cells seed descriptor
        # defaults, no tier resolution — same contract as a registry-less
        # NodeSettings bag.
        if settings_registry is None:
            try:
                from haywire.core.di.context import get_settings_registry

                settings_registry = get_settings_registry()
            except RuntimeError:
                settings_registry = None
        from haywire.core.graph.properties import GraphProperties

        self.props: GraphProperties = GraphProperties(registry=settings_registry, graph=self)
        self.props._subscribe_settings()
```

(c) Add two methods after `clear()` (~line 856):

```python
    def settings_bag_for(self, owner_cls: type) -> "GraphSettings | None":
        """Return this graph's settings bag that is an instance of *owner_cls*.

        THE lookup seam for graph mirrors ("which bag on my graph does this
        src descriptor live on?" — see Settings._graph_src_cell, ADR 0022).
        Plain class matching: haywire-core never hot-reloads, so class
        identity is stable. One framework bag today; a future registration
        path for library graph bags changes only this method.
        """
        if isinstance(self.props, owner_cls):
            return self.props
        return None

    def cleanup(self) -> None:
        """Release graph-owned resources (the props bag's registry
        subscriptions). Call when the graph object is discarded for good.
        ``clear()`` deliberately does NOT call this — a cleared graph is
        still usable (``load_from_dict`` clears and reloads in place)."""
        self.props.cleanup()
```

with `from haywire.core.settings.graph_settings import GraphSettings` added under `if TYPE_CHECKING:`.

(d) Wire the discard site: run

```sh
grep -rn "def close\|def cleanup\|graphs.pop\|del .*graph" packages/haywire-core/src/haywire/core/graph/editor.py packages/haywire-studio/src/haywire_studio/app.py barn/haybale-graph-editor/haybale_graph_editor/state/*.py
```

If a site exists where a `BaseGraph` is discarded (closed/removed from a registry of open graphs), add `graph.cleanup()` there, guarded `if hasattr(graph, "cleanup")`. If no such site exists (graphs live for the app's lifetime), skip — the method is the contract for owners, and headless embedders call it themselves. Record which case you found in the commit body.

- [ ] **Step 4: Implement — NodeWrapper.graph**

In `packages/haywire-core/src/haywire/core/node/node_wrapper.py`, after the `node_id` property (~line 226):

```python
    @property
    def graph(self) -> "BaseGraph":
        """The parent graph this wrapper belongs to."""
        return self._graph
```

(`BaseGraph` is already imported under TYPE_CHECKING in that file — verify, add if missing.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_settings/test_graph_settings.py -v`
Expected: PASS (13 tests). Also run `uv run pytest tests/core/test_graph -q` — the existing bare-`BaseGraph` tests must still pass (proves the DI try/except holds).

- [ ] **Step 6: Gates + commit**

```bash
git add packages/haywire-core/src/haywire/core/graph/base.py packages/haywire-core/src/haywire/core/node/node_wrapper.py tests/core/test_settings/test_graph_settings.py
git commit -m "feat(graph): BaseGraph owns GraphProperties bag; settings_bag_for seam; cleanup"
```

---

### Task 3: Graph props serialization — `props` block, restored before nodes

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/graph/base.py` (`to_dict` ~line 861, `load_from_dict` ~line 887)
- Test: `tests/core/test_graph/test_graph_props_serialization.py` (new)

**Interfaces:**
- Consumes: `Settings.to_dict()` (`{"values": {...}, "promoted": {...}}`), `Settings.from_dict()`, `Settings.reset_all()` — all existing.
- Produces: graph dict gains top-level `"props"` key; `load_from_dict` restores it after `clear()` and BEFORE the nodes loop. Task 5's integration tests rely on that ordering.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_graph/test_graph_props_serialization.py`:

```python
"""Graph props block round-trip (ADR 0022, ticket 01).

Only locally-set values serialize; an opinion-less graph emits an empty
values block; a dict WITHOUT the block (pre-feature graph) loads clean.
"""

import haywire.core.graph.editor  # noqa: F401  (circular-import guard, per CLAUDE.md)

import pytest

from haywire.core.di.test_config import create_test_settings_registry
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler

pytestmark = [pytest.mark.unit, pytest.mark.core]

SKIN_KEY = "ui.node.default.skin.studio_skin"


def _graph(registry=None):
    return BaseGraph(
        graph_id="g", name="G", validation_scheduler=SyncScheduler(), settings_registry=registry
    )


def test_opinionless_graph_serializes_empty_props():
    data = _graph().to_dict()
    assert data["props"] == {"values": {}, "promoted": {}}


def test_local_opinion_round_trips():
    registry = create_test_settings_registry()
    g1 = _graph(registry)
    g1.props.default_skin = "skin-mine"
    data = g1.to_dict()
    assert data["props"]["values"] == {"default_skin": "skin-mine"}

    g2 = _graph(registry)
    assert g2.load_from_dict(data) is True
    assert g2.props.default_skin == "skin-mine"
    assert g2.props.is_locally_set("default_skin")


def test_missing_props_block_loads_with_defaults():
    """Pre-feature graph JSON has no 'props' key — must load unchanged."""
    registry = create_test_settings_registry()
    g1 = _graph(registry)
    data = g1.to_dict()
    del data["props"]
    g2 = _graph(registry)
    g2.props.default_skin = "stale-opinion"  # reused instance with stale state
    assert g2.load_from_dict(data) is True
    assert not g2.props.is_locally_set("default_skin")  # reset_all ran


def test_load_restores_props_into_live_bag():
    registry = create_test_settings_registry()
    g1 = _graph(registry)
    g1.props.default_skin = "skin-early"
    data = g1.to_dict()

    g2 = _graph(registry)
    assert g2.load_from_dict(data) is True
    assert g2.props.default_skin == "skin-early"
    # The ordering guarantee (props before nodes) is exercised with real
    # nodes in the Task 5 integration tests.
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_graph/test_graph_props_serialization.py -v`
Expected: FAIL — `KeyError: 'props'` in the first test.

- [ ] **Step 3: Implement**

In `packages/haywire-core/src/haywire/core/graph/base.py`:

(a) `to_dict` (~line 871): add after the `"variables"` entry:

```python
            "props": self.props.to_dict(),
```

(b) `load_from_dict` (~line 907): directly after `self.clear()` and before the variables block:

```python
            # Graph-tier settings restore BEFORE nodes: node-bag graph
            # mirrors seed from the graph bag's cells at node construction
            # (ADR 0022). reset_all first — load_from_dict may reuse a live
            # graph whose bag still carries the previous graph's opinions.
            self.props.reset_all()
            self.props.from_dict(data.get("props", {}))
```

(`from_dict({})` is valid — restores nothing; the block emitted by `to_dict` always carries `"values"`, so `PromotedFormatError` cannot fire for our own output.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_graph/test_graph_props_serialization.py tests/core/test_graph -v`
Expected: PASS, including all pre-existing graph serialization tests.

- [ ] **Step 5: Gates + commit**

```bash
git add packages/haywire-core/src/haywire/core/graph/base.py tests/core/test_graph/test_graph_props_serialization.py
git commit -m "feat(graph): serialize graph props block; restore before nodes on load"
```

---

### Task 4: Graph-mirror wiring in `Settings` — seed, sync, reset, cleanup

The heart of the feature. A graph mirror keeps its OWN cell and *listens* to the src field's cell on the owning graph's bag (never borrows — a locally-set node value must diverge). "Unset tracks, set ignores" per hop. **Detached bag (no reachable graph): the field holds its descriptor default and is not live — no registry fallback.** A plain `shadow()` mistakenly pointed at a per-instance bag field fails loudly at wiring time.

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/settings/settings.py` (`__init__`, `_cell_for`, `_subscribe_setting`, `reset`, `cleanup` + two new helpers; `_on_field_change` is NOT touched)
- Test: `tests/core/test_settings/test_graph_mirror.py` (new)

**Interfaces:**
- Consumes: Task 1 (`is_graph_mirror`, `_owner_cls`, `graph()` factory), Task 2 (`BaseGraph.settings_bag_for`, `NodeWrapper.graph`).
- Produces: `Settings._owning_graph() -> BaseGraph | None`; `Settings._graph_src_cell(descriptor) -> DataField | None`; instance state `_graph_mirror_adapters: dict[str, tuple[DataField, Callable]]`. Task 5 relies on the whole mechanism transparently (no new names).

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_settings/test_graph_mirror.py`:

```python
"""Graph mirror: node field declared graph(src=<GraphSettings field>) (ADR 0022, ticket 02).

Unit seam: public Settings/Graph API only. The node side is a minimal stub
exposing exactly the path the wiring walks (node.wrapper.graph) — no
library system needed.
"""

import haywire.core.graph.editor  # noqa: F401  (circular-import guard, per CLAUDE.md)

import pytest

from haywire.core.di.test_config import create_test_settings_registry
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.properties import GraphProperties
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.settings import NodeSettings, graph
from haywire.core.settings.descriptor import shadow

pytestmark = [pytest.mark.unit, pytest.mark.core]

SKIN_KEY = "ui.node.default.skin.studio_skin"


class ChainedBag(NodeSettings):
    """A node bag whose field graph-mirrors the graph bag's default_skin."""

    skin = graph(src=GraphProperties.default_skin)


class _StubWrapper:
    def __init__(self, graph_obj):
        self.graph = graph_obj


class _StubNode:
    """Exposes exactly what Settings._owning_graph() walks."""

    def __init__(self, graph_obj):
        self.wrapper = _StubWrapper(graph_obj)


def _make_chain():
    registry = create_test_settings_registry()
    graph_obj = BaseGraph(
        graph_id="g", name="G", validation_scheduler=SyncScheduler(), settings_registry=registry
    )
    bag = ChainedBag(registry=registry, node=_StubNode(graph_obj))
    bag._subscribe_settings()
    return registry, graph_obj, bag


def test_unset_tracks_graph_value_live():
    registry, graph_obj, bag = _make_chain()
    graph_obj.props.default_skin = "skin-graph"
    assert bag.skin == "skin-graph"
    graph_obj.props.default_skin = "skin-graph-2"
    assert bag.skin == "skin-graph-2"


def test_subscribe_field_fires_on_graph_change():
    registry, graph_obj, bag = _make_chain()
    seen: list = []
    bag.subscribe_field("skin", lambda value, old: seen.append(value))
    graph_obj.props.default_skin = "skin-x"
    assert seen == ["skin-x"]


def test_local_set_wins_and_reset_returns_to_graph_current():
    registry, graph_obj, bag = _make_chain()
    graph_obj.props.default_skin = "skin-graph"
    bag.skin = "skin-node"
    assert bag.skin == "skin-node"
    graph_obj.props.default_skin = "skin-graph-2"
    assert bag.skin == "skin-node"          # set ignores
    bag.reset("skin")
    assert bag.skin == "skin-graph-2"       # falls to graph CURRENT, not framework
    graph_obj.props.default_skin = "skin-graph-3"
    assert bag.skin == "skin-graph-3"       # tracking resumed


def test_transitive_chain_framework_to_node():
    registry, graph_obj, bag = _make_chain()
    registry.set_global(SKIN_KEY, "skin-fw")
    assert graph_obj.props.default_skin == "skin-fw"
    assert bag.skin == "skin-fw"            # framework → graph → node
    graph_obj.props.default_skin = "skin-graph"  # graph opinion interposes
    registry.set_global(SKIN_KEY, "skin-fw-2")
    assert bag.skin == "skin-graph"          # blocked at the graph tier
    graph_obj.props.reset("default_skin")
    assert bag.skin == "skin-fw-2"           # chain reopens end to end


def test_detached_bag_holds_descriptor_default():
    """No node / no graph → descriptor default, NOT live (ADR 0022).

    Deliberate contract: no production path constructs a detached bag (a
    NodeWrapper's graph is a non-optional constructor arg); an honest
    default surfaces the detachment instead of masking it."""
    registry = create_test_settings_registry()
    registry.set_global(SKIN_KEY, "skin-fw")
    bag = ChainedBag(registry=registry, node=None)
    bag._subscribe_settings()
    assert bag.skin is None                 # descriptor default, not "skin-fw"
    registry.set_global(SKIN_KEY, "skin-fw-2")
    assert bag.skin is None                 # and not tracking either
    bag.skin = "skin-local"                 # local writes still work
    assert bag.skin == "skin-local"


def test_plain_shadow_of_graph_field_fails_loudly():
    class Misdeclared(NodeSettings):
        skin = shadow(src=GraphProperties.default_skin)  # should be graph(...)

    bag = Misdeclared(registry=create_test_settings_registry(), node=None)
    with pytest.raises(TypeError, match=r"graph\("):
        bag._subscribe_settings()


def test_cleanup_detaches_graph_cell_adapter():
    registry, graph_obj, bag = _make_chain()
    graph_obj.props.default_skin = "skin-a"
    bag.cleanup()
    graph_obj.props.default_skin = "skin-b"
    desc = type(bag)._property_settings()["skin"]
    assert bag._cell_for(desc).get_value() == "skin-a"  # no sync after cleanup


def test_node_removal_does_not_leak_callbacks():
    registry, graph_obj, bag = _make_chain()
    seen: list = []
    bag.subscribe_field("skin", lambda value, old: seen.append(value))
    bag.cleanup()
    graph_obj.props.default_skin = "skin-after"
    assert seen == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_settings/test_graph_mirror.py -v`
Expected: FAIL — `test_unset_tracks_graph_value_live` gets `None` for `bag.skin` (no seeding/sync exists yet); the loud-guard test fails with no exception raised.

- [ ] **Step 3: Implement — instance state + helpers**

In `packages/haywire-core/src/haywire/core/settings/settings.py`:

(a) In `Settings.__init__`, after `self._promoted_keys...` (~line 130):

```python
        # Graph-mirror wiring (ADR 0022): storage_key -> (src cell, adapter)
        # for fields synced cell-to-cell against the owning graph's bag.
        self._graph_mirror_adapters: dict[str, tuple["DataField", Callable]] = {}
```

(b) New helpers, placed directly before `_cell_for` (~line 225):

```python
    def _owning_graph(self) -> "BaseGraph | None":
        """The graph this bag can reach: its own (GraphSettings) or its
        node's (node → wrapper → graph). None for standalone bags."""
        graph_obj = getattr(self, "_graph", None)
        if graph_obj is not None:
            return graph_obj
        if self._node is None:
            return None
        wrapper = getattr(self._node, "wrapper", None)
        if wrapper is None:
            return None
        return getattr(wrapper, "graph", None)

    def _graph_src_cell(self, descriptor: setting) -> "DataField | None":
        """The live cell of a graph mirror's src field on the owning graph's
        bag — or None when detached (standalone bag, node not in a graph,
        graph lacks the src bag). Detached fields hold the descriptor
        default and are not live (ADR 0022)."""
        if not descriptor.is_graph_mirror:
            return None
        src = descriptor._mirror_descriptor
        owner = getattr(src, "_owner_cls", None)
        if src is None or owner is None:
            return None
        graph_obj = self._owning_graph()
        if graph_obj is None:
            return None
        bag = graph_obj.settings_bag_for(owner)
        if bag is None or bag is self:
            return None
        if not isinstance(src, setting):
            return None
        return bag._cell_for(src)
```

Add `from haywire.core.graph.base import BaseGraph` under the existing `if TYPE_CHECKING:` block, and `from haywire.core.settings.descriptor import setting` is already imported via the `.descriptor` import at the top (verify — the module imports `setting` from `.descriptor` at line 42).

(c) `_cell_for` seeding (~line 259) — replace the two-way seed branch:

```python
            src_cell = self._graph_src_cell(descriptor) if descriptor.is_graph_mirror else None
            if src_cell is not None:
                # Graph mirror on an attached bag: seed from the src field's
                # live cell (the graph bag restores before nodes on load).
                seed = src_cell.get_value()
            elif descriptor.is_mirror and self._registry is not None:
                seed = self._resolve(descriptor.storage_key, descriptor._mirror_key, descriptor._default)
            else:
                # Plain field, DETACHED graph mirror, or no registry: the
                # descriptor default. A callable default is late-binding —
                # evaluated ONCE here at seed time, never on the read path.
                default = descriptor._default
                seed = default() if callable(default) else default
```

(d) `_subscribe_setting` (~line 316) — new first branch, loud guard, and the new method:

```python
    def _subscribe_setting(self, descriptor: setting) -> None:
        """Keep a single mirror field's cell synced to what it mirrors.

        Registry-key mirror → registry notification channel. Graph mirror →
        cell adapter on the src bag's cell (detached bags stay at the
        descriptor default, not live). No-op for plain fields."""
        if descriptor.is_graph_mirror:
            self._subscribe_graph_mirror(descriptor)
            return
        if descriptor._mirror_descriptor is not None and not descriptor._mirror_key:
            # A plain shadow() pointed at a per-instance bag field: it has no
            # registry key to ride and was not declared via graph(), so it
            # would silently never track. Fail loudly at wiring time.
            raise TypeError(
                f"setting field '{descriptor.storage_key}' on {type(self).__name__} shadows a "
                f"field on a per-instance bag ({descriptor._mirror_descriptor!r}) — declare it "
                f"with graph(src=...) instead of shadow() (ADR 0022)."
            )
        if self._registry is None or not descriptor._mirror_key:
            return
        self._registry.subscribe(descriptor._mirror_key, self._on_field_change)

    def _subscribe_graph_mirror(self, descriptor: setting) -> None:
        """Wire one graph mirror ('unset tracks, set ignores', per hop).

        Attaches ONE adapter to the src field's cell on the owning graph's
        bag; the adapter writes changes into this field's own cell unless a
        local opinion suppresses it. Detached bag → no-op (descriptor
        default, not live). Idempotent per field. ADR 0022."""
        key = descriptor.storage_key
        if key in self._graph_mirror_adapters:
            return
        src_cell = self._graph_src_cell(descriptor)
        if src_cell is None:
            return  # detached — seeded with the descriptor default (ADR 0022)
        self._cell_for(descriptor)  # ensure own cell exists + is seeded first

        def _adapter(change: Any, _descriptor: setting = descriptor) -> None:
            if self._cleaned_up or self._is_locally_set(_descriptor):
                return
            self._cell_for(_descriptor).set_value(change.value)

        src_cell.on_changed.append(_adapter)
        self._graph_mirror_adapters[key] = (src_cell, _adapter)
```

(`_on_field_change` is deliberately untouched — graph mirrors never ride the registry channel.)

(e) `reset()` (~line 485) — extend the no-override-value branch:

```python
            src_cell = self._graph_src_cell(descriptor) if descriptor.is_graph_mirror else None
            if src_cell is not None:
                new = src_cell.get_value()
            elif descriptor.is_mirror and self._registry is not None:
                new = self._resolve(descriptor.storage_key, descriptor._mirror_key, descriptor._default)
            else:
                default = descriptor._default
                new = default() if callable(default) else default
```

(f) `cleanup()` (~line 502) — before `self._ui_state_listeners.clear()`:

```python
        # Detach graph-mirror adapters — MANDATORY: the src cells are
        # graph-owned and outlive this bag (same rule as registry-owned cells).
        for cell, adapter in self._graph_mirror_adapters.values():
            try:
                cell.on_changed.remove(adapter)
            except ValueError:
                pass
        self._graph_mirror_adapters.clear()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_settings/test_graph_mirror.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Run the whole settings + graph suites (regression sweep)**

Run: `uv run pytest tests/core/test_settings tests/core/test_graph -q`
Expected: PASS — the registry-key mirror path (`test_mirror_cell_authoritative.py`, `test_cell_subscription.py`) must be byte-for-byte unaffected, and no existing bag construction may trip the new loud guard.

- [ ] **Step 6: Gates + commit**

```bash
git add packages/haywire-core/src/haywire/core/settings/settings.py tests/core/test_settings/test_graph_mirror.py
git commit -m "feat(settings): graph-mirror wiring — cell sync, detachment contract, loud misdeclaration guard (ADR 0022)"
```

---

### Task 5: Re-source `NodeProperties.skin` — the chain live on real nodes

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/node/properties.py` (`skin` field, lines 63–70)
- Modify: `packages/haywire-core/src/haywire/ui/panel/render_utils.py` (one-line mirror-wording tweak)
- Test: `tests/core/test_node/test_node_skin_graph_tier.py` (new, integration)

**Interfaces:**
- Consumes: everything from Tasks 1–4; `graph_with_library_system` fixture (`tests/core/conftest.py`); test nodes from `haybale_testing` (pattern: `tests/core/test_execution/test_interpreter.py`).
- Produces: `NodeProperties.skin` is a graph mirror of `GraphProperties.default_skin`. Serialized attr name (`skin`, bare value under the node's `props` block) is UNCHANGED — old graphs load as-is.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_node/test_node_skin_graph_tier.py`:

```python
"""framework < graph < node skin chain on real nodes (ADR 0022, ticket 03)."""

import haywire.core.graph.editor  # noqa: F401  (circular-import guard, per CLAUDE.md)

import pytest

from haywire.core.di.context import get_settings_registry
from haywire.core.graph.base import BaseGraph

SKIN_KEY = "ui.node.default.skin.studio_skin"


def _add_node(graph_obj: BaseGraph):
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    return graph_obj.create_node_wrapper(
        TestPrintNode.class_identity.registry_key, position=(100, 100)
    )


@pytest.mark.integration
class TestNodeSkinGraphTier:
    def test_unset_node_tracks_graph_default(self, graph_with_library_system):
        graph_obj = graph_with_library_system
        wrapper = _add_node(graph_obj)
        graph_obj.props.default_skin = "skin-graph"
        assert wrapper.node.props.skin == "skin-graph"

    def test_node_override_wins_and_resets_fall_one_tier(self, graph_with_library_system):
        graph_obj = graph_with_library_system
        registry = get_settings_registry()
        wrapper = _add_node(graph_obj)

        registry.set_global(SKIN_KEY, "skin-fw")
        graph_obj.props.default_skin = "skin-graph"
        wrapper.node.props.skin = "skin-node"
        assert wrapper.node.props.skin == "skin-node"

        wrapper.node.props.reset("skin")
        assert wrapper.node.props.skin == "skin-graph"   # node → graph
        graph_obj.props.reset("default_skin")
        assert wrapper.node.props.skin == "skin-fw"      # graph → framework

    def test_round_trip_preserves_all_three_tiers(self, graph_with_library_system, library_system):
        graph_obj = graph_with_library_system
        w1 = _add_node(graph_obj)
        w2 = _add_node(graph_obj)
        graph_obj.props.default_skin = "skin-graph"
        w1.node.props.skin = "skin-node"                  # w1 overridden, w2 tracking
        data = graph_obj.to_dict()

        g2 = BaseGraph(graph_id="g2", name="G2")
        assert g2.load_from_dict(data) is True
        loaded = list(g2.node_wrappers.values())
        overridden = [w for w in loaded if w.node.props.is_locally_set("skin")]
        tracking = [w for w in loaded if not w.node.props.is_locally_set("skin")]
        assert len(overridden) == 1 and overridden[0].node.props.skin == "skin-node"
        assert len(tracking) == 1 and tracking[0].node.props.skin == "skin-graph"

    def test_pre_feature_graph_without_props_block_loads(self, graph_with_library_system):
        graph_obj = graph_with_library_system
        _add_node(graph_obj)
        data = graph_obj.to_dict()
        del data["props"]                                  # simulate old file
        g2 = BaseGraph(graph_id="g2", name="G2")
        assert g2.load_from_dict(data) is True
        assert not g2.props.is_locally_set("default_skin")
        assert len(g2.node_wrappers) == 1

    def test_skin_promotion_still_works(self, graph_with_library_system):
        from haywire.core.types.enums import PortType

        graph_obj = graph_with_library_system
        wrapper = _add_node(graph_obj)
        wrapper.node.props.promote("skin", PortType.INLET)
        assert wrapper.node.props.is_promoted("skin")
        wrapper.node.props.demote("skin")
        assert not wrapper.node.props.is_promoted("skin")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_node/test_node_skin_graph_tier.py -v -m integration`
Expected: FAIL — `test_unset_node_tracks_graph_default` sees the framework value, not `"skin-graph"` (the skin still shadows the framework key directly).

- [ ] **Step 3: Implement — re-source the field**

In `packages/haywire-core/src/haywire/core/node/properties.py`:

(a) Change the imports (lines 12–14): extend the descriptor import with `graph`, add the bag import, keep `_node_skin_choices`, drop `NodeDefaultSkinSettings` if now unused:

```python
from haywire.core.settings.descriptor import graph, shadow
from haywire.core.graph.properties import GraphProperties
from haywire.ui.skin.settings import _node_skin_choices
```

(keep the `shadow` import only if other fields in the file still use it — check before dropping.)

(b) Replace the `skin` field (lines 63–70):

```python
    skin = graph(
        src=GraphProperties.default_skin,
        label="Skin",
        category="appearance",
        order=10,
        # Mirrors inherit IType (-> CHOICES/SELECT_WIDGET) from src, but NOT its
        # per-setting widget_config — options must be re-supplied here.
        widget_config={"options": _node_skin_choices},
    )
```

Note: the explicit `label="Skin"` is deliberate — without it the row would inherit the graph field's label ("Default Node Skin"), and before this change it inherited the framework label ("Default Studio Skin"). "Skin" is the honest name for the node's own row; flag in the commit body as an intentional cosmetic change.

(c) Import-cycle check: `core/graph/properties.py` imports only skin settings + settings core; `core/node/properties.py` importing it adds no cycle (node → graph.properties → ui.skin.settings, never back into node). Run `uv run python -c "import haywire.core.node.properties"` — must import clean.

- [ ] **Step 4: Implement — mirror wording in the panel row**

In `packages/haywire-core/src/haywire/ui/panel/render_utils.py`, find the assignment feeding the reset tooltip (`grep -n "is_mirrored" packages/haywire-core/src/haywire/ui/panel/render_utils.py`) and extend it:

```python
    is_mirrored = defn.is_mirror or defn.is_graph_mirror
```

(so the node skin row keeps its "Reset to global default" wording now that `is_mirror` is False for it).

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_node/test_node_skin_graph_tier.py -v -m integration`
Expected: PASS (5 tests).

- [ ] **Step 6: Full-suite regression + gates + commit**

Run: `uv run pytest` (FULL suite — this task touches a builtin every node uses; any existing bag that constructs `NodeProperties` off-graph would now hold `None` instead of the framework skin, and any plain-shadow misdeclaration trips the Task 4 guard — both must surface here, not in production).
Expected: PASS. Then gates, then:

```bash
git add packages/haywire-core/src/haywire/core/node/properties.py packages/haywire-core/src/haywire/ui/panel/render_utils.py tests/core/test_node/test_node_skin_graph_tier.py
git commit -m "feat(node): NodeProperties.skin graph-mirrors the graph default skin (framework < graph < node)"
```

- [ ] **Step 7: Human check (leave unchecked for the reviewer)**

Run `uv run haywire`, open a graph with several nodes, change the graph default skin (programmatically or after Task 6 via the panel) and confirm the canvas restyles; override one node's skin and confirm it stays. This is ticket 03's human-only acceptance box.

---

### Task 6: Properties panel — graph scope section

**Files:**
- Create: `barn/haybale-graph-editor/haybale_graph_editor/panels/properties/setting/graph.py`
- Test: `tests/core/test_settings/test_graph_settings.py` (one added invariant test)

Panels register by folder scan (`Library.register_components` adds `panels/` to `PanelRegistry`) — a new `@panel` module needs NO import wiring.

**Interfaces:**
- Consumes: `render_settings(bag)` (`haywire.ui.panel.render_utils`), `GraphFocus` + `EditState` (same imports as the sibling `introspect/graph.py` `GraphInfoPanel`), `@panel` decorator (same kwargs as `setting/node.py` `NodeSettingsPanel`).
- Produces: `GraphSettingsPanel` under GraphFocus. Promote entries are absent structurally: `_build_row_menu` in render_utils only adds them when `obj._node is not None`, and a `GraphSettings` bag always has `_node is None`.

- [ ] **Step 1: Write the failing invariant test**

Append to `tests/core/test_settings/test_graph_settings.py`:

```python
def test_graph_bag_never_carries_a_node():
    """The setting-row menu's promote guard keys on obj._node is None
    (_build_row_menu in render_utils). This invariant is what keeps promote
    entries structurally absent for every GraphSettings bag."""
    registry, bag = _make_bag()
    assert bag._node is None
    from haywire.core.graph.base import BaseGraph

    graph_obj = BaseGraph(graph_id="g", name="G", settings_registry=registry)
    assert graph_obj.props._node is None
```

Run: `uv run pytest tests/core/test_settings/test_graph_settings.py -v -k never_carries`
Expected: PASS already (the invariant holds since Task 1) — this test pins it against regressions. If it FAILS, stop: something set `_node` on a graph bag.

- [ ] **Step 2: Implement the panel**

Create `barn/haybale-graph-editor/haybale_graph_editor/panels/properties/setting/graph.py`:

```python
# barn/haybale-graph-editor/haybale_graph_editor/panels/properties/setting/graph.py
"""
GraphSettingsPanel — renders the active graph's settings bag (graph.props).

The graph-scope section of the properties editor (ADR 0022): shown under
GraphFocus (graph itself in focus, no node selected). Reuses the generic
bag renderer; the setting-row menu offers no promote entries because a
GraphSettings bag has ``_node is None`` (structural guard in
``_build_row_menu``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.core.session.signals import ActiveGraphMoved, GraphDataMutated
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.render_utils import render_settings

from ....focuses import GraphFocus
from ....state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    focus=GraphFocus,
    label="Graph Settings",
    icon=hui.icon.graph,
    order=20,
    default_open=True,
    redraw_on=(ActiveGraphMoved, GraphDataMutated),
)
class GraphSettingsPanel(BasePanel):
    """Renders ``graph.props`` for the active graph."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        graph_obj = ctx.data[EditState].active_graph
        return graph_obj is not None and getattr(graph_obj, "props", None) is not None

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        graph_obj = ctx.data[EditState].active_graph
        if graph_obj is None:
            return
        with layout:
            render_settings(graph_obj.props)
```

If any import differs in this haybale (e.g. icon name), mirror EXACTLY what `panels/properties/introspect/graph.py` (`GraphInfoPanel`) uses — it is the adjacent, working reference for focus/icon/state imports.

- [ ] **Step 3: Verify registration + render smoke**

Run: `uv run pytest tests/graph_editor -q` (the graph-editor library's panel scan must still load — an import error in the new module fails these).
Expected: PASS.

- [ ] **Step 4: Human check (leave unchecked for the reviewer)**

`uv run haywire` → click empty canvas → the properties editor shows "Graph Settings" with the Default Node Skin dropdown; its row context-menu offers Reset but no Promote entries; picking a skin restyles tracking nodes live.

- [ ] **Step 5: Gates + commit**

```bash
git add barn/haybale-graph-editor/haybale_graph_editor/panels/properties/setting/graph.py tests/core/test_settings/test_graph_settings.py
git commit -m "feat(graph-editor): Graph Settings panel — graph scope for graph.props"
```

---

### Task 7: ADR 0022 + documentation

**Files:**
- Create: `docs/adr/0022-graph-settings-tier.md`
- Modify: `docs/architecture/settings/settings-arch.md` (§6.1 table, §7.3, §10)
- Modify: `docs/components/settings/setting-canon.md` (authoring section for graph bags + the `graph()` factory)
- Modify: `docs/reference/glossary.md` (GraphSettings / graph mirror entries)

**Interfaces:** none produced — documents what Tasks 1–6 landed. Every doc claim must be verified against the merged code, not this plan.

- [ ] **Step 1: Write the ADR**

Create `docs/adr/0022-graph-settings-tier.md` following the style of `docs/adr/0013-settings-single-cell.md` (read it first). Required content — Decision: the `GraphSettings` flavour, one framework `GraphProperties` bag on `BaseGraph`, chained mirrors with the explicit `graph()` factory (`is_graph_mirror` flag + eager owner-class validation + the loud wiring-time guard for a plain `shadow()` of a per-instance field), the `settings_bag_for()` seam, the **detachment contract** (descriptor default, not live, no registry fallback — and why: no production path constructs a detached bag; masking detachment with a plausible value is worse than an honest default), props block restored before nodes. Rejected alternatives WITH reasons (from the spec + design review): library-registered graph bags (hot-reload live-bag rebinding risk; the seam is the deliberate containment), registering graph bags in the registry with per-graph keys (key pollution; class-level declarations cannot name per-instance keys), borrowing the graph's cell instead of listening (a locally-set node value must be able to diverge), lazy resolve-on-read mirrors (breaks the cell-authoritative invariant: promoted ports and widgets bind the cell; notification rides the cell event), terminal-registry-key fallback with live tracking (dropped: defended behaviour with zero consumers; kept `_on_field_change` untouched by dropping it).

- [ ] **Step 2: Update the architecture doc**

In `docs/architecture/settings/settings-arch.md`:
- §6.1 table: add row `GraphSettings | settings/graph_settings.py | Never registered as a class — one instance owned per BaseGraph (graph.props) | Per-instance: BaseGraph.__init__ injects the DI registry`.
- §7.3: add the graph-mirror hop to the change-notification flow (graph cell write → node cell adapter → node cell event) and the detachment contract.
- §10: delete the "Per-graph settings tier" open question; replace with a pointer: `Resolved by [ADR 0022](../../adr/0022-graph-settings-tier.md) — graphs own a GraphSettings bag; see §6.1.`

- [ ] **Step 3: Update the canon + glossary**

`setting-canon.md`: add an authoring subsection "Mirroring a graph setting from a node bag" showing the exact `NodeProperties.skin` declaration (`graph(src=GraphProperties.default_skin, ...)`), the three-tier semantics (track/win/reset per hop), the detachment contract, and the `shadow()` vs `graph()` decision rule (registry-keyed src → `shadow()`/`watch()`; GraphSettings src → `graph()`). `glossary.md`: entries for **GraphSettings** (fourth flavour) and **graph mirror** (vs registry-key mirror), consistent with the existing tier vocabulary.

- [ ] **Step 4: Build check**

Run: `uv run mkdocs build 2>&1 | tail -20`
Expected: build succeeds; no new warnings referencing the touched files.

- [ ] **Step 5: Gates + commit**

```bash
git add docs/adr/0022-graph-settings-tier.md docs/architecture/settings/settings-arch.md docs/components/settings/setting-canon.md docs/reference/glossary.md
git commit -m "docs: ADR 0022 graph settings tier; settings arch/canon/glossary updates"
```

---

## Self-Review (performed while writing)

- **Spec coverage:** flavour + bag + factory (Task 1 ← ticket 01), graph ownership + seam (Task 2 ← ticket 01), serialization + load order (Task 3 ← ticket 01), graph-mirror wiring + detachment + guard (Task 4 ← ticket 02), skin re-source + regression + promotion (Task 5 ← ticket 03), panel + promote guard (Task 6 ← ticket 04), ADR + docs (Task 7 ← ticket 05). Cross-graph paste (ticket 03) is covered behaviourally by Task 5's round-trip test (unset fields re-track whichever graph restores them).
- **Amendments vs the spec** (settled in design review after the spec was written; the ADR records them): explicit `graph()` factory instead of src-kind inference; detachment contract (descriptor default, not live) instead of the terminal-registry-key fallback — ticket 02's "behaves byte-for-byte like a direct framework shadow when headless" criterion is superseded by `test_detached_bag_holds_descriptor_default` and `test_plain_shadow_of_graph_field_fails_loudly`.
- **Known deliberate deviations to flag in review:** node skin row label becomes explicit `"Skin"` (was inherited "Default Studio Skin"); `is_mirrored` wording tweak in render_utils.
- **Type consistency check:** `settings_bag_for(owner_cls)` (Tasks 2→4), `is_graph_mirror` + `graph()` (Tasks 1→4→5), `_graph_src_cell` / `_owning_graph` / `_graph_mirror_adapters` (Task 4 internal), `GraphProperties.default_skin` (Tasks 1→4-tests→5), `NodeWrapper.graph` (Tasks 2→4) — names match across tasks.
- **Naming hazard, checked:** the factory export `graph` collides easily with local variables named `graph`; every test in this plan uses `graph_obj` for graph instances, and Task 5's `node/properties.py` has no local `graph` name. Executors must keep that discipline in new test code.
- **Line numbers** are anchors as of the plan date; trust the surrounding code snippets over the numbers if the file has drifted.
