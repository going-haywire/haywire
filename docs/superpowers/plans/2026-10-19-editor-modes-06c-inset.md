# Editor modes 6c: the Inset — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Graph-node card (Group or macro placement) can be drawn with the **Inset** skin, which shows its interior's stage inside the card. Widgets in it can be operated at the host level's mode; its layout cannot be edited.

**Architecture:** `InsetSkin` (a `NodeSkin` subclass in haybale-graph-editor) draws the card frame. Its body is an `InsetView` that builds one ordinary `UINode` per staged interior node, through an interior `EditRoute` derived from the host card's route. The card redraws itself on any interior visual change (6b), and the view is rebuilt with it. One CSS rule in `canvas.vue` makes everything inside the body inert except operable widgets, and box select skips it.

**Tech Stack:** Python 3.12, NiceGUI, haywire skins (`BaseSkin`, `NodeSkin`, `SkinFactory`), `UINode`, `EditRoute`/`Editor`, Vue (`canvas.vue` global CSS + box select), Playwright harness.

**Spec:** [2026-10-12-editor-modes.md](2026-10-12-editor-modes.md), section "Inset (bpatcher)" (settled 2026-10-19) and Sequence item 6c. 6a ([ADR 0057](../../adr/0057-the-default-skins-live-in-the-graph-editor.md)) and 6b ([plan](2026-10-19-editor-modes-06b-inset-groundwork.md)) are built and live-checked.

## Decisions this plan adds (for review)

These fill gaps the spec leaves open. The plan follows them unless you overrule one at review.

1. **`EditRoute.for_subgraph(definition) -> EditRoute`** (core). A route to a Subgraph's nodes at **this** route's level mode. Edits record on this route's history, through `Editor(definition, node_factory, history_manager=...)` of the route's current editor. This is how the spec's "interior route at the host route's mode" gets built without reaching into private fields.
2. **`BaseSkin.on_card_cleanup(node_id, callback)`** (core, plus `UINodeCard.add_cleanup`). A skin registers a callback that runs when the card it is drawing is cleaned up, i.e. on redraw or teardown, alongside its widgets' cleanup. The InsetView uses it to tear down its child `UINode`s. Today a skin can only own widgets.
3. **InsetSkin gets the `SkinFactory` from `get_library_system().get_skin_factory()`** at render. It is the existing DI singleton, read where the card is drawn. A skin is constructed with a widget factory only.
4. **The stage face keeps the card frame** (theme background and border) around the body. It has no title.
5. **A Graph-node with no bound interior** shows the same placeholder as an empty stage.
6. **The canvas owns its cards' client teardown, on `client.on_delete`** (user, option A, 2026-10-19). `UINode.__init__` registers `client.on_disconnect(lambda: self.cleanup())`. NiceGUI 3.x runs disconnect handlers immediately on **every** websocket drop, even one the browser reconnects from, so a network blip tears down the subscriptions of every card on screen. Each new `UINode` also adds a closure that is never removed. `UINode` stops registering it. `VisualLayerHandlers` registers one `client.on_delete(self.cleanup)` instead, and Inset child cards are released through their host card. `BaseWidget` registers `on_disconnect(self.cleanup)` (`ui/widget/base.py:174`) with the same blip effect, so it moves to `on_delete` too.

## Global Constraints

- Builtin references nothing outside core. graph-editor gains no dependency.
- InsetSkin: `@skin(label="Inset", description="The interior's stage, operable in the card", tags=["special", "graph-node"])`. Registry key `haybale-graph-editor:skin:InsetSkin`.
- Body floor: exactly **240 × 160 px**, `overflow: hidden` (clip), stage (0,0) at the body's top-left.
- Placeholder text, verbatim: **"Nothing on stage — Enter to arrange"**.
- The interior cards' containers carry **no `data-node-id`**. The body carries `data-hw-inset`.
- No folds, no detail, no port labels, no port widgets and no config ports on the Inset's own card. `honours_detail()` → `False`.
- The level-mode gate in `canvas.vue` keeps precedence: in `view` nothing inside an Inset takes input, and in `operate` only operable widgets do.
- **Trap:** `tests/studio/test_docs/test_generate.py` reverts `barn/haybale-testing` in teardown. Commit anything there before a full run.

## Review Focus

1. **A slider in an Inset keeps its drag.** A value write must not rebuild the Inset (6b guarantees no card redraw for values). The browser test drags a slider and checks the value.
2. **A press on the Inset body acts on the host card:** select and move the host, open the host's menu, double-click to Enter. A press on a widget operates the widget. Pinned by `test_a_press_on_the_body_selects_the_host_card` and the slider test.
3. **Box select never picks interior ids.** Pinned by `test_box_select_takes_the_inset_card_not_its_interior`.
4. **Child cards are released on every redraw.** No skin, widget or hot-reload tracking is leaked for interior node ids after the host card redraws or goes. Pinned by `test_a_redraw_releases_the_interior_cards`.
5. **An Inset write follows the host level's mode**: an undo step in `edit`, a plain write in `operate`, refused in `view`. Pinned by `test_an_interior_route_follows_the_host_mode`.
6. **A websocket drop that reconnects leaves every card and widget subscribed, and a rebuilt Inset adds no client handlers.** Pinned by Task 1b's tests. Still pre-existing, not fixed here: `BaseWidget` adds one `on_delete` closure per widget per card redraw, and they stay until the tab closes. Report it as a deferred minor.

---

### Task 0: Baseline

- [ ] Run `uv run ruff check barn/haybale-graph-editor packages/haywire-core/src/haywire/ui/skin packages/haywire-core/src/haywire/core/graph/edit_route.py` and `uv run mypy barn/haybale-graph-editor/haybale_graph_editor/ packages/haywire-core/src/haywire/ui/skin/ packages/haywire-core/src/haywire/core/graph/edit_route.py`. Expected: clean.
- [ ] Run `uv run pytest tests/ui/skin tests/graph_editor tests/core/test_graph/test_edit_route.py -m "not browser" -n 4 -q`. Expected: green. Note the count.

---

### Task 1: Two core seams: `EditRoute.for_subgraph` and `BaseSkin.on_card_cleanup`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/graph/edit_route.py` (add `for_subgraph`, plus an example line in the class docstring)
- Modify: `packages/haywire-core/src/haywire/ui/skin/nodecard.py` (`UINodeCard.add_cleanup(callback: Callable[[], None]) -> None`; `cleanup()` runs the registered callbacks after the widgets, each once, then forgets them)
- Modify: `packages/haywire-core/src/haywire/ui/skin/base.py` (`BaseSkin.on_card_cleanup(node_id: str, callback: Callable[[], None]) -> None`, collected per node for one render like `_nodeids_widget_instances`, handed to the card in `_render_into_card` via `add_cleanup`, and cleared there)
- Test: `tests/core/test_graph/test_edit_route.py` (append), `tests/ui/skin/test_card_cleanup.py` (create)

**Interfaces:**
- Produces: `EditRoute.for_subgraph(definition: SubgraphDefinition) -> EditRoute`. Its `mode()` is always this route's `mode()`. Its editor is an `Editor(definition, <current editor's node factory>, history_manager=<current editor's history_manager>)`, rebuilt only when this route's current editor changes. Calling it below `EDIT` is fine: it reads the editor ungated.
- Produces: `BaseSkin.on_card_cleanup(node_id, callback)` and `UINodeCard.add_cleanup(callback)`.

- [ ] **Step 1: Write the failing tests**

In `test_edit_route.py`, reusing its fixtures (`held_graph`/`route` style; build a definition with `held_graph.add_subgraph(SubgraphDefinition(key="sg", label="G"))` and a node in it with `make_node`):

```python
def test_an_interior_route_follows_the_host_mode(...):
    # host route over an EDIT level; inner = route.for_subgraph(definition)
    # set level mode EDIT: inner.set_port(inner_node_id, <a port with an own value>, v, minimum=OPERATE) is True,
    #   and the host editor's history_manager.can_undo() is True (the step landed on the host history)
    # set mode OPERATE: write is True, no new undo step
    # set mode VIEW: write is False and the value is unchanged
    assert inner.mode() is route.mode()

def test_an_interior_route_reaches_only_interior_nodes(...):
    # inner.set_port(<a host node id>, ...) is False
```

`tests/ui/skin/test_card_cleanup.py` (unit; a `BaseSkin` subclass whose `render` calls `self.on_card_cleanup(wrapper.node_id, spy)`; render via `skin._render(wrapper)` under a NiceGUI `Client` as in `tests/graph_editor/test_ui_node_stage_skin.py::_card`):

```python
def test_a_skin_cleanup_runs_when_the_card_is_cleaned_up(): card = skin._render(...); spy not called; card.cleanup(); spy called once
def test_a_skin_cleanup_runs_once(): card.cleanup(); card.cleanup(); spy called once
def test_a_skin_cleanup_belongs_to_one_render(): two renders, cleaning the first runs only the first render's callback
```

- [ ] **Step 2: Run them and confirm they fail** (AttributeError on `for_subgraph` / `on_card_cleanup`)

Run: `uv run pytest tests/core/test_graph/test_edit_route.py tests/ui/skin/test_card_cleanup.py -q`

- [ ] **Step 3: Implement both seams as specified in Interfaces**

- [ ] **Step 4: Run the tests and the skin and edit-route areas**

Run: `uv run pytest tests/core/test_graph/test_edit_route.py tests/ui/skin tests/graph_editor -m "not browser" -n 4 -q`
Expected: all PASS.

- [ ] **Step 5: Commit** `feat(core): EditRoute.for_subgraph and skin-owned card cleanups`

---

### Task 1b: The canvas owns its cards' client teardown

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/ui_node.py:85`: drop the `on_disconnect` registration. Its docstring gains: "Whoever creates a UINode tears it down (`teardown_subscriptions`); it registers nothing on the client."
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/visual_layer.py` `__init__`: `canvas_vue.client.on_delete(self.cleanup)`, guarded by `hasattr(canvas_vue, "client")` as `BaseWidget` does. `cleanup()` must stay idempotent; it is, since `node_panels` is cleared.
- Modify: `packages/haywire-core/src/haywire/ui/widget/base.py:174`: `on_disconnect` → `on_delete`.
- Test: `tests/graph_editor/test_client_teardown.py` (create; NiceGUI `Client` pattern from `tests/graph_editor/test_ui_node_stage_skin.py`)

**Interfaces:**
- Produces: a `UINode` registers no client handler. A canvas's cards are torn down when the client is deleted. 6c's InsetView relies on the first: its child cards add nothing to the client.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_card_registers_no_client_handler(library_system, held_graph):
    # with client: before = len(client.disconnect_handlers) + len(client.delete_handlers); build a UINode (as _card does)
    # assert len(client.disconnect_handlers) + len(client.delete_handlers) == before
def test_a_disconnect_leaves_the_cards_subscribed(library_system, held_graph):
    # build a UINode; run every handler in client.disconnect_handlers (as Client.handle_disconnect does: client.safe_invoke(h))
    # assert the node id is still in factory._nodeid_to_factory_subscriber
def test_deleting_the_client_tears_the_canvas_cards_down():
    # layer = VisualLayerHandlers.__new__(VisualLayerHandlers); layer.node_panels = {"n1": mock}; layer.edge_states = {}
    # with a real Client: call the registration helper __init__ uses (extract it as
    #   _release_on_client_delete(self, client) so the test needs no full canvas); client.delete()
    # mock.teardown_subscriptions.assert_called_once()
def test_a_widget_survives_a_disconnect(...):
    # a NumberWidget rendered for a port under a Client; run the disconnect handlers;
    # a model change still reaches the widget (its _model_dispatch_cb is still subscribed on port.data.on_changed)
```

- [ ] **Step 2: Run and confirm they fail**

Run: `uv run pytest tests/graph_editor/test_client_teardown.py -q`
Expected: FAIL. The UINode adds a handler, the disconnect tears the card down, the helper doesn't exist, and the widget unsubscribes on disconnect.

- [ ] **Step 3: Implement the three changes** (`VisualLayerHandlers._release_on_client_delete(client)` called from `__init__`)

- [ ] **Step 4: Run the tests, the canvas areas, and the browser tier**

Run: `uv run pytest tests/graph_editor/test_client_teardown.py -q`, then `uv run pytest tests/ui tests/graph_editor -m "not browser" -n 4 -q`, then `uv run pytest -m browser -n 4 -q`
Expected: all PASS.

- [ ] **Step 5: Commit** `fix(canvas): a websocket drop no longer tears down the cards on screen`

---

### Task 2: `InsetView`, the interior's stage as plain cards

**Files:**
- Create: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/inset_view.py`
- Test: `tests/graph_editor/test_inset_view.py`

**Interfaces:**
- Consumes: `EditRoute.for_subgraph` (Task 1), `UINode(container, wrapper, factory, route, channel=STAGE)`, `STAGE.includes(props)`, `props.get_position(STAGE)`.
- Produces:

```python
class InsetView:
    """The staged nodes of one Subgraph, each drawn by its own UINode with its stage skin."""
    def __init__(self, body: ui.element, definition: SubgraphDefinition | None,
                 factory: SkinFactory, route: EditRoute | None) -> None: ...
    @property
    def cards(self) -> dict[str, UINode]: ...   # interior node id -> its card
    def cleanup(self) -> None: ...              # teardown_subscriptions() on every card, once
```

Building happens in `__init__`, inside `with body:`. For every interior wrapper whose props `STAGE.includes(...)`, in `stage_z` order (ties by creation order):
- a container `ui.element("div").classes("absolute").style(f"left: {x}px; top: {y}px; transform-origin: top-left;").props(f'data-hw-inset-node="{node_id}"')`, where `(x, y) = props.get_position(STAGE)` (the raw stage position, so stage (0,0) is the body's top-left);
- a `UINode(container, wrapper, factory, interior_route, channel=STAGE)` with `.refresh(ChangeReason.NODE_ADDED)`.

Here `interior_route = route.for_subgraph(definition)`, or `None` when `route` is `None`. A `definition` of `None`, or none staged, builds no card and leaves `cards` empty. The placeholder belongs to the skin (Task 3).

- [ ] **Step 1: Write the failing tests** (integration; `Client`/`UINode` pattern from `tests/graph_editor/test_ui_node_stage_skin.py`; a host graph with `add_subgraph` and two `TestAddFloatNode`s inside, one with `props.on_stage = True`, `stage_x=30`, `stage_y=40`)

```python
def test_only_staged_interior_nodes_get_a_card(...): assert set(view.cards) == {staged.node_id}
def test_a_card_sits_at_its_stage_position(...):
    container = view.cards[staged.node_id].container
    assert container._style["left"] == "30.0px" and container._style["top"] == "40.0px"
def test_interior_cards_carry_no_node_id_attribute(...):
    assert not [e for e in body.descendants() if e._props.get("data-node-id") == staged.node_id and "data-pin-id" not in e._props]
    # the container carries data-hw-inset-node instead
def test_a_redraw_releases_the_interior_cards(...):
    factory = library_system.injector.get(SkinFactory)
    view.cleanup()
    assert staged.node_id not in factory._nodeid_to_factory_subscriber
def test_no_definition_builds_nothing(...): InsetView(body, None, factory, route).cards == {}
```

- [ ] **Step 2: Run and confirm they fail** (ModuleNotFoundError)

Run: `uv run pytest tests/graph_editor/test_inset_view.py -q`

- [ ] **Step 3: Implement `InsetView`**

- [ ] **Step 4: Run the tests and the graph-editor area**

Run: `uv run pytest tests/graph_editor -m "not browser" -n 4 -q` → PASS

- [ ] **Step 5: Commit** `feat(graph-editor): InsetView draws a Subgraph's stage as plain cards`

---

### Task 3: `InsetSkin`

**Files:**
- Create: `barn/haybale-graph-editor/haybale_graph_editor/skins/inset_skin.py`
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/skins/node_skin.py`: add `NodeSkin.card_style(self) -> str`, returning the theme-token card style string `StackedNodeSkin.render` builds today (background, border, radius, colour, backdrop blur, `overflow: visible`, horizontal padding). Make Stacked and Split call it instead of building their own copy. The string must stay identical, which the existing skin tests confirm.
- Test: `tests/graph_editor/test_inset_skin.py`

**Interfaces:**
- Consumes: `InsetView` (Task 2), `BaseSkin.on_card_cleanup` (Task 1), NodeSkin helpers `header_row`, `_render_title`, `_render_diagnostics_badge`, `_render_root_ghost_pins`, `_render_pin_column`, `render_pin_strip`, `_render_collapsed`, `strip_min_width`, `vertical_card_style`, `layout_of`, `is_collapsed`, `card_classes`.
- Produces: `InsetSkin` with `INSET_FLOOR_PX: tuple[int, int] = (240, 160)` and `honours_detail(*, on_stage) -> False`. `card_classes()` returns `"inset-node-card"`, a sibling token next to `node-card`.

`render(main_card, wrapper, *, on_stage)`:
- **Pins:** `inlets` / `outlets` = `node.get_all_ports()` filtered to `not port.is_fold and port.has_pin()`, split by `is_inlet()` / `is_outlet() and not is_swinglet()`.
- **Collapsed** (`is_collapsed(wrapper) and not on_stage`): `self._render_collapsed(main_card, node, wrapper, layout, self.card_style())`.
- **Stage** (`on_stage`): `main_card.classes(f"node-card zoom-pan-lod0 {self.card_classes(wrapper)}").style(self.card_style())`, then only the body.
- **Patch, horizontal:** the card classes `w-full node-card zoom-pan-lod0 inset-node-card` and `card_style()`. Inside the card:
  - the diagnostics badge;
  - `header_row("gap-2")` holding the root ghost pins and the title;
  - a body row `ui.row().classes("w-full no-wrap").style(f"position: relative; flex: 1 1 auto; min-height: {max(len(inlets), len(outlets)) * self.PIN_GUTTER}px;")` holding the inlet pin column, the body and the outlet pin column. The column order follows `layout.inlet_side`, as in SplitNodeSkin.
- **Patch, vertical:** `card_style()` + `vertical_card_style()` + `min-width: strip_min_width(...)`. The top pin strip (with its ghost), the header row with the title, the body, then the bottom pin strip. The top-first rule is the one `_render_collapsed_vertical` uses.
- **Body:** `ui.element("div").classes("hw-inset-body").props("data-hw-inset").style("position: relative; overflow: hidden; flex: 1 1 auto; min-width: 240px; min-height: 160px;")`. Inside it:
  - `view = InsetView(body, definition, get_library_system().get_skin_factory(), self._nodeids_routes.get(wrapper.node_id))`, where `definition = getattr(wrapper.node, "resolve_definition", lambda: None)()`;
  - `self.on_card_cleanup(wrapper.node_id, view.cleanup)`;
  - if `view.cards` is empty, a centred `ui.label("Nothing on stage — Enter to arrange").classes("text-xs hw-text-muted")`.

- [ ] **Step 1: Write the failing tests** (integration; render a Group card through `UINode` on PATCH and STAGE via the `_card` pattern, with the card's `props.skin` / `props.stage_skin` set to `InsetSkin.class_identity.registry_key`)

```python
def test_the_inset_is_offered_for_graph_nodes_only(library_system):
    key = InsetSkin.class_identity.registry_key
    assert key in _graph_node_patch_skin_choices() and key in _graph_node_stage_skin_choices()
    assert key not in _patch_skin_choices() and key not in _stage_skin_choices()
def test_the_patch_face_is_title_pins_and_body(...):  # a title label, a [data-hw-inset] element, the card's interface pins, no port labels
def test_the_stage_face_is_the_body_only(...):        # [data-hw-inset] present, no title label, no data-pin-id
def test_the_body_draws_the_staged_interior(...):     # a [data-hw-inset-node=<staged id>] inside [data-hw-inset]
def test_an_empty_stage_shows_the_placeholder(...):   # label text == "Nothing on stage — Enter to arrange"
def test_a_collapsed_inset_has_no_body(...):          # props.collapsed = True → no [data-hw-inset] on PATCH
def test_redrawing_the_card_releases_the_old_interior_cards(...):
    # ui_node.refresh(...) twice; the staged id's factory subscribers number exactly 1 (the new card)
```

- [ ] **Step 2: Run and confirm they fail** (ImportError)

Run: `uv run pytest tests/graph_editor/test_inset_skin.py -q`

- [ ] **Step 3: Implement `card_style()` (Stacked and Split use it) and `InsetSkin`**

- [ ] **Step 4: Run the tests and the skin areas**

Run: `uv run pytest tests/graph_editor tests/ui/skin -m "not browser" -n 4 -q` → PASS

- [ ] **Step 5: Commit** `feat(graph-editor): the Inset skin — a Graph-node's interior stage in its card`

---

### Task 4: Input inside an Inset, and the browser checks

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue`:
  - **(a)** In the global style block after the level-mode gate (`:4461-4469`), add:
    - `.graph-canvas [data-hw-inset] *:not([data-hw-operable]):not([data-hw-operable] *) { pointer-events: none !important; }`
    - `:where(.graph-canvas [data-hw-inset] [data-hw-operable]) { pointer-events: auto; }`
    - `.graph-canvas [data-hw-inset] [data-pin-id] { display: none !important; }`
    - with one comment line: an Inset's interior takes input only on operable widgets, so any other press lands on the host card.
  - **(b)** In `_findNodesInRectangle` (`:2718`), skip `nodeElement.closest('[data-hw-inset]')`.
  - **(c)** Add a line to the header comment block listing `data-hw-inset`.
- Modify: `tests/ui/harness/routes.py`: a new `GET /graph-inset?mode=edit|operate|view` route. It is `_build_enter_graph`'s Group, with its card's `props.skin = InsetSkin key`, and one `FloatSliderNode` placed inside the definition on stage at `(20, 20)`. Expose:
  - `inset-card-id` (the card id) and `inset-slider-id` (the slider id);
  - a polled echo `echo-inset-value` of the slider's `value` outlet;
  - a polled `echo-undo` of `editor.history_manager.can_undo()`;
  - `_mount_graph_canvas(..., level=_HarnessLevel(mode=LevelMode(mode)))`.
- Create: `tests/ui/harness/test_inset.py` (`pytestmark = pytest.mark.ui`, `_open` as in `test_widget_nodes.py`)

- [ ] **Step 1: Write the browser tests**

```python
def test_a_slider_in_an_inset_writes_the_interior_value(page, harness):   # mode=operate; drag the .q-slider inside [data-hw-inset] full right → echo-inset-value "1.0"
def test_an_inset_write_in_edit_is_an_undo_step(page, harness):           # mode=edit; drag → echo-undo "True"
def test_a_view_session_cannot_move_the_inset_slider(page, harness):      # mode=view; drag → echo-inset-value unchanged
def test_a_press_on_the_body_selects_the_host_card(page, harness):        # mode=edit; click inside [data-hw-inset] away from the slider → host card has class node-selected
def test_box_select_takes_the_inset_card_not_its_interior(page, harness): # marquee from empty canvas over the whole card →
    # the ids of all '.graph-canvas .node-selected' elements (as tests/ui/harness/test_graph_views.py:226 collects them)
    # == {card id}; nothing carries data-hw-inset-node with node-selected
def test_inset_pins_are_hidden(page, harness):                             # every [data-hw-inset] [data-pin-id] is not visible
```

- [ ] **Step 2: Run them and confirm the input tests fail before the CSS** (body press selects nothing / box select returns the interior id)

Run: `uv run pytest tests/ui/harness/test_inset.py -q`

- [ ] **Step 3: Implement the CSS rule and the box-select guard**

- [ ] **Step 4: Run the Inset tests and the whole browser tier**

Run: `uv run pytest tests/ui/harness/test_inset.py -q`, then `uv run pytest -m browser -n 4 -q`
Expected: PASS.

- [ ] **Step 5: Commit** `feat(canvas): an Inset's interior takes input only on its widgets`

---

### Task 5: Docs, full verification, live check

**Files:**
- Modify: `docs/reference/glossary.md`: add **Inset**: "A Graph-node card drawn with the Inset skin: its body shows the interior's stage, whose widgets can be operated at the host level's mode, while its layout can only be changed by entering the interior. Patch: title, pins and the body; stage: the body only." Its avoid-column holds *bpatcher* (Max's word) and *presentation* (taken, ADR 0029).
- Modify: `docs/components/skins/skin-canon.md`: a short "The Inset" section. Its tags (`special`, `graph-node`); how it is built (InsetView of `UINode`s at `stage_x/y`, interior route `for_subgraph`, cleanup via `on_card_cleanup`); input (`data-hw-inset` rule); a 240 × 160 floor, clipped; no edges.
- Modify: [2026-10-12-editor-modes.md](2026-10-12-editor-modes.md) Sequence 6c: link this plan. Fix the stale `_graph_node_skin_choices()` name (6b review minor).
- Regenerate: `uv run haywire docs barn/haybale-graph-editor` (the new skin's page).

- [ ] **Step 1: Edit the docs and regenerate**
- [ ] **Step 2: Quality gates.** Run `uv run ruff check . && uv run ruff format --check .` and the full mypy command (CLAUDE.md). Expected: clean apart from the known `.scratch/draw-perf`.
- [ ] **Step 3: Suites.** Run `uv run pytest -m "not browser and not perf" -n 4 -q` and `uv run pytest -m browser -n 4 -q`. Expected: green. The only allowed failure is `test_the_fixture_that_carries_fold_keys_migrates_them` (the user's local graph file).
- [ ] **Step 4: Commit** `docs: the Inset — glossary, skin canon, plan 6c linked`
- [ ] **Step 5: Live check (user)**

1. In a graph, collapse two or three nodes into a Group. Enter it, switch to Stage, put a widget node (e.g. a Float Slider) and an annotation on stage, then go back up.
2. Properties of the Group → Skin → **Inset**. The card shows its title, its pins on the edges, and the slider and annotation in the body at their stage positions. Edges still attach to the card's pins.
3. Drag the slider: the value changes (check downstream inside or out), and Ctrl+Z undoes it while the canvas is unlocked.
4. Click and drag on the body away from the slider: the Group card is selected and moves. Right-click: the Group's menu. Double-click: enters the Group.
5. Lock the canvas (Mod+E). The slider still works, the card can't be moved, and the annotation text can't be edited.
6. Enter the Group, move the slider on its stage, go back up: the Inset shows the new position.
7. Set Stage Skin → Inset and switch the host to Stage: the card shows only the body. A Group with nothing on stage shows "Nothing on stage — Enter to arrange".
8. Resize the card (manual size): the body grows, and content beyond the edge is clipped.
