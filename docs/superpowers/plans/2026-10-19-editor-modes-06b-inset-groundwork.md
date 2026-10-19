# Editor modes 6b: Inset groundwork — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Three changes the Inset (6c) builds on: a Graph-node card redraws when its interior changes visually, Graph-nodes get their own skin lists via a `graph-node` tag, and a card's teardown stops dropping the hot-reload tracking of the node's other cards.

**Architecture:** All three are small, general changes in core, builtin and graph-editor. None of them mentions the Inset. Builtin `GraphNode` learns nothing about skins beyond a tag string, and the redraw is unconditional.

**Tech Stack:** Python 3.12, haywire validation (`ValidationResult`, `ChangeReason`), settings descriptors (`graph()` mirrors), `SkinFactory`, pytest.

**Spec:** [2026-10-12-editor-modes.md](2026-10-12-editor-modes.md), section "Inset (bpatcher)" and Sequence item 6 (6b), as settled by the 2026-10-19 inquisition.

## Global Constraints

- Builtin (`haywire.barn.builtin`) references nothing outside haywire-core. The `graph-node` tag is a string constant in `haywire.core.skin.tags`.
- graph-editor gains no dependency.
- A value write inside an interior (`NODE_VALUE_CHANGED`) never redraws the card.
- Every existing test passes unchanged. In particular, `test_an_interior_value_edit_does_not_mark_the_host` (placements stay runtime state, ADR 0038).
- **Trap:** `tests/studio/test_docs/test_generate.py` runs `git checkout -- barn/haybale-testing` in teardown. This plan doesn't touch that folder; keep it that way.

## Review Focus

1. **A slider in an interior must survive its drag** once 6c draws it inside the card. A value write must produce no card redraw for a Group or a placement. Pinned by `test_an_interior_value_edit_does_not_redraw_the_card` and `test_a_placement_value_edit_does_not_redraw_the_card`.
2. **Visual-only interior batches.** A lone `NODE_REDRAW_REQUESTED` (e.g. an interior `stage_skin` change, a first runtime error) is dropped today by the `requires_save()` early return. It must now redraw the card. Pinned by `test_an_interior_redraw_request_redraws_the_card`.
3. **The Graph-node skin field keeps its tier chain** (framework < graph < node) after GraphNode redeclares `skin`/`stage_skin` for its options. Pinned by `test_a_graph_node_skin_still_follows_the_graph_default`.
4. **Removing one card of a node** (Remove from Stage, closing a level, an Inset redraw in 6c) must leave the node's other cards hearing skin and widget hot reloads. Pinned by `test_tearing_down_one_card_keeps_the_other_cards_reloads` and `test_widget_tracking_ends_with_the_last_card`.
5. **MacroNode inherits GraphNode's skin lists** (placements get the Inset too). Pinned by an assertion in `test_graph_nodes_offer_graph_node_skins`.

---

### Task 1: A Graph-node card redraws when its interior changes visually

**Files:**
- Modify: `packages/haywire-core/src/haywire/barn/builtin/nodes/graph_node.py:111-137` (`_on_definition_validated` and its docstring)
- Create: `tests/core/test_graph/test_interior_redraws_the_card.py`
- Modify: `tests/core/test_macro/test_macro_node.py` (two placement tests, after `test_an_interior_value_edit_does_not_mark_the_host`)

**Interfaces:**
- Produces: the card's wrapper receives `NODE_REDRAW_REQUESTED` (via `self.wrapper.redraw()`) whenever an interior batch has a node reason with `reason.requires_redraw() or reason is ChangeReason.NODE_STAGE_CHANGED`. 6c's InsetSkin relies on this.

- [ ] **Step 1: Write the failing tests**

`tests/core/test_graph/test_interior_redraws_the_card.py`, `pytestmark = [pytest.mark.integration]`, using `graph_with_library_system` (synchronous) and `make_node` from `tests.conftest`:

```python
_ADD_FLOAT = "haybale-testing:node:TestAddFloatNode"
_CARD = "haywire-core:node:GraphNode"

@pytest.fixture
def group(graph_with_library_system):
    # definition = graph.add_subgraph(SubgraphDefinition(key="sg", label="Group"));
    # interior = make_node(definition, _ADD_FLOAT);
    # card = make_node(graph, _CARD, node_data={"store": {SUBGRAPH_KEY: "sg"}}); card.node.reconcile_interface();
    # graph.force_validation(); return graph, definition, card, interior

def _card_redraws(seen, card) -> bool:
    return any(card.node_id in r.nodes and r.nodes[card.node_id].requires_redraw() for r in seen)

def test_an_interior_move_redraws_the_card(group):          # definition.move_node(interior.node_id, 10.0, 20.0)
def test_an_interior_stage_change_redraws_the_card(group):  # interior.node.props.on_stage = True
def test_an_interior_redraw_request_redraws_the_card(group):  # interior.redraw()
    ...  # each: seen = []; graph.subscribe_to_validation(seen.append); act; assert _card_redraws(seen, card)

def test_an_interior_value_edit_does_not_redraw_the_card(group):
    # interior.mark_value_edited(); assert not _card_redraws(seen, card)
```

In `tests/core/test_macro/test_macro_node.py`, using `_place` / `_interior_adder` / `macro_registry`:

```python
def test_a_placement_interior_move_redraws_the_card(graph_with_library_system, macro_registry):
    # card.node.resolve_definition().move_node(_interior_adder(card).node_id, 10.0, 20.0)
    # assert any(card.node_id in r.nodes and r.nodes[card.node_id].requires_redraw() for r in seen)

def test_a_placement_value_edit_does_not_redraw_the_card(graph_with_library_system, macro_registry):
    # _interior_adder(card).mark_value_edited(); assert no such batch
```

- [ ] **Step 2: Run them and confirm the right ones fail**

Run: `uv run pytest tests/core/test_graph/test_interior_redraws_the_card.py tests/core/test_macro/test_macro_node.py -q -k "redraw"`
Expected: the move, stage-change and redraw-request tests FAIL (no card reason). The two value-edit tests PASS. They pin behaviour that must survive.

- [ ] **Step 3: Implement it in `GraphNode._on_definition_validated`**

Before the `if not result.requires_save(): return` line, redraw the card once if any `result.nodes` reason `requires_redraw()` or is `ChangeReason.NODE_STAGE_CHANGED`. The rest stays as is: the reassembly branch's own `redraw()` is harmless, because marks collapse by priority. Update the docstring: an interior batch that repaints a node (move, stage change, redraw request, reload) redraws the card, whatever else it carries; a value edit does not.

- [ ] **Step 4: Run the tests**

Run: the Step 2 command, then `uv run pytest tests/core/test_graph tests/core/test_macro -n 4 -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/barn/builtin/nodes/graph_node.py tests/core/test_graph/test_interior_redraws_the_card.py tests/core/test_macro/test_macro_node.py
git commit -m "feat(graph): a Graph-node card redraws when its interior changes visually"
```

---

### Task 2: Graph-nodes offer `graph-node` skins

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/skin/tags.py` (add `SKIN_TAG_GRAPH_NODE = "graph-node"` with a `#:` comment: "A skin for Graph-nodes (Groups and macro placements); offered only in their skin lists.")
- Modify: `packages/haywire-core/src/haywire/core/skin/settings.py` (two functions, next to `_widget_node_stage_skin_choices`)
- Modify: `packages/haywire-core/src/haywire/barn/builtin/nodes/graph_node.py` (a `class props(BaseNode.props)` redeclaring `skin` and `stage_skin`)
- Modify: `tests/core/test_skin/test_stage_skin_fields.py` (append tests)

**Interfaces:**
- Produces: `_graph_node_patch_skin_choices() -> dict[str, str]` = `{**_patch_skin_choices(), **skin_choices(include=[SKIN_TAG_SPECIAL, SKIN_TAG_GRAPH_NODE], exclude=[SKIN_TAG_STAGE_ONLY])}`, and `_graph_node_stage_skin_choices() -> dict[str, str]` = `{**_stage_skin_choices(), **skin_choices(include=[SKIN_TAG_SPECIAL, SKIN_TAG_GRAPH_NODE])}`. 6c tags InsetSkin `["special", "graph-node"]`, which puts it in both.

- [ ] **Step 1: Write the failing tests** (in `test_stage_skin_fields.py`, reusing its `registry` fixture and `_skin_cls`)

```python
def test_graph_node_lists_add_graph_node_skins_to_the_general_ones(registry) -> None:
    from haywire.core.skin.settings import _graph_node_patch_skin_choices, _graph_node_stage_skin_choices
    general = _skin_cls("General", tags=["general"])
    stage_only = _skin_cls("StageOnly", tags=["general", "stage-only"])
    inset = _skin_cls("Inset", tags=["special", "graph-node"])
    stage_inset = _skin_cls("StageInset", tags=["special", "graph-node", "stage-only"])
    widget = _skin_cls("Widget", tags=["special", "stage-only", "widget-node"])
    # register all five
    key = lambda c: c.class_identity.registry_key
    assert set(_graph_node_patch_skin_choices()) == {key(general), key(inset)}
    assert set(_graph_node_stage_skin_choices()) == {key(general), key(stage_only), key(inset), key(stage_inset)}

def test_graph_nodes_offer_graph_node_skins() -> None:
    from haywire.barn.builtin.nodes.graph_node import GraphNode
    from haywire.barn.builtin.nodes.macro_node import MacroNode
    from haywire.core.skin.settings import _graph_node_patch_skin_choices, _graph_node_stage_skin_choices
    for cls in (GraphNode, MacroNode):
        fields = cls.props._settings_descriptors()
        assert fields["skin"].widget_config["properties"]["options"] is _graph_node_patch_skin_choices
        assert fields["stage_skin"].widget_config["properties"]["options"] is _graph_node_stage_skin_choices

def test_a_graph_node_skin_still_follows_the_graph_default(graph_with_library_system) -> None:
    # card = make_node(graph, "haywire-core:node:GraphNode"); graph.props.default_skin = "skin-graph"
    # graph.props.default_stage_skin = "stage-graph"
    # assert card.node.props.skin == "skin-graph" and card.node.props.stage_skin == "stage-graph"
```

- [ ] **Step 2: Run them and confirm they fail**

Run: `uv run pytest tests/core/test_skin/test_stage_skin_fields.py -q -k "graph_node"`
Expected: the first two FAIL (ImportError / wrong options). The tier test PASSES already: it pins the chain, which must survive the redeclare.

- [ ] **Step 3: Implement the tag, the two functions, and `GraphNode.props`**

`GraphNode.props` redeclares both fields exactly as `NodeProperties` declares them (`graph(src=GraphProperties.default_skin, label="Skin", category="appearance", order=10, ...)` and the `stage_skin` twin with its description and `order=11`). Only `widget_config={"options": ...}` changes, to the new functions. Class docstring: "Offers the skins tagged for Graph-nodes on top of the general ones; inherits every other field." `GraphProperties` comes from `haywire.core.graph.properties` (check the import `node/properties.py` uses).

- [ ] **Step 4: Run the tests and the skin and Graph-node areas**

Run: `uv run pytest tests/core/test_skin tests/core/test_node/test_node_skin_graph_tier.py tests/core/test_graph tests/core/test_macro -n 4 -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/skin packages/haywire-core/src/haywire/barn/builtin/nodes/graph_node.py tests/core/test_skin/test_stage_skin_fields.py
git commit -m "feat(skins): Graph-nodes list skins tagged graph-node"
```

---

### Task 3: Tearing down one card keeps the node's other cards' hot-reload tracking

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/skin/factory.py`: delete `_unregister_node` (`:331-341`). `remove_factory_lifecycle_subscriber` (`:251-269`) also calls `self._widget_factory.unregister_widget_for_node(node_id)` once the node's last subscriber is gone. Update its docstring: "Releases one card: the node's widget tracking ends with its last card."
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/ui_node.py:569` (drop the `self.factory._unregister_node(self._node_id)` line from `teardown_subscriptions`)
- Modify: `tests/ui/skin/test_skin_factory_subscribers.py` (append tests; reuse `_factory`, `_reloaded`)

**Interfaces:**
- Consumes: `SkinFactory.add_factory_lifecycle_subscriber(node_id, skin_registry_key, callback)` and `remove_factory_lifecycle_subscriber(node_id, callback)`, unchanged signatures.
- Produces: a card's teardown is exactly `remove_factory_lifecycle_subscriber(node_id, own_callback)`. 6c's InsetView tears interior cards down through `UINode.teardown_subscriptions` and relies on this.

- [ ] **Step 1: Write the failing tests**

```python
def test_widget_tracking_ends_with_the_last_card() -> None:
    factory = _factory()
    patch_card, stage_card = MagicMock(), MagicMock()
    factory.add_factory_lifecycle_subscriber("n1", "lib:skin:Split", patch_card)
    factory.add_factory_lifecycle_subscriber("n1", "lib:skin:StackedStage", stage_card)
    factory.remove_factory_lifecycle_subscriber("n1", patch_card)
    factory._widget_factory.unregister_widget_for_node.assert_not_called()
    factory.remove_factory_lifecycle_subscriber("n1", stage_card)
    factory._widget_factory.unregister_widget_for_node.assert_called_once_with("n1")

def test_tearing_down_one_card_keeps_the_other_cards_reloads(monkeypatch) -> None:
    from haybale_graph_editor.editors.graph_canvas.ui_node import UINode
    factory = _factory()
    ui_node = UINode.__new__(UINode)
    ui_node.factory, ui_node._node_id, ui_node.current_ui_card = factory, "n1", None
    monkeypatch.setattr(ui_node, "_unsubscribe_slot_fields", lambda: None)
    other_card = MagicMock()
    factory.add_factory_lifecycle_subscriber("n1", "lib:skin:Split", ui_node._listen_on_factory_lifecycle_event)
    factory.add_factory_lifecycle_subscriber("n1", "lib:skin:StackedStage", other_card)
    ui_node.teardown_subscriptions()
    _reloaded(factory, "lib:skin:StackedStage")
    other_card.assert_called()
```

- [ ] **Step 2: Run them and confirm they fail**

Run: `uv run pytest tests/ui/skin/test_skin_factory_subscribers.py -q`
Expected: both new tests FAIL. The bug is confirmed: `_unregister_node` drops every card's skin index, and nothing ever ends widget tracking per card.

- [ ] **Step 3: Implement the factory change and drop the UINode call**

After the edit, `grep -rn "_unregister_node" packages barn tests` should find nothing.

- [ ] **Step 4: Run the tests and the canvas areas**

Run: `uv run pytest tests/ui/skin tests/graph_editor tests/ui/graph_canvas -m "not browser" -n 4 -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/skin/factory.py barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/ui_node.py tests/ui/skin/test_skin_factory_subscribers.py
git commit -m "fix(skins): tearing down one card keeps the node's other cards' hot-reload tracking"
```

---

### Task 4: Docs and full verification

**Files:**
- Modify: `docs/components/skins/skin-canon.md` "Tags: which lists offer a skin": add a `graph-node` row to the tag table ("For Graph-nodes (Groups and macro placements); their lists add these to the general ones") and to the list table: `| Graph-node patch skin | general, or special + graph-node | special without graph-node, stage-only |` and `| Graph-node stage skin | general, or special + graph-node | special without graph-node |`.
- Modify: [2026-10-12-editor-modes.md](2026-10-12-editor-modes.md) Sequence 6b: link this plan.
- Regenerate: `uv run haywire docs --all`, then commit only the drift caused by this plan (builtin GraphNode/MacroNode pages). Report any unrelated drift and leave it uncommitted.

- [ ] **Step 1: Edit the docs and regenerate**

- [ ] **Step 2: Quality gates**

Run: `uv run ruff check . && uv run ruff format --check .`, then the full mypy command from CLAUDE.md.
Expected: clean, apart from the known pre-existing `.scratch/draw-perf` findings.

- [ ] **Step 3: Suites**

Run: `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/6b-full.log 2>&1; echo "exit=$?"` and `uv run pytest -m browser -n 4 -q > /tmp/6b-browser.log 2>&1; echo "exit=$?"`
Expected: green. The only allowed failure is `test_the_fixture_that_carries_fold_keys_migrates_them`, which is caused by the user's uncommitted `graphs/any_and_nonde.haywire`. Report it, don't fix it.

- [ ] **Step 4: Commit**

```bash
git add docs/components/skins/skin-canon.md docs/superpowers/plans/2026-10-12-editor-modes.md <regenerated builtin docs>
git commit -m "docs: graph-node skin lists; plan 6b linked"
```

- [ ] **Step 5: Live check (user)**

1. Open a graph with a Group, enter it, move an interior node, go back up: the Group card is unchanged and nothing logs an error.
2. A Group's and a placement's Properties → Skin and Stage Skin list the same skins as before. Nothing is tagged `graph-node` until 6c.
3. Put a node on stage, open the stage view once, then Remove from Stage. Touch its patch skin file (`haybale_graph_editor/skins/stacked_skin.py`, add and remove a blank line): the patch card still redraws on the reload.
