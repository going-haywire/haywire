# Design: `hui.icon` — Semantic Icon Registry

**Date:** 2026-04-05
**Status:** Approved

---

## Problem

Icon strings are scattered as raw literals across ~38 files. There is no central authority
for which Material icon represents which Haywire concept. The same icon can appear for
unrelated purposes, and the same concept can drift to different icons across panels.

---

## Goal

A single `AppIcons` class in `elements.py`, aliased as `icon = AppIcons`, so callers write:

```python
icon=hui.icon.canvas
icon=hui.icon.edge
icon=hui.icon.zoom_pan
```

**One rule:** each Material icon string appears at most once in `AppIcons`.
One icon = one concept. Collisions in existing code are resolved by assigning the icon
to the "bigger" (more general) concept; the sub-concept gets a distinct icon.

---

## Collision Resolution

| Collision | Winner (keeps icon) | Loser (gets new icon) | New icon assigned |
| --------- | ------------------ | --------------------- | ----------------- |
| `"grid_on"` — canvas scope vs canvas grid sub-panel | `canvas` | `canvas_grid` | `"grid_4x4"` |
| `"cable"` — edge scope vs canvas edges sub-panel | `edge` | *(alias dropped — same concept)* | — |
| `"play_circle"` — execution scope vs execution panel | `execution` | *(alias dropped — same concept)* | — |
| `"bug_report"` — debug scope vs debug panel | `debug` | *(alias dropped — same concept)* | — |
| `"polyline"` — graph scope vs graph info panel | `graph` | *(alias dropped — same concept)* | — |
| `"check_circle"` — node_status vs generic ok | `node_status` | `ok` | `"task_alt"` |
| `"description"` — library_component vs library_docs | `library_component` | `library_docs` | `"menu_book"` |

---

## Final Mapping

```python
class AppIcons:
    # ── Scope tabs (Properties sidebar) ──────────────────────────────────────
    app:           Final[str] = "settings"         # application-wide settings
    execution:     Final[str] = "play_circle"      # execution behaviour
    canvas:        Final[str] = "grid_on"          # canvas & nodes scope
    debug:         Final[str] = "bug_report"       # debug / dev tools
    graph:         Final[str] = "polyline"         # active graph info
    node:          Final[str] = "wysiwyg"          # selected node properties
    node_settings: Final[str] = "tune"             # node settings (requires bags)
    edge:          Final[str] = "cable"            # selected edge info

    # ── Canvas sub-panels ────────────────────────────────────────────────────
    canvas_grid:       Final[str] = "grid_4x4"         # grid display settings
    canvas_node_skins: Final[str] = "format_shapes"    # node dimensions / typography
    canvas_zoom_pan:   Final[str] = "settings_overscan" # pan / zoom behaviour
    canvas_minimap:    Final[str] = "map"              # minimap visibility / position

    # ── Node panel sections ──────────────────────────────────────────────────
    node_info:   Final[str] = "info"        # node identity / metadata
    node_ports:  Final[str] = "device_hub"  # port list
    node_status: Final[str] = "check_circle" # validation / runtime status

    # ── Graph ────────────────────────────────────────────────────────────────
    haystack: Final[str] = "account_tree"  # multi-graph file browser

    # ── Library / editor tabs ────────────────────────────────────────────────
    library_browser:   Final[str] = "widgets"      # library browser editor
    library_component: Final[str] = "description"  # component detail editor
    library_docs:      Final[str] = "menu_book"    # component documentation tab
    library_source:    Final[str] = "code"         # component source tab
    library_view:      Final[str] = "visibility"   # component preview tab

    # ── App panels ───────────────────────────────────────────────────────────
    theme: Final[str] = "palette"  # theme / appearance settings

    # ── Actions ──────────────────────────────────────────────────────────────
    add:     Final[str] = "add"            # add / create
    delete:  Final[str] = "delete"         # remove / destroy
    copy:    Final[str] = "content_copy"   # duplicate / copy to clipboard
    paste:   Final[str] = "content_paste"  # paste
    refresh: Final[str] = "refresh"        # reload / revalidate
    save:    Final[str] = "save"           # persist to disk
    edit:    Final[str] = "edit"           # open for editing
    reset:   Final[str] = "restart_alt"    # reset to default / restart

    # ── Status (forward-looking) ─────────────────────────────────────────────
    ok:      Final[str] = "task_alt"   # generic success / pass
    error:   Final[str] = "error"      # error state
    warning: Final[str] = "warning"    # warning state
```

---

## Location

`AppIcons` is defined in `packages/haywire-core/src/haywire/ui/elements.py`, immediately
after the internal style constants block, before the first component function.

Module-level alias at the bottom of the same file:

```python
icon = AppIcons
```

`elements.py` is imported as `from haywire.ui import elements as hui`, so `hui.icon.canvas`
works with no additional imports.

---

## What Is Not In Scope

- **Migration of existing call sites** — existing `icon="grid_on"` literals are not changed
  in this task. That is a follow-up.
- **The `ICONS` class in `themes/icons.py`** — unchanged. It serves a different purpose
  (raw Material icon constants, not semantic Haywire concepts).
- **Enforcement** — no lint rule preventing raw strings. Adoption is by convention.

---

## Testing

No new tests required. `AppIcons` is a pure data class (all `Final[str]`). The collision
rule (uniqueness of values) can be verified manually by inspection — all values in the
final mapping above are unique except the documented `info`/`node_info` alias.
