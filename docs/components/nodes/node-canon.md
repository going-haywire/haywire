---
status: draft
doc_template: canonical-example
scope: Authoring node classes — BaseNode, @node decorator, lifecycle hooks, worker function, dynamic reconfiguration
see-also:
  - ../../guides/ports.md
  - ../datatypes/datatype-canon.md
  - ../settings/setting-canon.md
  - ../../guides/node-roles.md
  - ../../architecture/execution/virtual-machine/virtual-machine-arch.md
  - ../../reference/glossary.md
---

# Node — Canonical Example

**Where you are.** This is the first chapter of *Make a node*. It assumes only
what you know from using the studio: cards on a canvas, the pins on them, the
edges you draw between pins.

**New terms in this chapter:** node class, `@node`, `init()`, `worker()`,
DATA and CONTROL nodes, lifecycle hooks, `rejig()`.

## 1. What a node is

Think of a guitar effects pedal: jacks to plug cables into, knobs to turn by
hand, and circuitry inside that turns what comes in into what goes out.

A **node** is the same idea in code. Its jacks are **ports** — *inlets* that
receive values, *outlets* that send them; a card's pins are its ports. Its
knobs are the **widgets** a port shows when nothing is connected to it. Its
circuitry is the **worker**, a method that computes outputs from inputs.

As a node author you write one Python class, and in it three things:

| You write | What it is | Where |
|---|---|---|
| the decorator | the node's name, menu entry and kind | `@node(...)` above the class |
| the ports | what the node receives and sends | `init()` |
| the worker | the computation | `worker()` |

Everything else — the menu entry, placing the node on a canvas, saving it with
the graph, rebuilding it when you save the file (hot-reload), running it — the
framework does.

**Your node lives in a library.** A node class is found because the library it
belongs to registers its `nodes/` folder in `register_components()`. To start,
use a library you already have, or let the New Node wizard (canvas right-click
→ new-node icon) copy a template into one. Creating and shipping a library of
your own is the last chapter: [haybale](../../haybale/haybale-canon.md).

## 2. The class and the placed node

The class you write describes a kind of node. The node on a canvas is one
placed instance of it — a graph can hold three of your nodes, each with its
own values.

```text
you write                       the framework builds
─────────                       ────────────────────
BaseNode subclass  ──registers──►  NodeRegistry  ──places──►  NodeWrapper
(the node class)                   (every class,              (one placed node:
                                    by registry key)           live ports, lifecycle,
                                                               run by the VM)
```

You write only the left column. The framework builds a `NodeWrapper` each time
a node is placed, loaded or hot-reloaded; you never create one yourself.

## 3. A complete node

```python
--8<-- "barn/haybale-example/haybale_example/nodes/math_op.py:12:61"
```
from: `MathOP` — registry_key: `haybale-example:node:MathOP`

**The decorator — `@node(...)`.** `label`, `description`, `menu` (the canvas
menu path), `search_tags`, `node_type`. Section 4 explains `node_type`.

**The ports — `init()`.** Each `self.add(...)` adds one port. `FLOAT` is a
**datatype** — what kind of value the port carries; `as_inlet` / `as_outlet`
picks the side; `id` names the port; `widget=` and `default=` give an inlet its
widget and starting value. Here you *use* the built-in `FLOAT` and
`NumberWidget`; writing your own is the subject of the
[datatype](../datatypes/datatype-canon.md) and
[widget](../widgets/widget-canon.md) chapters. Everything a port accepts:
[guides/ports](../../guides/ports.md).

**The worker — `worker()`.** One rule: **a worker parameter named like an inlet
receives that inlet's value.** `value_a: float` gets the value of the port with
`id="value_a"`, already unwrapped. To send a result, call
`self.out('outlet_id', value)`.

That is a whole node. Most nodes override `init()` and `worker()` and nothing
else.

!!! note "Binding details"
    A parameter with a default is optional — the default applies when no port
    of that name exists. A required parameter (no default) with no matching
    port raises `ValueError` when the worker's signature is analysed. Outside
    the worker — in a callback, say — read an inlet with `self.value('inlet_id')`.
    (Older docs say `self.inlet(...)` / `self.set_outlet(...)`; those names are
    gone.)

## 4. Data and control

The edges you draw in the studio come in two kinds, and so do ports.

**Data ports carry a value.** `FLOAT`, `INT`, an image — the value sits on the
port and anyone connected can read it.

**Control ports carry the moment to run.** Their type is `EXEC`. An edge
between two control ports says "when this one finishes, run that one next".

Every node is one of two kinds, chosen by its ports:

**A DATA node has only data ports.** It computes outputs from inputs. `MathOP`
is one. DATA nodes are *pulled, not pushed*: one runs only when a node
downstream needs its output, and if none of its inputs changed since its last
run, it skips its worker — the answer would be the same. Its worker returns
`None`.

**A CONTROL node has at least one `EXEC` inlet and one `EXEC` outlet.** It runs
when control reaches its inlet, reading whatever data ports it has at that
moment, and then decides where control goes next: **its worker returns the id
of the `EXEC` outlet to continue through.**

```python
def worker(self, context: ExecutionContext, condition: bool) -> str | None:
    return 'true' if condition else 'false'   # continue through one of two outlets
```

Returning `None` ends that path.

| Role | Ports | Runs when | Worker returns |
|---|---|---|---|
| **DATA** | data only | a consumer needs its output and an input changed | `None` |
| **CONTROL** | `EXEC` in *and* out, plus any data ports | control reaches it | the `EXEC` outlet id to follow, or `None` to stop |
| **EVENT / OUTPUT / LOOPBACK** | special CONTROL roles | where a flow starts, ends, or loops | as CONTROL |

`@node(node_type=...)` sets the default role; the `EXEC` ports you declare in
`init()` decide the actual one. Worked examples of every role:
[guides/node-roles](../../guides/node-roles.md). Full taxonomy:
[reference/glossary](../../reference/glossary.md) (**NodeType**).

## 5. Why `init()` is skipped when a graph is loaded

When a user saves a graph and opens it again, **your node's `init()` is not
called.** The ports are there anyway.

Think of `init()` as the **factory settings**: the ports and starting values a
new node comes with. By the time a graph is saved, the user has changed those
values — and the node may even have changed its ports (Section 7). Running the
factory setup again on load would wipe all of that.

So a saved graph stores **the ports themselves**, values included, and loading
restores them directly. That gives one rule with two parts:

- **`init()`** declares the ports a *new* (or reset) node starts with — and
  only that. Anything else done here is lost on load, because it does not run.
- **`post_init()`** runs in both cases: right after `init()` for a new node,
  right after loading for a saved one. Put here what saving cannot carry —
  helper objects, a parser, a lookup table built in code.

Neither hook is the place to open a camera or a file. That waits until the
graph runs — the next section.

**When you edit the class (hot-reload),** every placed node of it is rebuilt
through `init()`: fresh, with only its arrangement kept (position, stacking order,
place on stage), so your port changes show
at once. The user's setup is not lost: a node the rebuild changed keeps its
**previous setup** and shows an amber badge ("Settings reset by a code change").
In the node's right-click menu, or the Node tab of the Properties editor,
**Restore** brings the earlier settings back on the new code and **Discard**
drops them; both are undoable, and the node stays where it is. This works in every
graph, a closed Group interior included, and each such node also gets a warning in
the Errors list. A reload records no undo step. A node that handles the reload
itself in `on_class_reloaded` keeps nothing; see
[ADR 0062](../../adr/0062-a-reload-keeps-the-previous-setup.md). Reset Node is
undoable and also drops a held previous setup
([ADR 0059](../../adr/0059-reload-and-reset-are-undoable.md)).

## 6. The lifecycle

From creation to removal, the framework calls these hooks in this order:

```text
created          flow starts        each frame                                     flow stops    saved       removed
───────          ───────────        ───────────────────────────────────────        ──────────    ─────       ───────
init()*          on_startup()       on_frame_start → on_validate → worker →        on_shutdown   on_saved    on_teardown
post_init()                                                         on_frame_end
* new nodes only — Section 5
```

| Hook | When | Use it to |
|---|---|---|
| `init(self)` | a node is created, reset or hot-reloaded — never on load | declare ports |
| `post_init(self)` | after `init()`, or after loading | build what saving cannot carry |
| `on_startup(self, context)` | once, before the first worker run | acquire resources (devices, files) |
| `on_frame_start(self, context)` | each frame, before any node runs | per-frame setup |
| `on_validate(self, context)` | each frame, right before this worker | check inlet values |
| `worker(self, context, ...)` | each frame this node executes | compute |
| `on_frame_end(self, context)` | each frame, after every node ran | per-frame cleanup |
| `on_shutdown(self, context)` | the flow stops | release resources |
| `on_saved(self)` | the graph is saved, before serializing | capture last-moment state |
| `on_teardown(self)` | the node is removed or unloaded | clean up |

Override only what you need.

## 7. Changing ports at runtime

So far a node's ports were fixed by `init()`. They need not be. A node can
change its ports *while placed, with edges connected* — and keep the edges that
still fit. This is what makes a "compare INTs or FLOATs" selector, or a node
with "N inputs", possible.

The tool is `rejig()`, and it rests on two things you already have: ports are
added with `self.add(...)` and named by `id` (Section 3), and the ports a node
has right now are what is saved (Section 5).

```python
--8<-- "barn/haybale-testing/haybale_testing/nodes/testbed/dynamic_port_test.py:13:65"
```
from: `DynamicPortTestNode` — registry_key: `haybale-testing:node:DynamicPortTestNode`

Follow the chain:

1. `port_count` declares `on_change="hb_reconfigure"` — changing its value
   calls the method.
2. `hb_reconfigure` opens `with self.rejig(include=r"^dynamic_"):` — the ports
   whose id starts with `dynamic_` are up for replacement.
3. Inside the block it re-adds the ports it wants. **Flagged ports not re-added
   are destroyed; a port re-added under the same id keeps its edges** — ports
   are matched by id. `bool_inlet` / `bool_outlet` never match the pattern, so
   they are never touched.

### Choosing which ports are up for replacement

`rejig()` takes `include=` and `exclude=`. Each is a regex string, or a list
mixing exact port ids, `PortOrigin` values and compiled patterns (a list's
entries are OR'd). A port is flagged when it matches `include` and does *not*
match `exclude` — named by both, it is spared. `include=None` means every port;
`include=[]` means none.

A bare `rejig()` flags **every** port, including the ones `init()` declared.
To protect those, say so by origin rather than by name:

```python
with self.rejig(exclude=[PortOrigin.DECLARED]):
    for port in interface:
        self.add(port.spec())
```

`PortOrigin` records where a port came from; `PortOrigin.DECLARED` means
"declared by the class itself". It is sturdier than an id pattern, which only
works as long as a naming convention holds.

### The growing slot

A **growing slot** is a port that, when the user connects an edge to it, turns
into a real port of the edge's type and adds a fresh empty slot below. Declare
a bare `ADD` port in `init()`. A bare `ADD` accepts data, control and callback
edges alike.

The two ports carry different origins — exactly what the previous subsection's
filter is for:

- the grown port is `PortOrigin.RESOLVED` — the user may remove it again;
- the slot itself stays `DECLARED` — it is part of what the node *is*, so it
  cannot be removed or renamed.

Code that rebuilds the grown set therefore spares the slot with
`exclude=[PortOrigin.DECLARED]`. The idiom ships in `AddPortTestNode`
(`barn/haybale-testing/haybale_testing/nodes/testbed/add_port_test.py`); the
Subgraph boundary nodes use it to make an interface growable. See
[ADR 0034](../../adr/0034-add-is-a-type.md) and **Growing slot** in the
[glossary](../../reference/glossary.md).

### Folds

`with self.fold('Advanced'):` puts the ports declared inside it under a
collapsible header. It changes only the card, not the worker. Collapsed ports
keep their edges — they show as ghost pins. Every port in one fold faces the
same way, and a fold holds ports, not other folds (nesting raises). See
[guides/ports](../../guides/ports.md) and
[ADR 0035](../../adr/0035-fold-replaces-group-and-section.md).

## 8. How the node is offered — menu, hidden, templates

Three `@node(...)` options decide how a node appears in the add-node menu:

- **`menu="a/b/c"`** — its path in the menu. An empty `menu=""` puts it under
  the top-level **Misc** category.
- **`hidden=True`** — registered and fully working (in code, in existing
  graphs, on hot-reload), but left out of the add-node menu and node search.
  Framework-internal nodes (the reroute node) and test/example nodes use it.
  It hides the node *as a choice* only — not from browsing or debug surfaces.
  See **Hidden component** in the glossary.
- **`template=True`** — the node becomes a **Node template**: a starting point
  that the New Node wizard and Farmhand's `studio_scaffold_component` *copy*
  into a library as a new class. It implies `hidden=True`.
  `NodeFactory.list_templates()` lists them.

The copy never follows its template later — it is new code the user edits. Two
rules keep the copy standalone, and
`tests/core/test_authoring/test_templates_and_targets.py` enforces both for
every registered template — **only absolute imports**, and **no module-level
names besides imports**. The copy's `@node(...)` states `label`, `description`,
`menu` and `search_tags` explicitly and drops `template`, `hidden`,
`registry_id` and `deprecation_warning`; every other keyword (`node_type`, …)
is kept as written. Any library may ship templates in its `nodes/` folder.
Builtin ships the Data template:

```python
--8<-- "packages/haywire-core/src/haywire/barn/builtin/nodes/templates/data_node.py:9:39"
```

## 9. Finer points — read when you need them

**Name your own additions with a prefix.** Methods and attributes you add start
with `hb_`, `my_`, `custom_` or `ext_`, so a future framework attribute cannot
collide with them. `hb_` is the project convention for "node-author hook".

**Settings instead of config ports.** A node can declare `NodeSettings` inner
classes (`setting()`, `shadow()`, `watch()`) instead of config ports. See
[components/settings](../settings/setting-canon.md).

**The card redraws itself when its looks change.** Writing an appearance field
on `self.props` — `skin`, `layout_direction`, `collapsed`, `detail`, `locked`,
`comment`, `label` (the set is `NodeProperties.REDRAW_FIELDS`) — schedules a
debounced card redraw; never call `self.wrapper.redraw()` for these.
`collapsed` and `detail` decide what the card *contains*, so they rebuild it
([ADR 0032](../../adr/0032-node-detail-and-collapse.md)). Three groups are
deliberately *not* redraws:

- position (`posX` / `posY`) rides a cheaper path; a node's position lives only
  there ([ADR 0053](../../adr/0053-position-lives-in-props.md));
- `node_theme` and `color_override` become CSS custom properties on the node's
  host slot, which the browser re-resolves — redrawing for a colour used to
  destroy the input being typed into ([components/themes](../themes/theme-canon.md));
- size (`width` / `height` / `size_adapt`, below) restyles the slot.

This covers `self.props` only. If a field in your own settings bag affects the
card, subscribe yourself:
`self.settings._subscribe_field('field', lambda v, o: self.wrapper.redraw())`.

**Connecting or disconnecting an edge redraws both nodes.** `EdgeWrapper.link()`
/ `unlink()` / `detach()` mark source and sink `NODE_REDRAW_REQUESTED`. The
reason is the widget: a port's `show_widget` mode (inlet default `NOT_LINKED`)
is decided at render time from `is_linked()`, so a card not rebuilt on connect
would keep showing a widget for a port that now has an edge. The redraw goes
through `mark_node_dirty`, so a stronger reason in the same batch (`NODE_ADDED`
on paste, `NODE_REMOVED` on clear) wins. Anything else that reads link state
while rendering — a folded card's linked-pin set, for one — relies on this same
call.

**Size belongs to the host slot, not the skin.** `self.props` carries `width`,
`height` (default `200.0`) and `size_adapt` (`"auto"`, `"manual_width"`,
`"manual_height"`, `"manual"`; default `"auto"`). Per axis, `auto` *measures*
the rendered card (a `ResizeObserver` on the host slot writes it back into
`props`) and `manual` *uses* what the user dragged. A manual size is a
**minimum**: content that needs more room grows the node, so nothing — pins,
widgets, edges — is ever clipped. The size is written as `min-width` /
`min-height` on the host slot (`.ui-node-slot`), never as a card rebuild, so
measure → write cannot loop. Under a manual mode, CSS in `canvas.vue` (keyed
off the slot's `data-node-props-size-adapt`) releases the skin's own clamps
(`min-w-64 max-w-sm`). **A skin never sets card width or height.** Switching
back to `"auto"` clears the minimum and the observer refills `props`.

**Graph-nodes are created by the framework, not written.** The **Graph-node**
(a Group's card) and the two **boundary nodes** (`Subgraph Input` /
`Subgraph Output`) live in the framework's `builtin` library, are
`hidden=True`, and start with no ports — collapsing a selection stamps their
ports from the edges that cross it. The boundary pair carries
`NodeType.BOUNDARY`, which is neither DATA nor CONTROL: one pair of classes
serves both kinds of crossing, and it keeps them out of the DATA shortcut from
Section 4, so they run even with nothing feeding them. The Graph-node *derives*
its role per instance — DATA when only data crosses, CONTROL otherwise — by
overriding the `behavior` property. If you are writing a node, none of this
applies to you; if you are changing how a Group runs, see
[ADR 0036](../../adr/0036-groups-execute-through-their-boundary-nodes.md).

## 10. Next

What the two embedded examples exercise:

| Concept | Where it shows up |
|---|---|
| `@node(node_type=NodeType.DATA)` | both nodes |
| `init()` declaring ports with `self.add(...)` | both nodes |
| `worker()` with named inlet params | `MathOP` — `value_a`, `value_b`, `operator` |
| `self.out('id', value)` to write outlets | `MathOP` — `self.out("result", result)` |
| `on_change='hb_reconfigure'` on a config port | `DynamicPortTestNode` — `port_count` |
| `with self.rejig(include=r'^dynamic_')` | `DynamicPortTestNode` — regex-matched replacement |
| `hb_*` prefix for custom helpers | `DynamicPortTestNode` — `hb_reconfigure` |
| `self.value('id')` inside a callback | `DynamicPortTestNode` — `self.value("port_count")` |

**Next in *Make a node*:** [ports](../../guides/ports.md) — everything a port
accepts, and the edges the user connects to it. Then
[datatypes](../datatypes/datatype-canon.md),
[settings](../settings/setting-canon.md),
[widgets](../widgets/widget-canon.md) and
[adapters](../adapters/adapter-canon.md).

Worked examples of every node role: [guides/node-roles](../../guides/node-roles.md).
How the VM runs your worker:
[architecture/execution/virtual-machine](../../architecture/execution/virtual-machine/virtual-machine-arch.md).

---

## Worker function reference

| Return value | Meaning |
|---|---|
| `None` | DATA node, or no further control flow |
| `'outlet_id'` | continue control through that `EXEC` outlet |

Parameter binding: a `worker` parameter named like an inlet receives that
inlet's unwrapped value. Defaults make a parameter optional. A required
parameter with no matching port raises `ValueError`.

## Lifecycle hook reference

| Hook | Signature | Purpose |
|---|---|---|
| `init` | `(self)` | Declare ports via `self.add(...)` — new/reset nodes only |
| `post_init` | `(self)` | Setup saving cannot carry — runs after `init()` and after load |
| `on_startup` | `(self, context)` | Once when flow starts |
| `on_frame_start` | `(self, context)` | Each frame, before workers |
| `on_validate` | `(self, context)` | Each frame, before this worker |
| `worker` | `(self, context, *args, **kwargs)` | Main computation; returns `None` or `'outlet_id'` |
| `on_frame_end` | `(self, context)` | Each frame, after workers |
| `on_shutdown` | `(self, context)` | Once when flow stops |
| `on_saved` | `(self)` | Just before graph is saved |
| `on_teardown` | `(self)` | When node is destroyed |
