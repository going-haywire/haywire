# Surface model — implementation plan

Implements [ADR-0029](../../adr/0029-surface-model.md). Vocabulary is canon in
[glossary.md](../../reference/glossary.md).

Clean break: no compatibility shim, no dual vocabulary. `haybale-visiongraph`
declares no panels, so the whole blast radius is in-tree.

## Baseline

Established clean at `76928218`:

```sh
uv run ruff check packages/haywire-core/src/haywire/ui/ barn/haybale-graph-editor/ barn/haybale-studio/
uv run mypy packages/haywire-core/src/haywire/ui/panel/ barn/haybale-graph-editor/haybale_graph_editor/
```

Both pass. Anything new after an edit belongs to that edit.

## Scope

Roughly 60+ source files and 30 test files, across four barn libraries and core.
The vocabulary rename alone is 67 registered `@panel` declarations (74 `focus=`
call sites counting the surface classes) and ~126 `BasePanel` subclasses once test
doubles are included.

That figure has grown twice and is a floor, not an estimate:

- The first pass said 16 barn files, missing `haybale-testing` (4 panel files +
  `test_focuses.py`), `haybale-haystack` (2 panel files), and the graph-editor
  properties panels sitting on focuses the naming table treats as menu-only.
- The review that produced Stages 3b and `draw_disabled` added: the canvas
  dispatch rewrite (`canvas.vue`, two events, the generated JS, `node_skin.py`,
  the graph-editor handlers), the ~20 menu panels that opt into greying, the
  toolbar's delegation to `SessionContextMenuProvider`, and Stage 0's extension of
  `flyout.py`.

Do not plan around a file count; plan around the stage boundaries in Order, and
note that Stages 2–4 land together.

Beyond the obvious panel and focus files, these carry the vocabulary and are easy
to miss:

- `packages/haywire-core/src/haywire/core/di/config.py` — the startup panel dump
  groups by `focus.id`. It also reads `class_identity.action`, which has never
  existed (the field is `action_protocol`), so it has always printed `?`. Fix
  both while there.
- `packages/haywire-core/src/haywire/ui/panel/__init__.py` — module docstring
  documents the two query surfaces, and `__all__` exports `Focus`,
  `focus_by_id`, `all_focuses`.
- `packages/haywire-core/src/haywire/ui/editor/wrapper.py:159` — comment about
  panel-driven subscriptions being the editor's own business.

Stage 3b rewrites the canvas menu dispatch, which pulls in a further set:

- `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue` —
  `handleContextMenu`, the whole priority chain.
- `packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py` —
  two events collapse into one.
- `packages/haywire-core/src/haywire/ui/components/graph/generated/graph_events.js`
  — generated; regenerate with `uv run python scripts/generate_vue_events.py`,
  never by hand.
- `packages/haywire-core/src/haywire/ui/skin/pin_render.py:128` — the comment
  saying the menu attribute is a host concern. It stops being one.
- `barn/haybale-studio/haybale_studio/skins/node_skin.py:307` — the only line in
  the tree that emits a menu attribute. Deleted.

`haybale-visiongraph` needs no change — grep for `focus=` returns only camera
settings labels there.

## Naming

| Now | Becomes |
| --- | --- |
| `Focus` | `Surface` |
| `Focus.available()` | `Surface.poll()` |
| `_FOCUS_BY_ID`, `focus_by_id()`, `all_focuses()` | `_SURFACE_BY_ID`, `surface_by_id()`, `all_surfaces()` |
| `@panel(focus=…, actions=…)` | `@panel(surface=…, hosts=…)` |
| `PanelIdentity.focus`, `.action_protocol` | `PanelIdentity.surface`, `.hosts` |
| `get_panels_for_focus()`, `get_panels_for_action()` | `get_panels()` |
| `get_display_focuses()` | `get_root_surfaces()` |
| `get_redraw_signals_for_focus()` | `get_redraw_signals()` |
| `NodeFocus`, `PortFocus`, `GraphFocus` | `NodeInspector`, `PortInspector`, `GraphInspector` |
| `PinFocus`, `SelectionFocus`, `FileFocus` | `PinMenu`, `SelectionMenu`, `FileMenu` |
| `CanvasFocus` | **splits** — `CanvasSettings` (`id="canvas"`) + the menu half absorbed by `GraphContext` |
| `EdgeFocus` | **splits** — `EdgeInspector` (`id="edge"`) + `EdgeMenu` (`id="edge-menu"`) |
| `ToolbarFocus` | `SelectionToolbar` |
| `SettingsFocus`, `AppFocus`, `ExecutionFocus`, `AccountFocus` | `SettingsInspector`, `AppSettings`, `ExecutionInspector`, `AccountMenu` |
| `SelectionContextActions`, `EdgeContextActions`, … | `SelectionActions`, `EdgeActions`, … |
| `ToolbarActions` | deleted — the ⋯ is a panel hosting a surface |
| `PropertiesEditor._active_focus_id` | `._active_surface_id` |
| `ScopeToolbar`, `hui.scope_button` | `SurfaceToolbar`, `hui.surface_button` |
| `data-hw-port-menu-focus-id`, `data-hw-custom-menu-focus-id` | one `data-hw-menu-surface-id` (Stage 3b) |
| `ContextMenuPortEvent`, `ContextMenuCustomEvent` | `ContextMenuSurfaceEvent` |
| `NodeContextActions` | deleted — the empty marker only served the action fork |

`AccountMenu` collides with the existing `AccountMenuProvider` class in
`haywire/ui/app/account_menu.py`. Keep the provider's name; the surface is the
`AccountMenu` the provider hosts.

### The two double-duty focuses

Dropping the display/action fork merges anything that shared a focus id. Two ids
do, and `action_protocol is None` is the only thing keeping them apart today:

| Focus | Display panels (properties tab) | Action panels (menu) |
| --- | --- | --- |
| `CanvasFocus` (`id="canvas"`) | 6 — CanvasSettings, NodeSkinSettings, EdgeUISettings, EditorZoomPanSettings, MinimapSettings, DebugOverlaySettings | 2 — CreateNodeMenu, PasteMenu |
| `EdgeFocus` (`id="edge"`) | 4 — EdgeErrors, EdgeWarnings, EdgeStats, EdgePath | 5 — EdgeErrorsMenu, EdgeWarningsMenu, InsertRerouteMenu, DeleteEdgeMenu, ReconnectEdgeMenu |

Left alone, the Edge properties tab grows a "Delete Edge" row and the edge
right-click menu grows EdgePath. Each needs two surfaces:

- **Canvas** resolves for free. Stage 4 already replaces the canvas right-click
  menu with `GraphContext` and its regions, so the action half has a new home.
  `CanvasFocus` becomes `CanvasSettings` — inspector, keeps `id="canvas"`, keeps
  its presentation, no `provides`. Note the surface `CanvasSettings` then sits one
  import away from the panel `CanvasSettingsPanel` that lives on it; keep them in
  different modules (`builtin/surfaces.py` vs `panels/properties/setting/`) so the
  two names never appear in the same file.
- **Edge** needs a real split. `EdgeInspector` keeps `id="edge"` and the
  presentation (`label="Edge"`, `icon="cable"`, `order=70`); `EdgeMenu` takes the
  new `id="edge-menu"` with `provides = EdgeActions` and no presentation. Giving
  the *menu* the new id leaves the DOM attributes and docs pointing at `edge`
  unchanged.

`EdgeErrorsPanel`/`EdgeErrorsMenuPanel` and the Warnings pair are duplicates the
fork forced into existence. Merging them is a separate ticket — do not widen this
one.

## Stage 0 — the nesting primitive

Stage 4's target shape needs a way to draw a thing that opens a panel-filled
flyout. **`hui.flyout_category` already is that** — the first draft of this plan
claimed nothing in `hui` did, which is wrong.
`packages/haywire-core/src/haywire/ui/elements/flyout.py` has `FlyoutMenu`,
`FlyoutSiblings`, `flyout_category`, `open_on_hover` and `close_flyout`:
hover-open, sibling-close, depth-first cascade-close, `FLYOUT_Z = 7100` over the
Popup's 7001. `NodeMenuBuilder` uses it for the add-node tree. This stage extends
it; it does not rebuild it.

### The sibling-group problem

That primitive is correct because callers thread a **shared `siblings` list**
through one menu level — opening a flyout closes the others in its group, leaving
exactly one open path from the root ([flyout.py:77-93](../../../packages/haywire-core/src/haywire/ui/elements/flyout.py#L77-L93)).
`NodeMenuBuilder` can do that because it owns its whole recursion.

Surface-model panels are mutually blind, which is the point of the model — so a
bare `hui.submenu_row(...)` call per panel would create a sibling group of one
each, and opening "Image ▸" would never close "Export ▸". Multiple open paths:
exactly the bug `flyout.py` exists to prevent.

**The sibling group is owned by the container, not by the panel and not by the
surface.** A menu *level* is a popup or a flyout — a visual box. It is emphatically
not a surface: `GraphContextPanel` renders `GraphToolBar` and `GraphContextBody`
into the **same** popup with two `render_surface` calls, and a submenu row in the icon
row is a visual sibling of one in the body. Grouping per surface would put them in
different groups and let both stay open, which is the pile-up from insights §5.

So the group is pushed by whoever opens a box:

- the context-menu host, around the popup content;
- `SubmenuRow.__enter__`, around its flyout body.

`render_surface` touches none of it. It renders panels into whatever slot and whatever
level is current, exactly as it does now.

Mechanism is a `ContextVar[FlyoutSiblings]`, the same shape as `_render_path`. On
construction a row reads the ambient group to register into and wires
sibling-close; on `__enter__` it pushes a fresh group for its body, which *is* its
`_child_flyouts` for the depth-first cascade. Panels pass nothing and never learn
they have siblings.

This generalises beyond flyouts — anything needing sibling awareness (roving
focus, radio-group behaviour) resolves the same way.

### The two faces

- `hui.flyout(icon, tooltip=…)` — an icon that opens a flyout.
- `hui.submenu_row(label, icon=…, enabled=True)` — a labelled row that expands
  sideways; `enabled=False` renders the greyed, non-expanding form that
  `draw_disabled()` needs (Stage 3), following `hui.icon_action`'s documented
  rule — `opacity: 0.4; pointer-events: none`, never a grey fill.

**Both are classes, not `@contextmanager` generators.** The two call sites need
different shapes — `with hui.submenu_row(…)` in `draw()`, a bare
`hui.submenu_row(…, enabled=False)` in `draw_disabled()` — and a generator that is
never entered executes nothing, so the disabled call would draw no row at all. A
class that draws its anchor in `__init__` and opens the flyout slot in `__enter__`
serves both, and matches how `ui.menu` already behaves.

```python
class SubmenuRow:
    def __init__(self, label, icon=None, enabled=True):
        self._row = _anchor_row(label, icon, enabled)
        if not enabled:
            self._menu = None
            return
        self._menu = FlyoutMenu()
        self._menu.props(f"{FLYOUT_PROPS} auto-close").style(FLYOUT_Z)
        siblings = _flyout_siblings.get()          # ambient: this level's group
        siblings.append(self._menu)
        open_on_hover(self._row, self._menu, siblings)

    def __enter__(self):
        self._child: FlyoutSiblings = []
        self._token = _flyout_siblings.set(self._child)   # body is a new level
        self._menu.__enter__()
        return self

    def __exit__(self, *exc):
        self._menu.__exit__(*exc)
        _flyout_siblings.reset(self._token)
        self._menu._child_flyouts = self._child
```

`_anchor_row` should be a **styled `ui.row`, not a `ui.menu_item`.**
`flyout_category` uses `ui.menu_item`, which inherits its look from an enclosing
QMenu — `NodeMenuBuilder` opens one
([node_menu_builder.py:69](../../../barn/haybale-graph-editor/haybale_graph_editor/panels/node_menu_builder.py#L69)),
but a panel drawing into a `Popup` content column does not, so the same call would
render an unstyled row there. A row that carries its own look is identical in both
contexts. Settle it here rather than discovering it in Stage 4.

Prove both faces standing alone, inside a `Popup`, and two levels deep **with two
siblings at each level** before anything in Stage 4 depends on them. Two siblings
is the case a per-panel group silently breaks.

Two properties Stage 4 assumes and this stage must confirm:

- **Built eagerly server-side, lazy in the DOM.** The body renders during the
  hosting panel's `draw()`, so panels inside a flyout are polled and drawn then,
  not on hover. NiceGUI 3.x supplies the laziness that matters:
  `Menu._render_markdown()` returns `''` while `value` is `False`, so a closed
  flyout has no client DOM at all (insights §1) — verified, along with the
  children still being on `default_slot.children`, in
  `tests/ui/test_nested_render_mechanics.py`. Do **not** defer `render_surface` to
  a hover callback to "save work" — it would run off the draw stack, outside
  `_render_path` and the error boundary, with the wrong ambient slot, polling
  against state that may have moved since the menu opened.
- **The `ContextVar` render path survives it.** `render_surface` guards re-entry
  with a per-render `ContextVar`; since the body is built inline during `draw()`,
  the path is still on the stack. Proven in
  `tests/ui/test_nested_render_mechanics.py` — including that it unwinds, so one
  render cannot leak into the next.

### Spike the popup lifecycle here too

Stage 0 de-risks the flyout. Three other mechanisms this plan rests on needed the
same treatment, since they were asserted from reading code rather than running it.

**Render-then-discard is now proven** — `tests/ui/test_popup_discard_lifecycle.py`
(3 tests, passing). It establishes the two properties the `on_close` contract
depends on:

- A `Popup` built and never opened is not shown. `popup.vue` gates its card on
  `v-show="visible"`, `visible` starts `false`, and only `startVisible` or
  `open()` flips it; Python passes `start-visible: False` at construction. The
  test also opens one, so the flag is not vacuously false.
- `delete()` reclaims the whole subtree, and a `ui.timer` created inside it is
  cancelled rather than leaked — `Element.delete()` → `remove_elements` →
  `_handle_delete()` per descendant, which `Timer` overrides to cancel itself.
  This is what makes running `draw()` for a menu nobody sees affordable. A timer
  deliberately re-parented to a stable element would still survive; that is a
  panel-authoring problem, not a framework one.

`Popup.delete` had no coverage at all before this, despite the whole
nothing-visible-means-no-popup path now resting on it.

**The nested-render mechanics are proven too** —
`tests/ui/test_nested_render_mechanics.py` (3 tests, passing):

- **ContextVars survive the slot stack.** A counter and a render path set by an
  outer host accumulate correctly through nested `ui.column` / `ui.menu` slots to
  depth 3, and unwind cleanly so one render cannot bleed into the next. Element
  construction inside `with` blocks is synchronous on the calling task; if it were
  not, the leaf counter would read zero for every nested panel and every menu
  would look empty — silently, because empty is a legitimate outcome.
- **A closed `ui.menu` holds its children server-side while rendering nothing.**
  `Menu._render_markdown()` returns `''` unless `value` is truthy, and the
  children are on `default_slot.children` either way; opening reveals the same
  elements rather than rebuilding. This is the "built eagerly, lazy in the DOM"
  property that makes drawing a flyout's panels during the hosting panel's
  `draw()` correct.
- **An element can be restyled after its children exist.** A row takes the
  disabled treatment once its body has rendered, and its children are untouched —
  which is what `SubmenuRow.__exit__` needs to grey an anchor it has already
  opened.

Nothing in Stage 0 is now asserted from reading alone. What remains is building
the two faces on top of these, and the two-siblings-per-level proof below.

Two things worth folding in while the primitive is open:

- **An open delay.** Insights' "known rough edge": no delay means a fast diagonal
  mouse path across a sibling switches flyouts. This architecture invites far more
  submenus than the one add-node tree, so add ~120 ms in `open_on_hover` — one
  place, every caller. Keep closing on `auto-close`; do **not** reintroduce 2.x
  close-timers (insights §1).
- **A row whose body drew nothing greys itself.** `__exit__` reads Stage 3's leaf
  counter — the same one the popup-emptiness rule uses — and applies the disabled
  treatment to the anchor retroactively; NiceGUI elements are mutable after
  creation, and no user can observe the row during body construction.

  "Nothing" means no leaf drew via *either* method. A surface whose panels all
  poll false but implement `draw_disabled()` yields a flyout of greyed rows, which
  is not empty: the parent row stays live and hovering shows them. The empty case
  is narrower — no panel applied and none offered a disabled view — which is
  precisely the resting state of an extension surface nobody has extended. Not an
  edge case once libraries declare `hosts=` targets for third parties.

  This is a deliberate reversal of the earlier "row reflects only its own `poll()`"
  call, which was made before eager building was established. Do not let the
  primitive *hide* the row instead: it cannot distinguish "nothing ever" from
  "nothing right now", and guessing wrong removes a menu entry with no trace.

**The node search/tree split is out of scope for this whole plan.**
`NodeMenuBuilder` couples search and tree through mutable element handles held on
one instance — `_handle_search` toggles `display` on `self._search_results` and
`self._main_menu`. Two panels means two builder instances and no shared handle.
Round one keeps `create_node_menu(show_search=True)` whole on one panel; moving
Add-Nodes into a flyout is a follow-up with its own design.

## Stage 1 — the surface package

New `packages/haywire-core/src/haywire/ui/surface/`:

- `surface.py` — `Surface` ABC: `id`, `order`, `presentation`, `provides`,
  `poll()`. `__init_subclass__` registers into `_SURFACE_BY_ID`, keeping the
  same-module/qualname hot-reload supersede rule from ADR-0009.
- `presentation.py` — `Presentation` dataclass: `label`, `icon`.
- `tree.py` — `surface_by_id()` and `all_surfaces()`.

Two contracts that `Focus` got wrong and must not be inherited:

- **`poll()` is concrete, defaulting to `return True`.** `Focus.available` is an
  `@abstractmethod` with a docstring-only body, so it returns `None`. A surface
  is never instantiated, so ABC does not stop anything — the abstract method just
  gets *called* and its `None` reads as false. Nested surfaces are supposed to
  declare no `poll`; with the inherited shape they would silently never render.
- **`provides` must be `@runtime_checkable` when set.** `__init_subclass__`
  raises at class-definition time otherwise. Host validation is an `isinstance`
  call, and a plain Protocol raises `TypeError` there — at render time, deep in a
  flyout, with no useful frame.

There is no `parent` field and no surface-to-surface tree. Nesting is declared by
panels via `hosts=` (Stage 2) and realised at render by `render_surface` (ADR-0029).

`panel` imports `surface`; never the reverse.

Tests: new `tests/ui/surface/` covering registration, id collision, the `poll`
default, and the `runtime_checkable` rejection. Re-entry and cycle rejection are
covered in Stage 2.

## Stage 2 — panel identity, decorator, registry

- `identity.py` — `PanelIdentity.focus`/`action_protocol` → one `surface` field,
  plus `hosts: tuple[type[Surface], ...] = ()`. **`label` and `icon` stay exactly
  as they are** — component identity for listings, `extract.py`'s panel docs, and
  the properties editor's expansion header. Panels get no `presentation`
  (ADR-0029); that field is a surface's.

  **Delete `scopes` and `editor_keys`.** Both are dead: the decorator sets them to
  `[]` and forbids passing them, and the only reader is `extract.py`, which emits
  them into generated panel docs as permanently-empty lists. No test asserts on
  either. Removal touches `identity.py` (two fields, two docstring lines),
  `decorator.py` (two assignments and the "must not be passed" line), and
  `extract.py` (two dict entries); generated library docs lose two empty keys,
  which Stage 6 regenerates anyway.

  `scopes` has to go regardless — it is the pre-Focus name for Surface, and
  keeping it through a rename whose whole point is vocabulary leaves a third
  synonym on the same dataclass. `editor_keys` goes with it rather than being kept
  speculatively: it would be a second routing axis alongside `surface=`, which is
  exactly what this model collapses. An editor hosts surfaces; that is the routing.
- `decorator.py` — `@panel(surface=…, hosts=…)`; drop `actions=`. Validation:
  `surface=` required and a `Surface` subclass; every `hosts=` entry likewise.
  `label=` stays required.
- `base.py` — `draw()` unchanged; new `draw_disabled(self, ctx, layout)` with a
  no-op default. See below. The nesting call is `render_surface()`, pairing with
  `host_rendering.render_panel()`. **Do not name it `hb_render`** — `hb_*` is the
  documented namespace reserved for *authors*
  ([node-canon.md:108](../../components/nodes/node-canon.md)), so a framework
  method claiming it inverts the convention. For the same reason the injected
  attributes are `_hw_registry` / `_hw_state_bag`, matching the `_haywire_*`
  prefix already used for framework-set markers in `session/handlers.py`.
- `registry.py` — the two query methods collapse into `get_panels(surface)`
  filtering on `surface.id`, sorted by `order`. `get_root_surfaces()` replaces
  `get_display_focuses()`. `get_redraw_signals(surface)` walks the tree.
- `base.py` — `render_surface(surface, ctx, actions=None)`, sketched below.

The `actions:` class-body annotation stays purely for type-checker visibility on
`self.actions`. Note that the framework has **never** read it — `decorator.py`
takes `action_protocol` straight from the `actions=` kwarg, and both
`identity.py`'s docstring ("resolved from the panel's `actions:` annotation") and
`panel-canon.md:365` ("the verb surface is a class-body annotation, not a
decorator argument") describe machinery that does not exist. Delete those two
claims rather than carrying them across the rename.

### Why `hosts=` (reversing the first draft)

The first draft of this plan had no `hosts` field, on the grounds that it would
only serve the `redraw_on` union. It does four things, and three of them are
otherwise unbuildable:

| Job | Without `hosts=` | With |
| --- | --- | --- |
| Redraw union | blind to nested panels; a missing subscription is indistinguishable from a signal that never fired | transitive walk, computed on mount |
| Root vs nested | uncomputable — nesting exists only after rendering, and the strip has to list before it renders | root = named by some panel's `surface=`, absent from every panel's `hosts=` |
| Cycle detection | undetectable until someone renders it | walked at registration and logged; the render guard enforces |
| Authoring errors | `render_surface` of an unrelated surface is legal | rendering outside `hosts=` is an error |

The redraw claim in the first draft was also slightly off: six panels declare
`redraw_on`, not five (`introspect/graph.py`, `introspect/node_ports.py`,
`setting/metadata.py`, `setting/graph.py`, `setting/node.py`, and haystack's
`graph_run_settings_panel.py`). All six sit directly on a properties surface
today — but Stage 4 turns `setting/node.py` into a hosting panel, so the
arrangement the first draft called hypothetical is one stage away.

ADR-0029 rejects a `zone` string and a surface-level `parent`; `hosts=` is
neither. It names a `Surface` class (so the registry can verify it, which is
exactly why `zone` was rejected) and the edge runs panel → surface (so a surface
hosted by two panels is two edges, not a contested parent).

### The three registry queries

```python
def get_panels(self, surface) -> list[type[BasePanel]]:
    """Panels on this surface, by id, sorted by order."""

def get_root_surfaces(self) -> list[type[Surface]]:
    """Surfaces named by some registered panel's surface=, minus every
    surface named in some registered panel's hosts=. Deduped by id."""

def get_redraw_signals(self, surface) -> set[type[Signal]]:
    """Union of redraw_on across surface's panels and, transitively,
    every surface those panels host. Visited-set guarded."""
```

All three compare surfaces **by `id`**, never by class object — `hosts=` holds
classes captured at decoration time, and a panel may host a surface from a
library that reloads on its own schedule (ADR-0009). This is the same rule
`get_panels_for_focus` already follows and the one `get_panels_for_action`
deliberately did not, which was defensible only while a panel and its Protocol
were guaranteed to reload together.

`get_root_surfaces` reads the **panel catalog**, never `_SURFACE_BY_ID`.
`_SURFACE_BY_ID` never evicts, so a surface whose library was uninstalled would
linger there as a ghost tab; deriving from panels is what
`get_display_focuses()` does today and it keeps that behaviour for free.

Root-ness is not the whole answer for the properties strip — `SelectionMenu`,
`AccountMenu` and `SelectionToolbar` are all roots too. The strip lists **root
surfaces that declare `presentation`** (ADR-0029, Presentation). Keep that filter
in `PropertiesEditor`, not in the registry: every other host names its surface
explicitly, so discovery policy belongs to the one host that discovers.

Registration-time validation: cycles in the `hosts=` graph are **logged, not
rejected** — a warning naming both edges, and the panel registers anyway. The
graph closes only through surface → panels, so a cycle first appears when the
*second* panel registers; refusing that one drops a panel from the catalog based
on library load order, and two libraries each sound alone would fail differently
depending on install order. Enforcement is the render-time re-entry guard below,
which has to exist regardless — so this costs no code and keeps the author's two
signals (an early log, and an inline error at the point of nesting). Protocol
satisfaction cannot be — the host is a runtime object — so that check stays in
`render_surface`.

### `render_surface` — what it lifts

Everything it needs exists in `host_rendering.py`; this is composition, not new
machinery. Its jobs: check the declaration, guard re-entry, gate the surface,
validate the host, then reuse the shared poll-filter and renderer.

```python
def render_surface(self, surface, ctx, actions=None) -> None:
    """Render surface's panels here, inside the caller's layout context."""

    # 1. Declared? hosts= is what the registry walks for the redraw union
    #    and the root split; rendering outside it makes that tree a lie.
    #    Compared by id, not class object — a panel may host a surface from
    #    another library that reloads on its own schedule (ADR-0009).
    if surface.id not in {s.id for s in self.class_identity.hosts}:
        hui.error_label(f"{type(self).__name__} does not declare hosts={surface.__name__}")
        return

    # 2. Re-entry guard — this IS the cycle enforcement, not a backstop:
    #    registration only logs (see above). The path is per-render, not
    #    global: the same surface may legitimately appear twice side by side.
    path = _render_path.get()
    if surface.id in path:
        hui.error_label(f"Surface {surface.id!r} is already being rendered")
        return

    # 3. Surface gate, under the error boundary like every other poll.
    #    Ahead of host validation: a surface that does not apply right now
    #    has no business complaining about hosts.
    if not _poll_surface(surface, ctx):
        return

    # 4. Host. Piped by default, never inferred (ADR-0029). isinstance is
    #    a check on the chosen object, not a way of choosing it.
    host = actions if actions is not None else self.actions
    want = getattr(surface, "provides", None)
    if want is not None and not isinstance(host, want):
        hui.error_label(f"Host {type(host).__name__} does not satisfy {want.__name__}")
        return

    # 5. Shared filter + renderer, unchanged from the outer hosts.
    panels = visible_panels(self._hw_registry.get_panels(surface), ctx)
    layout = PanelLayout(ui.element("div"), state_bag=self._hw_state_bag)
    with _render_path.extend(surface.id):
        for cls in panels:
            render_panel(cls, ctx, layout, actions_host=host, registry=self._hw_registry)
```

Four things this needs that do not exist yet:

- **`_render_path`** — a `ContextVar` holding the surface ids on the current
  render path. Per-render rather than per-session; note the DI trap in
  `.insights/project_di_context.md` applies to the *injector*, not to ordinary
  request-scoped state like this.
- **`_poll_surface(surface, ctx)`** — the surface-level twin of `_poll_panel`,
  same error boundary, same false-on-raise rule. It lives beside `_poll_panel`
  but is **not** folded into `visible_panels()`: that function is shared by three
  hosts, takes no surface, and folding the gate in would both change its
  signature and poll the surface a second time on every nested render.
- **`self._hw_registry`** — `render_panel` gains a `registry=` keyword and sets it
  on the instance next to `actions`. All three outer hosts already hold a
  `PanelRegistry`, so this is passing along what they have rather than reaching
  for an ambient injector.
- **`self._hw_state_bag`** — `render_panel` sets it from `layout.state_bag`, so no
  new parameter. Nested panels share the host's bag; the namespaced-key rule
  already documented on `PanelLayout.state_bag` is what keeps them from
  colliding, exactly as it does between siblings today. Transient hosts pass
  `None` and nested panels inherit `None`, which is correct — an ephemeral menu
  has no state to persist.

A hosting panel therefore writes `render_surface(S, ctx)` for the common case and the
host it received travels one hop further. Only a panel that means to *be* the
host says so:

| Case | What the panel is | Call | Host passed |
| --- | --- | --- | --- |
| Pipe (common) | Arranges layout only | `render_surface(S, ctx)` | `self.actions` |
| Own | Implements the surface's Protocol | `render_surface(S, ctx, actions=self)` | `self` |
| Delegate | Neither implements nor received it | `render_surface(S, ctx, actions=obj)` | `obj` |

The first draft had this the other way round — `self` preferred, structurally
detected. That silently breaks on any Protocol a panel happens to match, and
`NodeContextActions` is an *empty* marker Protocol today, which every object
satisfies. Retire that Protocol too: it existed only to route custom-scope menus
through the action fork, and surfaces now route by id alone.

The display/action fork disappears: which panels a surface yields no longer
depends on whether a protocol is set, only on the surface id.

## Stage 3 — hosts

- `host_rendering.py` — `visible_panels()` keeps its signature and its job. Each
  host gates its own surface once, before calling it (see Stage 2). `render_panel`
  gains `registry=` and sets `_hw_registry` / `_hw_state_bag` on the instance
  alongside `actions`.
- `context_menu_base.py` — `_open_menu(surface, pos, on_close=…)`; the protocol
  comes from `surface.provides`. The host renders only the root surface's panels;
  anything nested is a panel's own `render_surface` call. The
  nothing-visible-means-no-popup path **keeps its contract and changes its
  mechanism** (see below). It also pushes the root flyout-sibling group around the
  popup content (Stage 0) — the popup is a menu level, and nothing below it knows
  that. `SelectionToolbarProvider._render_into_popup` does the same for its row.

- `redraw_coordinator.py` — `focus_provider` → `surface_provider`; subscribes to
  the union `get_redraw_signals` returns, which now spans each surface's whole
  `hosts=` tree. Rewrite the docstring's "owns BOTH surfaces of that machine"
  (collides with the canonical term). It stays the `PropertiesEditor`'s alone —
  the toolbar is event-driven and deliberately subscribes to nothing (ADR-0029,
  Redraw), guarded by a Stage 5 test rather than by a comment.
- `properties_editor.py` — `_active_surface_id`; the strip lists root surfaces
  **that declare `presentation`**, sorted by `order`. A false `poll()` greys the
  tab and drops the content.
- `selection_toolbar.py` — delete `open_overflow_menu()`, `ToolbarActions`, and
  the synthetic `ContextMenuSelectedEvent`; the ⋯ becomes a panel that hosts a
  surface. `_collect_toolbar_panels()` collapses to one `get_panels()` call — the
  two-protocol loop and its dedup exist only because `SelectionContextActions`
  and `ToolbarActions` both routed against `ToolbarFocus`.
  **Also delete `_rendered_panels` and the `visible != self._rendered_panels`
  guard; render unconditionally.** See below. And the provider gains the five
  `SelectionActions` verbs it lacks — see "The ⋯ hosts the selection menu".
- `elements.py` — `scope_button` → `surface_button`. Visual rules unchanged
  (36×36, `opacity: 0.3; pointer-events: none` when gated off).

### The disabled render path

ADR-0029 lets a panel render its own inapplicable state, which is what makes
platform-standard menu greying possible without any host learning to draw a
panel. Three touch points, all small:

- `base.py` — `draw_disabled(self, ctx, layout)`, default `pass`. Not abstract:
  the no-op default is what makes this a zero-migration change for every existing
  panel (67 registered, ~126 `BasePanel` subclasses counting test doubles).
- `host_rendering.py` — `visible_panels()` stops being the only gate.
  Hosts need the split, so add `partition_panels(classes, ctx)` returning
  `(applies, disabled)`: `access=` denied is dropped from **both** (a greyed entry
  advertises what the principal may not have), and the rest split on `poll()`.
  `render_panel` gains `disabled: bool = False` and calls the matching method
  under the same error boundary.
- Every host renders both lists in `order`, interleaved — not applies-then-
  disabled, or a menu reshuffles as the selection changes.

`visible_panels()` keeps its name and signature for the hosts that only want the
applicable set; `partition_panels` is the superset it delegates to.

Authoring shape, for the docs in Stage 6:

```python
class ExportSubmenuPanel(BasePanel):
    LABEL = "Export"

    @classmethod
    def poll(cls, ctx) -> bool:
        return bool(ctx.data[EditState].selected_nodes)

    def draw(self, ctx, layout):
        with layout:
            with hui.submenu_row(self.LABEL, icon=hui.icon.download):
                self.render_surface(ExportMenu, ctx)

    def draw_disabled(self, ctx, layout):
        with layout:
            hui.submenu_row(self.LABEL, icon=hui.icon.download, enabled=False)
```

The label appears twice because the panel owns both renderings; a class constant
is the whole answer. Note what `poll()` false buys here: the flyout body is never
built, so nothing below it is queried or polled — a disabled branch costs one row.

`hui.submenu_row` therefore needs an `enabled` parameter (Stage 0), matching
`hui.icon_action`'s documented disabled rule — `opacity: 0.4; pointer-events:
none`, never a grey fill — and `hui.scope_button`'s existing `available=False`
treatment.

### Emptiness after nesting

`_open_menu` poll-filters before building anything and, when nothing is visible,
runs `on_close` and returns without a popup. That early return is load-bearing:
the canvas provider resets `active_port` / `active_edge` and resumes a paused
edge-drag in it, the file browser resets `right_clicked_file`, and
`AccountMenuProvider` documents it as the reason a principal with no entries
needs no special case.

Nesting breaks the *test*, not the contract. `GraphContextPanel` polls true
unconditionally — it is a layout panel — so the root surface always yields one
visible panel and the popup always opens, sometimes around nothing.

Per ADR-0029, emptiness becomes a property of the tree, decided by rendering it:

1. Gate the surface. A surface that does not apply costs nothing and takes the
   old early return — this is what keeps the common paths cheap, since
   `GraphContext.poll` already gates on `active_graph`.
2. Build the popup. `Popup` is constructed with `start-visible: False` and only
   becomes visible on `open()`, so a built-but-unopened popup is invisible.
3. Render the whole tree into it.
4. Open it if a **leaf panel** drew; otherwise `popup.delete()` and run the close
   cleanup.

"Leaf" is `class_identity.hosts == ()`, so `render_panel` can count it with no
author involvement. Accumulate in the same per-render `ContextVar` that carries
`_render_path`.

Steps 2 and 4 are proven — `tests/ui/test_popup_discard_lifecycle.py` covers the
unopened popup staying hidden, `delete()` reclaiming the whole subtree, and a
`ui.timer` created during a discarded `draw()` being cancelled with it.

The same test applies to `SelectionToolbarProvider.show_at`, whose
`if not visible: self.hide()` has the identical blind spot.

### The ⋯ hosts the selection menu

Today the ⋯ emits a synthetic `ContextMenuSelectedEvent` that round-trips through
the canvas into `on_selection_context`, opening the full `SelectionMenu`. The
glossary states the intent: *the overflow re-opens the selection right-click menu
so the batch ops live in one place.* Keep that — the ⋯ becomes a hosting panel:

```python
@panel(surface=SelectionToolbar, order=999, hosts=(SelectionMenu,))
class SelectionOverflowPanel(BasePanel):
    actions: SelectionActions

    def draw(self, ctx, layout):
        with layout:
            with hui.flyout(hui.icon.more_horiz, tooltip="More actions"):
                self.render_surface(SelectionMenu, ctx)
```

It pipes — the default. No separate overflow surface, so no panel is duplicated
and nothing moves off the right-click menu.

**This is blocked by a latent bug, which is why it is called out here.**
`SelectionToolbarProvider`'s docstring claims it "implements the ToolbarActions
and SelectionContextActions Protocols structurally". It does not: it has
`copy_selection`, `delete_selection` and `open_overflow_menu` against
`SelectionContextActions`' seven verbs. Nothing catches it today because
`get_panels_for_action` matches by Protocol *class identity* and `render_panel`
merely assigns `instance.actions = host` — **there is no structural check anywhere
in the current system.** `render_surface`'s `isinstance` is new enforcement, and the
toolbar is the first thing it catches.

Fix by delegation, not by duplication. `SessionContextMenuProvider` already
implements all seven and is constructed a few lines earlier in
`graph_canvas_manager` ([graph_canvas_manager.py:78-97](../../../barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/graph_canvas_manager.py#L78-L97)),
so pass it in and forward the five missing verbs. Then
`SelectionToolbar.provides = SelectionActions` is honest, the ⋯ panel pipes, and
no panel learns anything. Fix the docstring while there.

### The toolbar's re-render guard goes away

`show_at` skips the DOM rebuild when `visible == self._rendered_panels`. That list
holds only the *root* surface's panels, so once ⋯ hosts a surface the guard cannot
see anything nested: a poll flip inside the flyout with an unchanged root set
renders stale and never corrects.

Delete the guard rather than teach it about nesting. The reason it existed no
longer holds:

> **The docstrings are stale.** `show_at`'s comment says "clearing and
> re-rendering every frame is what made panning jerky", and `hide()`'s says "the
> gesture path calls hide()/show_at() on every pan frame". Neither is true any
> more. Every `selectionBounds` emission in `canvas.vue` is edge-triggered — hide
> on drag/pan **start**, show on drag **end**
> ([1520](../../../packages/haywire-core/src/haywire/ui/components/graph/canvas.vue#L1520),
> [1702](../../../packages/haywire-core/src/haywire/ui/components/graph/canvas.vue#L1702)),
> and a 120 ms trailing debounce for wheel-zoom/trackpad bursts
> ([756-781](../../../packages/haywire-core/src/haywire/ui/components/graph/canvas.vue#L756-L781)).
> The glossary already describes it correctly as low-frequency; the Python
> comments describe the world before the Vue-side gating landed.

So a rebuild costs one three-button row per gesture end — what a selection change
already pays today. Dropping `_rendered_panels` removes a state field, a stale-
content bug class, and one more thing Stage 3 would have to teach about nesting.

**Verify before deleting, not after:** pan with a multi-node selection and confirm
the toolbar does not stutter on gesture end. The reasoning above is inferred from
the emission sites, not measured. If it does stutter, keep a guard but diff
against the panel set the render actually produced, not the root list.

Fix both stale docstrings while there. `hide()`'s `v-show` DOM preservation is
still worth keeping — but for avoiding a rebuild across one gesture's hide/show
round trip, not for a per-frame path that no longer exists.

### What greys and what vanishes

ADR-0029's rule is *whoever draws a thing is who greys it*. A surface never
draws, so its host greys it; a panel always draws, so it greys itself:

| Thing | Gated off → |
| --- | --- |
| Properties tab (surface with `presentation`) | greyed in place by the editor, content dropped — already what `hui.scope_button(available=False)` does |
| Menu surface / menu region / toolbar surface (no `presentation`) | contributes nothing |
| Panel implementing `draw_disabled()` | renders its own disabled row — a greyed menu row, a greyed submenu row |
| Panel not implementing it (the default, every panel today) | vanishes — unchanged |
| Panel denied by `access=` | vanishes, whatever it implements — never greyed |
| Root context menu whose tree drew nothing | no popup opens; `on_close` runs |

Nothing in core decides between the last four; `partition_panels` hands the host
two lists and `render_panel` calls the matching method. The only new visual rule
is `hui.submenu_row(enabled=False)`.

## Stage 3b — canvas menu dispatch

`handleContextMenu` ([canvas.vue](../../../packages/haywire-core/src/haywire/ui/components/graph/canvas.vue))
is one priority chain over two unrelated mechanisms:

| # | Path | Detected by | Surface chosen by |
| --- | --- | --- | --- |
| 1 | port | `closest('[data-hw-port-menu-focus-id]')` | the skin |
| 2 | custom | `closest('[data-hw-custom-menu-focus-id]')` | the skin |
| 3 | node | `closest('[data-node-id]')` | Vue (opens the *selection* menu) |
| 4 | edge | `path[data-edge-id]`, else `_isPointNearStroke` proximity | Vue |
| 5 | canvas | nothing matched | Vue |

3–5 are **structural**: found from attributes that exist for dragging, selection
and routing, with the surface hard-coded. They cannot become declarative — edge
detection is a geometric hit-test, node and canvas both mutate state before
emitting (replace-then-act selection; snapshot pending connection and
`_enterPausedEdge`), and each carries a different payload.

1–2 are **declarative** and are the same mechanism twice. Collapse them.

### Pin becomes structural

`render_pin` already emits `data-node-id`, `data-pin-id`, `data-pin-dir`,
`data-pin-dir-x/y`, `data-pin-data-type` and `data-pin-color` on every pin from
every skin, so `closest('[data-pin-id]')` — checked **before** the node branch,
since a pin sits inside a node — is a structural detector exactly parallel to
node and edge. Accept `data-port-id` as an alias; nothing in the tree emits it.

The pin menu therefore stops being opt-in. `node_skin.py:307` goes away, and with
it `port.info` — an unregistered id whose behaviour depended on a registry miss.
Two consequences to verify rather than assume:

- Every skin gains a pin menu, including `error_skin` and `example_skin`, with no
  way to suppress it. `PinMenu`'s panels are display-only plus a demote verb that
  polls true only on a promoted inlet, so this should be right — confirm it.
- Ghost pins go through `render_pin` too. Check they do not pick up a menu.

### One declarative attribute

`data-hw-menu-surface-id="<id>"`, replacing both. `closest()` on a single
attribute makes the **innermost annotation win**, which the priority-ordered pair
did not: today a pin inside a custom-marked container takes the port branch even
when the custom marker is nearer.

`ContextMenuCustomEvent` and `ContextMenuPortEvent` collapse into one:

```python
@graph_event(
    "contextMenuSurface",
    category="user",
    description="Context menu on an element carrying data-hw-menu-surface-id",
)
@dataclass
class ContextMenuSurfaceEvent(BaseGraphEvent):
    screenX: float
    screenY: float
    canvasX: float
    canvasY: float
    nodeId: str
    surfaceId: str
```

Regenerate with `uv run python scripts/generate_vue_events.py` — never hand-edit
`generated/graph_events.js`.

Python collapses to one handler. It seeds `active_node`, resolves the id, and
opens it:

```python
def on_surface_context(self, pos, canvas_pos, node_id, surface_id):
    surface = surface_by_id(surface_id)
    if surface is None:
        logger.warning("No surface registered for id %r", surface_id)
        return
    ...
    self._open_menu(surface, pos)
```

**No fallback.** `on_custom_context`'s `or NodeFocus` is what made `NodeFocus` a
third double-duty focus — an inspector reachable by default. Deleting the branch
deletes the problem, so `NodeInspector` stays a pure inspector and needs no split
(unlike Edge). An unresolved id logs and opens nothing.

**No addressability check** (ADR-0029, Routing). Every id in that attribute was
typed by someone; there is no default left to misfire. An id naming an inspector
renders inspector panels with `actions=None` — inert, since inspector panels
never call `self.actions` — and the author sees it on the first right-click.

Note what a third-party surface may demand: `provides` is checked against
`SessionContextMenuProvider`, which a third-party library cannot extend. So such
a surface either reuses a Protocol that provider already satisfies, or declares
no `provides` and acts through `ctx`. The verb-less case is the common one, which
is why addressability is not derived from `provides`.

`NodeContextActions` dies here rather than in Stage 4 — the empty marker Protocol
existed only to route the custom attribute through the action fork, and that
branch is gone. `PortContextActions` survives as `PortActions`: it carries a real
verb (`demote_setting`) that `PinMenu`'s panels still call, and the pin path is
now structural rather than attribute-driven.

## Stage 4 — libraries

Per library, one file per surface under `surfaces/`, holding the surface and the
Protocol it names (convention, not machinery):

```text
haybale_graph_editor/surfaces/
    graph_context.py  # GraphContext + GraphToolBar + GraphContextBody
                      #   + GraphMoreActions + GraphActions
    selection.py      # SelectionMenu + SelectionActions
    edge.py           # EdgeInspector + EdgeMenu + EdgeActions
    pin.py            # PinMenu + PortActions
    node.py           # NodeInspector
    ports.py          # PortInspector
    graph.py          # GraphInspector
    toolbar.py        # SelectionToolbar (provides = SelectionActions)
                      #   — no overflow surface: the ⋯ hosts SelectionMenu
```

`haywire/barn/builtin/focuses.py` becomes `builtin/surfaces.py` holding
`CanvasSettings`, `AppSettings`, `ExecutionInspector` and `AccountMenu` — note
`CanvasSettings` is the inspector half of the old `CanvasFocus`; its menu half
moves into `GraphContext` in the graph editor.

Delete `focuses.py` and `handlers/context_menu_actions.py` in the graph editor;
likewise `focuses.py` + `editors/file_browser_menu/actions.py` in
`haybale-studio`, and `test_focuses.py` + `test_actions.py` in `haybale-testing`.
`NodeContextActions` goes with them rather than being renamed — an empty marker
Protocol had a job only while the action fork did the routing.

Every `@panel` in the four libraries moves to `surface=`. Toolbar and edge panels
whose `poll()` restates their surface's predicate drop the method.

**Menu greying is opt-in and lands here.** Nothing forces it: the default
`draw_disabled()` is a no-op, so a library that changes nothing keeps today's
vanish behaviour exactly. The ~20 menu panels that should follow the platform
convention — an inapplicable command greys rather than disappearing — implement
it. Take the selection menu first (`Copy` / `Delete` / the batch node ops), since
those are the ones a user right-clicks into with an empty selection.

Note what those panels already look like: `CopySelectionMenuPanel` computes
`_selection_counts(ctx)` in `draw()` for a dynamic `"Copy 3 nodes"` label, and
`poll()` reads the same state. `draw_disabled()` renders the static form —
`"Copy"`, greyed — which is what it should say when there is nothing to copy.
That is the case that made host-drawn rows unworkable and is free here.

### Target shape — the graph context menu

The canvas menu is also being redesigned into three parts: a row of icon
shortcuts ending in a "…" flyout, and a prime area below. Paste becomes an icon.

**Round one keeps `NodeMenuBuilder.create_node_menu(show_search=True)` whole in
the prime area** — search and its tree stay in one panel. Moving Add-Nodes into
the flyout means splitting them, and they are coupled through mutable element
handles on one builder instance (Stage 0). The `GraphMoreActions` surface still
gets built here, with the panels that genuinely belong behind a "…"; the node
tree joins it in a follow-up.

Sketches below are the intended end state, not working code.

```python
# surfaces/graph_context.py

@runtime_checkable
class GraphActions(Protocol):
    def paste_at_click(self) -> None: ...
    def create_node_at_click(self, registry_key: str) -> None: ...


class GraphContext(Surface):
    """Root of the canvas right-click menu."""
    id = "graph-context"
    provides = GraphActions

    @classmethod
    def poll(cls, ctx) -> bool:
        return ctx.data[EditState].active_graph is not None


class GraphToolBar(Surface):
    """Icon shortcut row along the menu's top edge."""
    id = "graph-toolbar"
    provides = GraphActions


class GraphContextBody(Surface):
    """Prime area below the shortcut row."""
    id = "graph-body"
    provides = GraphActions


class GraphMoreActions(Surface):
    """Secondary commands behind the "…" flyout."""
    id = "graph-more"
    provides = GraphActions
```

Every surface states its own `provides`, including nested ones: it is the
surface's contract with whatever hosts it, and nothing inherits it. `render_surface`
checks the object it is handed against the target surface's `provides` before
injecting, so a panel that pipes a host missing those verbs fails at that call
rather than handing its panels a broken `self.actions`.

The nested surfaces declare no `poll` — they are reached only by being rendered,
and the panel rendering them has already passed its own gate. This works only
because `Surface.poll` defaults to a concrete `return True` (Stage 1); the
inherited-abstract shape `Focus.available` has would return `None` and gate every
one of them off.

The panel that owns the two regions. It implements none of `GraphActions` itself
— `SessionContextMenuProvider` does — so it pipes, which is the default:

```python
# panels/graph/context.py

@panel(surface=GraphContext, order=0, hosts=(GraphToolBar, GraphContextBody))
class GraphContextPanel(BasePanel):
    actions: GraphActions

    def draw(self, ctx, layout):
        with layout:
            with ui.row().classes("items-center gap-1"):
                self.render_surface(GraphToolBar, ctx)
            with ui.column().classes("w-full"):
                self.render_surface(GraphContextBody, ctx)
```

This is the common case for a layout-only panel: it owns the arrangement, not the
verbs. `render_surface` passes `self.actions` — the provider — down without being
told. `PastePanel` below reaches that provider two levels up without either panel
naming it.

An icon shortcut. No `presentation` — `draw` renders the icon itself:

```python
@panel(surface=GraphToolBar, order=10)
class PastePanel(BasePanel):
    actions: GraphActions

    def draw(self, ctx, layout):
        with layout:
            hui.icon_action(hui.icon.paste, tooltip="Paste",
                            on_click=self.actions.paste_at_click)
```

Paste declares no `poll`, matching today's `PasteMenuPanel`: the OS clipboard is
not readable synchronously at poll time, so the panel is always shown and the
handler reports "Nothing to paste". Do not give it a `ctx.app.clipboard`
predicate — there is no such thing, and there is a documented reason there isn't.
A panel has no disabled state either; panels vanish, only surfaces grey.

The "…" — a panel that is itself a host. The provider travels one hop further,
again by the pipe default:

```python
@panel(surface=GraphToolBar, order=999, hosts=(GraphMoreActions,))
class GraphMorePanel(BasePanel):
    actions: GraphActions

    def draw(self, ctx, layout):
        with layout:
            with hui.flyout("more_horiz", tooltip="More actions"):
                self.render_surface(GraphMoreActions, ctx)
```

`GraphActions` therefore reaches `AddNodesPanel` through three hops — provider →
`GraphContextPanel` → `GraphMorePanel` → `AddNodesPanel` — with each hop an
explicit argument rather than an inherited tree edge.

A panel lands in the flyout by naming its surface, and never learns it is inside
one:

```python
@panel(surface=GraphMoreActions, order=0)
class SomeSecondaryPanel(BasePanel):
    actions: GraphActions

    def draw(self, ctx, layout):
        with layout:
            hui.menu_row("…", on_click=self.actions.something)
```

The prime area carries the node menu, search and tree together, unchanged from
today:

```python
@panel(surface=GraphContextBody, order=0)
class CreateNodeMenuPanel(BasePanel):
    actions: GraphActions

    def draw(self, ctx, layout):
        with layout:
            NodeMenuBuilder(ctx.app.node_factory, ...).create_node_menu(show_search=True)
```

`hui.flyout` and `hui.menu_row` come from Stage 0, which is why Stage 0 is
Stage 0. Splitting search from tree is explicitly deferred there.

### Target shape — a nested submenu

The flyout above is one panel opening one surface. A hierarchical submenu is the
same mechanism repeated: a row that expands sideways, whose contents are a
surface, and whose own rows may expand again.

A library adding "Export ▸" to the selection menu, with a further "Image ▸"
level under it:

```python
# surfaces/export.py

@runtime_checkable
class ExportActions(Protocol):
    def export_selection(self, fmt: str) -> None: ...


class ExportMenu(Surface):
    """Contents of the "Export ▸" submenu."""
    id = "export-menu"
    provides = ExportActions


class ExportImageMenu(Surface):
    """Contents of the "Image ▸" submenu nested under Export."""
    id = "export-image-menu"
    provides = ExportActions
```

The row that opens the first level. It sits on `SelectionMenu` — a surface owned
by another library — and needs no change there:

```python
# panels/graph/menu/selection/export.py

@panel(surface=SelectionMenu, order=500, hosts=(ExportMenu,), label="Export")
class ExportSubmenuPanel(BasePanel):
    actions: ExportActions
    LABEL = "Export"

    @classmethod
    def poll(cls, ctx) -> bool:
        return bool(ctx.data[EditState].selected_nodes)

    def draw(self, ctx, layout):
        with layout:
            with hui.submenu_row(self.LABEL, icon=hui.icon.download):
                self.render_surface(ExportMenu, ctx)

    def draw_disabled(self, ctx, layout):
        with layout:
            hui.submenu_row(self.LABEL, icon=hui.icon.download, enabled=False)
```

`draw_disabled` is optional — omit it and the row vanishes instead, which is what
every panel does today. `label=` on the decorator is component identity (listings,
generated docs); the row's text comes from the panel's own render, which is why
the constant exists.

A leaf inside it, and a row that opens a further level — identical shapes, one
level apart:

```python
@panel(surface=ExportMenu, order=10)
class ExportJsonPanel(BasePanel):
    actions: ExportActions

    def draw(self, ctx, layout):
        with layout:
            hui.menu_row("JSON", on_click=lambda: self.actions.export_selection("json"))


@panel(surface=ExportMenu, order=20, hosts=(ExportImageMenu,))
class ExportImageSubmenuPanel(BasePanel):
    actions: ExportActions

    def draw(self, ctx, layout):
        with layout:
            with hui.submenu_row("Image", icon=hui.icon.image):
                self.render_surface(ExportImageMenu, ctx)


@panel(surface=ExportImageMenu, order=10)
class ExportPngPanel(BasePanel):
    actions: ExportActions

    def draw(self, ctx, layout):
        with layout:
            hui.menu_row("PNG", on_click=lambda: self.actions.export_selection("png"))
```

Three things this shows that the flyout example does not:

- **Depth is not a special case.** `ExportSubmenuPanel` and
  `ExportImageSubmenuPanel` are the same shape at different depths. Nothing in
  either names its own level.
- **A submenu is extensible by a third library.** Another haybale can add a panel
  on `ExportImageMenu` and appear inside a submenu whose owner never anticipated
  it — the same openness a top-level surface has.
- **`poll` gates a whole branch cheaply.** `ExportSubmenuPanel.poll` returning
  false greys the row — or removes it, if the panel implements no
  `draw_disabled()` — and either way nothing below it is queried or polled: a
  disabled branch costs exactly one row. The redraw
  union is unaffected: it is derived from the `hosts=` catalog, not from what
  polled true, so a long-lived host stays subscribed to a branch that is
  currently gated off. That is correct — the signal that makes it apply again has
  to be able to trigger the redraw that reveals it.

`hui.submenu_row` and `hui.menu_row` come from Stage 0 — one primitive with two
faces, not two implementations of the same nested-popup problem.

### Target shape — the properties editor

The same machinery with no nesting and with chrome. The editor is the host; each
tab is a surface; each section is a panel. `presentation` appears here because
the editor draws a tab strip and an expansion header.

```python
# surfaces/node.py

class NodeInspector(Surface):
    id = "node"
    order = 60
    presentation = Presentation(label="Node", icon="account_tree")

    @classmethod
    def poll(cls, ctx) -> bool:
        return ctx.data[EditState].active_node is not None
```

No `provides` — inspector panels read state and need no host verbs.

```python
# panels/properties/introspect/node.py

@panel(surface=NodeInspector, order=10,
       label="Identity")
class NodeIdentityPanel(BasePanel):
    def draw(self, ctx, layout):
        node = ctx.data[EditState].active_node
        with layout:
            hui.info_row("Name", node.name)
            hui.info_row("Type", node.registry_key)
```

The editor polls the surface, then polls and draws each panel inside an expansion
section titled from the panel's `label` and `icon` — the identity fields it
already uses today, not a `presentation` (which is a surface's alone). A surface
whose `poll()` is false keeps its tab in place, greyed; a panel whose `poll()` is
false is omitted, because inspector panels implement no `draw_disabled()` and a
greyed accordion is noise where a greyed tab is a navigation target.

A panel here may host a surface exactly as a menu panel does. This one is the
`Own` case from the Stage 2 table: it implements the nested surface's Protocol
itself, and says so with `actions=self` rather than leaving it to be guessed:

```python
# panels/properties/setting/node.py

@runtime_checkable
class FieldGroupActions(Protocol):
    def reset_field(self, key: str) -> None: ...


class NodeFieldGroups(Surface):
    id = "node-field-groups"
    provides = FieldGroupActions


@panel(surface=NodeInspector, order=20,
       label="Settings",
       hosts=(NodeFieldGroups,),
       redraw_on=(SelectionMoved, GraphDataMutated, ActiveGraphMoved))
class NodeSettingsPanel(BasePanel):
    def draw(self, ctx, layout):
        self._ctx = ctx
        with layout:
            self.render_surface(NodeFieldGroups, ctx, actions=self)

    # satisfies FieldGroupActions for every panel it renders
    def reset_field(self, key: str) -> None:
        self._ctx.data[EditState].active_node.settings.reset(key)
```

This panel is also the reason `hosts=` had to come back. It already declares
`redraw_on`, and the moment any panel on `NodeFieldGroups` declares one too, the
properties editor has to be subscribed to it *before* the first render.
`get_redraw_signals(NodeInspector)` finds it by walking `hosts=`; nothing else
could.

Nothing about the properties editor is a special case.

## Stage 5 — tests

29 files. Most are vocabulary-only. Three need real changes:

- `tests/ui/panel/test_focus.py` → `tests/ui/surface/test_surface.py`; the
  assertions on `label`/`icon`/`order` move to `presentation`.
- `tests/ui/panel/test_panel_registry_class_keyed.py` — the protocol-identity
  matching it asserts no longer exists; rewrite against `get_panels`.
- `tests/graph_editor/test_toolbar_focus.py` and `test_toolbar_wiring.py` — the
  overflow round-trip they assert is gone; rewrite against the ⋯ hosting
  `SelectionMenu` directly.

`tests/libraries/test_focuses_have_ids.py` becomes `test_surfaces_have_ids.py`.

New coverage the reworked stages need — each of these is a decision that fails
silently if it regresses:

- `Surface.poll` defaults to `True`, and a surface declaring no `poll` renders.
- `provides` that is not `@runtime_checkable` is rejected at class-definition
  time, not at render.
- `render_surface` of a surface not in `hosts=` renders an error and draws nothing.
- A cycle in the `hosts=` graph logs a warning naming both edges at registration
  and **both panels still register**; rendering it produces one inline error and
  terminates rather than recursing. Assert both halves — the log is the early
  signal, the guard is the enforcement.
- `get_root_surfaces()` excludes hosted surfaces, and drops a surface when the
  library declaring its panels is removed — the ghost-tab case.
- `get_redraw_signals()` picks up a `redraw_on` on a panel two levels down.
- The strip lists root surfaces with `presentation` and no others — assert no
  menu surface declares one.
- Host is piped, never inferred: a panel that structurally satisfies the target
  Protocol still passes `self.actions` unless it says `actions=self`. Use a
  member-less Protocol for this one; that is the case the first draft broke on.
- The Edge split: `get_panels(EdgeInspector)` and `get_panels(EdgeMenu)` are
  disjoint, and neither is empty.
- Emptiness after nesting: a menu whose root holds only a hosting panel, with
  every leaf below it polling false, opens **no** popup and runs `on_close`. This
  is the regression that shows up as a stuck edge-drag, so assert the cleanup ran,
  not just that no popup exists.
- The inverse: one leaf two levels down polling true is enough to open the menu.
- A discarded popup is deleted, not merely left unopened.
- `on_surface_context` with an unregistered id opens nothing and logs — no
  fallback to any surface.
- Pin detection is structural: a right-click on an element carrying
  `data-pin-id` and no menu attribute opens `PinMenu`, and one on a node body
  still opens the selection menu (the pin branch must not swallow the node case).
- The innermost `data-hw-menu-surface-id` wins over an outer one.
- `draw_disabled()` defaults to a no-op, so a panel that implements only `draw()`
  still vanishes when `poll()` is false — the zero-migration guarantee.
- A panel implementing `draw_disabled()` renders it when `poll()` is false, and
  `draw()` is **not** called. Assert the latter: the whole point is that the
  inapplicable path never touches absent state.
- A panel denied by `access=` renders neither method. Use a panel that implements
  both — this is the asymmetry an author will get wrong.
- `partition_panels` interleaves applicable and disabled panels in `order`, not
  applicable-then-disabled.
- Two sibling submenu rows on one surface share a sibling group: opening the
  second closes the first. This is the case a per-panel group silently breaks, and
  it needs two panels that have never heard of each other.
- Two submenu rows on **different surfaces rendered into the same popup** — one on
  `GraphToolBar`, one on `GraphContextBody` — are also siblings. This is the case a
  per-*surface* group breaks, and it is why the group belongs to the container.
- Closing cascades: opening a row two levels down, then jumping to its uncle,
  leaves nothing open below the uncle.
- `get_redraw_signals(SelectionToolbar)` is empty — and it now walks into
  `SelectionMenu` via the ⋯'s `hosts=`, so this asserts across both. The toolbar
  is event-driven and subscribes to nothing (ADR-0029, Redraw), so a `redraw_on`
  anywhere in that tree would be inert; this is the tripwire that makes it loud.
- **Every host satisfies the `provides` of every surface it opens.** Parametrise
  over the root menu surfaces and their providers. This is the check whose absence
  let `SelectionToolbarProvider` claim a Protocol it satisfied 3/7 of, undetected
  for as long as the action fork hid it. There may be another.
- The ⋯ renders `SelectionMenu`'s panels inside the toolbar flyout — same panel
  classes the right-click menu yields, not a duplicated set.
- A submenu row whose surface has no panels at all renders greyed, not live —
  the unextended-extension-point case.
- A submenu row whose panels all poll false but implement `draw_disabled()` stays
  **live**, and opening it shows the greyed rows. This is the pair that catches a
  leaf counter wired to `poll()` instead of to what actually drew.

## Stage 6 — docs and bake

- `docs/components/panels/panel-canon.md` — the three-orthogonal-facets section
  becomes two (surface, poll); drop "verb surface". Also delete the anti-pattern
  row at line 365 claiming `action=` is not a decorator argument — it has been
  one since the decorator was written, and the row describes the opposite of the
  code. §3 needs three new subsections, since this is where an author learns the
  rules and it is the thinnest coverage today:
  - **Hosting a surface** — the pipe / own / delegate table from Stage 2 verbatim,
    plus rendering outside `hosts=` as an authoring error. This is the one place
    the never-inferred rule gets read by someone about to get it wrong.
  - **`draw()` and `draw_disabled()`** — what each may assume, and the rule that
    the disabled path must not touch state `poll()` gated on. Plus the `access=`
    asymmetry: denied renders neither.
  - **What a nested panel may not assume** — not its depth, not its siblings, not
    whether it sits in a flyout, not whether its host honours `redraw_on`.
  - Common pitfalls gains: hosting an undeclared surface; expecting `redraw_on`
    to fire under a transient host; expecting a greyed panel's `draw()` to run.
  - The §343 built-in-focus table becomes surfaces, each marked inspector or menu.
- `docs/guides/panels.md` — two new worked examples in the existing per-type
  structure: a hosting panel with regions, and a submenu row with its disabled
  form. Line 146 must be rewritten: it currently tells authors to register against
  `NodeContextActions`, which Stage 3b deletes.
- `docs/components/editors/editor-canon.md`, `docs/guides/signals.md`,
  `docs/architecture/studio/studio-arch.md` — vocabulary.
- `docs/reference/design-guide.md` — `scope_button` → `surface_button`, and the
  ScopeToolbar row in the §12 naming table. Add the disabled-menu-row treatment
  alongside the existing `icon_action` / `scope_button` disabled rules, so all
  three agree: `opacity`, `pointer-events: none`, never a grey fill.
- `docs/components/skins/skin-canon.md` — **the DOM attributes are replaced**
  (reversing this plan's first draft, which kept the wire names to avoid churn).
  Stage 3b collapses `data-hw-port-menu-focus-id` and
  `data-hw-custom-menu-focus-id` into `data-hw-menu-surface-id`. The cost is one
  generated file and one in-tree emitter — `node_skin.py:307` is the only line in
  the repo that emits either, and nothing emits the custom one at all — against
  removing the inspector-reachable default. skin-canon has no context-menu
  section today (just a TODO), so this is a new one: the attribute carries a
  surface id; the surface is your library's to declare; pin, node, edge and
  canvas menus are the framework's and are not addressable this way; an
  unresolved id opens nothing.
- `docs/adr/0009-surface-id-stable-key.md` and `docs/reference/glossary.md` are
  already updated in the working tree, but not correctly:
  - ~~**provides**~~ — **done, ahead of Stage 2** (see Order). It had documented
    the structural inference ADR-0029 rejects; it now says piped, never inferred.
  - ~~**presentation**~~, ~~**disabled render**~~, ~~**root surface**~~,
    ~~**sibling group**~~ — done alongside it.
  - Still to add: **inspector surface** / **menu surface**, the split on
    `provides` that Stage 3b's addressing rule leans on.
  - Retire **Scope** as a live alias — `PanelIdentity.scopes` is deleted in
    Stage 2, so there is nothing left for the word to mean.
  - Re-read 0009's nesting paragraph against the final `hosts=` shape. Its file
    has already been renamed to match its front matter (`git mv` from
    `0009-focus-id-stable-key.md`); ADRs are not in the mkdocs nav, so only
    in-document links needed fixing.
- `.insights/` — two things here are invisible from the code and will be
  rediscovered painfully:
  - Extend `feedback_nicegui_nested_menu_flyouts.md` with sibling-group
    ownership. That file already explains why the machinery exists; the surface
    model breaks its precondition, and `render_surface` is the fix.
  - New file for the on_close / emptiness contract: why a layout panel defeats the
    no-popup path, and why the toolbar's `_rendered_panels` diff is blind to
    nesting. The symptom is an edge-drag that never resumes, arbitrarily far from
    the cause. Add one line to CLAUDE.md's trap list.
- Re-run `uv run python scripts/bake_docs.py`; `_baked_docs/` is a generated
  mirror and still carries the old vocabulary.
- `uv run mkdocs build --strict` to catch broken links. **It already fails on
  master**, on a pre-existing bad relative link in `reference/glossary.md`
  (`../../barn/haybale-haystack/…` — one `../` too many). Fix that first or the
  gate tells you nothing about this branch.

## Verification

Per stage: `uv run ruff check <paths>` and `uv run mypy <paths>` against the
baseline commands above, plus the narrowest test tier that covers the stage.

Before calling it done:

```sh
uv run ruff check . && uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-marketplace/haybale_marketplace/ barn/haybale-share/haybale_share/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-haystack/haybale_haystack/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
uv run pytest -m "not browser and not perf" -q > /tmp/t.log 2>&1; echo "exit=$?"
```

Then the browser tier, since the properties strip, context menus, and the
toolbar all have Playwright coverage.

## Traps

- `tests/studio/test_docs/test_generate.py` runs `git checkout -- barn/haybale-testing`
  in teardown, discarding uncommitted work there. Commit Stage 4's
  `haybale-testing` changes before running any suite that includes it.
- Barn classes imported at module top go stale after `importlib.reload`; the
  surface tests must use `importlib.import_module` + `patch.object`.
- Playwright tests park an event loop for the rest of the session — keep new
  surface tests out of `tests/ui/harness/`.
- A `user_simulation()` test running after other tests emits
  `RuntimeWarning: coroutine 'Outbox.loop' was never awaited`. **Pre-existing and
  not yours** — the same warning appears from
  `tests/test_library_operation_progress_modal.py` in the same ordering, and from
  neither file run alone. Stage 0's remaining spikes (the leaf counter,
  retro-greying) will use the same fixture, so expect it and do not go hunting.

## Order

**Stages 2 through 4 are one landing, not four green commits.** The stage numbers
are review order inside a single branch. Read this before running the suite
mid-way and concluding you broke something:

- Stage 2 makes `@panel` require `surface=` and reject `focus=`. **74 call sites
  across four barn libraries still pass `focus=`.** The tree is red the moment it
  lands and stays red until Stage 4 finishes the last library.
- Stage 3 changes `_open_menu(action, focus, …)` to `_open_menu(surface, …)`, and
  `SessionContextMenuProvider` overrides it with the old signature. Stages 3, 3b
  and 4 all edit `haybale-graph-editor`.
- This is what "clean break, no compatibility shim" costs. It was the right call —
  a dual-vocabulary period across 67 registered panels is worse — but it means the
  green-tree checkpoint is at the *end* of Stage 4, not between stages.

What genuinely stands alone:

| | Independently green? |
| --- | --- |
| Stage 0 (`hui` primitives) | Yes — touches only `hui`, nothing in 1–4 depends on it. Land first or in parallel. |
| Stage 1 (new `surface/` package) | Yes — purely additive, nothing imports it yet. |
| Stages 2 → 3 → 3b → 4 | **No.** One landing. |
| Stage 5 (tests) | Follows 4. |
| Stage 6 (docs) | Follows 4, **except the glossary** — see below. |

**Do the glossary's `provides` correction before Stage 2, not in Stage 6.** It is
canon, an implementer reads it to know what to build, and it currently documents
the structural-inference rule ADR-0029 explicitly rejects — the opposite of what
Stage 2 builds. The rest of the glossary work can stay in Stage 6.

Within the 2–4 landing, keep the commits themselves in stage order so the diff is
reviewable per stage even though only the last one is green.

Stage 3b spans `haywire-core` (canvas.vue, the events, the generated JS),
`haybale-graph-editor` (the handlers) and `haybale-studio` (the skin line), so it
lands as one commit across all three or the pin menu breaks in between. It is
also the only stage whose diff is mostly Vue and generated output, which makes it
worth reviewing on its own.

Within Stage 4, do the Edge split in the same commit as the graph editor's move.
It is the only change that alters what a user sees rather than what an author
types — the Edge properties tab and the edge right-click menu stop being able to
show each other's panels — so it wants to be reviewable on its own diff.
