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

## 2. A rejected settings write is dropped silently

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
