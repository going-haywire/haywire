---
name: _settings_bags contains props, and settings writes fail silently
description: NodeProperties extends NodeSettings so every node's _settings_bags includes 13 framework fields under 'props' — generic bag-walks must filter it explicitly. Also, a validator-rejected PROGRAMMATIC settings write is dropped with no exception (the settings panel DOES show inline error chrome); min/max are UI-only hints, not enforced.
type: project
---

# `_settings_bags` contains `props` — and settings writes fail silently

Two traps that bite anything walking a node's settings generically (Farmhand
tools, panels, exporters, doc generators). Both found while building
`graph_editor_inspect_node`.

## 1. `props` is a settings bag

`NodeProperties` extends `NodeSettings`, so `type(node)._settings_bags` is
`{'props': ..., '<author bags>': ...}` — for `SettingsNode` it is literally
`['props', 'example']`. `props` carries **13 framework fields** (position,
size, muted, skin, …).

```python
uv run python -c "
from haybale_testing.nodes.testbed.settings_node import SettingsNode
print(list(SettingsNode._settings_bags))   # ['props', 'example']
"
```

Any bag-walk that means "the node author's settings" must filter `props` out
explicitly, or every node silently grows 13 rows of framework chrome. It is
also the bag `set_property(..., prefer_setting=True)` targets for the resize
commit (`props.width`), which is why it lives in the same dict rather than
somewhere separate.

`graph_editor_inspect_node` splits them into two selectable sections
(`settings` = author bags, `props` = framework) rather than merging or
dropping.

## 2. A rejected settings write is dropped silently — in *programmatic* writes

Scope: this applies to direct `setattr` on a bag. The **settings panel is not
affected** — see "The UI path does surface rejections" below before building a
workaround.

`setting.__set__` starts with `if not self.validate(value): return` — a value
failing the field's `validator` is discarded with **no exception, no log, no
return value**. The write path above it (`SetPropertyAction`, `Editor.set_property`)
therefore reports success:

```python
bag.even_int          # 4          (validator: value % 2 == 0)
bag.even_int = 7      # silently ignored
bag.even_int          # 4          <- still 4, and nothing raised
```

Separately, **`min`/`max` are NOT enforced on writes** — the descriptor
docstring says so, and it is easy to misread as validation:

```python
bag.example_int = 9999   # field declares min=0, max=100
bag.example_int          # 9999    <- accepted
```

`min`/`max` are UI hints only (folded into `widget_config["properties"]` at
`__set_name__` time, consumed by the number widget). Use `validator=` for
runtime enforcement.

**Consequence for agent-facing tools:** the only reliable way to know a write
landed is to read the value back and compare. `graph_editor_set_property` does
this and raises `FarmhandError("set_rejected", ...)`. A legitimate no-op
(writing the value the field already holds — `__set__` also returns early on
equality) passes the check naturally, because the read-back equals the request
either way.

Do **not** "fix" this by making `__set__` raise: the silent clamp/drop is
load-bearing for interactive widgets (a slider dragged out of range must not
explode). The verification belongs in the agent-facing caller.

### The UI path DOES surface rejections

A settings **panel** edit never reaches `__set__` unchecked. `SettingWidgetModel`
forwards edits to an injected `on_edit` write policy, and both policies render
inline error chrome instead of swallowing the failure:

- `_bag_on_edit` (instance path) — calls `descriptor.validate(value)` first and,
  on failure, paints `Invalid value: …` into the row's error container
  (`hw-text-danger`, `data-error="true"`) and returns without writing.
- `_registry_on_edit` (persistent path) — `set_global` *raises* `ValueError` on
  validator rejection (and `KeyError` on a hot-reload-dropped definition); the
  policy catches both and paints the same chrome.

Both live in `haywire/ui/panel/render_utils.py`.

**So: a `validator=` on a setting is sufficient for a UI-edited field** — the
user sees why the edit was refused. Do not add read-back-and-notify plumbing for
panel-edited settings; it already exists. Read-back is for *programmatic* and
agent-facing writes, which is exactly what `graph_editor_set_property` does.

## Bonus: where constraints actually live

Both ports and settings keep their UI constraints in the **same** place —
`widget_config["properties"]` — so one extraction helper serves both:

| Key | Appears on | Note |
|---|---|---|
| `min` / `max` | numeric settings/ports | folded in at `__set_name__`; UI-only |
| `options` | `CHOICES` fields | list, `{value: label}` dict, **or a zero-arg callable** |
| `vec_meta` | `VEC*` fields | `{length, labels}` |

A callable `options` is resolved fresh by `SelectWidget.build()` on every
build. It can only reach a **promoted** port — `DataPort.__post_init__` raises
for a non-serializable `widget_config` on a plain port, but skips the check
when `promoted` is True (ADR 0018). Anything serializing a port's
`widget_config` must resolve or drop it.
