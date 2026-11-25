# Chip selects and long labels as node widgets: design pass

Task `fix/chip-select-node-widgets` (started as `design/chip-select-node-widgets`), issue #243 (and its second comment). Library
side: going-haywire/haybale-protokol#27 (cleanup, `after-core-release`), the workarounds
added in going-haywire/haybale-protokol#26 (`haybale_protokol/chips.py`).

| Status | |
|---|---|
| Decided | 2026-11-25: 1A, 2A, 3A (no wrap opt-in), no 3C flag, `min_width=120`, Gap 4 and the `data-hw-requires` split go to their own issues |
| Implemented | on this branch; the widget canon, design guide §4.5 and `.insights/feedback_quasar_field_moves_attributes.md` are canonical, this page is the proposal as sent |

Versions read: NiceGUI 3.18.0, Quasar 2.18.5 (`.venv/.../nicegui/static/quasar.umd.js`).

## 0. Summary

Three gaps, each with a small fix that adds no Python API:

| Gap | Recommendation | New API |
|---|---|---|
| 1. Chips clipped at 26px in `compact-fields` | 1A: exempt Quasar's own `q-select--with-chips` from the fixed height | none |
| 2. `min_width` never reaches a Quasar root | 2A: the size-box marker becomes a **class**, not a `data-*` attribute | none (internal marker names change) |
| 3. A long `LabelWidget` floors and resizes its node | 3A: `LabelWidget` declares `min_width` and shows one line, cut with an ellipsis, full text as tooltip | none, or one optional property (owner) |
| 4. (issue point 3) chips mode for `MenuWidget` | defer to its own issue | owner decision if taken |

## 1. Root causes

### Gap 1: wrapped chips are clipped

`packages/haywire-core/src/haywire/ui/app/shell.py:409-429` fixes every field inside a
`compact-fields` container at `var(--hw-compact-field-h)` (26px, `:root` at
`shell.py:396`), with `!important`, on three Quasar parts:

- `.compact-fields .q-field__control { height; min-height }` (`shell.py:409-412`)
- `.compact-fields .q-field__marginal { height }` (`shell.py:422-424`)
- `.compact-fields .q-field__native { min-height; height }` (`shell.py:425-429`)

A `use-chips` select puts its chips in `.q-field__native` (a `row` that wraps). A second
row overflows the fixed 26px control and is cut. Node cards are `compact-fields`
(`barn/haybale-core/haybale_core/skins/widget_node_skin.py:58`,
`barn/haybale-graph-editor/haybale_graph_editor/skins/node_skin.py:560,660`), and so is the
settings panel (`haywire/ui/panel/render_utils.py:301`), so the clip happens in both.

The design guide documents the token as "Fixed input height for compact widgets"
(`docs/reference/design-guide.md:543`); it says nothing about content that wraps.

### Gap 2: the size box never reaches a Quasar root

1. `BaseSkin.render_widget` (`haywire/ui/skin/base.py:322-337`) and
   `render_setting_widget` (`base.py:381-387`) add the skin's classes (for example
   `widget-container`, `barn/haybale-core/haybale_core/skins/widget_node_skin.py:83`) to the
   element `build()` returned, then call `stamp_size_declaration`.
2. `stamp_size_declaration` (`haywire/ui/widget/sizing.py:76-97`) writes the custom
   properties with `element.style(...)` and the marker with `_set_attr`, which is
   `element._props[name] = "1"` (`sizing.py:100-102`).
3. The CSS matches class and attribute on the **same** element:
   `[data-node-id] .widget-container[data-hw-widget-inline-box]` (`haywire/ui/components/graph/canvas.vue:4911`),
   likewise `[data-hw-widget-box]` (`canvas.vue:4935`) and `[data-hw-widget-max-height]`
   (`canvas.vue:4903`).
4. On a `ui.select`, NiceGUI's `select.js` renders `<q-select>` and lets every prop fall
   through to it (`nicegui/elements/select.js:3-15`, no `inheritAttrs: false`).
5. Quasar's fields split those attributes: `useSplitAttrs` (`quasar.umd.js:13035-13055`)
   keeps `class` and `style` for the root and collects **every other attribute** into
   `attributes`; QSelect's `getControl` spreads `attributes` onto the inner
   `div.q-field__native` (`quasar.umd.js:~21680`), or onto the `<input>` with `use-input`
   (`quasar.umd.js:~21238`).

So on a QSelect root the class `widget-container` and the `--hw-widget-min-width` style
reach the outer `.q-field`, but `data-hw-widget-inline-box` lands on `.q-field__native`.
No element carries both, the rule never matches, the field keeps `contain: none`, and the
node's floor stays its max-content width (all chips in one row; 613px measured on Send
Rumble with four gates, haybale-protokol#26 round 3). Nothing warns. `PathWidget`
(`haywire/barn/builtin/widgets/path_widget.py:30,58`) works only because its root is a
`ui.column`.

The same split hits every Quasar field component (`QInput`, `QSelect`, `QFile`, …) used as
a root. Related, not part of this issue: `stamp_requires` (`haywire/ui/access_stamp.py:28`)
writes `data-hw-requires` as a prop the same way, so on a QSelect it too lands on
`.q-field__native`; `access_gate.vue:34` finds it with `closest()` from the click target, so
a click on the field's append area (the dropdown arrow) may miss it. To check during
implementation; if real, it gets its own issue.

### Gap 3: a long `LabelWidget` floors and resizes its node

`LabelWidget.build()` (`haywire/barn/builtin/widgets/basic_widgets.py:414-420`) returns a
bare `ui.label("").classes("text-base text-xs")` and its `@widget` (`basic_widgets.py:401`)
declares no size box. The node's floor is the card's max-content width
(`.insights/feedback_css_containment_node_floor.md`), and a label's max-content width is
its whole text on one line. So a node sized by hand cannot be narrower than its status
line, and a status written while the graph runs (`Listening 1 ch at 48000 Hz, blocks 256,
latency 56.9 ms, lost 0, overflow 0`) widens the node whenever it gets longer (up to the
`max-w-sm` clamp in auto mode, without limit in manual mode).

Here the root is a plain `div`, so `@widget(min_width=)` (or
`LabelWidget.config(min_width=...)` at the call site, `haywire/ui/widget/interface.py:76-102`)
already reaches the DOM; only the declaration is missing. It also breaks design guide
§3.5 (`docs/reference/design-guide.md:414-417`): "Any text that can overflow its
container must include `.truncate`."

Callers today: every status port of haybale-audio (`device_in.py:119`, `audio_clock.py:94`,
`reblock.py:92`, `recorder.py:63`, `file_player.py:93`, `audio_mixer.py:97`,
`resample.py:105`, `device_out.py:110`), haybale-speech's Speech Segmenter (outside this
repo), `haybale_core/file_listing.py:76` (an INT total), and
`haywire/core/skin/settings.py:149` (a skin name in the settings panel).

## 2. Options

### Gap 1: chips wrap in `compact-fields`

**1A. Match Quasar's own chips class (recommended).** Every QSelect carries
`q-select--with-chips` when `use-chips` is set (`quasar.umd.js:21601`). Add, after the
fixed-height rules in `shell.py`:

```css
.compact-fields .q-select--with-chips .q-field__control,
.compact-fields .q-select--with-chips .q-field__native { height: auto !important; }
```

The `min-height` stays 26px, so an empty or one-row chip field looks exactly like every
other field; a second row grows it. `.q-field__marginal` keeps its 26px height so the
dropdown arrow stays on the first row (check in the browser whether `align-self:
flex-start` is needed on it).

- For: no API; every library's chip select wraps without knowing about it; the rule is
  one mechanism ("content that wraps grows"), not a per-widget gate.
- Against: depends on a Quasar class name (stable since Quasar 1, and the file already
  styles `q-field__*` internals throughout).

**1B. An opt-in class.** A new public class, for example `hw-field-grow`, that any widget
adds to a field to lift the fixed height (`.compact-fields .hw-field-grow .q-field__control
{ height: auto }`).

- For: also covers other growing fields (an autogrow `ui.textarea`), explicit.
- Against: a new public Author API name; every library still has to know it, which is the
  rediscovery the issue wants to end. Can be added later on top of 1A if a second case
  appears.

**1C. Drop the fixed `height` for every compact field, keep only `min-height`.**

- For: the simplest rule.
- Against: changes every field in every panel and card; Quasar's own heights for inputs,
  number fields and toggles then decide, and the 26px row rhythm (design guide §4.4) has to
  be re-verified everywhere. Too wide for this issue.

### Gap 2: the size box reaches the DOM whatever the root

**2A. The marker is a class (recommended).** `stamp_size_declaration` adds the classes
`hw-widget-box`, `hw-widget-inline-box` and `hw-widget-max-height` with
`element.classes(add=...)` instead of writing `data-*` props; `canvas.vue:4903,4911,4935`
match `.widget-container.hw-widget-inline-box` etc. Class and style are exactly the two
things Quasar keeps on the root (Gap 2, step 5), and `style` already carries the custom
properties there.

- For: one-line change at each site; no DOM change for any widget; every Quasar root works,
  `ui.select`, `ui.input`, `ui.number`; libraries can build the select as the root again.
- Against: the marker names change (`BOX_ATTR` / `INLINE_BOX_ATTR` / `MAX_HEIGHT_ATTR` in
  `sizing.py:37-39`, documented in `docs/components/widgets/widget-canon.md:182` and
  `canvas.vue` comments). A widget that later calls `classes(replace=...)` on its own root
  strips the marker (an attribute was immune); worth one sentence in the canon.
- The constants stay module-level in `haywire.ui.widget.sizing`, not exported from
  `haywire.api`; nothing in `barn/` reads the attribute names (checked with grep).

**2B. The render funnel wraps every widget in a plain container.**
`BaseSkin.render_widget` / `render_setting_widget` build a `div` that takes the skin's
`classes` (`widget-container`, `sf-widget`, `zoom-pan-lod2`, …) and the stamp, and build
the widget inside it.

- For: any root at all, also a future component that drops `class`; the marker could stay
  an attribute.
- Against: changes the DOM of every widget on every skin (one more element per widget, see
  `.insights/project_browser_rendering_cost.md`); `w-full`, `flex-1` and `min-w-0` on
  widget roots now sit one level deeper, so layouts need re-checking in every skin
  (haybale-graph-editor's node, split, stacked, inset and error skins, haybale-core's
  widget node skin, the settings panel); the funnel returns a different element than `build()` did, which
  changes who owns the widget container (**owner decision**: ownership of the container
  between skin and widget).

**2C. Warn and document only.** `stamp_size_declaration` logs a warning when the root's
component is a Quasar field (detectable through NiceGUI's `element.tag` / component
name), and the widget canon says the root must be a plain element.

- For: no behaviour change.
- Against: keeps the workaround in every library; detection is a list of component names
  to maintain. Useful only as the fallback if 2A is refused.

### Gap 3: a long status label

**3A. `LabelWidget` declares a size box and shows one line (recommended).**
`@widget(description=..., min_width=120)` (value to confirm), the label gets
`truncate w-full` (design guide §3.5: `overflow: hidden; text-overflow: ellipsis;
white-space: nowrap`), and a `ui.tooltip` child bound one-way to the same text shows the
full line on hover. The node's width decides; the height stays one line, so a status that
changes while the graph runs never resizes the node either way.

- For: no API; every status port in haybale-audio and haybale-speech is fixed without a
  release of theirs; follows §3.5; stable height.
- Against: changes how every existing `LabelWidget` looks: a long label that wrapped at
  the 384px `max-w-sm` clamp now cuts to one line at the card's width (in auto mode the
  card no longer grows for it). A caller who wants the old content floor back passes
  `LabelWidget.config(min_width=None)`: an explicit `None` override wins over the class
  default (`IWidget._resolve_size_field`, `interface.py:76-86`, reads the port's
  `widget_config` with `.get(name, class_default)`). It removes the box, not the
  `truncate`; a caller who wants wrapped text needs **3A+** below.
- One extra tooltip element per label, and the binding sends the text twice per update.
  If that matters, the tooltip can be bound only on hover (implementation detail).

**3A+. Plus an optional wrapping mode.** `LabelWidget.config(properties={"wrap": True})`
keeps the box but lets the text wrap (height grows, ceiling `max_height`). A new public
config property name (**owner decision**).

**3B. `min_width` only, text wraps.** Declare the box, leave the label as it is.

- For: smallest change, nothing cut.
- Against: the height jitters as the status changes its number of lines; and the
  `inline-box` rule removes the 200px ceiling (`canvas.vue:4914`,
  `max-height: var(--hw-widget-max-height, none)`), so a very long text grows the node
  downward without limit unless `max_height` is declared too. Breaks §3.5.

**3C. A size box by default for every display-only widget.** The comment's general
proposal. Core has no notion of "display-only"; it would need a new flag
(`@widget(display_only=True)` or similar, **owner decision**: new public Author API name)
or a rule keyed on binding direction (all bindings `one_way`), which is a special case
that misfires (a one-way `ProgressWidget` has a fixed size anyway). Recommend instead:
give each stock display widget whose content can grow its own declaration, starting with
`LabelWidget` (3A). `ProgressWidget` has a bounded width already and needs nothing.

### Gap 4 (issue point 3, optional): a chips mode for `MenuWidget`

Not needed for gaps 1–3. With 1A and 2A, a chip select needs no core help beyond
`MenuWidget(multiple=True)` + `use-chips`. A chips mode would add public config
(`properties={"chips": True}`), a storage choice (text `"a, b"` as haybale-protokol saves,
or a list), and a hook for what a chip shows (label, tooltip, state colour: a Vue template
string, as haybale-protokol's `selected-item` slot, or a Python callable per option). Each
is a new public Author API name and a storage contract (**owner decision**). Recommend a
separate issue, designed with both haybale-protokol widgets as the cases.

## 3. API surface each option adds

| Option | Python API | CSS / DOM contract | Descriptor / config |
|---|---|---|---|
| 1A | none | rule on Quasar's `q-select--with-chips` inside `compact-fields` | none |
| 1B | none | new public class `hw-field-grow` (name to decide) | none |
| 1C | none | `--hw-compact-field-h` becomes a minimum, doc wording changes | none |
| 2A | none public; `sizing.py` constants renamed to `*_CLASS` | classes `hw-widget-box`, `hw-widget-inline-box`, `hw-widget-max-height` replace the `data-hw-widget-*` attributes | none |
| 2B | `render_widget` returns the wrapper, not `build()`'s root | one `div.widget-container` per widget | none |
| 2C | a logged warning | none | none |
| 3A | none | `LabelWidget` root gets `truncate`, a `q-tooltip` child | `@widget(min_width=120)` default on `LabelWidget` |
| 3A+ | none | as 3A | `LabelWidget.config(properties={"wrap": bool})` |
| 3C | new `@widget` flag | as 3A per widget | new decorator param |
| 4 | `MenuWidget` chips property, chip hook | as 1A | `properties={"chips": ..., ...}` |

The `@widget(min_width=)` / `config(min_width=)` parameters already exist
(`haywire/ui/widget/identity.py:25-27`); no option adds a descriptor parameter except 3C.

## 4. Test strategy

Unit (no browser):

- `tests/ui/widget/test_widget_size_declaration.py`: the stub element records `classes`
  instead of `_props`; the existing stamp tests assert the marker class. One new test builds
  a real `ui.select` in a NiceGUI test client and checks the marker class is in its
  `_classes` and the vars in its `_style` (the Python half of 2A).
- `LabelWidget`: its class identity declares `min_width`; the built label carries
  `truncate`; the tooltip text follows the port value (one-way).

Browser (`tests/ui/harness/`, `@pytest.mark.ui`, the `/graph-widget-box` route in
`tests/ui/harness/routes.py` and the widgets in `barn/haybale-testing/haybale_testing/widgets/`):

- A test widget whose **root is** `ui.select(multiple=True).props("use-chips")` with
  `min_width`, preselected with enough chips for three rows. Assert, on the selected node:
  - the outer `.q-field` is the `.widget-container` and its computed `contain` includes
    `inline-size` (2A; fails on master, which is the regression check);
  - the manual-mode floor (`_floor`) is below the one-row chip width;
  - `.q-field__control` is taller than 26px and every chip's bottom lies inside it (1A);
  - a plain single select on the same card stays 26px (1A does not leak).
- The existing `test_removing_the_marker_restores_the_content_floor` is parametrized by
  attribute; it becomes the marker class.
- A node with a `LabelWidget` holding a 100-character status: the floor is below the text's
  width, the label's `scrollWidth > clientWidth` (cut), and setting a longer value changes
  neither the node's width nor its height (3A).
- The settings panel (also `compact-fields`, outside `[data-node-id]`): the same chip
  select wraps there too.

Live check (studio, final confirmation only): Send Rumble and Gamepad Event of
haybale-protokol built **without** `chip_field_root` and `wrap_chips` against this core
branch, haybale-protokol#26 rounds 3 and 4 (chips wrap; any manual width in between), plus
Device In's status line (haybale-speech#9's report).

Docs to update with the change: `docs/components/widgets/widget-canon.md:159-182` (marker
is a class; the root may be any element; `classes(replace=)` strips it),
`docs/reference/design-guide.md:543` (chip fields grow), the `canvas.vue` and `sizing.py`
comments, `.insights/feedback_css_containment_node_floor.md` (a note that markers must be
classes because Quasar moves attributes), and a new insight + index entry for the Quasar
attribute split (`useSplitAttrs`), which is a silent trap of its own.

## 5. What haybale-protokol can delete (haybale-protokol#27)

With 1A and 2A, once a core release contains them:

| In `haybale_protokol/chips.py` and the widgets | Goes? |
|---|---|
| `WRAP_CHIPS_STYLE` and the `.style(...)` in `wrap_chips` | yes (1A); `wrap_chips` shrinks to `.props("use-chips")` or goes |
| `chip_field_root()` and the `with chip_field_root() as root:` blocks in `GateMenuWidget.build` and `OutputsMenuWidget.build` | yes (2A): `build()` returns the select again |
| `GateMenuWidget._select` and the `getattr(self, "_select", None)` in `on_model_changed` | yes, `self.ui_element` is the select again |
| the module docstring's "Two workarounds" section | yes |
| `CHIP_FIELD_MIN_WIDTH` and `@widget(min_width=CHIP_FIELD_MIN_WIDTH)` | **no**: the declaration is still what lifts the floor; core only makes it work |
| `CHIP_STYLE`, the `selected-item` chip templates, `NameListConverter` | no (only with Gap 4) |
| `tests/gamepad/test_outputs_menu_widget.py::test_chip_fields_do_not_floor_their_node_at_one_row` | stays |

Libraries with status labels (haybale-audio, haybale-speech) delete nothing and need no
change with 3A; with 3A+ they could opt into wrapping.

## 6. Questions for the owner

1. **Gap 2, 2A vs 2B.** Change the size-box marker from a `data-*` attribute to a class
   (2A, no DOM change), or wrap every widget in a plain container in the render funnel
   (2B, changes who owns the widget container: an ownership decision)? Recommendation 2A.
2. **Gap 1, 1A vs 1B.** Exempt Quasar's `q-select--with-chips` automatically (1A, no API),
   or add a public opt-in class such as `hw-field-grow` (1B, a new public name)?
   Recommendation 1A.
3. **Gap 3, LabelWidget's default.** Every `LabelWidget` shows one line cut with an
   ellipsis and declares `min_width` by default (3A), knowing it changes how existing long
   labels look; and should there be a public `properties={"wrap": True}` opt-in (3A+), and
   under which name? Recommendation 3A now, 3A+ only when a caller asks.
4. **Gap 3, the general rule (3C).** Confirm no new `@widget` flag for display-only
   widgets; each stock widget declares its own box instead.
5. **Default widths.** `LabelWidget` `min_width=120` px? (`PathWidget` uses 200,
   haybale-protokol's chip fields 160.)
6. **Gap 4.** Leave the `MenuWidget` chips mode out of #243 and file it as its own issue
   (storage as text or list, the chip hook's shape, and its names are owner decisions
   there)?
7. **`stamp_requires` on Quasar roots.** If the implementation confirms the same attribute
   split for `data-hw-requires`, file it separately rather than widen #243?
