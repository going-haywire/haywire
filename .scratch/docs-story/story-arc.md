# One story for the component docs — the term tower

Proposal, 2026-10-16. Pilot: `docs/components/nodes/node-canon.md`. No other
canon rewritten yet.

## 1. The principle

From the TED-Ed piece on Dan Gilbert's talk: understanding is built like a
tower. Each new term stands on terms the reader already has, and is made solid
with one example. Curiosity — a real problem the term solves — opens each block.

Haywire's component names are already metaphors (node, port, pin, edge, wire,
widget, skin, theme, panel, slot, adapter), borrowed from electronics, UI and
visual programming. So the docs **introduce each component in its own
terminology** and do not lay a second story on top. A metaphor is used only
where a single block is counter-intuitive (§6), and dropped after that block.

**The ground floor is not code.** It is what the reader knows as a *studio
user*: cards on a canvas, pins, the edges they drew, the Properties sidebar.
Every chapter may stand on that.

## 2. The order — by need, in four groups

A reader starts from what they want to build. Someone making their first node
needs no library chapter, no panel, no editor. So the order follows need, and
each group is a **stopping point**: finish a group, and you can stop.

```text
MAKE A NODE              node · port (+ edges) · datatype · settings · widget · adapter
MAKE IT LOOK RIGHT       skin · theme
EXTEND THE STUDIO        panel (+ a first look at signals) · editor · state · signal
AUTOMATE AND SHIP        farmhand · wire types · haybale
```

| # | Chapter | New terms (the block) | Stands on | Canon |
|---|---|---|---|---|
| 1 | Node | node, `@node`, `init()`, `worker()`, DATA/CONTROL, lifecycle, `rejig` | studio-user knowledge; *library* named only (§3) | `nodes/node-canon.md` |
| 2 | Port | inlet, outlet, port spec, **edge** (the user draws it), widget *as an argument* | node | `guides/ports.md` |
| 3 | Datatype | `@type`, the four families, inheritance, type colour | port | `datatypes/datatype-canon.md` |
| 4 | Settings | `NodeSettings`, `LibrarySettings`, `setting`/`shadow`/`watch`, `cache`/`store` | port, datatype | `settings/setting-canon.md` |
| 5 | Widget | `@widget`, `build()`, `bind()`, `widget_key` | port, settings (both show widgets) | `widgets/widget-canon.md` |
| 6 | Adapter | `@adapter`, chains, link-time sample test | datatype, edge | `adapters/adapter-canon.md` |
| — | *stop: you can build any node* | | | |
| 7 | Skin | `render()`, the card class-list contract, host slot | node card (user view), widget | `skins/skin-canon.md` *(placeholder)* |
| 8 | Theme | `@theme`, `--hw-*` tokens, workbench vs node theme, cascade | skin | `themes/theme-canon.md` |
| — | *stop: your nodes look the way you want* | | | |
| 9 | Panel | `@panel`, `poll`/`draw`, surface, host, *signal (first look)* | Properties sidebar (user view) | `panels/panel-canon.md` |
| 10 | Editor | `@editor`, slot, `draw`, `@redraw_on`/`@react_on` | panel | `editors/editor-canon.md` |
| 11 | State | `AppState` / `SessionState`, `on_enable`/`on_disable`, `ctx.app_data` | editor, panel; settings (contrast) | `states/state-canon.md` |
| 12 | Signal | `Signal`, `signal_field`, the bus | panel, editor, state | `guides/signals.md` |
| — | *stop: you can extend the studio* | | | |
| 13 | Farmhand | `@farmhand`, `run()`, `FarmhandContext`, read/write pairing | everything above | `farmhands/farmhand-canon.md` |
| 14 | Wire types | `DataWire`/`ControlWire`/`CallbackWire`, authoring one (ADR 0042) | edge, datatype | *(no canon yet — today inside datatype-canon)* |
| 15 | Haybale | `@library`, `register_components()`, `haybale.toml`, sharing | everything above | `haybale/haybale-canon.md` |

### Four adjustments to the plain list, and why

1. **The library appears briefly at step 0.** A node cannot exist outside a
   library — `register_components()` is what puts it in the menu, and the New
   Node wizard copies its template *into* a library. The node chapter says so in
   one paragraph and points to chapter 15; the full chapter stays last because
   it is about shipping, not building.
2. **Edges before adapters.** "An adapter lets an edge join two types" needs
   edges first. The author never writes an edge — the user draws one — so edges
   enter in the **port** chapter. The authorable part, **wire types**, gets its
   own late chapter.
3. **Meet first, write your own later** (§4). The node chapter *uses* `FLOAT`,
   `NumberWidget` and settings off the shelf; later chapters teach writing your
   own. This is why settings may precede widgets: widgets were met in chapter 1
   as a port argument, and are authored in chapter 5.
4. **Signals get a first look inside the panel chapter** (`redraw_on=` is
   already a signal); the full chapter follows editor and state.

## 3. Rules every canon follows

### Rule A — every term is introduced earlier in the tower, or on this page

The "curse of knowledge" check. Today the canons use `NodeWrapper`,
`DataField`, `registry_key`, `PortOrigin`, `class_identity` before any page
introduced them. Each canon lists, near the top, the **3–6 new terms** it
introduces; anything else it uses must appear in an earlier chapter's list or
be studio-user knowledge. Checkable mechanically against the glossary.

### Rule B — the four-part introduction of a term

1. **The problem** that forces the term to exist — the curiosity hook. ("An
   edge cannot join FLOAT to STRING. Yet users drag exactly that edge.")
2. **Why it is called that** — one line. A *skin* is a surface over the same
   body; a *widget* is a small control; an *adapter* sits between two plugs.
3. **One concrete example** — a live `--8<--` embed, read through the term.
4. **The contrast with its nearest neighbour** — where most confusion lives
   (§5). Replaces today's dense "Boundaries" paragraphs.

### Rule C — the chapter shape

1. **Where you are** — one sentence naming the block this chapter stands on.
2. **New terms** — the short list (Rule A).
3. **The problem and the term** (Rule B 1–2).
4. **A complete example** (Rule B 3).
5. **Building up** — further blocks, each using only what came before.
6. **Contrast** (Rule B 4).
7. **Finer points** — today's dense prose, kept intact for reference.
8. **Next** — the chapter this one hands to, and whether this is a stopping point.
9. **Reference tables** — unchanged.

## 4. Meet first, write your own later

Most terms are met twice:

| Term | Met as a user of built-ins | Authored |
|---|---|---|
| datatype | `FLOAT.as_inlet(...)` in chapter 1 | chapter 3 |
| widget | `widget=NumberWidget.config()` in chapter 1 | chapter 5 |
| settings | a node's settings in the Properties panel | chapter 4 |
| skin | the default node card | chapter 7 |
| signal | `redraw_on=` in a panel | chapter 12 |
| library | "your node lives in one" | chapter 15 |

A chapter that authors a term opens by naming where the reader already met it.

## 5. Neighbour contrasts — one per chapter

| Chapter | Contrast with | The one-line difference |
|---|---|---|
| Port | setting | a port can be wired; a setting cannot (unless promoted) |
| Datatype | wire type | the datatype is *what* travels; the wire type is *which kind of edge* carries it |
| Settings | state | settings are persisted configuration; state is live runtime data |
| Widget | panel | a widget shows one value; a panel shows a context |
| Adapter | node | an adapter converts on the edge, invisibly; a node is placed and seen |
| Skin | theme | a skin decides the card's structure; a theme only its colours |
| Panel | editor | a panel is stateless content inside a host; an editor owns a slot and its state |
| State | settings | (mirror of Settings) |
| Farmhand | panel | a panel serves the user in the studio; a farmhand serves an agent outside it |
| Haybale | library | the distribution vs the class — glossary meanings #3 and #1 |

## 6. Where a metaphor earns its place

Only where the block is counter-intuitive, once, and dropped after:

| Chapter | Block | Metaphor |
|---|---|---|
| Node §1 | what a node is | an effects pedal — jacks, knobs, circuitry (opening image only) |
| Node | `init()` skipped on load | factory settings vs how the user left it |
| Node | lazy DATA nodes | pulled, not pushed |
| Node | `rejig` | ports are matched by id, so connections survive |
| Adapter | chains | stacked plug adapters |
| Theme | nothing reads a theme in Python | the card does not know what colour it is painted |

### Words a metaphor must never borrow

The glossary owns these; using them loosely makes a reader see a real term:
**signal, stage, patch, slot, host, surface, frame, session, workbench**.

## 7. Nav consequence

Reorder `mkdocs.yml` → Components to the order in §2, grouped under the four
headings, with `guides/ports.md` and `guides/signals.md` placed at their
chapter positions. Open question: (a) group with sub-headings; (b) reorder
only; (c) leave nav and rely on each chapter's "Next".
